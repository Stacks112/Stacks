/* Stacks comments worker (v8.2 = v8.1 + surge alerts cron)
   v8.2 ADDS ONLY: a scheduled() cron + /cron/surge[-dryrun] routes that price
   every followed company from items.json and push the day's biggest movers
   (|daily change| >= 4%) to their c_<slug> follow tags. Nothing from v8.1 was
   changed. Reuses the same D1 + ONESIGNAL_REST_KEY/NOTIFY_SECRET secrets.
   ORIGINAL v8.1 HEADER BELOW.
*/
/* Stacks comments worker (v8.1)
   (v8.1, auto-deploy test) = your existing v8 (per-timezone + multi-language push delivery,
     ranged quotes, views/likes, comment replies & likes, /notify)
   + the reader poll: GET /votes and POST /vote.
   Nothing from your v8 was removed — the timezone/multi-language push
   logic (langMap, deliver_at) is all preserved.
   Free Cloudflare Worker + D1. Comments show instantly, no approval.

   HOW TO DEPLOY (Cloudflare dashboard):
   1. Open your worker (stacks-comments...) -> "Edit code".
   2. Select ALL the existing code and delete it.
   3. Paste THIS entire file in its place.
   4. Click "Deploy".
   (No new bindings, secrets, or tables needed — reuses the same D1.)
*/

const ALLOWED_ORIGINS = [
  "https://stacksdaily.com",
  "https://www.stacksdaily.com",
  "https://stacks112.github.io"
];

const MAX_NICK = 40;
const MAX_CONTENT = 2000;
const RATE_LIMIT_PER_MIN = 3;
const ONESIGNAL_APP_ID = "88ed92c8-315e-497f-bec1-4f5862f5f45b";

/* ---- surge-alert config (v8.2 additions) ---- */
const ITEMS_URL = "https://raw.githubusercontent.com/Stacks112/Stacks/main/items.json";
const SURGE_ABS_MIN = 4;   // push only |daily % change| >= this
const SURGE_TOP_N = 3;     // at most this many movers per day

function cors(origin) {
  const ok = ALLOWED_ORIGINS.includes(origin);
  return {
    "Access-Control-Allow-Origin": ok ? origin : ALLOWED_ORIGINS[0],
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400"
  };
}

function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: { "Content-Type": "application/json", ...cors(origin) }
  });
}

async function ipHash(request) {
  const ip = request.headers.get("CF-Connecting-IP") || "0.0.0.0";
  const buf = await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode("stacks-salt-2026::" + ip));
  return [...new Uint8Array(buf)].slice(0, 12)
    .map(b => b.toString(16).padStart(2, "0")).join("");
}

async function ensureTables(db) {
  await db.exec(
    "CREATE TABLE IF NOT EXISTS comments (" +
    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
    "page_id TEXT NOT NULL, " +
    "nickname TEXT NOT NULL, " +
    "content TEXT NOT NULL, " +
    "ip_hash TEXT NOT NULL, " +
    "created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')))"
  );
  /* one row per (kind, id): kind = 'view' | 'like' | 'clike' | 'vup' | 'vdown' */
  await db.exec(
    "CREATE TABLE IF NOT EXISTS counters (" +
    "kind TEXT NOT NULL, " +
    "page_id TEXT NOT NULL, " +
    "n INTEGER NOT NULL DEFAULT 0, " +
    "PRIMARY KEY (kind, page_id))"
  );
  /* migrate v4 comments table: add parent_id once, ignore if it exists */
  try { await db.exec("ALTER TABLE comments ADD COLUMN parent_id INTEGER"); }
  catch (e) {}
  /* newsletter subscribers: one row per email, language + opt-out flag */
  await db.exec(
    "CREATE TABLE IF NOT EXISTS subscribers (" +
    "email TEXT PRIMARY KEY, " +
    "lang TEXT NOT NULL DEFAULT 'ko', " +
    "unsubscribed INTEGER NOT NULL DEFAULT 0, " +
    "created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')))"
  );
}

/* atomic +delta (clamped at 0), returns the new value */
async function bump(db, kind, id, delta) {
  const row = await db.prepare(
    "INSERT INTO counters (kind, page_id, n) VALUES (?1, ?2, MAX(0, ?3)) " +
    "ON CONFLICT(kind, page_id) DO UPDATE SET n = MAX(0, n + ?3) " +
    "RETURNING n"
  ).bind(kind, id, delta).first();
  return row ? row.n : 0;
}

async function allCounts(db, kind) {
  const { results } = await db
    .prepare("SELECT page_id, n FROM counters WHERE kind = ?1 AND n > 0")
    .bind(kind).all();
  const data = {};
  for (const r of results) data[r.page_id] = r.n;
  return data;
}

const PAGE_ID_RE = /^[a-z0-9_-]{1,64}$/i;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* first 24 hex chars of HMAC-SHA256(secret, msg) — must match the Python
   unsub_link() in scripts/weekly_send.py exactly. */
async function hmac24(secret, msg) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
}

/* ---------- welcome email (sent right after a new /subscribe) ----------
   Localized copy; unsubscribe link is the same HMAC one-click link the
   weekly email uses. Requires the worker secrets RESEND_API_KEY (sending-
   only key) and UNSUB_SECRET; silently skipped if either is missing. */
const WELCOME_COPY = {
  ko: {
    subj: "Stacks 구독 완료 — 매주 일요일에 만나요",
    hi: "구독해 주셔서 고마워요!",
    body: "매주 일요일 아침, 이번 주 가장 중요한 투자 읽을거리를 요약과 관점까지 담아 이 메일함으로 보내드려요.",
    note: "그동안의 글이 궁금하면 지금 바로 둘러보세요.",
    cta: "Stacks 둘러보기",
    unsub: "구독 해지"
  },
  en: {
    subj: "You\u2019re subscribed to Stacks \u2014 see you Sunday",
    hi: "Thanks for subscribing!",
    body: "Every Sunday morning we\u2019ll send this inbox the week\u2019s most important investing reads, summarized with a take.",
    note: "Want a head start? The archive is open now.",
    cta: "Explore Stacks",
    unsub: "Unsubscribe"
  },
  ja: {
    subj: "Stacksの購読完了 — 毎週日曜にお届けします",
    hi: "ご購読ありがとうございます！",
    body: "毎週日曜の朝、今週最も重要な投資の読みものを、要約と視点付きでこのメールボックスにお届けします。",
    note: "これまでの記事は今すぐご覧いただけます。",
    cta: "Stacksを見る",
    unsub: "購読解除"
  }
};

async function sendWelcome(env, workerOrigin, email, lang) {
  if (!env.RESEND_API_KEY) return;  // welcome mail not configured — fine
  const T = WELCOME_COPY[lang] || WELCOME_COPY.ko;
  let unsubUrl = "https://stacksdaily.com";
  if (env.UNSUB_SECRET) {
    const t = await hmac24(env.UNSUB_SECRET, email);
    unsubUrl = workerOrigin + "/unsub?e=" + encodeURIComponent(email) + "&t=" + t;
  }
  const html =
    "<!DOCTYPE html><html><body style=\"margin:0;padding:0;background:#f4f5f7\">"
    + "<div style=\"max-width:520px;margin:0 auto;padding:32px 20px;"
    + "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans KR',sans-serif\">"
    + "<div style=\"background:#ffffff;border-radius:16px;padding:36px 32px;text-align:center;"
    + "border:1px solid #e5e7eb\">"
    + "<img src=\"https://stacksdaily.com/apple-touch-icon.png\" width=\"56\" height=\"56\" alt=\"Stacks\" "
    + "style=\"border-radius:14px;display:block;margin:0 auto 20px\">"
    + "<h1 style=\"font-size:20px;margin:0 0 12px;color:#111827\">" + T.hi + "</h1>"
    + "<p style=\"font-size:15px;line-height:1.65;color:#4b5563;margin:0 0 8px\">" + T.body + "</p>"
    + "<p style=\"font-size:14px;line-height:1.6;color:#6b7280;margin:0 0 24px\">" + T.note + "</p>"
    + "<a href=\"https://stacksdaily.com\" style=\"display:inline-block;background:#111827;color:#ffffff;"
    + "text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:999px\">"
    + T.cta + "</a>"
    + "</div>"
    + "<p style=\"text-align:center;font-size:12px;color:#9ca3af;margin:20px 0 0\">"
    + "Stacks \u00b7 <a href=\"" + unsubUrl + "\" style=\"color:#9ca3af\">" + T.unsub + "</a></p>"
    + "</div></body></html>";
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + env.RESEND_API_KEY
    },
    body: JSON.stringify({
      from: env.RESEND_FROM || "Stacks Weekly <weekly@stacksdaily.com>",
      to: [email],
      subject: T.subj,
      html: html,
      headers: {
        "List-Unsubscribe": "<" + unsubUrl + ">",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
      }
    })
  });
}

/* build a OneSignal language map ({en, ko, ja, ...}) for a heading or body,
   from an object {en,ko,ja}, flat title_en/title_ko/..., or a plain string.
   OneSignal requires an "en" fallback, so we always fill it. */
const OS_LANGS = ["en", "ko", "ja", "zh-Hans", "zh-Hant", "es", "fr", "de", "pt", "ru", "id", "vi", "th"];
function langMap(p, base, limit) {
  let m = {};
  const v = p[base];
  if (v && typeof v === "object" && !Array.isArray(v)) {
    m = { ...v };
  } else {
    for (const L of OS_LANGS) {
      const k = p[base + "_" + L];
      if (k) m[L] = k;
    }
    if (Object.keys(m).length === 0 && typeof v === "string" && v) m.en = v;
  }
  if (!m.en) m.en = m.ko || m.ja || Object.values(m)[0] || "";
  const out = {};
  for (const k of Object.keys(m)) {
    const s = String(m[k]).slice(0, limit);
    if (s) out[k] = s;
  }
  return out;
}


/* ===================== surge alerts (v8.2) ===================== */
/* company follow-tag slug — MUST stay identical to the site's slugTag()
   in index.html, or pushes miss every subscriber:
   c_ + name.toLowerCase, non-alnum(+Hangul) -> "_", trimmed. */
function surgeSlug(k) {
  return String(k).toLowerCase().replace(/[^a-z0-9가-힣]+/g, "_").replace(/^_+|_+$/g, "");
}

/* stooq-style ticker -> Yahoo symbol, identical mapping to the /quote route. */
function yahooSymbol(rawTicker) {
  const s = String(rawTicker || "").toLowerCase().replace(/[^a-z0-9.\-]/g, "").slice(0, 20);
  if (!s) return "";
  if (s.endsWith(".us")) return s.slice(0, -3).toUpperCase();
  if (s.endsWith(".ks")) return s.slice(0, -3).toUpperCase() + ".KS";
  if (s.endsWith(".jp")) return s.slice(0, -3).toUpperCase() + ".T";
  return s.toUpperCase();
}

/* most-recent completed daily close vs the prior close (percent).
   returns { pct, price, prevClose, currency } or null. never throws. */
async function fetchDailyChange(rawTicker) {
  const ysym = yahooSymbol(rawTicker);
  if (!ysym) return null;
  try {
    const yr = await fetch("https://query1.finance.yahoo.com/v8/finance/chart/"
        + encodeURIComponent(ysym) + "?range=5d&interval=1d",
      { headers: { "User-Agent": "Mozilla/5.0 (compatible; StacksSurge/1.0)" } });
    if (!yr.ok) return null;
    const j = await yr.json();
    const res = j && j.chart && j.chart.result && j.chart.result[0];
    if (!res) return null;
    const cl = (res.indicators && res.indicators.quote
                && res.indicators.quote[0] && res.indicators.quote[0].close) || [];
    const closes = cl.filter(c => c != null && isFinite(c));
    if (closes.length < 2) return null;
    const last = closes[closes.length - 1];
    const prev = closes[closes.length - 2];
    if (!prev) return null;
    return {
      pct: (last - prev) / prev * 100,
      price: last,
      prevClose: prev,
      currency: (res.meta && res.meta.currency) || ""
    };
  } catch (e) { return null; }
}

/* one OneSignal push to a company follow tag. returns bool. */
async function osPushTag(env, tag, headings, contents, link) {
  if (!env.ONESIGNAL_REST_KEY) return false;
  const payload = {
    app_id: ONESIGNAL_APP_ID,
    headings,
    contents,
    url: link ? String(link).slice(0, 500) : undefined,
    filters: [{ field: "tag", key: String(tag).slice(0, 80), relation: "=", value: "1" }]
  };
  try {
    const res = await fetch("https://api.onesignal.com/notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Key " + env.ONESIGNAL_REST_KEY },
      body: JSON.stringify(payload)
    });
    return res.ok;
  } catch (e) { return false; }
}

/* read items.json entities, price every followable company, return the
   top-N movers whose |daily change| >= threshold. read-only, never throws. */
async function computeSurges() {
  let entities = {};
  try {
    const r = await fetch(ITEMS_URL, { cf: { cacheTtl: 60 } });
    if (!r.ok) return [];
    const data = await r.json();
    entities = (data && data.entities) || {};
  } catch (e) { return []; }
  const companies = [];
  for (const name in entities) {
    const e = entities[name];
    if (e && e.kind === "company" && e.ticker) companies.push({ name, ticker: e.ticker });
  }
  const moved = [];
  for (const c of companies) {
    const q = await fetchDailyChange(c.ticker);
    if (q && isFinite(q.pct) && Math.abs(q.pct) >= SURGE_ABS_MIN) {
      moved.push({
        name: c.name,
        ticker: c.ticker,
        pct: Math.round(q.pct * 100) / 100,
        price: q.price,
        currency: q.currency,
        tag: "c_" + surgeSlug(c.name)
      });
    }
  }
  moved.sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct));
  return moved.slice(0, SURGE_TOP_N);
}

async function ensureSurgeTable(db) {
  await db.exec(
    "CREATE TABLE IF NOT EXISTS surge_alerts (" +
    "date TEXT NOT NULL, tag TEXT NOT NULL, PRIMARY KEY (date, tag))"
  );
}

/* compute + (unless dryRun) push, deduping one push per company per UTC day. */
async function runSurgeAlerts(env, opts) {
  const dryRun = !!(opts && opts.dryRun);
  const surges = await computeSurges();
  const date = new Date().toISOString().slice(0, 10);
  if (dryRun) {
    return { date, dryRun: true, threshold: SURGE_ABS_MIN, count: surges.length, surges };
  }
  const out = [];
  await ensureSurgeTable(env.DB);
  for (const sge of surges) {
    const dup = await env.DB
      .prepare("SELECT 1 FROM surge_alerts WHERE date = ?1 AND tag = ?2")
      .bind(date, sge.tag).first();
    if (dup) { out.push({ ...sge, sent: false, skipped: "already_sent_today" }); continue; }
    const up = sge.pct >= 0;
    const arrow = up ? "▲" : "▼";
    const abs = Math.abs(sge.pct).toFixed(1);
    const heading = sge.name + " " + arrow + abs + "%";
    const headings = { en: heading, ko: heading, ja: heading };
    const contents = {
      en: sge.name + " closed " + arrow + abs + "% yesterday. Read the latest on Stacks.",
      ko: sge.name + ", 어제 " + arrow + abs + "% " + (up ? "급등" : "급락") + " 마감. Stacks에서 확인하세요.",
      ja: sge.name + "、昨日" + arrow + abs + "% " + (up ? "急騰" : "急落") + "。Stacksでチェック。"
    };
    const ok = await osPushTag(env, sge.tag, headings, contents, "https://stacksdaily.com/");
    if (ok) {
      await env.DB.prepare("INSERT OR IGNORE INTO surge_alerts (date, tag) VALUES (?1, ?2)")
        .bind(date, sge.tag).run();
    }
    out.push({ ...sge, sent: ok });
  }
  return { date, dryRun: false, threshold: SURGE_ABS_MIN, count: out.length, sent: out };
}
/* =================== end surge alerts (v8.2) =================== */

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(origin) });
    }

    /* ---------- surge alerts: read-only diagnostic (no secret) ----------
       returns today's computed movers without pushing or writing to D1.
       This is what the 08:20 KST monitor task polls. */
    if (url.pathname === "/cron/surge-dryrun") {
      const r = await runSurgeAlerts(env, { dryRun: true });
      return json(r, 200, origin);
    }
    /* ---------- surge alerts: force a real send (June only) ----------
       same NOTIFY_SECRET as /notify. Deduped per company per day. */
    if (url.pathname === "/cron/surge") {
      const p = request.method === "POST"
        ? await request.json().catch(() => ({}))
        : Object.fromEntries(url.searchParams);
      if (!env.NOTIFY_SECRET || p.secret !== env.NOTIFY_SECRET) {
        return json({ error: "forbidden" }, 403, origin);
      }
      const r = await runSurgeAlerts(env, { dryRun: false });
      return json(r, 200, origin);
    }
    /* ---------- quote: /quote?s=SYMBOL ----------
       Ranged daily/intraday prices via Yahoo Finance with a cache,
       so cards & charts can show prices. */
    if (url.pathname === "/quote") {
      const s = (url.searchParams.get("s") || "").toLowerCase().replace(/[^a-z0-9.\-]/g, "").slice(0, 20);
      if (!s) return json({ error: "s required" }, 400, origin);
      /* range support for real charts. r = 1d | 5d | 1mo | 6mo | 1y */
      const RANGES = {
        "1d":  { range: "1d",  interval: "5m",  ttl: 300 },
        "5d":  { range: "5d",  interval: "30m", ttl: 900 },
        "1mo": { range: "1mo", interval: "1d",  ttl: 3600 },
        "6mo": { range: "6mo", interval: "1d",  ttl: 3600 },
        "1y":  { range: "1y",  interval: "1d",  ttl: 3600 }
      };
      const rkey = RANGES[url.searchParams.get("r")] ? url.searchParams.get("r") : "1mo";
      const R = RANGES[rkey];
      const cache = caches.default;
      const cacheKey = new Request("https://stacks-quote-cache/v7-" + s + "-" + rkey);
      const hit = await cache.match(cacheKey);
      if (hit) {
        const body = await hit.text();
        return new Response(body, { status: 200,
          headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=" + R.ttl, ...cors(origin) } });
      }
      /* map stooq-style tickers to Yahoo symbols:
         aapl.us -> AAPL, 000660.ks -> 000660.KS, 7203.jp -> 7203.T */
      let ysym = s;
      if (s.endsWith(".us")) ysym = s.slice(0, -3).toUpperCase();
      else if (s.endsWith(".ks")) ysym = s.slice(0, -3).toUpperCase() + ".KS";
      else if (s.endsWith(".jp")) ysym = s.slice(0, -3).toUpperCase() + ".T";
      else ysym = s.toUpperCase();
      let t = [], closes = [], meta = null;
      try {
        const yr = await fetch("https://query1.finance.yahoo.com/v8/finance/chart/"
            + encodeURIComponent(ysym) + "?range=" + R.range + "&interval=" + R.interval,
          { headers: { "User-Agent": "Mozilla/5.0 (compatible; StacksQuote/1.0)" } });
        if (yr.ok) {
          const j = await yr.json();
          const res = j && j.chart && j.chart.result && j.chart.result[0];
          meta = (res && res.meta) || null;
          const ts = (res && res.timestamp) || [];
          const cl = (res && res.indicators && res.indicators.quote
                      && res.indicators.quote[0] && res.indicators.quote[0].close) || [];
          for (let i = 0; i < ts.length; i++) {
            const c = cl[i];
            if (c != null && isFinite(c)) {
              t.push(ts[i]);
              closes.push(Math.round(c * 10000) / 10000);
            }
          }
        }
      } catch (e) {}
      if (closes.length < 2) return json({ error: "no data" }, 404, origin);
      const dates = t.map(x => new Date(x * 1000).toISOString().slice(0, 10));
      const body = JSON.stringify({
        s, r: rkey, t, closes, dates,
        currency: meta && meta.currency || "",
        price: meta && meta.regularMarketPrice || closes[closes.length - 1],
        prevClose: meta && (meta.chartPreviousClose || meta.previousClose) || null,
        tz: meta && meta.exchangeTimezoneName || "UTC"
      });
      const resp = new Response(body, { status: 200,
        headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=" + R.ttl, ...cors(origin) } });
      await cache.put(cacheKey, new Response(body, { headers: { "Cache-Control": "public, max-age=" + R.ttl } }));
      return resp;
    }

    /* ---------- share preview: /s/{id}?t=...&d=... ---------- */
    if (url.pathname.startsWith("/s/")) {
      const id = url.pathname.slice(3);
      if (!/^[a-z0-9-]{1,60}$/.test(id)) {
        return new Response("bad id", { status: 400 });
      }
      const esc = s => String(s || "").slice(0, 300)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
      const t = esc(url.searchParams.get("t")) || "Stacks";
      const d = esc(url.searchParams.get("d")) ||
        "Sharp investment writing from around the world, summarized with a take.";
      const target = "https://stacksdaily.com/#sig-" + id;
      const img = "https://stacksdaily.com/apple-touch-icon.png";
      const page = "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        + "<title>" + t + "</title>"
        + "<meta property=\"og:type\" content=\"article\">"
        + "<meta property=\"og:site_name\" content=\"Stacks\">"
        + "<meta property=\"og:title\" content=\"" + t + "\">"
        + "<meta property=\"og:description\" content=\"" + d + "\">"
        + "<meta property=\"og:url\" content=\"" + target + "\">"
        + "<meta property=\"og:image\" content=\"" + img + "\">"
        + "<meta name=\"twitter:card\" content=\"summary\">"
        + "<meta name=\"twitter:title\" content=\"" + t + "\">"
        + "<meta name=\"twitter:description\" content=\"" + d + "\">"
        + "<meta http-equiv=\"refresh\" content=\"0;url=" + target + "\">"
        + "</head><body>"
        + "<script>location.replace(" + JSON.stringify(target) + ");</scr" + "ipt>"
        + "<p><a href=\"" + target + "\">Continue to Stacks</a></p>"
        + "</body></html>";
      return new Response(page, {
        status: 200,
        headers: { "Content-Type": "text/html; charset=utf-8",
                   "Cache-Control": "public, max-age=300" }
      });
    }

    /* ---------- notify: push to followers (June only) ----------
       v8: multi-language (title/msg may be string, {en,ko,ja}, or flat
       title_en/…), and optional per-timezone delivery (deliver_at="7:30AM"
       sends at each subscriber's local time; the "daily" tag defaults to it). */
    if (url.pathname === "/notify") {
      const p = request.method === "POST"
        ? await request.json().catch(() => ({}))
        : Object.fromEntries(url.searchParams);
      if (!env.NOTIFY_SECRET || p.secret !== env.NOTIFY_SECRET) {
        return json({ error: "forbidden" }, 403, origin);
      }
      if (!env.ONESIGNAL_REST_KEY) {
        return json({ error: "ONESIGNAL_REST_KEY secret not set" }, 500, origin);
      }
      if (!p.tag) {
        return json({ error: "need tag, title, msg" }, 400, origin);
      }
      const headings = langMap(p, "title", 120);
      const contents = langMap(p, "msg", 300);
      if (!headings.en || !contents.en) {
        return json({ error: "need tag, title, msg" }, 400, origin);
      }
      const payload = {
        app_id: ONESIGNAL_APP_ID,
        headings,
        contents,
        url: p.url ? String(p.url).slice(0, 500) : undefined,
        filters: [{ field: "tag", key: String(p.tag).slice(0, 80), relation: "=", value: "1" }]
      };
      /* per-timezone delivery for the worldwide morning briefing */
      let deliverAt = p.deliver_at;
      if (!deliverAt && String(p.tag) === "daily") deliverAt = "7:30AM";
      if (deliverAt) {
        payload.delayed_option = "timezone";
        payload.delivery_time_of_day = String(deliverAt).slice(0, 10);
      }
      const res = await fetch("https://api.onesignal.com/notifications", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Key " + env.ONESIGNAL_REST_KEY
        },
        body: JSON.stringify(payload)
      });
      const out = await res.json().catch(() => ({}));
      return json({ sent: res.ok, onesignal: out }, res.ok ? 200 : 502, origin);
    }

    /* ---------- subscribe: add/refresh a newsletter subscriber (D1) ----------
       The site signup form (all languages) POSTs {email, lang} here. Idempotent:
       re-subscribing a previously unsubscribed address re-activates it and
       updates its language. */
    if (url.pathname === "/subscribe" && (request.method === "POST" || request.method === "GET")) {
      const p = request.method === "POST"
        ? await request.json().catch(() => ({}))
        : Object.fromEntries(url.searchParams);
      if (p.website) return json({ ok: true }, 200, origin);  // honeypot
      const email = String(p.email || "").trim().toLowerCase();
      let lang = String(p.lang || "ko").toLowerCase();
      if (!["ko", "en", "ja"].includes(lang)) lang = "ko";
      if (!EMAIL_RE.test(email) || email.length > 200) {
        return json({ ok: false, error: "invalid email" }, 400, origin);
      }
      await ensureTables(env.DB);
      // was this address already an active subscriber? (guards duplicate welcomes)
      const prev = await env.DB.prepare(
        "SELECT unsubscribed FROM subscribers WHERE email = ?1").bind(email).first();
      const wasActive = prev && !prev.unsubscribed;
      await env.DB.prepare(
        "INSERT INTO subscribers (email, lang, unsubscribed) VALUES (?1, ?2, 0) " +
        "ON CONFLICT(email) DO UPDATE SET lang = ?2, unsubscribed = 0"
      ).bind(email, lang).run();
      if (!wasActive) {
        // fresh (or re-activated) subscriber → send the welcome email.
        // Never let a mail hiccup break the signup itself.
        try { await sendWelcome(env, url.origin, email, lang); } catch (e) {}
      }
      return json({ ok: true }, 200, origin);
    }

    /* ---------- subscribers: active list for a language (secret-guarded) ----------
       Read by scripts/weekly_send.py at send time. Secret travels in the
       Authorization: Bearer header (or ?secret= as a fallback), never exposed
       to the browser. */
    if (url.pathname === "/subscribers" && request.method === "GET") {
      const auth = request.headers.get("Authorization") || "";
      const secret = auth.startsWith("Bearer ")
        ? auth.slice(7) : (url.searchParams.get("secret") || "");
      if (!env.NOTIFY_SECRET || secret !== env.NOTIFY_SECRET) {
        return json({ error: "forbidden" }, 403, origin);
      }
      let lang = String(url.searchParams.get("lang") || "").toLowerCase();
      await ensureTables(env.DB);
      let stmt;
      if (["ko", "en", "ja"].includes(lang)) {
        stmt = env.DB.prepare(
          "SELECT email FROM subscribers WHERE unsubscribed = 0 AND lang = ?1 ORDER BY email")
          .bind(lang);
      } else {
        stmt = env.DB.prepare(
          "SELECT email FROM subscribers WHERE unsubscribed = 0 ORDER BY email");
      }
      const { results } = await stmt.all();
      return json({ data: results.map(r => r.email) }, 200, origin);
    }

    /* ---------- unsub: one-click unsubscribe from the weekly email ----------
       Link carries e=email & t=hmac24(UNSUB_SECRET, email). Flips unsubscribed=1
       in D1. Supports GET (browser click, returns a small page) and POST
       (RFC 8058 List-Unsubscribe-Post). */
    if (url.pathname === "/unsub") {
      const email = String(url.searchParams.get("e") || "").trim().toLowerCase();
      const t = String(url.searchParams.get("t") || "");
      const page = (title, body) => new Response(
        "<!DOCTYPE html><meta charset=utf-8>"
        + "<meta name=viewport content='width=device-width,initial-scale=1'>"
        + "<div style='font-family:system-ui,-apple-system,sans-serif;max-width:420px;"
        + "margin:64px auto;padding:0 20px;text-align:center'>"
        + "<h2 style='font-size:18px;margin:0 0 8px'>" + title + "</h2>"
        + "<p style='color:#666;font-size:14px;line-height:1.5'>" + body + "</p>"
        + "<p style='margin-top:20px'><a href='https://stacksdaily.com' "
        + "style='color:#2563eb;text-decoration:none'>stacksdaily.com</a></p></div>",
        { status: 200, headers: { "Content-Type": "text/html; charset=utf-8", ...cors(origin) } });
      if (!EMAIL_RE.test(email)) return page("Invalid link", "This unsubscribe link is malformed.");
      if (!env.UNSUB_SECRET) return page("Not available", "Unsubscribe isn’t configured yet.");
      const expect = await hmac24(env.UNSUB_SECRET, email);
      if (t !== expect) return page("Invalid link", "This unsubscribe link is invalid or expired.");
      await ensureTables(env.DB);
      await env.DB.prepare("UPDATE subscribers SET unsubscribed = 1 WHERE email = ?1")
        .bind(email).run();
      if (request.method === "POST") return json({ ok: true }, 200, origin);
      return page("You’re unsubscribed", "You won’t receive the Stacks weekly email anymore.");
    }

    /* ---------- views & likes: batch reads ---------- */
    if (request.method === "GET" && (url.pathname === "/views" || url.pathname === "/likes")) {
      await ensureTables(env.DB);
      const kind = url.pathname === "/views" ? "view" : "like";
      return json({ data: await allCounts(env.DB, kind) }, 200, origin);
    }

    /* ---------- view: +1 per device (frontend dedupes) ---------- */
    if (request.method === "POST" && url.pathname === "/view") {
      const body = await request.json().catch(() => ({}));
      const pageId = String(body.pageId || "");
      if (!PAGE_ID_RE.test(pageId)) return json({ error: "bad pageId" }, 400, origin);
      await ensureTables(env.DB);
      const count = await bump(env.DB, "view", pageId, 1);
      return json({ count }, 200, origin);
    }

    /* ---------- like: toggle ---------- */
    if (request.method === "POST" && url.pathname === "/like") {
      const body = await request.json().catch(() => ({}));
      const pageId = String(body.pageId || "");
      if (!PAGE_ID_RE.test(pageId)) return json({ error: "bad pageId" }, 400, origin);
      await ensureTables(env.DB);
      const count = await bump(env.DB, "like", pageId, body.action === "unlike" ? -1 : 1);
      return json({ count }, 200, origin);
    }

    /* ---------- reader poll: batch read all splits ---------- */
    if (request.method === "GET" && url.pathname === "/votes") {
      await ensureTables(env.DB);
      const up = await allCounts(env.DB, "vup");
      const down = await allCounts(env.DB, "vdown");
      const data = {};
      for (const id in up)   (data[id] = data[id] || { up: 0, down: 0 }).up = up[id];
      for (const id in down) (data[id] = data[id] || { up: 0, down: 0 }).down = down[id];
      return json({ data }, 200, origin);
    }

    /* ---------- reader poll: cast / change / clear a vote ---------- */
    if (request.method === "POST" && url.pathname === "/vote") {
      const body = await request.json().catch(() => ({}));
      const pageId = String(body.pageId || "");
      if (!PAGE_ID_RE.test(pageId)) return json({ error: "bad pageId" }, 400, origin);
      await ensureTables(env.DB);
      const kindOf = d => d === "up" ? "vup" : d === "down" ? "vdown" : null;
      const pk = kindOf(body.prev);   // what they had before (or null)
      const nk = kindOf(body.dir);    // what they have now  (or null = cleared)
      if (pk && pk !== nk) await bump(env.DB, pk, pageId, -1);
      if (nk && nk !== pk) await bump(env.DB, nk, pageId, 1);
      const up = await bump(env.DB, "vup", pageId, 0);     // delta 0 = read current
      const down = await bump(env.DB, "vdown", pageId, 0);
      return json({ data: { up, down } }, 200, origin);
    }

    /* ---------- clike: comment hearts ---------- */
    if (request.method === "POST" && url.pathname === "/clike") {
      const body = await request.json().catch(() => ({}));
      const cid = String(body.commentId || "");
      if (!/^[0-9]{1,12}$/.test(cid)) return json({ error: "bad commentId" }, 400, origin);
      await ensureTables(env.DB);
      const likes = await bump(env.DB, "clike", cid, body.action === "unlike" ? -1 : 1);
      return json({ likes }, 200, origin);
    }

    if (url.pathname !== "/comments" && url.pathname !== "/counts") {
      return json({ error: "not found" }, 404, origin);
    }

    await ensureTables(env.DB);

    /* ---------- counts: one call, every page's comment count ---------- */
    if (url.pathname === "/counts") {
      if (request.method !== "GET") return json({ error: "method not allowed" }, 405, origin);
      const { results } = await env.DB
        .prepare("SELECT page_id, COUNT(*) AS n FROM comments GROUP BY page_id")
        .all();
      const data = {};
      for (const r of results) data[r.page_id] = r.n;
      return json({ data }, 200, origin);
    }

    /* ---------- list (with parentId + likes) ---------- */
    if (request.method === "GET") {
      const pageId = (url.searchParams.get("pageId") || "").slice(0, 100);
      if (!pageId) return json({ error: "pageId required" }, 400, origin);
      const { results } = await env.DB
        .prepare("SELECT c.id, c.nickname, c.content, c.created_at, c.parent_id, " +
                 "COALESCE(k.n, 0) AS likes " +
                 "FROM comments c " +
                 "LEFT JOIN counters k ON k.kind = 'clike' AND k.page_id = CAST(c.id AS TEXT) " +
                 "WHERE c.page_id = ?1 ORDER BY c.id DESC LIMIT 200")
        .bind(pageId).all();
      return json({
        data: results.map(r => ({
          id: r.id,
          parentId: r.parent_id || undefined,
          likes: r.likes || 0,
          nickname: r.nickname,
          content: r.content,
          createdAt: r.created_at
        }))
      }, 200, origin);
    }

    /* ---------- post (accepts parentId for replies) ---------- */
    if (request.method === "POST") {
      let body;
      try { body = await request.json(); }
      catch (e) { return json({ error: "bad json" }, 400, origin); }

      /* honeypot: real users never see or fill this field */
      if (body.website) return json({ ok: true }, 200, origin);

      const pageId = String(body.pageId || "").slice(0, 100).trim();
      const nickname = String(body.nickname || "").slice(0, MAX_NICK).trim();
      const content = String(body.content || "").slice(0, MAX_CONTENT).trim();
      if (!pageId || !nickname || !content) {
        return json({ error: "missing fields" }, 400, origin);
      }

      /* replies: keep only a valid parent on the same page, one level deep */
      let parentId = parseInt(body.parentId, 10) || null;
      if (parentId) {
        const parent = await env.DB
          .prepare("SELECT page_id, parent_id FROM comments WHERE id = ?1")
          .bind(parentId).first();
        if (!parent || parent.page_id !== pageId || parent.parent_id) parentId = null;
      }

      const hash = await ipHash(request);
      const recent = await env.DB
        .prepare("SELECT COUNT(*) AS n FROM comments WHERE ip_hash = ?1 " +
                 "AND created_at > strftime('%Y-%m-%dT%H:%M:%SZ','now','-60 seconds')")
        .bind(hash).first();
      if (recent && recent.n >= RATE_LIMIT_PER_MIN) {
        return json({ error: "rate limited" }, 429, origin);
      }

      await env.DB
        .prepare("INSERT INTO comments (page_id, nickname, content, ip_hash, parent_id) " +
                 "VALUES (?1, ?2, ?3, ?4, ?5)")
        .bind(pageId, nickname, content, hash, parentId).run();
      return json({ ok: true }, 200, origin);
    }

    /* ---------- delete (admin only) ---------- */
    if (request.method === "DELETE") {
      const auth = request.headers.get("Authorization") || "";
      if (!env.ADMIN_KEY || auth !== "Bearer " + env.ADMIN_KEY) {
        return json({ error: "unauthorized" }, 401, origin);
      }
      const id = parseInt(url.searchParams.get("id") || "", 10);
      if (!id) return json({ error: "id required" }, 400, origin);
      await env.DB.prepare("DELETE FROM comments WHERE id = ?1").bind(id).run();
      return json({ ok: true }, 200, origin);
    }

    return json({ error: "method not allowed" }, 405, origin);
  },

  /* ---------- CRON: surge alerts (Cron Trigger: 0 23 * * 1-5 = KST Tue-Sat 08:00) ----------
     Prices every followed company from items.json and pushes the day's biggest
     movers (|change| >= 4%) to their c_<slug> follow tags. One push per company
     per UTC day (D1 surge_alerts dedupe). A cron must never throw. */
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try {
        if (!env.DB || !env.ONESIGNAL_REST_KEY) return;
        await runSurgeAlerts(env, { dryRun: false });
      } catch (e) { /* swallow: cron must never throw */ }
    })());
  }
};

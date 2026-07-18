/* Stacks comments worker (v8: adds the reader poll /vote + /votes;
   everything else identical to v7 — ranged quotes via Yahoo Finance,
   views/likes counters, comment replies & likes, /notify push).
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

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(origin) });
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

    /* ---------- notify: push to followers (June only) ---------- */
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
      if (!p.tag || !p.title || !p.msg) {
        return json({ error: "need tag, title, msg" }, 400, origin);
      }
      const payload = {
        app_id: ONESIGNAL_APP_ID,
        headings: { en: String(p.title).slice(0, 120) },
        contents: { en: String(p.msg).slice(0, 300) },
        url: p.url ? String(p.url).slice(0, 500) : undefined,
        filters: [{ field: "tag", key: String(p.tag).slice(0, 80), relation: "=", value: "1" }]
      };
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
  }
};

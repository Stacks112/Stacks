/* Stacks comments worker (v9.0 = v8.2 + security hardening)
   v9.0 CHANGES (2026-07-25 security pass, no feature removed):
     * /subscribe is POST-only, double opt-in (/confirm), per-IP send cap,
       gmail alias/dot normalisation before the dedupe check.
     * /cron/surge-dryrun is memoised for 10 minutes, so it can no longer be
       used to fan out a Yahoo request per followed company on demand. It
       stays readable without a secret because the 08:20 KST monitor polls
       it over a plain GET; only a secret-holder can force a recompute.
     * secrets split: PUSH_SECRET (push/surge) and SUBSCRIBERS_SECRET
       (subscriber list) with NOTIFY_SECRET kept as a fallback so the
       existing GitHub Actions secret keeps working. Query-string ?secret=
       and GET on privileged routes are gone; Bearer header or POST body only.
       Constant-time comparison.
     * push `url` is whitelisted to stacksdaily.com.
     * shared per-IP throttle on /view /like /vote /clike /comments (D1-backed
       rate_limits table; there is no KV binding on this worker).
     * pageId must exist in items.json before a counter can be created.
     * /vote is server-authoritative (votes table keyed on ip+device), the
       caller-supplied `prev` is ignored.
     * allCounts is capped; comments got the missing indexes.
     * IP hash salt moved to the IP_SALT secret (old salt kept as fallback).
   FIXES FOUND IN REVIEW, same pass:
     * the items.json id set is memoised in isolate memory with a cf.cacheTtl
       hint, and skipped entirely for any pageId that already owns a counter
       row. caches.default is a no-op on workers.dev, so the first draft would
       have re-downloaded 1.3 MB on every single /view.
     * sendConfirm returns Resend's actual result, so a rejected send falls
       back to confirmed = 1 + welcome instead of stranding the subscriber.
     * /confirm no longer clears `unsubscribed` (an old link could re-add an
       opted-out reader), and the confirm token is separated by "\n" rather
       than ":" (which EMAIL_RE allows inside a local part).
     * /clike canonicalises the comment id, so "07" cannot split a comment's
       hearts into an invisible second counter row.
     * a JSON body of literal `null` no longer 500s eight routes.
     * ensureTables runs once per isolate, not nine round trips per request.
     * /vote honours the browser's `prev` once per (IP, article) so pre-v9.0
       votes migrate instead of double-counting, and caps distinct new voters
       per (IP, article) per day so rotating `did` cannot stack votes.
     * push url check compares parsed origin, so a bare https://stacksdaily.com
       passes and https://stacksdaily.com.evil.tld/ does not.
     * the subscribe throttle fails CLOSED; counter throttles still fail open.
   ORIGINAL v8.2 / v8.1 HEADERS BELOW.
*/
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
  "https://stacks112.github.io",
  "http://127.0.0.1:4177"
];

const MAX_NICK = 40;
const MAX_CONTENT = 2000;
const RATE_LIMIT_PER_MIN = 3;
const ONESIGNAL_APP_ID = "88ed92c8-315e-497f-bec1-4f5862f5f45b";

/* ---- surge-alert config (v8.2 additions; sharded in v10.0) ---- */
const ITEMS_URL = "https://raw.githubusercontent.com/Stacks112/Stacks/main/items.json";
const SURGE_ABS_MIN = 4;   // push only |daily % change| >= this
const SURGE_TOP_N = 3;     // at most this many pushes per UTC day (ranked globally)
/* v10.0 — why this is sharded. The Workers Free plan allows 50 subrequests per
   invocation. Pricing every followed company in one pass needed 1 + N, and N
   grew to 78 by 2026-08-03, so every cron firing died at exactly 50 — before
   it ever reached the OneSignal calls, and silently, because fetchDailyChange
   and osPushTag both swallow their errors. Measured: 2026-07-23 used 44
   subrequests and pushed fine; 07-27..07-30 each used exactly 50 and pushed
   nothing. The cron now fires three times (:00 :05 :10) and each firing prices
   one shard into surge_scan; pushes rank across everything scanned that day,
   so the day's top movers stay global. */
const SURGE_SHARDS = 3;     // MUST match the number of cron minutes in wrangler.toml
const SURGE_SCAN_MAX = 40;  // hard ceiling on price lookups per invocation
const SURGE_SCAN_KEEP_DAYS = 7;  // surge_scan rows older than this are pruned

/* ---- security config (v9.0) ---- */
/* every push/notification link must live on one of these origins */
const PUSH_ORIGINS = [
  "https://stacksdaily.com",
  "https://www.stacksdaily.com"
];
/* counter writes: per IP, per 60s window, shared across /view /like /vote /clike.
   Sized for CGNAT/office egress, where hundreds of readers share one IP. */
const COUNTER_RATE_PER_MIN = 300;
/* distinct new voters one IP may register on one article per day. Stops a
   script from minting a fresh device id per request to stack votes. */
const VOTE_NEW_PER_IP_DAY = 8;
/* newsletter: welcome/confirm mails one IP can trigger per hour */
const SUBSCRIBE_RATE_PER_HOUR = 5;
/* hard ceiling on the /views /likes /votes batch payloads */
const COUNTS_MAX_ROWS = 5000;

function cors(origin) {
  const ok = ALLOWED_ORIGINS.includes(origin);
  return {
    "Access-Control-Allow-Origin": ok ? origin : ALLOWED_ORIGINS[0],
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Stacks-Admin-Token",
    "Access-Control-Max-Age": "86400"
  };
}

function json(data, status, origin) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: { "Content-Type": "application/json", ...cors(origin) }
  });
}

/* Pseudonymous per-IP id. The salt used to be a literal in this file, which
   GitHub Pages serves publicly — anyone could rebuild the table and reverse a
   hash back to an IP. Set the IP_SALT worker secret to rotate it; the old
   literal stays as the fallback so existing rows keep matching until then. */
async function ipHash(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "0.0.0.0";
  const salt = (env && env.IP_SALT) || "stacks-salt-2026::";
  const buf = await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode(salt + ip));
  return [...new Uint8Array(buf)].slice(0, 12)
    .map(b => b.toString(16).padStart(2, "0")).join("");
}

/* length-independent constant-time string compare (no early return on
   the first differing byte, so response timing does not leak the prefix) */
function safeEq(a, b) {
  a = String(a == null ? "" : a);
  b = String(b == null ? "" : b);
  let diff = a.length ^ b.length;
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return diff === 0;
}

/* Privileged-route auth. The secret may travel in the Authorization: Bearer
   header or, for POST, in the JSON body — never in the query string (query
   strings land in access logs, browser history and Referer headers).
   `names` is tried in order, so a route can prefer its own narrow secret and
   still accept the legacy NOTIFY_SECRET that GitHub Actions already holds. */
function authorized(request, env, bodySecret, names) {
  const auth = request.headers.get("Authorization") || "";
  const given = auth.startsWith("Bearer ") ? auth.slice(7)
    : (request.method === "POST" ? String(bodySecret || "") : "");
  if (!given) return false;
  let ok = false;
  for (const n of names) {
    const want = env[n];
    if (want && safeEq(given, want)) ok = true;   // no early exit: constant work
  }
  return ok;
}

/* A push/notification link must point at our own site. Without this, anyone
   holding the push secret (or a future bug that leaks it) could blast every
   subscriber a notification that opens an attacker-controlled page. */
function safePushUrl(raw) {
  const s = String(raw || "").slice(0, 500).trim();
  if (!s) return undefined;
  /* compared on parsed origin, not string prefix: a prefix test either
     rejects the bare "https://stacksdaily.com" (no trailing slash) or, if
     the slash is dropped, accepts "https://stacksdaily.com.evil.tld/". */
  try {
    return PUSH_ORIGINS.includes(new URL(s).origin) ? s : undefined;
  } catch (e) { return undefined; }
}

/* v9.0 migrations are idempotent but not free: nine serial D1 round trips on
   every counter write is real latency. One isolate only needs to do it once. */
let TABLES_READY = false;

async function ensureTables(db) {
  if (TABLES_READY) return;
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
  /* v9.0 double opt-in. DEFAULT 1 on purpose: every address that signed up
     under the old single opt-in flow stays confirmed, so the existing list
     keeps receiving the weekly mail. Only new signups start at 0. */
  try { await db.exec("ALTER TABLE subscribers ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 1"); }
  catch (e) {}
  /* own-comment edit/delete: a per-comment secret the browser generates and
     keeps; we store only its SHA-256. Old rows have NULL and stay read-only. */
  try { await db.exec("ALTER TABLE comments ADD COLUMN owner_hash TEXT"); }
  catch (e) {}
  /* edited comments carry a timestamp so the UI can show "(수정됨)" */
  try { await db.exec("ALTER TABLE comments ADD COLUMN edited_at TEXT"); }
  catch (e) {}
  /* v9.0 the comment rate-limit query used to full-scan the table */
  try { await db.exec("CREATE INDEX IF NOT EXISTS idx_comments_ip ON comments(ip_hash, created_at)"); }
  catch (e) {}
  try { await db.exec("CREATE INDEX IF NOT EXISTS idx_comments_page ON comments(page_id, id)"); }
  catch (e) {}
  /* v9.0 generic throttle buckets (this worker has no KV binding, so the
     counter has to live in D1). One row per (key, time window). */
  await db.exec(
    "CREATE TABLE IF NOT EXISTS rate_limits (" +
    "bucket TEXT PRIMARY KEY, " +
    "n INTEGER NOT NULL DEFAULT 0, " +
    "exp INTEGER NOT NULL)"
  );
  /* v9.0 server-side record of who voted what, so /vote no longer has to
     believe the `prev` value the browser sends it. */
  await db.exec(
    "CREATE TABLE IF NOT EXISTS votes (" +
    "page_id TEXT NOT NULL, " +
    "voter TEXT NOT NULL, " +
    "dir TEXT NOT NULL, " +
    "updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), " +
    "PRIMARY KEY (page_id, voter))"
  );
  await db.exec(
    "CREATE TABLE IF NOT EXISTS view_dedup (" +
    "page_id TEXT NOT NULL, " +
    "ip_hash TEXT NOT NULL, " +
    "created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')), " +
    "PRIMARY KEY (page_id, ip_hash))"
  );
  await ensureManualTables(db);
  TABLES_READY = true;
}

async function ensureManualTables(db) {
  await db.exec(
    "CREATE TABLE IF NOT EXISTS manual_post_overrides (" +
    "slug TEXT PRIMARY KEY, " +
    "title TEXT NOT NULL, " +
    "body_html TEXT NOT NULL, " +
    "source_url TEXT, " +
    "published_at TEXT, " +
    "status TEXT NOT NULL DEFAULT 'active', " +
    "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, " +
    "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
  );
  await db.exec(
    "CREATE INDEX IF NOT EXISTS idx_manual_post_overrides_status_updated " +
    "ON manual_post_overrides (status, updated_at DESC)"
  );
}

/* Fixed-window counter in D1. Returns true while the caller is under `limit`.
   Expired buckets are swept opportunistically (~2% of first hits) so the
   table cannot grow without bound. Fails OPEN: a D1 hiccup must not take
   likes and views down with it. */
async function rateOk(db, key, limit, windowSec, failOpen) {
  if (failOpen === undefined) failOpen = true;
  try {
    const now = Math.floor(Date.now() / 1000);
    const slot = Math.floor(now / windowSec);
    const row = await db.prepare(
      "INSERT INTO rate_limits (bucket, n, exp) VALUES (?1, 1, ?2) " +
      "ON CONFLICT(bucket) DO UPDATE SET n = n + 1 RETURNING n"
    ).bind(key + ":" + slot, (slot + 2) * windowSec).first();
    const n = row ? row.n : 1;
    if (n === 1 && Math.random() < 0.02) {
      try { await db.prepare("DELETE FROM rate_limits WHERE exp < ?1").bind(now).run(); }
      catch (e) {}
    }
    return n <= limit;
  } catch (e) { return !!failOpen; }   // mail paths pass false: fail CLOSED
}

/* The set of item ids that actually exist, straight from the published
   items.json, cached at the edge for 5 minutes. Without this any stranger can
   POST /view with a made-up pageId and grow the counters table forever.
   Fails OPEN (returns null = "cannot tell") if items.json is unreachable. */
/* v10.0: the surge dry-run no longer prices anything on demand — it reads the
   rows the cron already wrote — so the old DRY memo, which existed only to stop
   a stranger fanning out one Yahoo request per followed company, is gone. That
   memo is also what made three days of monitor runs report a frozen date. */

let PAGEIDS = null;        // Set, memoised in isolate memory
let PAGEIDS_AT = 0;        // epoch seconds of the last successful load
let PAGEIDS_INFLIGHT = null;
const PAGEIDS_TTL = 300;

async function knownPageIds() {
  const now = Math.floor(Date.now() / 1000);
  if (PAGEIDS && now - PAGEIDS_AT < PAGEIDS_TTL) return PAGEIDS;
  if (PAGEIDS_INFLIGHT) return PAGEIDS_INFLIGHT;   // collapse a thundering herd
  PAGEIDS_INFLIGHT = (async () => {
    try {
      /* cf.cacheTtl works on workers.dev; caches.default does not, which is
         why this is a subrequest cache hint and not a Cache API round trip.
         items.json is ~1.3 MB, so this must not run per request. */
      const r = await fetch(ITEMS_URL, {
        headers: { "User-Agent": "StacksWorker/9.0" },
        cf: { cacheTtl: PAGEIDS_TTL, cacheEverything: true }
      });
      if (!r.ok) return null;
      const j = await r.json();
      const arr = (j && j.items) || [];
      const ids = arr.map(x => String((x && x.id) || "")).filter(Boolean);
      if (!ids.length) return null;
      PAGEIDS = new Set(ids);
      PAGEIDS_AT = Math.floor(Date.now() / 1000);
      return PAGEIDS;
    } catch (e) {
      return null;
    } finally {
      PAGEIDS_INFLIGHT = null;
    }
  })();
  return PAGEIDS_INFLIGHT;
}

/* Fast path: an id that already owns a counter row was validated once before,
   so it never needs the items.json lookup again. In steady state this makes
   the existence check free for every real article. */
async function pageIdSeen(db, pageId) {
  try {
    const row = await db.prepare(
      "SELECT 1 AS x FROM counters WHERE page_id = ?1 LIMIT 1").bind(pageId).first();
    return !!row;
  } catch (e) { return false; }
}

/* shape check + existence check. `kind` lets comment-hearts (numeric comment
   ids) skip the items.json lookup, which does not apply to them. */
async function viewIsNew(db, pageId, ipH) {
  try {
    const row = await db.prepare(
      "INSERT INTO view_dedup (page_id, ip_hash) VALUES (?1, ?2) ON CONFLICT(page_id, ip_hash) DO NOTHING RETURNING page_id"
    ).bind(pageId, ipH).first();
    return !!row;
  } catch (e) {
    return true;
  }
}
__name(viewIsNew, "viewIsNew");
async function validPageId(db, pageId, checkExists) {
  if (!PAGE_ID_RE.test(pageId)) return false;
  if (!checkExists) return true;
  if (await pageIdSeen(db, pageId)) return true;
  const known = await knownPageIds();
  return known ? known.has(pageId) : true;   // unknown = allow, never 500 the site
}

/* Stable-ish voter identity: the IP hash alone would let one office network
   overwrite a colleague's vote, and a device id alone is trivially forged, so
   the key is both. Forging device ids still costs an IP, and the IP is what
   the throttle counts. */
function deviceKey(ipH, rawDid) {
  const did = String(rawDid || "").replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 32);
  return ipH + ":" + (did || "-");
}

/* One shared budget for every counter write (/view /like /vote /clike), so a
   script cannot dodge the limit by rotating between endpoints. Sized well
   above what a fast reader scrolling a full feed produces. */
async function counterOk(request, env) {
  const ipH = await ipHash(request, env);
  return rateOk(env.DB, "cnt:" + ipH, COUNTER_RATE_PER_MIN, 60);
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
    .prepare("SELECT page_id, n FROM counters WHERE kind = ?1 AND n > 0 " +
             "ORDER BY n DESC LIMIT " + COUNTS_MAX_ROWS)
    .bind(kind).all();
  const data = {};
  for (const r of results) data[r.page_id] = r.n;
  return data;
}

const PAGE_ID_RE = /^[a-z0-9_-]{1,64}$/i;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* first 24 hex chars of HMAC-SHA256(secret, msg) — must match the Python
   unsub_link() in scripts/weekly_send.py exactly. */
async function sha256hex(msg) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(msg)));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}
async function hmac24(secret, msg) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 24);
}

function cleanManualSlug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}

function cleanManualText(value, maxLength) {
  return String(value || "")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .trim()
    .slice(0, maxLength);
}

function cleanManualUrl(value) {
  const text = cleanManualText(value, 500);
  if (!text.startsWith("/") && !text.startsWith("https://") && !text.startsWith("http://")) {
    return "";
  }
  return text;
}

function cleanManualHtml(value) {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
    .replace(/<object[\s\S]*?<\/object>/gi, "")
    .replace(/<embed[\s\S]*?>/gi, "")
    .replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "")
    .replace(/\s(href|src)\s*=\s*(['"])\s*javascript:[\s\S]*?\2/gi, "")
    .trim()
    .slice(0, 250000);
}

function manualAuthorized(request, env) {
  const auth = request.headers.get("Authorization") || "";
  const bearer = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  const given = request.headers.get("X-Stacks-Admin-Token") || bearer;
  return !!given && (
    (env.MANUAL_EDITOR_TOKEN && safeEq(given, env.MANUAL_EDITOR_TOKEN)) ||
    (env.ADMIN_KEY && safeEq(given, env.ADMIN_KEY))
  );
}

function normalizeManualPost(body) {
  return {
    slug: cleanManualSlug(body.slug || ""),
    title: cleanManualText(body.title || "", 240),
    bodyHtml: cleanManualHtml(body.bodyHtml || ""),
    sourceUrl: cleanManualUrl(body.sourceUrl || body.source_url || ""),
    publishedAt: cleanManualText(body.publishedAt || body.published_at || body.date || "", 40),
    status: body.status === "archived" ? "archived" : "active"
  };
}

/* ---------- welcome email (sent right after a new /subscribe) ----------
   Localized copy; unsubscribe link is the same HMAC one-click link the
   weekly email uses. Requires the worker secrets RESEND_API_KEY (sending-
   only key) and UNSUB_SECRET; silently skipped if either is missing. */
const WELCOME_COPY = {
  ko: {
    subj: "🎉 Stacks 구독 완료! 매주 일요일에 만나요",
    hi: "구독해 주셔서 감사해요!",
    body: "매주 일요일 아침,<br>이번 주 가장 중요한 투자 읽을거리를 요약과 관점까지 담아 이 메일함으로 보내드려요.",
    note: "그동안의 글이 궁금하면 지금 바로 둘러보세요.",
    cta: "Stacks 둘러보기",
    unsub: "구독 해지"
  },
  en: {
    subj: "🎉 You\u2019re subscribed to Stacks! See you Sunday",
    hi: "Thanks for subscribing!",
    body: "Every Sunday morning,<br>we\u2019ll send this inbox the week\u2019s most important investing reads, summarized with a take.",
    note: "Want a head start? The archive is open now.",
    cta: "Explore Stacks",
    unsub: "Unsubscribe"
  },
  ja: {
    subj: "🎉 Stacksの購読完了！毎週日曜にお届けします",
    hi: "ご購読ありがとうございます！",
    body: "毎週日曜の朝、<br>今週最も重要な投資の読みものを、要約と視点付きでこのメールボックスにお届けします。",
    note: "これまでの記事は今すぐご覧いただけます。",
    cta: "Stacksを見る",
    unsub: "購読解除"
  }
};

/* ---------- confirmation email (v9.0 double opt-in) ----------
   Nobody joins the list until they click this. Without it anyone could POST a
   stranger's address (or a thousand of them) and we would mail people who
   never asked, from our own sending domain. */
const CONFIRM_COPY = {
  ko: {
    subj: "Stacks 구독 확인만 해주세요",
    hi: "한 번만 눌러주세요",
    body: "이 주소로 Stacks 주간 메일 구독 요청이 들어왔어요.<br>본인이 맞다면 아래 버튼을 눌러 구독을 확정해주세요.",
    note: "요청한 적이 없다면 이 메일을 무시하시면 됩니다. 아무 일도 일어나지 않아요.",
    cta: "구독 확정하기",
    unsub: "무시하기"
  },
  en: {
    subj: "Confirm your Stacks subscription",
    hi: "One click to finish",
    body: "Someone asked to subscribe this address to the Stacks weekly email.<br>If that was you, confirm with the button below.",
    note: "If you did not request this, just ignore this email. Nothing will happen.",
    cta: "Confirm subscription",
    unsub: "Ignore"
  },
  ja: {
    subj: "Stacksの購読確認をお願いします",
    hi: "あと1クリックです",
    body: "このアドレスでStacksの週刊メール購読リクエストがありました。<br>ご本人であれば下のボタンで確定してください。",
    note: "心当たりがない場合は、このメールを無視してください。何も起こりません。",
    cta: "購読を確定する",
    unsub: "無視する"
  }
};

/* token for the opt-in link. Distinct message prefix from the unsubscribe
   token, so a leaked unsubscribe link can never be replayed as a confirm. */
function confirmToken(env, email) {
  /* "\n" cannot appear in an address, so no address can ever hash to another
     address's confirm message. A ":" separator could: EMAIL_RE admits a ":"
     in the local part, so subscribing "confirm:victim@x.tld" would hand the
     attacker victim@x.tld's confirm token in their own welcome mail. */
  return hmac24(env.UNSUB_SECRET, "confirm\n" + email);
}

async function sendConfirm(env, workerOrigin, email, lang) {
  if (!env.RESEND_API_KEY || !env.UNSUB_SECRET) return false;
  const T = CONFIRM_COPY[lang] || CONFIRM_COPY.ko;
  const t = await confirmToken(env, email);
  const ctaUrl = workerOrigin + "/confirm?e=" + encodeURIComponent(email)
    + "&t=" + t + "&l=" + encodeURIComponent(lang);
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
    + "<a href=\"" + ctaUrl + "\" style=\"display:inline-block;background:#111827;color:#ffffff;"
    + "text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:999px\">"
    + T.cta + "</a>"
    + "</div>"
    + "<p style=\"text-align:center;font-size:12px;color:#9ca3af;margin:20px 0 0\">"
    + "Stacks · <a href=\"https://stacksdaily.com\" style=\"color:#9ca3af\">" + T.unsub + "</a></p>"
    + "</div></body></html>";
  /* the result matters: a discarded response means a Resend 4xx (bad key,
     unverified domain, quota, suppression) leaves the row confirmed = 0 with
     no mail ever sent, i.e. a subscriber stuck pending forever. */
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + env.RESEND_API_KEY
    },
    body: JSON.stringify({
      from: env.RESEND_FROM || "Stacks Weekly <weekly@stacksdaily.com>",
      to: [email],
      subject: T.subj,
      html: html
    })
  });
  return r.ok;
}

/* Canonical form used for the duplicate check only. "a.b+news@gmail.com",
   "ab@gmail.com" and "a.b@googlemail.com" are one mailbox, so without this a
   single person (or a script) can sign the same inbox up an unlimited number
   of times and walk straight past every per-address guard below. */
const SUBADDR_HOSTS = ["gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
                       "live.com", "icloud.com", "me.com", "fastmail.com", "proton.me"];
function canonEmail(raw) {
  const e = String(raw || "").trim().toLowerCase();
  const at = e.lastIndexOf("@");
  if (at < 1) return e;
  let local = e.slice(0, at);
  const host = e.slice(at + 1);
  if (!SUBADDR_HOSTS.includes(host)) return e;
  local = local.split("+")[0];
  if (host === "gmail.com" || host === "googlemail.com") {
    return local.replace(/\./g, "") + "@gmail.com";
  }
  return local + "@" + host;
}

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
    url: safePushUrl(link),
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

/* items.json -> the full list of followable companies, in a deterministic
   order. The order MUST be stable across invocations or shard membership
   drifts between the three firings and some companies are never priced.
   Costs 1 subrequest. Returns null when items.json is unreachable. */
async function listCompanies() {
  let entities = {};
  try {
    const r = await fetch(ITEMS_URL, { cf: { cacheTtl: 300 } });
    if (!r.ok) return null;
    const data = await r.json();
    entities = (data && data.entities) || {};
  } catch (e) { return null; }
  const companies = [];
  for (const name in entities) {
    const e = entities[name];
    if (e && e.kind === "company" && e.ticker) companies.push({ name, ticker: e.ticker });
  }
  companies.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  return companies;
}

async function ensureSurgeTables(db) {
  await db.exec(
    "CREATE TABLE IF NOT EXISTS surge_alerts (" +
    "date TEXT NOT NULL, tag TEXT NOT NULL, PRIMARY KEY (date, tag))"
  );
  await db.exec(
    "CREATE TABLE IF NOT EXISTS surge_scan (" +
    "date TEXT NOT NULL, tag TEXT NOT NULL, name TEXT NOT NULL, ticker TEXT NOT NULL, " +
    "pct REAL NOT NULL, price REAL, currency TEXT, PRIMARY KEY (date, tag))"
  );
}

/* price one shard of the company list into surge_scan for `date`.
   Subrequests: 1 (items.json) + at most SURGE_SCAN_MAX. Never throws. */
async function scanShard(env, date, shard) {
  const companies = await listCompanies();
  if (!companies) return { total: 0, picked: 0, priced: 0, skipped: 0 };
  const s = ((shard % SURGE_SHARDS) + SURGE_SHARDS) % SURGE_SHARDS;
  const mine = companies.filter((_, i) => i % SURGE_SHARDS === s);
  const take = mine.slice(0, SURGE_SCAN_MAX);
  let priced = 0;
  for (const c of take) {
    const q = await fetchDailyChange(c.ticker);
    if (!q || !isFinite(q.pct)) continue;
    priced++;
    await env.DB.prepare(
      "INSERT INTO surge_scan (date, tag, name, ticker, pct, price, currency) " +
      "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7) ON CONFLICT(date, tag) DO UPDATE SET " +
      "pct = excluded.pct, price = excluded.price, currency = excluded.currency"
    ).bind(
      date, "c_" + surgeSlug(c.name), c.name, c.ticker,
      Math.round(q.pct * 100) / 100, q.price, q.currency || ""
    ).run();
  }
  /* skipped > 0 means this shard is itself too big for one invocation, i.e.
     SURGE_SHARDS needs to go up. It is reported, never swallowed. */
  return { total: companies.length, picked: mine.length, priced, skipped: mine.length - take.length };
}

/* today's movers, ranked across everything scanned so far. D1 reads only. */
async function scannedSurges(env, date, limit) {
  const { results } = await env.DB.prepare(
    "SELECT name, ticker, pct, price, currency, tag FROM surge_scan " +
    "WHERE date = ?1 AND ABS(pct) >= ?2 ORDER BY ABS(pct) DESC LIMIT ?3"
  ).bind(date, SURGE_ABS_MIN, limit).all();
  return results || [];
}

async function sentTags(env, date) {
  const { results } = await env.DB.prepare(
    "SELECT tag FROM surge_alerts WHERE date = ?1"
  ).bind(date).all();
  return (results || []).map(r => r.tag);
}

/* push the biggest movers not yet pushed today, capped at SURGE_TOP_N per UTC
   day in total (surge_alerts is both the dedupe and the day's budget).
   Subrequests: at most SURGE_TOP_N. */
async function pushSurges(env, date) {
  const already = await sentTags(env, date);
  let budget = SURGE_TOP_N - already.length;
  if (budget <= 0) return [];
  const ranked = await scannedSurges(env, date, SURGE_TOP_N);
  const out = [];
  for (const sge of ranked) {
    if (budget <= 0) break;
    if (already.indexOf(sge.tag) !== -1) continue;
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
      budget--;
    }
    out.push({ name: sge.name, ticker: sge.ticker, pct: sge.pct, tag: sge.tag, sent: ok });
  }
  return out;
}

/* one cron firing (or one authorised manual call): scan my shard, then push.
   Returns the coverage numbers so a truncated scan can never look clean.

   WHY THE PUSH WAITS FOR A COMPLETE SCAN: the daily budget is SURGE_TOP_N
   pushes, so if an early shard spends it on its own local movers, a bigger
   mover living in a later shard can never be sent. (Caught in test: +20% was
   silently beaten by a +4.2% that happened to be scanned first.) So a firing
   only pushes once the day's scan is complete — which is the last shard in the
   normal case. `isLast` is kept as a fallback so a day where some shard never
   fired still sends the best of what was actually scanned rather than nothing.
   opts.push forces the decision either way for manual calls.
   opts.sweep = the :15 firing: push only, never scan. It exists so that a day
   where the last scanning shard was lost still sends something (measured: two
   cron firings vanished entirely in the nine days before 2026-08-03). Costs at
   most SURGE_TOP_N subrequests and is a no-op once the budget is spent. */
async function runSurgeShard(env, opts) {
  const sweep = !!(opts && opts.sweep);
  const shard = ((opts && opts.shard) | 0);
  const s = ((shard % SURGE_SHARDS) + SURGE_SHARDS) % SURGE_SHARDS;
  const date = new Date().toISOString().slice(0, 10);
  await ensureSurgeTables(env.DB);
  const cutoff = new Date(Date.now() - SURGE_SCAN_KEEP_DAYS * 86400000)
    .toISOString().slice(0, 10);
  await env.DB.prepare("DELETE FROM surge_scan WHERE date < ?1").bind(cutoff).run();
  const scan = sweep
    ? { total: 0, picked: 0, priced: 0, skipped: 0 }
    : await scanShard(env, date, shard);
  const row = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM surge_scan WHERE date = ?1").bind(date).first();
  const scannedToday = row ? row.n : 0;
  const complete = scan.total > 0 && scannedToday >= scan.total;
  const wantPush = (opts && typeof opts.push === "boolean")
    ? opts.push
    : (sweep || complete || s === SURGE_SHARDS - 1);
  const sent = wantPush ? await pushSurges(env, date) : [];
  return {
    date, mode: sweep ? "sweep" : "scan",
    shard: sweep ? null : s, shards: SURGE_SHARDS, threshold: SURGE_ABS_MIN,
    total: scan.total, pricedThisRun: scan.priced, skippedThisRun: scan.skipped,
    scannedToday, complete, pushed: wantPush,
    sent
  };
}

/* ============= end surge alerts (v8.2, sharded v10.0) ============ */

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(origin) });
    }

    if (url.pathname === "/api/manual-post") {
      await ensureManualTables(env.DB);

      if (request.method === "GET") {
        const slug = cleanManualSlug(url.searchParams.get("slug") || "");
        if (!slug) return json({ ok: false, error: "slug is required" }, 400, origin);
        const row = await env.DB.prepare(
          "SELECT slug, title, body_html, source_url, published_at, status, updated_at " +
          "FROM manual_post_overrides WHERE slug = ?1 AND status = 'active'"
        ).bind(slug).first();
        if (!row) return json({ ok: true, found: false }, 200, origin);
        return json({
          ok: true,
          found: true,
          post: {
            slug: row.slug,
            title: row.title,
            bodyHtml: row.body_html,
            sourceUrl: row.source_url,
            publishedAt: row.published_at,
            status: row.status,
            updatedAt: row.updated_at
          }
        }, 200, origin);
      }

      if (request.method === "POST") {
        if (!manualAuthorized(request, env)) return json({ ok: false, error: "unauthorized" }, 401, origin);
        const body = (await request.json().catch(() => null)) || {};
        const post = normalizeManualPost(body);
        if (!post.slug || !post.title || !post.bodyHtml) {
          return json({ ok: false, error: "slug, title, and bodyHtml are required" }, 400, origin);
        }
        await env.DB.prepare(
          "INSERT INTO manual_post_overrides " +
          "(slug, title, body_html, source_url, published_at, status, updated_at) " +
          "VALUES (?1, ?2, ?3, ?4, ?5, ?6, CURRENT_TIMESTAMP) " +
          "ON CONFLICT(slug) DO UPDATE SET " +
          "title = excluded.title, body_html = excluded.body_html, " +
          "source_url = excluded.source_url, published_at = excluded.published_at, " +
          "status = excluded.status, updated_at = CURRENT_TIMESTAMP"
        ).bind(post.slug, post.title, post.bodyHtml, post.sourceUrl || null,
          post.publishedAt || null, post.status).run();
        return json({ ok: true, slug: post.slug }, 200, origin);
      }

      if (request.method === "DELETE") {
        if (!manualAuthorized(request, env)) return json({ ok: false, error: "unauthorized" }, 401, origin);
        const slug = cleanManualSlug(url.searchParams.get("slug") || "");
        if (!slug) return json({ ok: false, error: "slug is required" }, 400, origin);
        await env.DB.prepare(
          "UPDATE manual_post_overrides SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE slug = ?1"
        ).bind(slug).run();
        return json({ ok: true, slug }, 200, origin);
      }

      return json({ ok: false, error: "method not allowed" }, 405, origin);
    }

    /* ---------- surge alerts: read-only diagnostic ----------
       What the 08:20 KST monitor task polls, over a plain GET with no
       credentials, so a secret gate here would just break the monitor.
       v10.0: this no longer prices anything itself. It reports what the cron
       already wrote to surge_scan, plus the coverage numbers, so a truncated
       scan can never look like a clean one — and it costs 1 subrequest
       instead of 79, which is what made the old version an amplifier and
       forced the memo that then reported a frozen date for three days.
       `sentToday` is the field that actually answers "did followers get it". */
    if (url.pathname === "/cron/surge-dryrun") {
      if (!env.DB) return json({ ok: false, error: "no db" }, 500, origin);
      await ensureSurgeTables(env.DB);
      const date = new Date().toISOString().slice(0, 10);
      const surges = await scannedSurges(env, date, SURGE_TOP_N);
      const row = await env.DB.prepare(
        "SELECT COUNT(*) AS n FROM surge_scan WHERE date = ?1").bind(date).first();
      const companies = await listCompanies();
      const scannedToday = row ? row.n : 0;
      const total = companies ? companies.length : null;
      return json({
        ok: true, date, dryRun: true, source: "surge_scan",
        threshold: SURGE_ABS_MIN, shards: SURGE_SHARDS,
        scannedToday, total,
        complete: total !== null && scannedToday >= total,
        count: surges.length, surges,
        sentToday: await sentTags(env, date)
      }, 200, origin);
    }
    /* ---------- surge alerts: force a real send (June only) ----------
       POST + Bearer (or a secret in the JSON body). Deduped per company/day.
       One shard per call — the whole list does not fit in one invocation's
       subrequest budget. Body: {shard: 0..SURGE_SHARDS-1, push: true|false} */
    if (url.pathname === "/cron/surge") {
      if (request.method !== "POST") return json({ error: "method not allowed" }, 405, origin);
      const p = (await request.json().catch(() => null)) || {};
      if (!authorized(request, env, p.secret, ["PUSH_SECRET", "NOTIFY_SECRET"])) {
        return json({ error: "forbidden" }, 403, origin);
      }
      const r = await runSurgeShard(env, { shard: p.shard | 0, push: p.push });
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
      /* v9.0: POST only. The old GET form put the push secret in the query
         string, where it ends up in edge logs and browser history. */
      if (request.method !== "POST") return json({ error: "method not allowed" }, 405, origin);
      const p = (await request.json().catch(() => null)) || {};
      if (!authorized(request, env, p.secret, ["PUSH_SECRET", "NOTIFY_SECRET"])) {
        return json({ error: "forbidden" }, 403, origin);
      }
      if (!env.ONESIGNAL_REST_KEY) {
        return json({ error: "ONESIGNAL_REST_KEY secret not set" }, 500, origin);
      }
      if (!p.tag) {
        return json({ error: "need tag, title, msg" }, 400, origin);
      }
      const headings = langMap(p, "title", 120);
      if (p.msg === undefined && p.body !== undefined) p.msg = p.body;  // caller alias
      const contents = langMap(p, "msg", 300);
      if (!headings.en || !contents.en) {
        return json({ error: "need tag, title, msg" }, 400, origin);
      }
      const payload = {
        app_id: ONESIGNAL_APP_ID,
        headings,
        contents,
        url: safePushUrl(p.url),          // v9.0: stacksdaily.com links only
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
    if (url.pathname === "/subscribe") {
      /* v9.0: POST only. GET made this a one-pixel mail cannon: any page on
         the internet could embed <img src=".../subscribe?email=victim@..."> and
         our sending domain would deliver the mail. A JSON POST is not a form
         or image request, so a cross-site page cannot forge one silently. */
      if (request.method !== "POST") return json({ error: "method not allowed" }, 405, origin);
      const ct = (request.headers.get("Content-Type") || "").toLowerCase();
      if (!ct.includes("application/json")) {
        return json({ error: "content-type must be application/json" }, 415, origin);
      }
      const p = (await request.json().catch(() => null)) || {};
      if (p.website) return json({ ok: true }, 200, origin);  // honeypot
      const typed = String(p.email || "").trim().toLowerCase();
      let lang = String(p.lang || "ko").toLowerCase();
      if (!["ko", "en", "ja"].includes(lang)) lang = "ko";
      if (!EMAIL_RE.test(typed) || typed.length > 200) {
        return json({ ok: false, error: "invalid email" }, 400, origin);
      }
      const email = canonEmail(typed);
      await ensureTables(env.DB);
      const prev = await env.DB.prepare(
        "SELECT unsubscribed, confirmed FROM subscribers WHERE email = ?1")
        .bind(email).first();

      /* Already on the list and confirmed: this is just a language change or a
         double submit. Update and return, silently, with no mail at all. */
      if (prev && !prev.unsubscribed && prev.confirmed) {
        await env.DB.prepare("UPDATE subscribers SET lang = ?2 WHERE email = ?1")
          .bind(email, lang).run();
        return json({ ok: true, status: "subscribed" }, 200, origin);
      }

      /* Anything past here sends mail, so it costs the caller their IP budget.
         Five confirmation mails per hour per IP is generous for a human and
         useless as a flooding tool. */
      const ipH = await ipHash(request, env);
      if (!await rateOk(env.DB, "sub:" + ipH, SUBSCRIBE_RATE_PER_HOUR, 3600, false)) {
        return json({ ok: false, error: "rate limited" }, 429, origin);
      }

      /* Pending row stays unconfirmed and, critically, stays OUT of the
         /subscribers list the weekly sender reads. */
      await env.DB.prepare(
        "INSERT INTO subscribers (email, lang, unsubscribed, confirmed) VALUES (?1, ?2, 0, 0) " +
        "ON CONFLICT(email) DO UPDATE SET lang = ?2, unsubscribed = 0, confirmed = 0"
      ).bind(email, lang).run();

      let sent = false;
      try { sent = await sendConfirm(env, url.origin, email, lang); } catch (e) {}
      if (!sent) {
        /* Double opt-in needs RESEND_API_KEY + UNSUB_SECRET. If either is
           missing we fall back to the old single opt-in rather than leaving a
           signup stuck in limbo the reader can never escape. */
        await env.DB.prepare("UPDATE subscribers SET confirmed = 1 WHERE email = ?1")
          .bind(email).run();
        try { await sendWelcome(env, url.origin, email, lang); } catch (e) {}
        return json({ ok: true, status: "subscribed" }, 200, origin);
      }
      return json({ ok: true, status: "pending" }, 200, origin);
    }

    /* ---------- confirm: finish a double opt-in signup ----------
       Link carries e=email & t=hmac24(UNSUB_SECRET, "confirm:"+email). Only
       the person holding the inbox can have this token, which is the whole
       point: it proves the address consented. */
    if (url.pathname === "/confirm") {
      const email = canonEmail(url.searchParams.get("e") || "");
      const t = String(url.searchParams.get("t") || "");
      let lang = String(url.searchParams.get("l") || "ko").toLowerCase();
      if (!["ko", "en", "ja"].includes(lang)) lang = "ko";
      const C = {
        ko: { ok: ["구독이 확정됐어요", "매주 일요일 아침에 만나요."],
              bad: ["링크가 올바르지 않아요", "주소가 잘린 것 같아요. 메일의 확인 버튼을 다시 눌러주세요."] },
        en: { ok: ["You are subscribed", "See you Sunday morning."],
              bad: ["Invalid link", "This confirmation link is not valid. Please tap the confirm button in the email again."] },
        ja: { ok: ["購読が確定しました", "毎週日曜の朝にお届けします。"],
              bad: ["リンクが無効です", "確認リンクが正しくありません。メールの確認ボタンをもう一度押してください。"] }
      }[lang];
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
      if (!EMAIL_RE.test(email) || !env.UNSUB_SECRET) return page(C.bad[0], C.bad[1]);
      const expect = await confirmToken(env, email);
      if (!safeEq(t, expect)) return page(C.bad[0], C.bad[1]);
      await ensureTables(env.DB);
      const before = await env.DB.prepare(
        "SELECT confirmed FROM subscribers WHERE email = ?1").bind(email).first();
      if (!before) return page(C.bad[0], C.bad[1]);
      /* confirmed only. `unsubscribed = 0` here would let anyone replaying an
         old confirm URL (forwarded mail, link scanner, synced history) re-add
         a reader who opted out. /subscribe already clears the flag on a real
         re-opt-in, so nothing legitimate needs it. */
      await env.DB.prepare(
        "UPDATE subscribers SET confirmed = 1 WHERE email = ?1")
        .bind(email).run();
      /* welcome mail once, on the transition only, so re-clicking the link in
         an old email does not send it again */
      if (!before.confirmed) {
        try { await sendWelcome(env, url.origin, email, lang); } catch (e) {}
      }
      return page(C.ok[0], C.ok[1]);
    }

    /* ---------- subscribers: active list for a language (secret-guarded) ----------
       Read by scripts/weekly_send.py at send time. Secret travels in the
       Authorization: Bearer header (or ?secret= as a fallback), never exposed
       to the browser. */
    if (url.pathname === "/subscribers" && request.method === "GET") {
      /* v9.0: Bearer header only. The old ?secret= fallback wrote the key that
         dumps the entire subscriber list into edge logs and Referer headers.
         SUBSCRIBERS_SECRET is the narrow key for this route; NOTIFY_SECRET is
         still accepted so the existing Actions secret keeps working. */
      if (!authorized(request, env, null, ["SUBSCRIBERS_SECRET", "NOTIFY_SECRET"])) {
        return json({ error: "forbidden" }, 403, origin);
      }
      let lang = String(url.searchParams.get("lang") || "").toLowerCase();
      await ensureTables(env.DB);
      let stmt;
      if (["ko", "en", "ja"].includes(lang)) {
        stmt = env.DB.prepare(
          "SELECT email FROM subscribers WHERE unsubscribed = 0 AND confirmed = 1 " +
          "AND lang = ?1 ORDER BY email").bind(lang);
      } else {
        stmt = env.DB.prepare(
          "SELECT email FROM subscribers WHERE unsubscribed = 0 AND confirmed = 1 ORDER BY email");
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
      if (t !== expect) return page("Invalid link", "This unsubscribe link is not valid.");
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

    /* ---------- view: +1 per device (frontend dedupes) ----------
       v9.0: the frontend dedupe is a localStorage flag, i.e. advisory only.
       The shared per-IP throttle below is what actually bounds this, and the
       items.json existence check stops made-up ids from creating rows. */
    if (request.method === "POST" && url.pathname === "/view") {
      const body = (await request.json().catch(() => null)) || {};
      const pageId = String(body.pageId || "");
      await ensureTables(env.DB);
      if (!await counterOk(request, env, "view")) {
        return json({ error: "rate limited" }, 429, origin);
      }
      if (!await validPageId(env.DB, pageId, true)) return json({ error: "bad pageId" }, 400, origin);
      const ipH = await ipHash(request, env);
      const isNew = await viewIsNew(env.DB, pageId, ipH);
      const count = await bump(env.DB, "view", pageId, isNew ? 1 : 0);
      return json({ count }, 200, origin);
    }

    /* ---------- like: toggle ---------- */
    if (request.method === "POST" && url.pathname === "/like") {
      const body = (await request.json().catch(() => null)) || {};
      const pageId = String(body.pageId || "");
      await ensureTables(env.DB);
      if (!await counterOk(request, env, "like")) {
        return json({ error: "rate limited" }, 429, origin);
      }
      if (!await validPageId(env.DB, pageId, true)) return json({ error: "bad pageId" }, 400, origin);
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
      const body = (await request.json().catch(() => null)) || {};
      const pageId = String(body.pageId || "");
      await ensureTables(env.DB);
      if (!await counterOk(request, env)) {
        return json({ error: "rate limited" }, 429, origin);
      }
      if (!await validPageId(env.DB, pageId, true)) return json({ error: "bad pageId" }, 400, origin);
      const kindOf = d => d === "up" ? "vup" : d === "down" ? "vdown" : null;
      const nk = kindOf(body.dir);    // what they want now (null = cleared)

      /* v9.0: `body.prev` used to decide the decrement, which meant a caller
         could send prev:null with dir:"up" forever and add a vote every time.
         The previous state now comes from the votes table, not the browser. */
      const ipH = await ipHash(request, env);
      const voter = deviceKey(ipH, body.did);
      const row = await env.DB.prepare(
        "SELECT dir FROM votes WHERE page_id = ?1 AND voter = ?2").bind(pageId, voter).first();
      let pk = kindOf(row && row.dir);

      /* Migration window. The votes table starts empty, so every reader who
         voted before v9.0 looks new: flipping up->down would add to vdown
         without ever removing from vup, and clearing a vote would do nothing
         at all while the UI showed it drop. So the browser's `prev` is still
         honoured, but exactly once per (IP, article) and only while no server
         row exists. That is one possible bogus -1 per IP per article, against
         the unlimited inflation the old code allowed. */
      if (!row && kindOf(body.prev)) {
        const first = await rateOk(env.DB, "vmig:" + ipH + ":" + pageId, 1, 2592000);
        if (first) pk = kindOf(body.prev);
      }

      /* A fresh device id is free to mint, so cap how many distinct new voters
         one IP may register on one article per day. Without this a script can
         rotate `did` and stack votes up to the counter throttle. */
      if (!row && nk) {
        const okNew = await rateOk(
          env.DB, "vnew:" + ipH + ":" + pageId, VOTE_NEW_PER_IP_DAY, 86400);
        if (!okNew) {
          const u = await bump(env.DB, "vup", pageId, 0);
          const d = await bump(env.DB, "vdown", pageId, 0);
          return json({ data: { up: u, down: d } }, 200, origin);
        }
      }

      if (pk !== nk) {
        if (pk) await bump(env.DB, pk, pageId, -1);
        if (nk) await bump(env.DB, nk, pageId, 1);
        if (nk) {
          await env.DB.prepare(
            "INSERT INTO votes (page_id, voter, dir) VALUES (?1, ?2, ?3) " +
            "ON CONFLICT(page_id, voter) DO UPDATE SET dir = ?3, " +
            "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')")
            .bind(pageId, voter, body.dir === "up" ? "up" : "down").run();
        } else {
          await env.DB.prepare("DELETE FROM votes WHERE page_id = ?1 AND voter = ?2")
            .bind(pageId, voter).run();
        }
      }
      const up = await bump(env.DB, "vup", pageId, 0);     // delta 0 = read current
      const down = await bump(env.DB, "vdown", pageId, 0);
      return json({ data: { up, down } }, 200, origin);
    }

    /* ---------- clike: comment hearts ---------- */
    if (request.method === "POST" && url.pathname === "/clike") {
      const body = (await request.json().catch(() => null)) || {};
      const raw = String(body.commentId || "");
      if (!/^[0-9]{1,12}$/.test(raw)) return json({ error: "bad commentId" }, 400, origin);
      /* canonicalised: bump() keys on the string, so "7"/"07"/"007" would
         otherwise be three counter rows and two of them invisible to the
         comments JOIN, which CASTs the integer id back to text. */
      const cid = String(parseInt(raw, 10));
      await ensureTables(env.DB);
      if (!await counterOk(request, env)) {
        return json({ error: "rate limited" }, 429, origin);
      }
      /* the comment has to exist: without this, hearts can be parked on ids
         that were never written and the counters table grows on command */
      const exists = await env.DB.prepare("SELECT 1 AS x FROM comments WHERE id = ?1")
        .bind(parseInt(cid, 10)).first();
      if (!exists) return json({ error: "bad commentId" }, 400, origin);
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
      if (!PAGE_ID_RE.test(pageId)) return json({ error: "bad pageId" }, 400, origin);
      const { results } = await env.DB
        .prepare("SELECT c.id, c.nickname, c.content, c.created_at, c.edited_at, c.parent_id, " +
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
          createdAt: r.created_at,
          editedAt: r.edited_at || undefined
        }))
      }, 200, origin);
    }

    /* ---------- post (accepts parentId for replies) ---------- */
    if (request.method === "POST") {
      let body;
      try { body = await request.json(); }
      catch (e) { return json({ error: "bad json" }, 400, origin); }
      /* a body of literal `null` parses fine, so the catch never fires and
         every property read below would throw a 500 instead */
      if (!body || typeof body !== "object") {
        return json({ error: "bad json" }, 400, origin);
      }

      /* honeypot: real users never see or fill this field */
      if (body.website) return json({ ok: true }, 200, origin);

      /* ---------- own-comment edit / delete ----------
         The browser proves ownership by presenting the raw ownerToken whose
         SHA-256 was stored when the comment was created. No accounts, no IPs. */
      if (body.action === "edit" || body.action === "delete") {
        const cid = parseInt(body.id, 10);
        const token = String(body.ownerToken || "");
        if (!cid || !token) return json({ error: "missing fields" }, 400, origin);
        const row = await env.DB
          .prepare("SELECT owner_hash FROM comments WHERE id = ?1")
          .bind(cid).first();
        if (!row) return json({ error: "not found" }, 404, origin);
        const ok = row.owner_hash && safeEq(row.owner_hash, await sha256hex(token));
        if (!ok) return json({ error: "forbidden" }, 403, origin);
        if (body.action === "delete") {
          /* one level of replies: lift them to top-level so they stay visible */
          await env.DB.prepare("UPDATE comments SET parent_id = NULL WHERE parent_id = ?1").bind(cid).run();
          await env.DB.prepare("DELETE FROM comments WHERE id = ?1").bind(cid).run();
          return json({ ok: true }, 200, origin);
        }
        const content = String(body.content || "").slice(0, MAX_CONTENT).trim();
        if (!content) return json({ error: "missing fields" }, 400, origin);
        await env.DB
          .prepare("UPDATE comments SET content = ?1, edited_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?2")
          .bind(content, cid).run();
        return json({ ok: true }, 200, origin);
      }

      const pageId = String(body.pageId || "").slice(0, 100).trim();
      const nickname = String(body.nickname || "").slice(0, MAX_NICK).trim();
      const content = String(body.content || "").slice(0, MAX_CONTENT).trim();
      if (!pageId || !nickname || !content) {
        return json({ error: "missing fields" }, 400, origin);
      }
      /* v9.0: this route never applied PAGE_ID_RE, so any 100-char string
         could open a brand new comment thread nobody can reach from the site */
      if (!PAGE_ID_RE.test(pageId)) return json({ error: "bad pageId" }, 400, origin);

      /* replies: keep only a valid parent on the same page, one level deep */
      let parentId = parseInt(body.parentId, 10) || null;
      if (parentId) {
        const parent = await env.DB
          .prepare("SELECT page_id, parent_id FROM comments WHERE id = ?1")
          .bind(parentId).first();
        if (!parent || parent.page_id !== pageId || parent.parent_id) parentId = null;
      }

      const hash = await ipHash(request, env);
      const recent = await env.DB
        .prepare("SELECT COUNT(*) AS n FROM comments WHERE ip_hash = ?1 " +
                 "AND created_at > strftime('%Y-%m-%dT%H:%M:%SZ','now','-60 seconds')")
        .bind(hash).first();
      if (recent && recent.n >= RATE_LIMIT_PER_MIN) {
        return json({ error: "rate limited" }, 429, origin);
      }

      const ownerHash = body.ownerToken ? await sha256hex(String(body.ownerToken)) : null;
      const ins = await env.DB
        .prepare("INSERT INTO comments (page_id, nickname, content, ip_hash, parent_id, owner_hash) " +
                 "VALUES (?1, ?2, ?3, ?4, ?5, ?6)")
        .bind(pageId, nickname, content, hash, parentId, ownerHash).run();
      const newId = ins && ins.meta && ins.meta.last_row_id;
      return json({ ok: true, id: newId || undefined }, 200, origin);
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

  /* ---------- CRON: surge alerts ----------
     Cron Trigger: "0,5,10,15 23 * * 1-5", starting KST Tue-Sat 08:00.
     Each firing prices one shard of the followed companies into surge_scan;
     the run that completes the day's scan pushes the biggest movers
     (|change| >= 4%, at most SURGE_TOP_N per UTC day, deduped by surge_alerts)
     to their c_<slug> follow tags. Split because the Free plan caps one
     invocation at 50 subrequests while the full list needs 79 — see the
     SURGE_SHARDS comment for the measurements.

     The role comes from the firing's own minute: index = minute / 5, and an
     index at or past SURGE_SHARDS is the push-only sweeper. So growing to four
     shards is "add a minute to the cron and bump SURGE_SHARDS", and the last
     minute always stays the sweeper. A cron must never throw. */
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try {
        if (!env.DB || !env.ONESIGNAL_REST_KEY) return;
        const idx = Math.floor(new Date(event.scheduledTime).getUTCMinutes() / 5);
        await runSurgeShard(env, idx >= SURGE_SHARDS ? { sweep: true } : { shard: idx });
      } catch (e) { /* swallow: cron must never throw */ }
    })());
  }
};

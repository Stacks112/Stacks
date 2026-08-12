// Stacks investor YTD returns — daily precompute for the 13F investor hub,
// v2: headless-browser producer, NOT a Python reimplementation.
//
// WHY THIS EXISTS INSTEAD OF A PYTHON PORT (read before "optimizing" this
// back into one):
//
// The previous version of this file was scripts/investor_returns.py, a
// line-by-line JavaScript->Python port of index.html's
// invComputeHistoricalValueSeries / invComputeValueSeries / the YTD window
// slice in invPaintValueChart. It was carefully annotated, reviewed, and
// still drifted from the live compare screen's own "연중 수익률" number for
// 2 of the 16 investors in the roster — situational-awareness by 2.7pp and
// tiger-global by 1.0pp — for a reason that could not be pinned down by
// further code comparison (float edge cases in the quarter-chaining
// rescale loop, subtle fetch/ordering differences, or something else
// entirely; it was never isolated). Every other investor matched exactly.
//
// A hub column that is off by single-digit points of "pp" for a couple of
// names, in a way nobody can explain, is worse than useless — it is a
// second, silently-different definition of the same on-screen label. So
// instead of chasing the remaining drift in a reimplementation, this
// script now drives a real headless Chromium against the live site and
// calls the site's OWN window.invComputeValueSeries()/window.quote1y()
// functions directly. There is exactly one implementation of the YTD math
// in this project (index.html); this script is a caller of it, not a
// second copy of it. If invComputeValueSeries ever changes, this script
// picks up the change automatically — nothing here needs to be re-ported.
//
// portfolios.json only refreshes quarterly (13f-refresh.yml) and carries
// no market-price data at all, so it cannot back a daily-changing "YTD
// return" column on its own — that gap is what this script fills, once a
// day, by asking the live page to do the same computation it does for a
// human visitor and writing the result to data/investor-returns.json for
// the hub UI to read directly. It does not touch index.html or
// portfolios.json.
//
// Failure handling (ported in spirit, not in code, from the previous
// Python version — see its git history for the fuller reasoning this
// summarizes):
//   - One investor's computation failing (network hiccup, unexpected
//     shape, no priceable tickers) only blanks that investor; every other
//     investor is unaffected.
//   - A SMALL drop in "usable" investors (coverage dipping under
//     COVERAGE_THRESHOLD for one or two names on an ordinary day) is
//     written anyway, with those investors' ytd_pct: null — the UI already
//     renders that honestly next to the investor's coverage_pct.
//   - A drop bigger than REGRESSION_TOLERANCE, or the site/function not
//     being reachable/found at all, or fewer than MIN_INVESTORS_WITH_RESULT
//     investors resolving anything, is treated as systemic: refuse to
//     write, exit non-zero, and let yesterday's file stand.
//   - Every successful investor's YTD window must start on the SAME
//     calendar date (they all key off "Jan 1 of the year of the latest
//     shared trading day" the same way) — if they disagree, something is
//     structurally wrong with the run, so abort rather than publish a
//     column where each cell silently measures a different window.
//
// Note on eligible/priced holdings counts: window.invComputeValueSeries()
// does not itself return holding counts (only a weighted `coverage`
// fraction), so this script derives eligible/priced independently, but
// EXACTLY the way the frontend does it, not by approximation from the
// coverage weight:
//   eligible = rows in (all_holdings || holdings) of the investor's
//              CURRENT (latest) disclosed book where
//              change !== "exit" && put_call !== "PUT" && put_call !== "CALL"
//              (mirrors `currentRows` in invComputeHistoricalValueSeries,
//              index.html; no ticker requirement — an unpriceable
//              position still counts against eligibility/coverage).
//   priced   = of those, rows with a ticker AND a numeric `shares` count
//              AND for which window.quote1y(ticker) resolves to a series
//              with more than one point and no `.error` (the exact
//              condition invComputeHistoricalValueSeries/invComputeValueSeries
//              use to decide whether a ticker's quote is usable:
//              `r.q && r.q.t && r.q.t.length > 1`). Calling window.quote1y
//              directly for these tickers reuses the SAME in-page cache
//              invComputeValueSeries already populated, so this costs no
//              extra network round trips for tickers already fetched.
//
// This script is a build tool, not the ES5-constrained runtime code in
// assets/investor-compare.js — modern Node ESM (top-level await, optional
// chaining, etc.) is fine here.
//
// WHY IT SERVES THE REPO LOCALLY INSTEAD OF NAVIGATING TO THE PUBLIC SITE
// (read before "simplifying" this back to the live URL):
//
// The first deployed version of this script pointed straight at
// https://stacksdaily.com/ and its very first workflow_dispatch run failed
// at the readiness gate below, with this exact console output:
//
//   [info] navigating to https://stacksdaily.com/
//   [fail] window.invComputeValueSeries/window.quote1y did not appear within
//   60000ms - site may be down or restructured; refusing to write
//   .../data/investor-returns.json
//
// The gate did exactly its job (nothing was written, a failure issue was
// opened) — but the site was NOT actually down: both globals are present
// within a few seconds in an ordinary desktop browser hitting the same URL.
// Something about headless Chromium reaching the public origin specifically
// (bot/challenge behaviour, edge/CDN quirk, the site's own service worker
// racing first paint — never root-caused) breaks it. Rather than chase that
// through a black-box public edge, this script now serves the repo checkout
// itself on localhost — the exact same `python3 -m http.server` pattern
// playwright.config.mjs already uses for the regression tests in this repo,
// which is proven to work in this repo's CI — and points the browser at
// that instead. This is strictly better, not just a workaround: the
// producer then computes against the code actually at HEAD rather than
// whatever happens to be deployed, and it has zero dependency on the public
// site being reachable from a runner at all. STACKS_SITE_URL (below) exists
// purely so a human can point this at the live site for debugging; it is
// not meant to be set in CI.

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { chromium } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const OUTPUT_PATH = path.join(ROOT, "data", "investor-returns.json");

// Debug escape hatch only — see the file-header comment above for why the
// normal path serves the repo locally instead. Set STACKS_SITE_URL to point
// this script at a live/staging origin by hand; when it is set, the local
// `python3 -m http.server` below is never spawned.
const STACKS_SITE_URL = process.env.STACKS_SITE_URL || null;
// Deliberately NOT 4173: playwright.config.mjs's own webServer (used by the
// regression tests in tests/) listens on 4173, and a developer running both
// that test suite and this script at once should not collide on the same
// port. Overridable via STACKS_SITE_PORT for anyone who needs a specific
// port anyway. If a server is already answering on this port (e.g. this
// script running twice, or a human's own `python3 -m http.server` left up
// for debugging), that server is reused rather than spawning a second one —
// mirroring playwright's own `reuseExistingServer` behaviour.
const LOCAL_SERVER_PORT = Number(process.env.STACKS_SITE_PORT) || 4174;
const LOCAL_SERVER_URL = `http://127.0.0.1:${LOCAL_SERVER_PORT}/`;
const SITE_URL = STACKS_SITE_URL || LOCAL_SERVER_URL;
const READY_TIMEOUT_MS = 60_000; // window.invComputeValueSeries/window.quote1y must appear within this
const NAV_TIMEOUT_MS = 45_000;
const LOCAL_SERVER_STARTUP_TIMEOUT_MS = 15_000;

// Same constants/intent as the retired scripts/investor_returns.py — see
// that file's git history for the full reasoning; summarized above.
export const COVERAGE_THRESHOLD = 0.90;
export const REGRESSION_TOLERANCE = 2;
export const MIN_INVESTORS_WITH_RESULT = 10;

// --------------------------------------------------------------------------
// Quote host — see the page.route block below for the CORS-workaround
// backstory this builds on. CI run #5 showed that backstory was incomplete:
// the public host (api.stacksdaily.com) 403s every proxied request from
// this runner - and from a second datacenter IP - even with Origin/Referer
// spoofed to the real site, while an ordinary desktop browser hitting the
// same URL gets 200. The public endpoint is blocking non-browser/datacenter
// traffic outright; no header spoofing from here fixes that.
//
// The retired scripts/investor_returns.py (see scripts/worker_url.py in its
// git history, e.g. `git show 6b5ab3a11:scripts/worker_url.py`) already
// solved this once: it read a private/allow-listed Cloudflare Worker URL
// from the repo secret STACKS_WORKER_URL, defaulting to the same public
// https://api.stacksdaily.com host when the secret was unset, and built
// each request as `${WORKER}/quote?s=<ticker>&r=1y` - i.e. the secret is a
// bare origin (or origin + path prefix), and the script appends the
// path/query it already had. This mirrors that: when STACKS_WORKER_URL is
// set, every request the page makes to api.stacksdaily.com is rewritten to
// that base, preserving the page's own path and query string exactly.
const STACKS_WORKER_URL = (process.env.STACKS_WORKER_URL || "").trim();
const WORKER_BASE = STACKS_WORKER_URL.replace(/\/+$/, "");

// The retired scripts/investor_returns.py succeeded against this same
// private Worker sending only a minimal header set - User-Agent and
// Accept-Encoding: identity, no Origin/Referer/Sec-Fetch-*/cookies (see
// `git show 6b5ab3a11:scripts/investor_returns.py`). When WORKER_BASE is
// set we mirror that exactly below, since forwarding the page's full
// browser header set (including a spoofed Origin/Referer) is the leading
// suspect for CI run #6's "proxied=899 rewritten=899 non2xx=899" against
// the private Worker.
const WORKER_PROXY_UA = "Stacks/1.0 (stacksdaily.com; investor-returns; contact@stacksdaily.com)";

/** Best-effort "does this look like it embeds a credential rather than
 * being a bare host" check, so the startup log below never risks printing a
 * token even by accident. Deliberately conservative: any userinfo, path
 * beyond "/", or query string on the secret trips it, since a bare worker
 * base (matching how scripts/worker_url.py used this same secret) should
 * never have any of those. */
function workerUrlLooksLikeCredential(raw) {
  try {
    const u = new URL(raw);
    return Boolean(u.username || u.password || u.search || (u.pathname && u.pathname !== "/"));
  } catch {
    return true; // unparseable - can't prove it's safe, so treat it as unsafe
  }
}

/** Logs, once, which quote host this run will use - origin only (scheme +
 * host), never the full STACKS_WORKER_URL (which may carry a path/token).
 * See workerUrlLooksLikeCredential above for when even the origin is
 * withheld. */
function logQuoteHost() {
  if (!WORKER_BASE) {
    console.log(`[info] quote host: https://api.stacksdaily.com (default; STACKS_WORKER_URL not set)`);
    return;
  }
  if (workerUrlLooksLikeCredential(WORKER_BASE)) {
    console.log(`[info] quote host: <redacted, from STACKS_WORKER_URL>`);
    return;
  }
  console.log(`[info] quote host: ${new URL(WORKER_BASE).origin} (from STACKS_WORKER_URL)`);
}

// --------------------------------------------------------------------------
// Pure helpers — no browser, no network. Unit-testable via dynamic import.
// --------------------------------------------------------------------------

/** Mirrors invPaintValueChart's ceiling search (index.html):
 *    var startIdx = 0;
 *    while (startIdx < calendar.length - 1 && calendar[startIdx] < requestedStart) startIdx++;
 * calendar entries are epoch seconds (numbers). */
export function ytdStartIndex(calendar, requestedStartEpoch) {
  let i = 0;
  while (i < calendar.length - 1 && calendar[i] < requestedStartEpoch) i++;
  return i;
}

/** UTC calendar date (YYYY-MM-DD) of an epoch-seconds timestamp. */
export function isoDateUTC(epochSeconds) {
  return new Date(epochSeconds * 1000).toISOString().slice(0, 10);
}

/** Same rounding the retired Python version used: 4 decimal places on the
 * fraction (e.g. 0.0902 == +9.02%). */
export function round4(x) {
  return x === null || x === undefined ? null : Math.round(x * 10000) / 10000;
}

/** Count investors with a non-null ytd_pct in the {slug: {...}} map. */
export function usableCount(investorsMap) {
  return Object.values(investorsMap || {}).filter(
    (v) => v && v.ytd_pct !== null && v.ytd_pct !== undefined
  ).length;
}

/** COVERAGE_THRESHOLD gate: below it, null out ytd_pct but keep coverage_pct
 * so the UI can explain why. Applied identically regardless of how the raw
 * result was produced. */
export function applyCoverageGate(result) {
  if (result.ytd_pct !== null && result.coverage_pct < COVERAGE_THRESHOLD) {
    return { ...result, ytd_pct: null };
  }
  return result;
}

/** Regression guard: refuse to publish if usable count fell by more than
 * REGRESSION_TOLERANCE vs. the previously written file. `prevUsable` is
 * null when there is no previous file (first run — never a regression). */
export function checkRegression(newUsable, prevUsable) {
  if (prevUsable === null || prevUsable === undefined) return { ok: true, warn: false };
  if (newUsable < prevUsable - REGRESSION_TOLERANCE) {
    return {
      ok: false,
      message:
        `systemic regression: usable count dropped from ${prevUsable} to ${newUsable} ` +
        `(more than the ${REGRESSION_TOLERANCE}-investor tolerance) - refusing to overwrite ` +
        `${OUTPUT_PATH} (previous file kept)`,
    };
  }
  return {
    ok: true,
    warn: newUsable < prevUsable,
    message:
      newUsable < prevUsable
        ? `usable count dipped from ${prevUsable} to ${newUsable} (within the ` +
          `${REGRESSION_TOLERANCE}-investor tolerance) - writing anyway, affected investors show ytd_pct: null`
        : null,
  };
}

/** Format "now" as an ISO-8601 UTC timestamp with a "+00:00" offset (rather
 * than "Z") and 6 fractional digits, matching the shape the retired Python
 * version's datetime.now(timezone.utc).isoformat() produced (e.g.
 * "2026-08-12T07:28:29.296472+00:00"). Node's Date only carries millisecond
 * precision, so the last 3 digits are zero-padded rather than genuine
 * microseconds — the FORMAT matches exactly, the precision does not (see
 * report for this caveat). */
export function nowIsoUtcMicros(date = new Date()) {
  const iso = date.toISOString(); // e.g. 2026-08-12T07:28:29.296Z
  const [head, msZ] = iso.split(".");
  const ms = msZ.slice(0, 3);
  return `${head}.${ms}000+00:00`;
}

async function loadJson(filePath, fallback) {
  try {
    return JSON.parse(await fs.readFile(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

// --------------------------------------------------------------------------
// In-page computation. Runs inside the live site via page.evaluate() so it
// calls the site's OWN window.invComputeValueSeries()/window.quote1y() —
// see the file-level comment for why this is deliberate.
// --------------------------------------------------------------------------

/**
 * Runs in the browser page context for a single investor. `inv` is the raw
 * investor object out of /portfolios.json (must be JSON-serializable to
 * cross the page.evaluate boundary). Returns a plain, JSON-serializable
 * result object; never throws across the boundary (network/shape errors
 * are caught and reported as { ok:false, reason }).
 */
/* eslint-disable no-undef -- this function body executes inside the page */
async function computeInvestorInPage(inv) {
  try {
    const res = await window.invComputeValueSeries(inv);
    if (!res || !res.calendar || !res.values || res.calendar.length < 2) {
      return { ok: false, reason: "no usable calendar/values from invComputeValueSeries" };
    }
    const calendar = res.calendar;
    const values = res.values;

    // Mirror invPaintValueChart's ytd branch exactly (index.html):
    //   var end = calendar[calendar.length - 1], endDate = new Date(end * 1000);
    //   requestedStart = Date.UTC(endDate.getUTCFullYear(), 0, 1) / 1000;
    //   var startIdx = 0;
    //   while (startIdx < calendar.length - 1 && calendar[startIdx] < requestedStart) startIdx++;
    const endEpoch = calendar[calendar.length - 1];
    const endYear = new Date(endEpoch * 1000).getUTCFullYear();
    const requestedStart = Date.UTC(endYear, 0, 1) / 1000;
    let startIdx = 0;
    while (startIdx < calendar.length - 1 && calendar[startIdx] < requestedStart) startIdx++;

    const startVal = values[startIdx];
    const endVal = values[values.length - 1];
    if (!(typeof startVal === "number" && startVal > 0)) {
      return { ok: false, reason: "ytd start value is not usable (<=0 or missing)" };
    }
    const ytd_pct = endVal / startVal - 1;
    const ytd_start_epoch = calendar[startIdx];
    const coverage_pct = typeof res.coverage === "number" ? res.coverage : 0;

    // eligible/priced from the CURRENT book — see file header for the exact
    // rule this mirrors (currentRows in invComputeHistoricalValueSeries /
    // rawTotal's skip condition).
    const source = (inv && (inv.all_holdings || inv.holdings)) || [];
    const reals = source.filter(
      (h) => h && h.change !== "exit" && h.put_call !== "PUT" && h.put_call !== "CALL"
    );
    const priceableCandidates = reals.filter(
      (h) => h && h.ticker && typeof h.shares === "number"
    );
    const tickers = Array.from(new Set(priceableCandidates.map((h) => h.ticker)));
    const checks = await Promise.all(
      tickers.map(async (t) => {
        try {
          const q = await window.quote1y(t);
          const usable = !!(q && !q.error && q.t && q.t.length > 1);
          return [t, usable];
        } catch {
          return [t, false];
        }
      })
    );
    const pricedTickers = new Set(checks.filter(([, ok]) => ok).map(([t]) => t));
    const priced_holdings = priceableCandidates.filter((h) => pricedTickers.has(h.ticker)).length;
    const eligible_holdings = reals.length;

    return {
      ok: true,
      ytd_pct,
      coverage_pct,
      ytd_start_epoch,
      priced_holdings,
      eligible_holdings,
    };
  } catch (e) {
    return { ok: false, reason: String((e && e.message) || e) };
  }
}
/* eslint-enable no-undef */

// --------------------------------------------------------------------------
// Local static server for the repo checkout (see the file-header comment
// for why this script serves the repo instead of navigating to the public
// site). Mirrors playwright.config.mjs's webServer: same command, same
// "reuse if already answering" behaviour.
// --------------------------------------------------------------------------

/** True if something is already answering HTTP on `url` (any status code
 * counts - we only care whether a server is listening, not what it serves). */
async function serverIsUp(url) {
  try {
    const res = await fetch(url, { method: "GET" });
    void res;
    return true;
  } catch {
    return false;
  }
}

async function waitForServer(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await serverIsUp(url)) return true;
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
}

/** Spawns `python3 -m http.server <port> --bind 127.0.0.1` with cwd=ROOT so
 * it serves the repo checkout (index.html, portfolios.json, assets/, etc.)
 * exactly the way playwright.config.mjs's webServer does for the regression
 * tests. Reuses an already-answering server on the same port instead of
 * spawning a second one. Returns { proc, url } - `proc` is null when an
 * existing server was reused (nothing for this script to own/kill). Throws
 * if a freshly spawned server never answers within
 * LOCAL_SERVER_STARTUP_TIMEOUT_MS (and kills the child before throwing, so
 * nothing is left running on that path either).
 */
async function startLocalServer() {
  if (await serverIsUp(LOCAL_SERVER_URL)) {
    console.log(`[info] reusing server already answering on ${LOCAL_SERVER_URL}`);
    return { proc: null, url: LOCAL_SERVER_URL };
  }
  console.log(
    `[info] starting local server: python3 -m http.server ${LOCAL_SERVER_PORT} --bind 127.0.0.1 (cwd=${ROOT})`
  );
  const proc = spawn(
    "python3",
    ["-m", "http.server", String(LOCAL_SERVER_PORT), "--bind", "127.0.0.1"],
    { cwd: ROOT, stdio: ["ignore", "ignore", "ignore"] }
  );
  let spawnError = null;
  proc.on("error", (e) => {
    spawnError = e;
  });
  const up = await waitForServer(LOCAL_SERVER_URL, LOCAL_SERVER_STARTUP_TIMEOUT_MS);
  if (!up) {
    proc.kill();
    const reason = spawnError ? `: ${spawnError.message}` : "";
    throw new Error(
      `local http.server did not answer on ${LOCAL_SERVER_URL} within ${LOCAL_SERVER_STARTUP_TIMEOUT_MS}ms${reason}`
    );
  }
  return { proc, url: LOCAL_SERVER_URL };
}

/** Kills the child process from startLocalServer, if this run owns one
 * (reused servers - proc:null - are left alone, they were not ours to
 * manage). Safe to call more than once / on an already-exited process. */
function stopLocalServer(localServer) {
  if (localServer && localServer.proc && !localServer.proc.killed) {
    localServer.proc.kill();
  }
}

// --------------------------------------------------------------------------
// main
// --------------------------------------------------------------------------

async function main() {
  logQuoteHost();

  const prev = await loadJson(OUTPUT_PATH, null);
  const prevUsable = prev ? usableCount(prev.investors) : null;

  // usingLocalServer/localServer are read/set in the outer finally below to
  // guarantee the spawned `python3 -m http.server` child never survives this
  // function on ANY exit path - normal return, an early `return` on a gate
  // failure, or an uncaught throw. See startLocalServer/stopLocalServer and
  // the file-header comment for why this script serves the repo locally at
  // all instead of navigating to the public site.
  const usingLocalServer = !STACKS_SITE_URL;
  let localServer = null;

  try {
    if (usingLocalServer) {
      localServer = await startLocalServer();
    }

    const browser = await chromium.launch({ headless: true });
    // NOTE: process.exitCode is set directly at each failure point below,
    // not via a local variable read after the try/finally - a `return`
    // inside `try` runs `finally` and then exits the function immediately,
    // so any statement placed after the try/finally block would never run
    // on those paths. Setting process.exitCode inline avoids that trap.
    try {
      // serviceWorkers: "block" - the site registers a service worker and
      // it must not interfere here (same setting playwright.config.mjs uses
      // for the regression tests, for the same reason).
      const context = await browser.newContext({ serviceWorkers: "block" });
      const page = await context.newPage();
      page.setDefaultTimeout(NAV_TIMEOUT_MS);

      // --------------------------------------------------------------------
      // Diagnostics (permanent - not tied to the CORS workaround below).
      // Without these, a run that silently returns "no result" for every
      // investor gives no clue why: the in-page try/catch in
      // computeInvestorInPage() swallows fetch failures into a generic
      // reason string, and nothing before this surfaced the page's own
      // console output or its failed network requests. Cap both so a
      // genuinely noisy page can't flood the CI log.
      // --------------------------------------------------------------------
      let pageConsoleLogged = 0;
      const PAGE_CONSOLE_LOG_CAP = 20;
      page.on("console", (msg) => {
        const type = msg.type();
        if (type !== "error" && type !== "warning") return;
        if (pageConsoleLogged >= PAGE_CONSOLE_LOG_CAP) return;
        pageConsoleLogged++;
        console.log(`[page] ${type}: ${msg.text()}`);
      });

      let reqFailLogged = 0;
      const REQFAIL_LOG_CAP = 10;
      page.on("requestfailed", (request) => {
        if (reqFailLogged >= REQFAIL_LOG_CAP) return;
        reqFailLogged++;
        const failure = request.failure();
        console.log(
          `[reqfail] ${request.method()} ${request.url()} ${failure ? failure.errorText : "unknown"}`
        );
      });

      // --------------------------------------------------------------------
      // Originally a hypothesis (this sandbox had no egress to
      // api.stacksdaily.com to test it against) - see CI run #4, where the
      // producer correctly finds window.invComputeValueSeries on the
      // locally-served page but every single investor still comes back
      // "[warn] <slug>: no result (no usable calendar/values from
      // invComputeValueSeries)". window.quote1y() (index.html) fetches
      // COMMENTS_API + "/quote?s=<ticker>&r=1y", i.e.
      // https://api.stacksdaily.com/quote - a real cross-origin request once
      // the page is served from http://127.0.0.1:4174 instead of
      // https://stacksdaily.com. The likely explanation was that the
      // Cloudflare Worker behind api.stacksdaily.com only allow-lists the
      // real site origin in its CORS response, so the browser discards every
      // quote response before invComputeValueSeries ever sees a usable
      // series - which matched the symptom exactly (found the function, got
      // nothing usable out of it).
      //
      // Confirmed and refined by CI run #5: intercepting every request to
      // that host, re-issuing it server-side (outside the page's CORS jail)
      // with an Origin/Referer that impersonates the real site, is not
      // enough on its own - the public host now 403s the re-issued request
      // too, from two different datacenter IPs, even with those headers
      // spoofed, while an ordinary desktop browser hitting the exact same
      // URL gets 200. So this isn't (only) a CORS allow-list problem; the
      // public endpoint itself blocks non-browser/datacenter traffic. See
      // STACKS_WORKER_URL above: when it's set, the rewritten request goes
      // to that private/allow-listed base instead of api.stacksdaily.com,
      // which is exactly what the retired scripts/investor_returns.py did
      // (see scripts/worker_url.py in its git history) and is why that
      // secret is back in .github/workflows/investor-returns.yml. When it's
      // unset, this falls back to the original same-host/spoofed-headers
      // behaviour so a local human run is unchanged.
      let quoteProxied = 0;
      let quoteRewritten = 0;
      let quoteNonOk = 0;
      let quoteThrew = 0;
      let firstNonOkLogged = false;
      await page.route(
        (url) => url.hostname === "api.stacksdaily.com",
        async (route) => {
          quoteProxied++;
          const request = route.request();
          try {
            let fetchOptions;
            if (WORKER_BASE) {
              // Preserve the path + query string exactly as the page built
              // it (e.g. "/quote?s=AAPL&r=1y"); only the scheme+host changes.
              // Send only the minimal header set the retired python producer
              // used against this same private Worker - no Origin, Referer,
              // Sec-Fetch-*, or cookies forwarded from the page.
              const original = new URL(request.url());
              fetchOptions = {
                url: `${WORKER_BASE}${original.pathname}${original.search}`,
                headers: {
                  "user-agent": WORKER_PROXY_UA,
                  "accept-encoding": "identity",
                },
              };
              quoteRewritten++;
            } else {
              fetchOptions = {
                headers: {
                  ...request.headers(),
                  origin: "https://stacksdaily.com",
                  referer: "https://stacksdaily.com/",
                },
              };
            }
            const response = await route.fetch(fetchOptions);
            if (!response.ok()) {
              quoteNonOk++;
              if (!firstNonOkLogged) {
                firstNonOkLogged = true;
                const respHeaders = response.headers();
                const hasContentType = Boolean(respHeaders && respHeaders["content-type"]);
                console.log(
                  `[warn] first non-2xx quote proxy response: status=${response.status()} ` +
                    `content-type-present=${hasContentType}`
                );
              }
            }
            const headers = { ...response.headers(), "access-control-allow-origin": "*" };
            delete headers["access-control-allow-credentials"];
            await route.fulfill({ response, headers });
          } catch (e) {
            quoteThrew++;
            await route.abort();
          }
        }
      );
      const quoteProxySummary = () =>
        `quote proxy (api.stacksdaily.com): proxied=${quoteProxied} rewritten=${quoteRewritten} ` +
        `non2xx=${quoteNonOk} threw=${quoteThrew}`;

      console.log(`[info] navigating to ${SITE_URL}`);
      await page.goto(SITE_URL, { waitUntil: "domcontentloaded", timeout: NAV_TIMEOUT_MS });

      try {
        await page.waitForFunction(
          () =>
            typeof window.invComputeValueSeries === "function" &&
            typeof window.quote1y === "function",
          { timeout: READY_TIMEOUT_MS }
        );
      } catch {
        console.error(
          `[fail] window.invComputeValueSeries/window.quote1y did not appear within ${READY_TIMEOUT_MS}ms - ` +
            `site may be down or restructured; refusing to write ${OUTPUT_PATH}`
        );
        process.exitCode = 1;
        return;
      }

      const portfolios = await page.evaluate(async () => {
        const r = await fetch("/portfolios.json");
        if (!r.ok) throw new Error(`portfolios.json fetch failed: HTTP ${r.status}`);
        return r.json();
      });
      const investors = (portfolios && portfolios.investors) || [];
      if (!investors.length) {
        console.error("[fail] /portfolios.json has no investors - nothing to do");
        process.exitCode = 1;
        return;
      }
      console.log(`[info] investors=${investors.length}`);

      const perInvestor = {}; // slug -> in-page result (ok:true|false)
      for (const inv of investors) {
        const slug = inv.slug;
        let result;
        try {
          result = await page.evaluate(computeInvestorInPage, inv);
        } catch (e) {
          result = { ok: false, reason: `page.evaluate threw: ${(e && e.message) || e}` };
        }
        perInvestor[slug] = result;
        if (result.ok) {
          console.log(
            `[ok] ${slug}: ytd=${(result.ytd_pct * 100).toFixed(2)}% coverage=${(result.coverage_pct * 100).toFixed(1)}% ` +
              `priced=${result.priced_holdings}/${result.eligible_holdings}`
          );
        } else {
          console.log(`[warn] ${slug}: no result (${result.reason})`);
        }
      }

      console.log(`[info] ${quoteProxySummary()}`);

      const successful = Object.entries(perInvestor).filter(([, r]) => r.ok);
      if (successful.length < MIN_INVESTORS_WITH_RESULT) {
        console.error(
          `[fail] only ${successful.length}/${investors.length} investors produced any result ` +
            `(minimum ${MIN_INVESTORS_WITH_RESULT}) - refusing to write ${OUTPUT_PATH}\n` +
            `[fail] ${quoteProxySummary()}`
        );
        process.exitCode = 1;
        return;
      }

      // Every successful investor must resolve to the SAME ytd_start date -
      // see file header. Disagreement means something structural is wrong
      // (e.g. different investors landing on different "latest calendar
      // point" years), not ordinary per-investor noise.
      const startDatesBySlug = {};
      for (const [slug, r] of successful) {
        startDatesBySlug[slug] = isoDateUTC(r.ytd_start_epoch);
      }
      const distinctDates = Array.from(new Set(Object.values(startDatesBySlug)));
      if (distinctDates.length > 1) {
        console.error(
          `[fail] investors disagree on ytd_start date - refusing to write ${OUTPUT_PATH}:\n` +
            JSON.stringify(startDatesBySlug, null, 1)
        );
        process.exitCode = 1;
        return;
      }
      const ytdStart = distinctDates[0];

      const newInvestors = {};
      const gated = {};
      for (const [slug, r] of Object.entries(perInvestor)) {
        if (!r.ok) continue; // per-investor failure -> omit (UI treats missing as no-data)
        const raw = {
          ytd_pct: round4(r.ytd_pct),
          coverage_pct: round4(r.coverage_pct),
          priced_holdings: r.priced_holdings,
          eligible_holdings: r.eligible_holdings,
        };
        const withGate = applyCoverageGate(raw);
        gated[slug] = withGate.ytd_pct === null && raw.ytd_pct !== null;
        newInvestors[slug] = withGate;
      }

      const newUsable = usableCount(newInvestors);
      console.log(`[info] usable ytd_pct count: new=${newUsable} previous=${prevUsable === null ? "n/a" : prevUsable}`);

      const regression = checkRegression(newUsable, prevUsable);
      if (!regression.ok) {
        console.error(`::error::investor-returns ${regression.message}`);
        process.exitCode = 1;
        return;
      }
      if (regression.warn && regression.message) {
        console.warn(`::warning::investor-returns: ${regression.message}`);
      }

      const out = {
        as_of: nowIsoUtcMicros(),
        ytd_start: ytdStart,
        investors: newInvestors,
      };

      await fs.mkdir(path.dirname(OUTPUT_PATH), { recursive: true });
      await fs.writeFile(OUTPUT_PATH, JSON.stringify(out, null, 1) + "\n", "utf8");
      console.log(`[info] wrote ${OUTPUT_PATH}`);

      console.log("\nslug,ytd_pct,coverage_pct,gated");
      for (const [slug, r] of Object.entries(newInvestors)) {
        const ytd = r.ytd_pct === null ? "null" : (r.ytd_pct * 100).toFixed(2) + "%";
        const cov = (r.coverage_pct * 100).toFixed(1) + "%";
        console.log(`${slug},${ytd},${cov},${gated[slug] ? "yes" : "no"}`);
      }
    } finally {
      await browser.close();
    }
  } finally {
    stopLocalServer(localServer);
  }
}

const isDirectRun = (() => {
  const entry = process.argv[1];
  if (!entry) return false;
  try {
    return fileURLToPath(import.meta.url) === path.resolve(entry);
  } catch {
    return false;
  }
})();

if (isDirectRun) {
  main().catch((e) => {
    console.error("[fail] uncaught error:", e);
    process.exitCode = 1;
  });
}

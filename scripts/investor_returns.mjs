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

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const OUTPUT_PATH = path.join(ROOT, "data", "investor-returns.json");

const SITE_URL = "https://stacksdaily.com/";
const READY_TIMEOUT_MS = 60_000; // window.invComputeValueSeries/window.quote1y must appear within this
const NAV_TIMEOUT_MS = 45_000;

// Same constants/intent as the retired scripts/investor_returns.py — see
// that file's git history for the full reasoning; summarized above.
export const COVERAGE_THRESHOLD = 0.90;
export const REGRESSION_TOLERANCE = 2;
export const MIN_INVESTORS_WITH_RESULT = 10;

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
// main
// --------------------------------------------------------------------------

async function main() {
  const prev = await loadJson(OUTPUT_PATH, null);
  const prevUsable = prev ? usableCount(prev.investors) : null;

  const browser = await chromium.launch({ headless: true });
  // NOTE: process.exitCode is set directly at each failure point below,
  // not via a local variable read after the try/finally - a `return`
  // inside `try` runs `finally` and then exits the function immediately,
  // so any statement placed after the try/finally block would never run
  // on those paths. Setting process.exitCode inline avoids that trap.
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(NAV_TIMEOUT_MS);
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

    const successful = Object.entries(perInvestor).filter(([, r]) => r.ok);
    if (successful.length < MIN_INVESTORS_WITH_RESULT) {
      console.error(
        `[fail] only ${successful.length}/${investors.length} investors produced any result ` +
          `(minimum ${MIN_INVESTORS_WITH_RESULT}) - refusing to write ${OUTPUT_PATH}`
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

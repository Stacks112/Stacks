"""Stacks investor YTD returns — daily precompute for the 13F investor hub.

portfolios.json only refreshes quarterly (13f-refresh.yml, cron
"0 22 8-19 2,5,8,11 *" — Feb/May/Aug/Nov only) and carries no market-price
data at all, so it cannot back a daily-changing "YTD return" column on its
own. This script fills that gap: once a day it prices each investor's
*current* 13F holdings against live quotes and writes a small summary,
data/investor-returns.json, for the hub UI to read directly. It does not
touch index.html or any other UI file.

Eligibility rule — copied verbatim from the compare screen's
invComputeValueSeries() (index.html, ~line 7130-7141), NOT reinvented:

    sourceHoldings = inv.all_holdings || inv.holdings || []
    reals    = sourceHoldings.filter(h => h.change !== "exit"
                                        && h.put_call !== "PUT"
                                        && h.put_call !== "CALL")
    eligible = reals.filter(h => h.ticker)

See eligible_holdings() below for the direct Python port.

Price source — the repo's own Cloudflare Worker, same one the frontend
calls (COMMENTS_API in index.html, resolved here via scripts/worker_url.py,
which normalizes to the canonical https://api.stacksdaily.com):

    GET {worker}/quote?s=<ticker>&r=1y  ->  {t: [epoch...], closes: [...], dates: [...]}

One ticker per request (the worker's `s` sanitizer strips commas, so
batching is not possible — see worker/index.js). Tickers are deduplicated
across all 16 investors first, so each ticker is fetched at most once per
run, then fetched with a small thread pool (see CONCURRENCY below).

YTD math, per investor, over only the *priced* eligible holdings:

    value(t)  = sum(shares * close_at_or_before(t))   for each priced holding
    ytd_pct   = value(latest) / value(first trading day on/after Jan 1) - 1

"latest"/"first trading day" both come off ONE canonical daily calendar (the
longest series among everything fetched this run) rather than a
per-investor calendar. Because every 13F holding is, by definition, a
US-listed reportable security (fetch_13f.py's normalize_ticker() always
appends ".us"), every ticker here trades on the same NYSE/NASDAQ calendar,
so a single shared calendar and a per-investor "pick the longest series I
hold" calendar (what the frontend actually does) agree on every trading
date in practice. This keeps `ytd_start` a single, reportable top-level
field instead of 16 slightly different ones.

Coverage gate — coverage_pct is the fraction of an investor's ELIGIBLE 13F
`value` (the dollar amount from the filing, summed over the same eligible
list above) whose ticker produced a usable price series this run. If
coverage_pct is below COVERAGE_THRESHOLD, ytd_pct is set to null (not 0, not
omitted) so the UI can render "insufficient data" instead of a misleading
number computed from a fraction of the real portfolio. See COVERAGE_THRESHOLD
below for the number and why.

Failure handling, matching fetch_13f.py's philosophy (one bad ticker must
not take down the run) plus one addition this file specifically needs
(silently blanking a previously-good column is worse than doing nothing):

  - One ticker's /quote request failing (timeout, HTTP error, no data) only
    drops that ticker; every other ticker and every other investor are
    unaffected. Failed tickers are logged with a reason.
  - If a run raises an uncaught exception, nothing is written — the
    existing data/investor-returns.json (whatever the workflow checked out)
    stays exactly as it was, so `git diff` sees no change and the calling
    workflow's "commit only if changed" step naturally does not commit.
  - A SMALL drop in usable investors (coverage_pct dipping under
    COVERAGE_THRESHOLD for one or two names - e.g. one ticker the Worker/
    Yahoo temporarily has no chart for) is normal day-to-day noise, not a
    pipeline failure: it blanks one or two cells to null, which the UI
    already renders honestly as "no data" alongside that investor's
    coverage_pct. The file IS written in this case (with those investors'
    ytd_pct: null), a warning is logged, and the run exits 0. Refusing to
    write over a single flaky ticker would wedge the whole daily pipeline
    and (via the calling workflow's failure() step) open a fresh GitHub
    issue every single day forever - worse than the one blank cell it was
    trying to prevent.
  - Only a SYSTEMIC drop - usable count falling by more than
    REGRESSION_TOLERANCE investors versus the previously written file - is
    treated as the "do not touch the file" case: log the regression
    loudly, do NOT write, and exit non-zero, so a stale "yesterday" file
    (via the calling workflow's "commit only if changed" step never
    running) beats today's, largely-blanked one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import worker_url  # noqa: E402 - needs sys.path tweak above

PORTFOLIOS_PATH = os.path.join(ROOT, "portfolios.json")
OUTPUT_PATH = os.path.join(ROOT, "data", "investor-returns.json")

WORKER = worker_url.worker_base()
UA = "Stacks/1.0 (stacksdaily.com; investor-returns; contact@stacksdaily.com)"

# Modest concurrency for a batch job hitting our own edge-cached Worker (not
# Yahoo directly). The frontend itself runs 5-way concurrent (invMapLimit(...,
# 5, ...)) against the same endpoint for a single investor's holdings; this
# run fans out across the whole 16-investor roster's unique tickers in one
# go, so a slightly higher pool (8) trades a bit more parallel load for a
# materially shorter wall-clock run, while staying well short of anything
# that would look like abuse to Yahoo behind the Worker.
CONCURRENCY = 8
REQUEST_TIMEOUT = 15  # seconds, per HTTP attempt
MAX_RETRIES = 3
RETRY_BASE_SLEEP = 1.5  # seconds; attempt N sleeps RETRY_BASE_SLEEP * N

# Below this fraction of an investor's eligible 13F `value` priced, the YTD
# number would be computed from too small a slice of the real portfolio to
# be worth showing as a number - report coverage (so the UI can say "partial
# data") but null out ytd_pct rather than publish something misleading.
# Chosen at 0.90: a single very large, unpriceable position (e.g. an OTC or
# newly-listed ticker the Worker/Yahoo has no chart for) can easily account
# for 5-10% of one investor's book without being unusual, so a much stricter
# gate (e.g. 0.99) would flip that investor to "no data" on ordinary market
# noise. Below 90% priced, more than a tenth of the book is invisible to the
# math, which is large enough that a misleading ytd_pct is a real risk.
COVERAGE_THRESHOLD = 0.90

# How many FEWER usable investors than the previously written file counts as
# a "systemic" regression worth refusing to write over (see module
# docstring). One or two investors dipping under COVERAGE_THRESHOLD on a
# given day is ordinary noise (a single ticker the Worker/Yahoo temporarily
# has no chart for) and is written anyway with a warning - the UI already
# renders a null ytd_pct as "no data" next to that investor's coverage_pct,
# so one blank cell is not worth wedging the whole daily pipeline and
# opening a fresh issue over. A drop bigger than this (out of 16 investors
# total) stops looking like one flaky ticker and starts looking like the
# Worker itself being down or broken, which IS worth refusing to publish.
REGRESSION_TOLERANCE = 2


def eligible_holdings(inv: dict) -> list:
    """Direct port of invComputeValueSeries' eligibility filter
    (index.html, ~line 7138-7141). Do not change this rule here without
    changing it there first - the two must always agree.
    """
    source = inv.get("all_holdings") or inv.get("holdings") or []
    reals = [
        h for h in source
        if h and h.get("change") != "exit"
        and h.get("put_call") not in ("PUT", "CALL")
    ]
    return [h for h in reals if h.get("ticker")]


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def http_get_json(url: str, retries: int = MAX_RETRIES) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (400, 404):
                # Worker itself rejected the symbol or had no data - retrying
                # will not help.
                raise
            time.sleep(RETRY_BASE_SLEEP * (attempt + 1))
        except Exception as e:  # noqa: BLE001 - network/timeout, worth a retry
            last_err = e
            time.sleep(RETRY_BASE_SLEEP * (attempt + 1))
    raise last_err


def fetch_ticker_series(ticker: str):
    """Return (ticker, series_dict_or_None, error_str_or_None)."""
    url = "%s/quote?s=%s&r=1y" % (WORKER, ticker)
    try:
        j = http_get_json(url)
    except Exception as e:  # noqa: BLE001 - reported to caller, not raised
        return ticker, None, "%s: %s" % (type(e).__name__, e)
    if not j or j.get("error"):
        return ticker, None, "worker returned error: %s" % j.get("error") if j else "empty response"
    ts, closes = j.get("t"), j.get("closes")
    if not ts or not closes or len(closes) < 2:
        return ticker, None, "no usable series (< 2 closes)"
    return ticker, j, None


def value_at(series: dict, t: int):
    """Port of invValueAt(): last close at-or-before t, clamped to the
    series' own edges. `series` here uses the worker's own field names
    (t/closes), same as the frontend's `q`.
    """
    ts, cs = series.get("t"), series.get("closes")
    if not ts:
        return None
    if t <= ts[0]:
        return cs[0]
    if t >= ts[-1]:
        return cs[-1]
    lo, hi = 0, len(ts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ts[mid] <= t:
            lo = mid
        else:
            hi = mid - 1
    return cs[lo]


def fetch_all_series(tickers: list, concurrency: int = CONCURRENCY):
    series_by_ticker = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(fetch_ticker_series, t): t for t in tickers}
        for fut in as_completed(futures):
            ticker, series, err = fut.result()
            if series is not None:
                series_by_ticker[ticker] = series
            else:
                errors[ticker] = err
    return series_by_ticker, errors


def compute_investor(inv: dict, series_by_ticker: dict, start_t: int, end_t: int):
    elig = eligible_holdings(inv)
    eligible_count = len(elig)
    eligible_value = sum(h.get("value") or 0 for h in elig)
    priced = [h for h in elig if h.get("ticker") in series_by_ticker]
    priced_count = len(priced)
    priced_value = sum(h.get("value") or 0 for h in priced)
    coverage_pct = round(priced_value / eligible_value, 4) if eligible_value else 0.0

    ytd_pct = None
    if priced and coverage_pct >= COVERAGE_THRESHOLD:
        value_start = 0.0
        value_end = 0.0
        for h in priced:
            s = series_by_ticker[h["ticker"]]
            shares = h.get("shares") or 0
            p0 = value_at(s, start_t)
            p1 = value_at(s, end_t)
            if p0 is not None:
                value_start += p0 * shares
            if p1 is not None:
                value_end += p1 * shares
        if value_start > 0:
            ytd_pct = round(value_end / value_start - 1, 4)

    return {
        "ytd_pct": ytd_pct,
        "coverage_pct": coverage_pct,
        "priced_holdings": priced_count,
        "eligible_holdings": eligible_count,
    }, elig


def usable_count(investors_map: dict) -> int:
    return sum(1 for v in investors_map.values() if isinstance(v, dict) and v.get("ytd_pct") is not None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="compute and print, but never write data/investor-returns.json",
    )
    args = parser.parse_args()

    portfolios = load_json(PORTFOLIOS_PATH, {"investors": []})
    investors = portfolios.get("investors", [])
    if not investors:
        print("[fail] portfolios.json has no investors - nothing to do", file=sys.stderr)
        return 1

    per_investor_eligible = {}
    all_tickers = set()
    for inv in investors:
        elig = eligible_holdings(inv)
        per_investor_eligible[inv["slug"]] = elig
        for h in elig:
            all_tickers.add(h["ticker"])
    tickers = sorted(all_tickers)
    print("[info] investors=%d unique_tickers=%d" % (len(investors), len(tickers)))

    t0 = time.time()
    series_by_ticker, fetch_errors = fetch_all_series(tickers)
    elapsed = time.time() - t0
    print("[info] fetched %d/%d tickers ok in %.1fs (concurrency=%d, %d failed)"
          % (len(series_by_ticker), len(tickers), elapsed, CONCURRENCY, len(fetch_errors)))
    for t in sorted(fetch_errors):
        print("[warn] ticker failed: %s (%s)" % (t, fetch_errors[t]))

    if not series_by_ticker:
        print("[fail] every ticker fetch failed - refusing to write a zero-coverage file", file=sys.stderr)
        return 1

    # Canonical daily calendar: the longest series fetched this run. See
    # module docstring for why one shared calendar is fine here (every
    # ticker is a .us-suffixed 13F holding, i.e. the same NYSE/NASDAQ
    # trading calendar).
    best_ticker = max(series_by_ticker, key=lambda t: len(series_by_ticker[t]["t"]))
    best = series_by_ticker[best_ticker]
    calendar, dates = best["t"], best.get("dates") or []
    now = datetime.now(timezone.utc)
    year_start_epoch = int(datetime(now.year, 1, 1, tzinfo=timezone.utc).timestamp())
    start_idx = None
    for i, t in enumerate(calendar):
        if t >= year_start_epoch:
            start_idx = i
            break
    if start_idx is None:
        start_idx = len(calendar) - 1
    start_t, end_t = calendar[start_idx], calendar[-1]
    ytd_start = dates[start_idx] if start_idx < len(dates) else \
        datetime.fromtimestamp(start_t, tz=timezone.utc).date().isoformat()
    print("[info] canonical calendar from %s: ytd_start=%s (%d points)"
          % (best_ticker, ytd_start, len(calendar)))

    new_investors = {}
    for inv in investors:
        slug = inv["slug"]
        result, elig = compute_investor(inv, series_by_ticker, start_t, end_t)
        new_investors[slug] = result
        cov_str = "%.1f%%" % (result["coverage_pct"] * 100)
        if result["ytd_pct"] is not None:
            print("[ok] %s: ytd=%.2f%% coverage=%s priced=%d/%d"
                  % (slug, result["ytd_pct"] * 100, cov_str,
                     result["priced_holdings"], result["eligible_holdings"]))
        else:
            print("[warn] %s: ytd=null coverage=%s (below %.0f%% threshold or no priced holdings) priced=%d/%d"
                  % (slug, cov_str, COVERAGE_THRESHOLD * 100,
                     result["priced_holdings"], result["eligible_holdings"]))

    new_usable = usable_count(new_investors)
    prev = load_json(OUTPUT_PATH, None)
    prev_usable = usable_count(prev.get("investors", {})) if prev else 0
    print("[info] usable ytd_pct count: new=%d previous=%d" % (new_usable, prev_usable))

    if prev is not None and new_usable < prev_usable - REGRESSION_TOLERANCE:
        print("::error::investor-returns systemic regression: usable count dropped from %d to %d "
              "(more than the %d-investor tolerance) - refusing to overwrite %s (previous file kept)"
              % (prev_usable, new_usable, REGRESSION_TOLERANCE, OUTPUT_PATH), file=sys.stderr)
        return 1
    if prev is not None and new_usable < prev_usable:
        print("::warning::investor-returns: usable count dipped from %d to %d "
              "(within the %d-investor tolerance) - writing anyway, affected investors show ytd_pct: null"
              % (prev_usable, new_usable, REGRESSION_TOLERANCE))

    out = {
        "as_of": now.isoformat(),
        "ytd_start": ytd_start,
        "investors": new_investors,
    }

    if args.dry_run:
        print("[info] --dry-run: not writing %s" % OUTPUT_PATH)
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("[info] wrote %s" % OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())

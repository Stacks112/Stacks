"""Stacks investor YTD returns — daily precompute for the 13F investor hub.

portfolios.json only refreshes quarterly (13f-refresh.yml, cron
"0 22 8-19 2,5,8,11 *" — Feb/May/Aug/Nov only) and carries no market-price
data at all, so it cannot back a daily-changing "YTD return" column on its
own. This script fills that gap: once a day it prices each investor's
disclosed 13F holdings against live quotes and writes a small summary,
data/investor-returns.json, for the hub UI to read directly. It does not
touch index.html or any other UI file.

THE NUMBER THIS PRODUCES MUST MATCH THE COMPARE SCREEN'S OWN "연중 수익률"
(index.html), because both are shown under the same label on the same
site. That screen does NOT hold the latest disclosed book constant across
the whole year — it chain-links the quarterly snapshots
(invComputeHistoricalValueSeries, index.html ~7063-7128), rescaling the
valuation at each quarter boundary so the series is continuous, then reads
the YTD window off the tail of that chained series
(invPaintValueChart's `period.ytd` branch, index.html ~7204-7213). This
file is a direct line-by-line port of BOTH of those functions - see
build_ordered_snapshots(), historical_ticker_union(), raw_total(),
chain_value_series() and ytd_window() below, each annotated with the
index.html line range it mirrors. Do not "approximate" the chaining (e.g.
by holding one quarter constant, or by linearly blending quarters). This
file's FIRST version did exactly that (held the single latest disclosed
book constant across the whole year, ~compute_investor_fallback() below)
and diverged from the live compare screen by up to 7 points of YTD on
high-turnover investors (ARK, Situational Awareness) - see
2026-08-12's review for the measured gaps - because holding a stale book
constant assumes the investor owned today's names before they were ever
disclosed.

invComputeValueSeries() (index.html ~7130-7184) only reaches its
non-historical, single-snapshot branch when an investor has FEWER THAN 2
snapshots with a parseable `filed` date - every investor in the current
roster has 5, so that branch is currently unreachable in production, but
compute_investor_fallback() below ports it faithfully anyway for when a
newly-added investor has a shallow history. It is also reused as this
script's own diagnostic: main() logs the fallback (held-constant) number
next to the chained number for every investor on every run, specifically
so the day this ships you can see, in the log, whether the chained numbers
now land on the compare screen's own figures (see the [check] lines).

Eligibility / coverage universe — copied verbatim from both frontend
functions, which use the SAME two filters:

    reals      = holdings.filter(h => h.change !== "exit"
                                    && h.put_call !== "PUT"
                                    && h.put_call !== "CALL")           # coverage denominator
    priceable  = reals.filter(h => h.ticker
                                    && typeof h.shares === "number")     # what actually prices

`reals` does NOT require a ticker - a disclosed position the Worker/Yahoo
can never price (an OTC name, a foreign listing with no ticker mapping)
still counts against that investor's coverage_pct, it just contributes $0
to priced_value. This is a DELIBERATE CHANGE from this script's first
version, which pre-filtered to ticker-having rows before computing the
coverage denominator (making coverage_pct look higher than the frontend's
own number for any investor holding an unmapped position). Matching the
frontend's own (more honest, and now load-bearing) definition took
priority - see reals_of()/priceable_of() below.

Coverage denominator is the LATEST disclosed quarter only, not summed
across the whole chained history - this matches both frontend functions
(`currentRows` in invComputeHistoricalValueSeries is explicitly
`ordered[ordered.length - 1].snapshot`) and is also the right call on the
merits: coverage_pct is meant to answer "how much of what this investor
holds RIGHT NOW can we price", which is what the UI's coverage badge next
to the YTD figure claims. A history-wide denominator would mix in
positions from a book that no longer exists and would not have an
intuitive reading (and can't be produced by a "port the frontend, don't
invent a new metric" instruction anyway - the frontend has no such
function). The TICKER UNION fetched every run, however, DOES span every
quarter being chained (see historical_ticker_union()) - pricing the chain
needs a ticker's series even for a quarter where that ticker has since
been fully exited from the latest disclosed book.

Price source — the repo's own Cloudflare Worker, same one the frontend
calls (COMMENTS_API in index.html, resolved here via scripts/worker_url.py,
which normalizes to the canonical https://api.stacksdaily.com):

    GET {worker}/quote?s=<ticker>&r=1y  ->  {t: [epoch...], closes: [...], dates: [...]}

One ticker per request (the worker's `s` sanitizer strips commas, so
batching is not possible — see worker/index.js). Tickers are deduplicated
across every quarter of every investor first, so each ticker is fetched at
most once per run, then fetched with a small thread pool (see CONCURRENCY
below).

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
from collections import Counter
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
# 5, ...)) against the same endpoint per investor; this run fans out across
# every quarter of the whole 16-investor roster's unique tickers in one go
# (see module docstring: the union now spans quarterly history, not just the
# latest book), so a slightly higher pool (8) trades a bit more parallel
# load for a materially shorter wall-clock run, while staying well short of
# anything that would look like abuse to Yahoo behind the Worker.
CONCURRENCY = 8
REQUEST_TIMEOUT = 15  # seconds, per HTTP attempt
MAX_RETRIES = 3
RETRY_BASE_SLEEP = 1.5  # seconds; attempt N sleeps RETRY_BASE_SLEEP * N

# Below this fraction of an investor's LATEST-quarter `reals` dollar value
# priced, the YTD number would be computed from too small a slice of the
# real portfolio to be worth showing as a number - report coverage (so the
# UI can say "partial data") but null out ytd_pct rather than publish
# something misleading. Chosen at 0.90: a single very large, unpriceable
# position (e.g. an OTC or newly-listed ticker the Worker/Yahoo has no
# chart for) can easily account for 5-10% of one investor's book without
# being unusual, so a much stricter gate (e.g. 0.99) would flip that
# investor to "no data" on ordinary market noise. Below 90% priced, more
# than a tenth of the book is invisible to the math, which is large enough
# that a misleading ytd_pct is a real risk.
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


# --------------------------------------------------------------------------
# Direct ports of index.html's investor-value-series functions. Each is
# annotated with the line range it mirrors (as of the 2026-08-12 read); if
# the frontend logic moves, re-diff against these before touching the math.
# --------------------------------------------------------------------------

def filed_epoch(filed):
    """Port of invFiledEpoch() (index.html ~7051-7055). Parses only the
    date portion as UTC midnight, then shifts 12h earlier - needed for the
    chain-boundary comparisons (`ordered[i].filed <= t`) to land on the
    exact instant the frontend does."""
    if not filed:
        return None
    try:
        d = datetime.strptime(str(filed)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(d.timestamp()) - 43200


def reals_of(snapshot_or_inv):
    """The `reals` filter shared by invComputeValueSeries (index.html
    ~7138-7139) and invComputeHistoricalValueSeries's `currentRows`
    (~7118). Every disclosed position that is not a 13F "exit" marker row
    and not an options contract - ticker presence is NOT required, because
    this is the COVERAGE denominator, not the priceable set. A position
    the Worker/Yahoo can never price still counts against coverage; it
    just contributes $0 to priced_value. Accepts either a snapshot dict or
    the investor dict itself (both carry all_holdings/holdings)."""
    if not snapshot_or_inv:
        return []
    source = snapshot_or_inv.get("all_holdings") or snapshot_or_inv.get("holdings") or []
    return [h for h in source if h and h.get("change") != "exit" and h.get("put_call") not in ("PUT", "CALL")]


def priceable_of(reals):
    """Reals that can actually be priced: has a ticker AND a numeric share
    count. Mirrors rawTotal()'s skip condition (index.html ~7095:
    `!h.ticker || typeof h.shares !== "number"`)."""
    return [h for h in reals if h.get("ticker") and isinstance(h.get("shares"), (int, float))]


def build_ordered_snapshots(inv):
    """Port of invComputeHistoricalValueSeries' `ordered` (index.html
    ~7064-7066): every snapshot with a parseable `filed` date, sorted
    oldest-first. invComputeValueSeries only takes the historical branch
    when raw `inv.snapshots.length > 1` (~7131); the historical function
    itself then bails to null if `ordered.length < 2` after this filter
    (~7067) - callers here must replicate BOTH checks, not just one."""
    out = []
    for s in (inv.get("snapshots") or []):
        fe = filed_epoch(s.get("filed") if s else None)
        if s and fe is not None:
            out.append({"snapshot": s, "filed": fe})
    out.sort(key=lambda x: x["filed"])
    return out


def historical_ticker_union(ordered):
    """Port of invComputeHistoricalValueSeries' `tickers`/`eligible`
    (index.html ~7068-7075): union of priceable tickers across EVERY
    quarter being chained, not just the latest. A ticker fully exited two
    quarters ago is still needed to price that quarter's segment of the
    chain."""
    tickers = set()
    for entry in ordered:
        for h in priceable_of(reals_of(entry["snapshot"])):
            tickers.add(h["ticker"])
    return tickers


def raw_total(ordered, idx, t, quotes):
    """Port of rawTotal(idx, t) (index.html ~7092-7100): dollar value of
    ordered[idx]'s disclosed book, priced at time t using each ticker's
    own series via value_at() (== invValueAt)."""
    total = 0.0
    for h in priceable_of(reals_of(ordered[idx]["snapshot"])):
        q = quotes.get(h["ticker"])
        if q is None:
            continue
        price = value_at(q, t)
        if price is not None:
            total += price * h["shares"]
    return total


def chain_value_series(ordered, quotes):
    """Port of invComputeHistoricalValueSeries' chain-linking loop
    (index.html ~7101-7115). Builds one continuous (calendar, values)
    series across quarter boundaries: `best` is the longest series among
    this investor's own priceable tickers (own function here:
    max(quotes, key=len), same tie-break as `r.q.t.length > best.t.length`
    in the frontend); at every point where the "active" snapshot switches,
    a rescale factor is solved so the new snapshot's valuation at that
    boundary date equals the old snapshot's valuation there (no level
    jump on the day the disclosed book changed); the WHOLE series is then
    renormalized once at the end (divide every value by the final
    chain_scale) so the most recent segment reflects true, unscaled
    current dollars. Returns (None, None) if there is nothing to chain.

    Faithful-port note: when the very first available price point already
    postdates two or more quarter boundaries at once (the 1y price window
    is shorter than the ~15 months five quarterly filings can span), the
    frontend's `while` loop can advance `active` by more than one step in
    a single iteration, and only computes ONE rescale (prevActive -> the
    new, possibly several-quarters-ahead active) - it does not solve
    intermediate rescales for the skipped-over quarters. That is
    replicated here exactly, not "fixed": it is what the live compare
    screen does, and this file's whole job is to match it.
    """
    if len(ordered) < 2 or not quotes:
        return None, None
    best_ticker = max(quotes, key=lambda t: len(quotes[t]["t"]))
    best_calendar = quotes[best_ticker]["t"]
    first_filed = ordered[0]["filed"]

    calendar, values = [], []
    active = 0
    chain_scale = 1.0
    for t in best_calendar:
        if t < first_filed:
            continue
        prev_active = active
        while active < len(ordered) - 1 and ordered[active + 1]["filed"] <= t:
            active += 1
        if active != prev_active:
            prior_level = raw_total(ordered, prev_active, t, quotes) * chain_scale
            anchor_raw = raw_total(ordered, active, t, quotes)
            if prior_level > 0 and anchor_raw > 0:
                chain_scale = prior_level / anchor_raw
        total = raw_total(ordered, active, t, quotes) * chain_scale
        if total > 0:
            calendar.append(t)
            values.append(total)

    if chain_scale > 0 and chain_scale != 1.0:
        values = [v / chain_scale for v in values]

    if len(calendar) < 2:
        return None, None
    return calendar, values


def ytd_window(calendar, values):
    """Port of invPaintValueChart's `period.ytd` slice (index.html
    ~7204-7213): from the chained series, find the first point on/after
    Jan 1 of the YEAR OF THE LAST CALENDAR POINT (not "today's" year
    literally - matches the frontend using `endDate.getUTCFullYear()`),
    drop non-finite/non-positive points, and return the (start, end) pair
    the pct is read from. Returns None if fewer than 2 usable points
    remain in the window (frontend: box renders "-" in that case)."""
    if not calendar or len(calendar) < 2:
        return None
    end_t = calendar[-1]
    end_year = datetime.fromtimestamp(end_t, tz=timezone.utc).year
    requested_start = int(datetime(end_year, 1, 1, tzinfo=timezone.utc).timestamp())
    start_idx = 0
    while start_idx < len(calendar) - 1 and calendar[start_idx] < requested_start:
        start_idx += 1
    window = [(t, v) for t, v in zip(calendar[start_idx:], values[start_idx:]) if v is not None and v > 0]
    if len(window) < 2:
        return None
    start_t, first_v = window[0]
    end_t2, last_v = window[-1]
    return {"start_t": start_t, "end_t": end_t2, "first": first_v, "last": last_v}


def compute_investor_chained(ordered, series_by_ticker):
    """Historical/chained path - port of invComputeHistoricalValueSeries
    end-to-end (index.html ~7063-7128), used whenever an investor has 2 or
    more valid-filed snapshots (every investor in the current roster).
    Returns None when the frontend function itself would resolve to its
    "no data" placeholder ({calendar:null, coverage:0}) - callers must NOT
    fall back to the single-snapshot method in that case (the frontend
    doesn't either); they should report coverage 0 / ytd_pct null instead.
    """
    tickers = historical_ticker_union(ordered)
    quotes = {t: series_by_ticker[t] for t in tickers if t in series_by_ticker}
    if not quotes:
        return None
    calendar, values = chain_value_series(ordered, quotes)
    if calendar is None:
        return None
    window = ytd_window(calendar, values)
    if window is None:
        return None

    ytd_pct = (window["last"] / window["first"] - 1) if window["first"] else None

    current_snapshot = ordered[-1]["snapshot"]
    current_reals = reals_of(current_snapshot)
    total_value = sum(h.get("value") or 0 for h in current_reals)
    priced_reals = [h for h in current_reals if h.get("ticker") and h["ticker"] in quotes]
    priced_value = sum(h.get("value") or 0 for h in priced_reals)
    if total_value > 0:
        coverage_pct = priced_value / total_value
    else:
        static_cov = current_snapshot.get("ticker_coverage_pct")
        coverage_pct = static_cov if isinstance(static_cov, (int, float)) else 0.0

    return {
        "ytd_pct": round(ytd_pct, 4) if ytd_pct is not None else None,
        "coverage_pct": round(coverage_pct, 4),
        "priced_holdings": len(priced_reals),
        "eligible_holdings": len(current_reals),
        "ytd_start_date": datetime.fromtimestamp(window["start_t"], tz=timezone.utc).date().isoformat(),
    }


def compute_investor_fallback(inv, series_by_ticker):
    """Non-historical path - port of invComputeValueSeries' fallback
    branch (index.html ~7135-7183): holds the SINGLE latest disclosed book
    constant across the whole requested window. This is the "real" result
    only for an investor with fewer than 2 valid-filed snapshots (none
    currently in the roster). It is ALSO called for every investor purely
    as this script's own diagnostic baseline (see main()'s [check] log
    lines) - the number this function used to be treated as authoritative
    before this file's chaining fix.
    """
    reals = reals_of(inv)
    priceable = priceable_of(reals)
    total_value = sum(h.get("value") or 0 for h in reals)
    priced = [h for h in priceable if h["ticker"] in series_by_ticker]

    if not priced:
        if total_value > 0:
            coverage_pct = 0.0
        else:
            static_cov = inv.get("ticker_coverage_pct")
            coverage_pct = static_cov if isinstance(static_cov, (int, float)) else 0.0
        return {
            "ytd_pct": None,
            "coverage_pct": round(coverage_pct, 4),
            "priced_holdings": 0,
            "eligible_holdings": len(reals),
            "ytd_start_date": None,
        }

    best_ticker = max(priced, key=lambda h: len(series_by_ticker[h["ticker"]]["t"]))["ticker"]
    calendar = series_by_ticker[best_ticker]["t"]
    now = datetime.now(timezone.utc)
    year_start = int(datetime(now.year, 1, 1, tzinfo=timezone.utc).timestamp())
    start_idx = len(calendar) - 1
    for i, t in enumerate(calendar):
        if t >= year_start:
            start_idx = i
            break
    start_t, end_t = calendar[start_idx], calendar[-1]

    value_start = value_end = 0.0
    for h in priced:
        s = series_by_ticker[h["ticker"]]
        shares = h["shares"]
        p0 = value_at(s, start_t)
        p1 = value_at(s, end_t)
        if p0 is not None:
            value_start += p0 * shares
        if p1 is not None:
            value_end += p1 * shares
    ytd_pct = (value_end / value_start - 1) if value_start > 0 else None

    priced_value = sum(h.get("value") or 0 for h in priced)
    if total_value > 0:
        coverage_pct = priced_value / total_value
    else:
        static_cov = inv.get("ticker_coverage_pct")
        coverage_pct = static_cov if isinstance(static_cov, (int, float)) else 0.0

    return {
        "ytd_pct": round(ytd_pct, 4) if ytd_pct is not None else None,
        "coverage_pct": round(coverage_pct, 4),
        "priced_holdings": len(priced),
        "eligible_holdings": len(reals),
        "ytd_start_date": datetime.fromtimestamp(start_t, tz=timezone.utc).date().isoformat(),
    }


def apply_coverage_gate(result):
    """Centralized COVERAGE_THRESHOLD gate, applied the same way regardless
    of which path (chained or fallback) produced the raw ytd_pct."""
    if result["ytd_pct"] is not None and result["coverage_pct"] < COVERAGE_THRESHOLD:
        result = dict(result, ytd_pct=None)
    return result


# --------------------------------------------------------------------------
# Networking (unchanged from the previous version).
# --------------------------------------------------------------------------

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
    """Port of invValueAt() (index.html ~7042-7050): last close at-or-before
    t, clamped to the series' own edges."""
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

    # Build each investor's ordered (>=2 valid snapshots) or single-book
    # ticker set, and the GLOBAL union to fetch - spans every quarter being
    # chained, not just the latest disclosed book (see module docstring).
    per_investor_ordered = {}
    all_tickers = set()
    for inv in investors:
        ordered = build_ordered_snapshots(inv)
        per_investor_ordered[inv["slug"]] = ordered
        if len(ordered) >= 2:
            tickers = historical_ticker_union(ordered)
        else:
            tickers = {h["ticker"] for h in priceable_of(reals_of(inv))}
        all_tickers |= tickers
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

    new_investors = {}
    ytd_start_dates = []
    for inv in investors:
        slug = inv["slug"]
        ordered = per_investor_ordered[slug]

        if len(ordered) >= 2:
            raw = compute_investor_chained(ordered, series_by_ticker)
            if raw is None:
                # Chaining was attempted and produced nothing usable (no
                # priceable tickers ever quoted, or <2 chained points) -
                # the frontend reports "no data" here, it does NOT fall
                # back to the single-snapshot method. Match that exactly.
                current_reals = reals_of(ordered[-1]["snapshot"])
                raw = {"ytd_pct": None, "coverage_pct": 0.0, "priced_holdings": 0,
                       "eligible_holdings": len(current_reals), "ytd_start_date": None}
            path = "chained"
        else:
            raw = compute_investor_fallback(inv, series_by_ticker)
            path = "fallback(<2 snapshots)"

        # Diagnostic-only: the OLD held-constant number, for every investor,
        # regardless of which path produced the real result. Never written
        # to the JSON - see module docstring for why.
        naive = compute_investor_fallback(inv, series_by_ticker)

        result = apply_coverage_gate(raw)
        if result.get("ytd_start_date"):
            ytd_start_dates.append(result["ytd_start_date"])
        new_investors[slug] = {k: v for k, v in result.items() if k != "ytd_start_date"}

        cov_str = "%.1f%%" % (result["coverage_pct"] * 100)
        if result["ytd_pct"] is not None:
            print("[ok] %s: ytd=%.2f%% coverage=%s priced=%d/%d (%s)"
                  % (slug, result["ytd_pct"] * 100, cov_str,
                     result["priced_holdings"], result["eligible_holdings"], path))
        else:
            print("[warn] %s: ytd=null coverage=%s (below %.0f%% threshold or no priced holdings) priced=%d/%d (%s)"
                  % (slug, cov_str, COVERAGE_THRESHOLD * 100,
                     result["priced_holdings"], result["eligible_holdings"], path))

        chained_str = ("%+.2f%%" % (raw["ytd_pct"] * 100)) if raw.get("ytd_pct") is not None else "null"
        naive_str = ("%+.2f%%" % (naive["ytd_pct"] * 100)) if naive.get("ytd_pct") is not None else "null"
        note = "" if path == "chained" else "  (real result used the fallback path too - chaining not applicable)"
        print("[check] %s: chained=%s naive_held_constant=%s%s" % (slug, chained_str, naive_str, note))

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

    if ytd_start_dates:
        ytd_start = Counter(ytd_start_dates).most_common(1)[0][0]
    else:
        # Nobody produced a chained/fallback window (extreme edge case) -
        # this is purely a reporting fallback, not used in any investor's
        # own math.
        now = datetime.now(timezone.utc)
        ytd_start = datetime(now.year, 1, 1, tzinfo=timezone.utc).date().isoformat()

    out = {
        "as_of": datetime.now(timezone.utc).isoformat(),
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

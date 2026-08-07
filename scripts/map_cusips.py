"""Fill missing 13F CUSIP -> ticker mappings.

The SEC 13F information table identifies a security by CUSIP, not ticker.
This script keeps the curated ``cusip_map.json`` as the canonical local
cache, then fills new CUSIPs from two public sources:

1. OpenFIGI's ID_CUSIP mapping endpoint (primary source).
2. SEC's company-tickers-exchange file, but only for a unique, conservative
   issuer-name match (fallback; it is not a CUSIP mapping table).

OpenFIGI is intentionally queried only for missing CUSIPs. The result is
stored in the repository so the public site and the next scheduled run do not
depend on a live mapping request. An optional OPENFIGI_API_KEY increases the
OpenFIGI request budget; the script also works without one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORTFOLIOS_PATH = os.path.join(ROOT, "portfolios.json")
CUSIP_MAP_PATH = os.path.join(ROOT, "cusip_map.json")

UA = "Stacks/1.0 (stacksdaily.com; contact@stacksdaily.com)"
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

# OpenFIGI documents 10 jobs/request without a key and 100 with a key.
# Its unauthenticated request limit is 25 requests/minute.
OPENFIGI_BATCH_NO_KEY = 10
OPENFIGI_BATCH_WITH_KEY = 100
OPENFIGI_INTERVAL_NO_KEY = 2.55
OPENFIGI_MAX_RETRIES = 4

_LEGAL_SUFFIXES = {
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "LTD",
    "LIMITED",
    "PLC",
    "P L C",
    "NV",
    "SA",
    "S A",
    "AG",
    "LP",
    "LLC",
    "L P",
    "L L C",
}
_CLASS_WORDS = {"CLASS", "CL", "SERIES", "SER", "SHS", "SHARES"}
_NAME_RE = re.compile(r"[^A-Z0-9]+")
_TICKER_RE = re.compile(r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$")


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def normalize_ticker(raw):
    """Return the Stooq-style ticker shape used by the 13F frontend.

    OpenFIGI can return class tickers such as ``LEN.B``. Keeping the class
    separator and adding ``.us`` lets the existing worker translate the
    symbol to the corresponding Yahoo symbol instead of silently dropping a
    valid mapping.
    """
    if not raw:
        return None
    ticker = str(raw).strip().upper()
    if not ticker or " " in ticker:
        return None
    # OpenFIGI represents US share classes as LEN/B, MOG/A, etc. Yahoo's
    # symbol form is LEN-B/MOG-A, so normalize only this unambiguous
    # two-part class notation. Do not guess at slash-separated dual listings.
    if ticker.count("/") == 1 and re.fullmatch(r"[A-Z0-9]+/[A-Z0-9]+", ticker):
        ticker = ticker.replace("/", "-")
    elif "/" in ticker:
        return None
    if not _TICKER_RE.fullmatch(ticker):
        return None
    low = ticker.lower()
    if low.endswith((".us", ".ks", ".kq", ".jp", ".t")):
        return low
    return low + ".us"


def normalize_name(raw: str, *, core: bool = False) -> str:
    value = str(raw or "").upper().replace("&", " AND ")
    value = value.replace("'", "")
    tokens = [t for t in _NAME_RE.split(value) if t]
    if core:
        tokens = [
            t
            for t in tokens
            if t not in _LEGAL_SUFFIXES and t not in _CLASS_WORDS and t != "THE"
        ]
    return "".join(tokens)


def collect_positions(portfolios: dict) -> dict[str, str]:
    """Return CUSIP -> representative issuer from current and historical 13F data."""
    positions: dict[str, str] = {}
    for investor in portfolios.get("investors", []):
        if not isinstance(investor, dict):
            continue
        row_sets = [investor.get("all_holdings") or investor.get("holdings") or []]
        for snapshot in investor.get("snapshots") or []:
            if isinstance(snapshot, dict):
                row_sets.append(snapshot.get("all_holdings") or snapshot.get("holdings") or [])
        for rows in row_sets:
            for holding in rows:
                if not isinstance(holding, dict):
                    continue
                cusip = str(holding.get("cusip") or "").strip().upper()
                issuer = str(holding.get("issuer") or "").strip()
                if not cusip:
                    continue
                # Prefer a non-empty, non-placeholder name if the same CUSIP is
                # present in more than one investor or as an option row.
                if cusip not in positions or (issuer and not positions[cusip]):
                    positions[cusip] = issuer
    return positions


def http_json(url: str, *, data: bytes | None = None, headers=None, timeout=30):
    req_headers = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def openfigi_jobs(cusips: list[str], api_key: str | None) -> dict[str, dict]:
    """Map CUSIPs through OpenFIGI and return accepted security metadata."""
    if not cusips:
        return {}
    batch_size = OPENFIGI_BATCH_WITH_KEY if api_key else OPENFIGI_BATCH_NO_KEY
    interval = 0 if api_key else OPENFIGI_INTERVAL_NO_KEY
    out: dict[str, dict] = {}
    failed_batches = 0
    for start in range(0, len(cusips), batch_size):
        batch = cusips[start : start + batch_size]
        payload = json.dumps(
            [{"idType": "ID_CUSIP", "idValue": cusip, "exchCode": "US"} for cusip in batch]
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-OPENFIGI-APIKEY"] = api_key
        response = None
        for attempt in range(OPENFIGI_MAX_RETRIES):
            try:
                response = http_json(OPENFIGI_URL, data=payload, headers=headers)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt + 1 < OPENFIGI_MAX_RETRIES:
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        delay = max(2.0, float(retry_after)) if retry_after else 2.0 ** (attempt + 1)
                    except ValueError:
                        delay = 2.0 ** (attempt + 1)
                    print(f"[map] OpenFIGI rate limited; retrying in {delay:.1f}s", file=sys.stderr)
                    time.sleep(delay)
                    continue
                print(f"[warn] OpenFIGI HTTP {exc.code} for batch starting at {start}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001 - fallback source remains usable
                print(f"[warn] OpenFIGI request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            break
        if not isinstance(response, list):
            failed_batches += 1
        else:
            for cusip, item in zip(batch, response):
                candidate = choose_openfigi_candidate(item)
                if candidate:
                    out[cusip] = candidate
        if interval and start + batch_size < len(cusips):
            time.sleep(interval)
    if failed_batches:
        print(f"[warn] OpenFIGI failed batches: {failed_batches}", file=sys.stderr)
    return out


def choose_openfigi_candidate(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    data = item.get("data")
    if not isinstance(data, list):
        return None

    def rank(row):
        security_type = str(row.get("securityType") or "").lower()
        security_type2 = str(row.get("securityType2") or "").lower()
        exchange = str(row.get("exchCode") or "").upper()
        ticker = normalize_ticker(row.get("ticker"))
        if not ticker:
            return (99, 99, 99)
        if "option" in security_type or "option" in security_type2:
            return (90, 90, 90)
        if "warrant" in security_type or "warrant" in security_type2:
            return (91, 91, 91)
        if security_type2 in {"common stock", "etf", "etp"}:
            type_rank = 0
        elif security_type in {"common stock", "etf", "etp"}:
            type_rank = 1
        elif "equity" in security_type or "equity" in security_type2:
            type_rank = 2
        else:
            type_rank = 10
        exchange_rank = 0 if exchange == "US" else 1
        return (type_rank, exchange_rank, len(ticker))

    # 13F positions are US-listed reportable securities. OpenFIGI can return
    # a foreign venue for the same CUSIP when no venue filter is supplied;
    # accepting that result would create a ticker that the Yahoo/Stooq price
    # path cannot price as a US position. Use only the US composite and let
    # the SEC-name fallback handle the few CUSIPs OpenFIGI cannot resolve.
    rows = sorted(
        [row for row in data if str(row.get("exchCode") or "").upper() == "US"],
        key=rank,
    )
    for row in rows:
        if rank(row)[0] >= 10:
            continue
        ticker = normalize_ticker(row.get("ticker"))
        if not ticker:
            continue
        return {
            "ticker": ticker,
            "source": "openfigi",
            "figi": row.get("figi"),
            "matched_name": row.get("name") or row.get("securityDescription"),
            "security_type": row.get("securityType2") or row.get("securityType"),
            "exch_code": row.get("exchCode"),
            "matched_at": datetime.now(timezone.utc).isoformat(),
        }
    return None


def fetch_sec_tickers() -> list[dict]:
    try:
        payload = http_json(SEC_TICKERS_URL, timeout=30)
    except Exception as exc:  # noqa: BLE001 - OpenFIGI results remain valid
        print(f"[warn] SEC ticker fallback failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []
    fields = payload.get("fields") if isinstance(payload, dict) else None
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(fields, list) or not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, list):
            continue
        item = dict(zip(fields, row))
        ticker = normalize_ticker(item.get("ticker"))
        name = str(item.get("name") or "").strip()
        if ticker and name:
            item["normalized_name"] = normalize_name(name)
            item["normalized_core"] = normalize_name(name, core=True)
            out.append(item)
    return out


def sec_name_candidate(issuer: str, sec_rows: list[dict]) -> dict | None:
    if not issuer:
        return None
    exact = normalize_name(issuer)
    core = normalize_name(issuer, core=True)
    exact_matches = [r for r in sec_rows if r.get("normalized_name") == exact]
    if len(exact_matches) != 1:
        exact_matches = []
    candidates = exact_matches or [r for r in sec_rows if r.get("normalized_core") == core and core]
    # A non-unique core match is too risky. A wrong ticker is worse than a
    # visible unmapped row, so only use a single SEC candidate.
    if len(candidates) != 1:
        return None
    row = candidates[0]
    return {
        "ticker": normalize_ticker(row["ticker"]),
        "source": "sec-name",
        "cik": str(row.get("cik") or ""),
        "matched_name": row.get("name"),
        "exchange": row.get("exchange"),
        "match": "exact" if exact_matches else "unique-core",
        "matched_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report mappings without writing cusip_map.json")
    args = parser.parse_args()

    portfolios = load_json(PORTFOLIOS_PATH, {"investors": []})
    existing = load_json(CUSIP_MAP_PATH, {})
    positions = collect_positions(portfolios)
    missing = sorted(
        cusip for cusip in positions if not (existing.get(cusip) or {}).get("ticker")
    )
    if not missing:
        print("[map] no missing CUSIPs")
        return 0

    print(f"[map] missing CUSIPs: {len(missing)}")
    api_key = os.environ.get("OPENFIGI_API_KEY", "").strip() or None
    figi = openfigi_jobs(missing, api_key)
    unresolved = [cusip for cusip in missing if cusip not in figi]
    sec_rows = fetch_sec_tickers() if unresolved else []
    sec = {
        cusip: candidate
        for cusip in unresolved
        if (candidate := sec_name_candidate(positions.get(cusip, ""), sec_rows))
    }

    additions = {}
    for cusip in missing:
        candidate = figi.get(cusip) or sec.get(cusip)
        if not candidate:
            print(f"[unresolved] {cusip} {positions.get(cusip, '')}".rstrip())
            continue
        entry = {
            "ticker": candidate.pop("ticker"),
            "entity_key": None,
            "issuer": positions.get(cusip, ""),
            **candidate,
        }
        additions[cusip] = entry
        print(f"[map] {cusip} -> {entry['ticker']} ({entry['source']})")

    if additions and not args.dry_run:
        merged = dict(existing)
        merged.update(additions)
        with open(CUSIP_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"[map] wrote {len(additions)} mappings to {CUSIP_MAP_PATH}")
    elif args.dry_run:
        print(f"[map] dry-run; would write {len(additions)} mappings")
    else:
        print("[map] no new mappings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fetch KOSPI/KOSDAQ index and KTB 10y yield from data.go.kr and write data/market.json.

Standard library only (urllib, json, datetime, os, sys, re, time). No requests.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
UTC = timezone.utc

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO_ROOT, "data", "market.json")

INDEX_URL = "https://apis.data.go.kr/1160100/service/GetMarketIndexInfoService/getStockMarketIndex"
BOND_URL = "https://apis.data.go.kr/1160100/service/GetBondSecuritiesInfoService/getBondPriceInfo"

TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds: 2, 4, 8

INDEX_TARGETS = ["코스피", "코스닥"]
INDEX_KEY_MAP = {"코스피": "kospi", "코스닥": "kosdaq"}

KTB10Y_NAME_RE = re.compile(r"^국고\d")


# Registry of secret values (raw + encoded service key) that must never reach
# stdout/stderr. Populated once in get_encoded_key(). Every log/err call is
# routed through _mask() so that even exception text that happens to embed a
# full request URL (some urllib/http.client errors do this) comes out
# redacted. GitHub Actions only masks the *raw* secrets.* value in logs, and
# we send the *encoded* form on the wire, so we must mask both ourselves.
_SECRETS = []

# Matches any http(s) URL embedded in a log/error message. Some urllib /
# http.client exceptions put the *entire* request URL - query string and
# all - into their message. We strip the query string outright (not just the
# secret) so no query parameter, sensitive or not, ever reaches the log.
_URL_RE = re.compile(r"https?://\S+")


def _register_secret(value):
    if value and value not in _SECRETS:
        _SECRETS.append(value)


def _strip_query(match):
    return match.group(0).split("?", 1)[0]


def _mask(text):
    """Redact secrets from a log message before it is ever printed.

    Two layers:
    1. Any full URL found in the text has its query string stripped
       entirely (endpoint path only survives) - so serviceKey and every
       other query param disappear together, regardless of encoding.
    2. Any literal occurrence of a registered secret (raw or
       percent-encoded DATA_GO_KR_KEY) is replaced with '***' as a
       fallback, in case a secret ever appears outside URL context.
    """
    text = text if isinstance(text, str) else str(text)
    text = _URL_RE.sub(_strip_query, text)
    for secret in _SECRETS:
        if secret:
            text = text.replace(secret, "***")
    return text


def log(*args):
    print(_mask(" ".join(str(a) for a in args)), file=sys.stdout)


def err(*args):
    print(_mask(" ".join(str(a) for a in args)), file=sys.stderr)


def get_encoded_key():
    key = os.environ.get("DATA_GO_KR_KEY")
    if not key:
        err("ERROR: DATA_GO_KR_KEY environment variable is not set")
        sys.exit(1)
    if "%" in key:
        # Already URL-encoded (encoding key)
        encoded = key
    else:
        encoded = urllib.parse.quote(key, safe="")
    # Register both forms so any accidental leak (e.g. inside an exception's
    # string representation) gets redacted before it is ever printed.
    _register_secret(key)
    _register_secret(encoded)
    return encoded


def http_get_json(base_url, params, encoded_service_key):
    """GET base_url with params + serviceKey (already-encoded), parse JSON.

    params values are url-encoded by us; serviceKey is appended raw since it is
    already percent-encoded (must not be double-encoded).

    Never logs the full URL (it contains serviceKey in the query string).
    Only base_url (endpoint path, no query) is used for identification in
    log/err messages. As a second layer of defense, log()/err() also mask any
    occurrence of the raw or encoded service key via _mask(), in case an
    exception's own string representation embeds the full URL (some
    urllib/http.client errors do this).
    """
    query = urllib.parse.urlencode(params)
    url = f"{base_url}?serviceKey={encoded_service_key}&{query}"

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "stacks-market-sync/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - want to catch/retry broadly
            last_exc = exc
            # Identify the failing call by base_url only; never the full URL.
            if attempt < MAX_RETRIES:
                sleep_s = BACKOFF_BASE * (2 ** (attempt - 1))
                err(f"WARN: request to {base_url} failed (attempt {attempt}/{MAX_RETRIES}): "
                    f"{exc}; retrying in {sleep_s}s")
                time.sleep(sleep_s)
            else:
                err(f"ERROR: request to {base_url} failed after {MAX_RETRIES} attempts: {exc}")
    raise last_exc


def normalize_items(body):
    """response.body.items.item may be a dict (single) or list (multi) or missing."""
    items_wrap = body.get("items")
    if not items_wrap:
        return []
    item = items_wrap.get("item")
    if item is None:
        return []
    if isinstance(item, dict):
        return [item]
    if isinstance(item, list):
        return item
    return []


def call_api(base_url, params, encoded_key, label):
    data = http_get_json(base_url, params, encoded_key)
    try:
        response = data["response"]
        header = response["header"]
        result_code = header.get("resultCode")
    except (KeyError, TypeError) as exc:
        err(f"ERROR: {label}: unexpected response shape: {exc}")
        return None, []

    if result_code != "00":
        msg = header.get("resultMsg", "unknown error")
        err(f"ERROR: {label}: resultCode={result_code} resultMsg={msg}")
        return None, []

    body = response.get("body", {})
    items = normalize_items(body)
    return body, items


def fetch_index_for_date(bas_dt, encoded_key):
    """Return dict idxNm -> item dict for the requested date, or {} on failure."""
    results = {}
    for idx_nm in INDEX_TARGETS:
        params = {
            "resultType": "json",
            "pageNo": "1",
            "numOfRows": "10",
            "basDt": bas_dt,
            "idxNm": idx_nm,
        }
        body, items = call_api(INDEX_URL, params, encoded_key, f"index/{idx_nm}/{bas_dt}")
        if not items:
            continue
        # exact match safety: idxNm should equal idx_nm exactly since we didn't use likeIdxNm
        match = None
        for it in items:
            if it.get("idxNm") == idx_nm:
                match = it
                break
        if match is None:
            match = items[0]
        results[idx_nm] = match
    return results


def index_has_data(bas_dt, encoded_key):
    """Cheap probe: does 코스피 index data exist for this basDt?"""
    params = {
        "resultType": "json",
        "pageNo": "1",
        "numOfRows": "1",
        "basDt": bas_dt,
        "idxNm": "코스피",
    }
    body, items = call_api(INDEX_URL, params, encoded_key, f"index-probe/{bas_dt}")
    if body is None:
        return False
    total_count = body.get("totalCount", 0)
    try:
        total_count = int(total_count)
    except (TypeError, ValueError):
        total_count = 0
    return total_count > 0 and len(items) > 0


def find_latest_business_date(encoded_key, start_date, max_days=7):
    """Scan backward from start_date (KST date) up to max_days, return first basDt with data."""
    for offset in range(max_days):
        d = start_date - timedelta(days=offset)
        bas_dt = d.strftime("%Y%m%d")
        log(f"probing basDt={bas_dt} ...")
        if index_has_data(bas_dt, encoded_key):
            return bas_dt
    return None


def fetch_bond_ktb10y(bas_dt, encoded_key):
    """Fetch all bonds for bas_dt, filter to KTB 10y benchmark issue.

    Returns (item_dict_or_None, matched_count).
    """
    params = {
        "resultType": "json",
        "pageNo": "1",
        "numOfRows": "500",
        "basDt": bas_dt,
    }
    body, items = call_api(BOND_URL, params, encoded_key, f"bond/{bas_dt}")
    if not items:
        return None, 0

    candidates = []
    for it in items:
        mrkt_ctg = (it.get("mrktCtg") or "").strip()
        itms_ctg = (it.get("itmsCtg") or "").strip()
        xp_yr_cnt = (it.get("xpYrCnt") or "").strip()
        itms_nm = it.get("itmsNm") or ""

        if mrkt_ctg != "KTS":
            continue
        if itms_ctg != "지표":
            continue
        if xp_yr_cnt != "10":
            continue
        if not KTB10Y_NAME_RE.match(itms_nm):
            continue
        # Exclude inflation-linked bonds (물가...) explicitly even though the
        # regex above should already exclude names not starting with 국고.
        if itms_nm.startswith("물가"):
            continue
        candidates.append(it)

    if not candidates:
        return None, 0
    if len(candidates) > 1:
        err(f"WARN: bond/{bas_dt}: expected 1 KTB10y benchmark match, got {len(candidates)}: "
            f"{[c.get('itmsNm') for c in candidates]}; using first")
    return candidates[0], len(candidates)


def find_bond_for_date_backward(encoded_key, start_date, max_days=7):
    """Scan backward from start_date for a date that has a KTB10y benchmark bond match."""
    for offset in range(max_days):
        d = start_date - timedelta(days=offset)
        bas_dt = d.strftime("%Y%m%d")
        item, count = fetch_bond_ktb10y(bas_dt, encoded_key)
        if item is not None:
            return bas_dt, item
    return None, None


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_existing():
    if not os.path.exists(OUT_PATH):
        return None
    try:
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        err(f"WARN: failed to read existing {OUT_PATH}: {exc}")
        return None


def content_equal(existing, new_data):
    if existing is None:
        return False
    e = {k: v for k, v in existing.items() if k != "updated"}
    n = {k: v for k, v in new_data.items() if k != "updated"}
    return e == n


def main():
    encoded_key = get_encoded_key()

    now_kst = datetime.now(KST)
    today_kst_date = now_kst.date()

    # Step 2: find latest basDt with index data, scanning back up to 7 days.
    latest_bas_dt = find_latest_business_date(encoded_key, today_kst_date, max_days=7)
    if latest_bas_dt is None:
        err("ERROR: could not find any index data in the last 7 days")
        # Still try to proceed with items empty -> exit 1 at the end if nothing collected.
    else:
        log(f"latest basDt with index data: {latest_bas_dt}")

    items_out = []

    # Step 3a: indices for latest_bas_dt
    if latest_bas_dt is not None:
        idx_results = fetch_index_for_date(latest_bas_dt, encoded_key)
        for idx_nm in INDEX_TARGETS:
            it = idx_results.get(idx_nm)
            if not it:
                err(f"WARN: no index data for {idx_nm} on {latest_bas_dt}; skipping")
                continue
            clpr = parse_float(it.get("clpr"))
            flt_rt = parse_float(it.get("fltRt"))
            if clpr is None or flt_rt is None:
                err(f"WARN: index {idx_nm} on {latest_bas_dt} missing clpr/fltRt; skipping")
                continue
            items_out.append({
                "k": INDEX_KEY_MAP[idx_nm],
                "v": clpr,
                "chg": flt_rt,
                "unit": "pct",
            })

    # Step 3b: bond for latest_bas_dt, and previous business day for bp calc
    if latest_bas_dt is not None:
        bond_today, matched_today = fetch_bond_ktb10y(latest_bas_dt, encoded_key)
        if bond_today is None:
            err(f"WARN: no KTB10y benchmark bond match on {latest_bas_dt}; skipping bond item")
        else:
            today_yield = parse_float(bond_today.get("clprBnfRt"))
            if today_yield is None:
                err(f"WARN: KTB10y bond on {latest_bas_dt} missing clprBnfRt; skipping bond item")
            else:
                # previous business day: scan backward starting the day before latest_bas_dt
                latest_dt_obj = datetime.strptime(latest_bas_dt, "%Y%m%d").date()
                prev_start = latest_dt_obj - timedelta(days=1)
                prev_bas_dt, bond_prev = find_bond_for_date_backward(encoded_key, prev_start, max_days=7)

                chg_bp = None
                if bond_prev is not None:
                    prev_yield = parse_float(bond_prev.get("clprBnfRt"))
                    if prev_yield is not None:
                        chg_bp = round((today_yield - prev_yield) * 100, 1)
                    else:
                        err(f"WARN: previous bond ({prev_bas_dt}) missing clprBnfRt; bp change unavailable")
                else:
                    err("WARN: could not find previous business day bond data for bp change; skipping bond item")

                if chg_bp is not None:
                    items_out.append({
                        "k": "ktb10y",
                        "v": today_yield,
                        "chg": chg_bp,
                        "unit": "bp",
                        "nm": bond_today.get("itmsNm"),
                    })
                else:
                    err("WARN: bp change unavailable; skipping bond item entirely")

    if not items_out:
        err("ERROR: no items collected at all; not writing file")
        sys.exit(1)

    new_data = {
        "basDt": latest_bas_dt,
        "updated": now_kst.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items_out,
    }

    existing = load_existing()
    if existing is not None:
        existing_bas_dt = existing.get("basDt")
        if existing_bas_dt and latest_bas_dt and existing_bas_dt > latest_bas_dt:
            log(f"existing basDt {existing_bas_dt} is newer than new basDt {latest_bas_dt}; not overwriting")
            sys.exit(0)
        if content_equal(existing, new_data):
            log("content unchanged (ignoring 'updated' field); not writing")
            sys.exit(0)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log(f"wrote {OUT_PATH}")
    log(f"basDt={latest_bas_dt}")
    for it in items_out:
        nm = f" ({it['nm']})" if "nm" in it else ""
        log(f"  {it['k']}{nm}: v={it['v']} chg={it['chg']}{it['unit']}")


def _install_secret_masking_excepthook():
    """Defense in depth: mask secrets even in an unhandled-exception traceback.

    err()/log() mask everything we print deliberately, but if an exception
    ever escapes main() unhandled, Python's default excepthook writes
    str(exc) (and the traceback) straight to stderr on its own, bypassing our
    masking. Some urllib/http.client exceptions embed the full request URL
    (which contains serviceKey) in their message, so this matters.
    """
    import traceback

    def _excepthook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(_mask(text))

    sys.excepthook = _excepthook


if __name__ == "__main__":
    _install_secret_masking_excepthook()
    main()

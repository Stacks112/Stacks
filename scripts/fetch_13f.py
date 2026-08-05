"""Stacks 13F sync — runs on GitHub Actions (schedule: quarterly-ish, e.g. weekly is fine).

Pulls the two most recent 13F-HR filings for a fixed roster of well-known
institutional investors from SEC EDGAR, aggregates each filing's
information-table rows by CUSIP (a single issuer is very often split across
many rows — one per internal manager/account — and must be summed, not left
as separate rows), diffs the aggregated holdings against the prior quarter,
and writes a single snapshot to portfolios.json.

Data source: SEC EDGAR (data.sec.gov + www.sec.gov/Archives). No scraping of
disallowed endpoints (cgi-bin/browse-edgar is robots-disallowed and is never
used here). Only the documented JSON/XML endpoints are used:
  - https://data.sec.gov/submissions/CIK{10-digit}.json
  - https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}/index.json
  - the information-table XML referenced from that index

Stdlib only (urllib + xml.etree.ElementTree) so this has no extra pip
dependency beyond what's already vendored for the rest of the pipeline.

Failure handling follows fetch_feeds.py's convention: one investor failing
to fetch must not take down the whole run. If portfolios.json already has a
good entry for that slug, it is kept as-is except for ok/error/checked_at.
If literally everything fails, the previous file is left untouched.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = "Stacks/1.0 (stacksdaily.com; contact@stacksdaily.com)"
REQUEST_SLEEP = 0.2  # SEC asks for <=10 req/s; this keeps us well under that
TOP_N = 25

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PORTFOLIOS_PATH = os.path.join(ROOT, "portfolios.json")
CUSIP_MAP_PATH = os.path.join(ROOT, "cusip_map.json")

INVESTORS = [
    {
        "slug": "berkshire",
        "cik": "0001067983",
        "filer": "BERKSHIRE HATHAWAY INC",
        "name": {"ko": "버크셔 해서웨이", "en": "Berkshire Hathaway", "ja": "バークシャー・ハサウェイ"},
        "manager": {"ko": "워런 버핏", "en": "Warren Buffett", "ja": "ウォーレン・バフェット"},
        "entity_key": None,  # not present in items.json entities (checked 2026-08-05)
        "desc": {
            "ko": "워런 버핏이 이끄는 지주회사로, 보험·철도·에너지 자회사와 함께 대규모 상장주식 포트폴리오를 운용한다. 13F 보고 대상 미국 주식 포지션은 분기 말 기준 수백억 달러 규모이며, 소수 종목에 집중된 장기 보유 스타일이 특징이다.",
            "en": "Warren Buffett's holding company, which runs insurance, rail and energy subsidiaries alongside a large public-equity portfolio. Its 13F-reportable U.S. stock positions total in the hundreds of billions of dollars and are concentrated in a small number of long-held names.",
            "ja": "ウォーレン・バフェット率いる持株会社。保険・鉄道・エネルギー子会社に加え、大規模な上場株式ポートフォリオを運用する。13F報告対象の米国株ポジションは四半期末時点で数百億ドル規模で、少数銘柄への長期集中保有が特徴。",
        },
    },
    {
        "slug": "pershing-square",
        "cik": "0001336528",
        "filer": "Pershing Square Capital Management, L.P.",
        "name": {"ko": "퍼싱스퀘어", "en": "Pershing Square", "ja": "パーシング・スクエア"},
        "manager": {"ko": "빌 애크먼", "en": "Bill Ackman", "ja": "ビル・アックマン"},
        "entity_key": None,
        "desc": {
            "ko": "빌 애크먼이 운용하는 액티비스트 헤지펀드로, 10개 안팎의 종목에 초집중 투자하는 전략을 쓴다. 13F 보고 포트폴리오는 소수의 대형 포지션이 대부분을 차지한다.",
            "en": "An activist hedge fund run by Bill Ackman that concentrates on roughly a dozen or fewer positions at a time. Its 13F portfolio is dominated by a handful of large stakes.",
            "ja": "ビル・アックマンが運用するアクティビスト・ヘッジファンドで、10銘柄前後への超集中投資を戦略とする。13F報告ポートフォリオは少数の大型ポジションが大半を占める。",
        },
    },
    {
        "slug": "ark",
        "cik": "0001697748",
        "filer": "ARK INVESTMENT MANAGEMENT LLC",
        "name": {"ko": "ARK 인베스트", "en": "ARK Invest", "ja": "アーク・インベスト"},
        "manager": {"ko": "캐시 우드", "en": "Cathie Wood", "ja": "キャシー・ウッド"},
        "entity_key": None,
        "desc": {
            "ko": "캐시 우드가 이끄는 액티브 운용사로, 혁신·성장 테마의 상장지수펀드(ARKK 등)를 통해 파괴적 혁신 기업에 집중 투자한다. 13F 포트폴리오는 수백 개 종목에 걸쳐 있으며 회전율이 높은 편이다.",
            "en": "An active manager led by Cathie Wood, best known for thematic innovation-growth ETFs such as ARKK. Its 13F portfolio spans a large number of names and turns over relatively quickly.",
            "ja": "キャシー・ウッド率いるアクティブ運用会社。ARKKなどのイノベーション・成長テーマ型ETFを通じて破壊的イノベーション企業に集中投資する。13Fポートフォリオは多数の銘柄にまたがり、回転率も比較的高い。",
        },
    },
    {
        "slug": "duquesne",
        "cik": "0001536411",
        "filer": "Duquesne Family Office LLC",
        "name": {"ko": "듀케인 패밀리 오피스", "en": "Duquesne Family Office", "ja": "デュケーヌ・ファミリーオフィス"},
        "manager": {"ko": "스탠리 드러켄밀러", "en": "Stanley Druckenmiller", "ja": "スタンレー・ドラッケンミラー"},
        "entity_key": None,
        "desc": {
            "ko": "스탠리 드러켄밀러가 자신의 자산을 운용하는 패밀리 오피스로, 매크로 관점에 따라 종목·비중을 자주 바꾸는 것으로 알려져 있다. 13F 포트폴리오는 옵션 포지션을 포함해 회전율이 높다.",
            "en": "Stanley Druckenmiller's family office, known for shifting names and sizing frequently around a top-down macro view. Its 13F filings include options positions and turn over quickly.",
            "ja": "スタンレー・ドラッケンミラーが自身の資産を運用するファミリーオフィス。マクロ観に基づき銘柄・比率を頻繁に入れ替えることで知られる。13Fポートフォリオはオプションポジションを含み回転率が高い。",
        },
    },
    # Bridgewater was deliberately dropped (june's call, 2026-08-05): it's a
    # thousand-plus-position macro book (hence a 583KB infotable), which
    # doesn't fit a "what did the famous investor buy" feature, and Ray Dalio
    # is no longer in a day-to-day investment role there. Do not re-add
    # without a product decision to do so.
    {
        "slug": "appaloosa",
        "cik": "0001656456",
        "filer": "Appaloosa LP",
        "name": {"ko": "아팔루사", "en": "Appaloosa", "ja": "アパルーサ"},
        "manager": {"ko": "데이비드 테퍼", "en": "David Tepper", "ja": "デビッド・テッパー"},
        "entity_key": None,
        "desc": {
            "ko": "데이비드 테퍼가 운용하는 헤지펀드로, 대형 기술주와 매크로 베팅 위주의 집중 포트폴리오로 알려져 있다. 13F 보고 종목 수는 수십 개 안팎이다.",
            "en": "A hedge fund run by David Tepper, known for a concentrated portfolio weighted toward large-cap tech and macro-driven bets. Its 13F typically lists on the order of a few dozen positions.",
            "ja": "デビッド・テッパーが運用するヘッジファンドで、大型テック株とマクロ主導のベットに偏った集中ポートフォリオで知られる。13F報告銘柄数はおおむね数十程度。",
        },
    },
]


def http_get(url: str, retries: int = 3) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            time.sleep(REQUEST_SLEEP)
            return data
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 404):
                raise
            time.sleep(1 + attempt)
        except Exception as e:  # noqa: BLE001 - network errors, retry
            last_err = e
            time.sleep(1 + attempt)
    raise last_err


def local_tag(el) -> str:
    """Strip an XML namespace off an element tag: '{uri}infoTable' -> 'infoTable'."""
    t = el.tag
    return t.split("}", 1)[1] if "}" in t else t


def find_child_text(el, name: str):
    for child in el:
        if local_tag(child) == name:
            return child
    return None


def find_two_recent_13f_hr(cik: str):
    """Return up to 2 most recent 13F-HR filings (excluding /A amendments),
    most recent first, as dicts with reportDate/filingDate/accessionNumber.
    """
    data = json.loads(http_get(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = data["filings"]["recent"]
    forms = recent["form"]
    out = []
    for i, form in enumerate(forms):
        if form == "13F-HR":
            out.append({
                "reportDate": recent["reportDate"][i],
                "filingDate": recent["filingDate"][i],
                "accessionNumber": recent["accessionNumber"][i],
            })
            if len(out) == 2:
                break
    # Older filers may need the paginated "files" list if fewer than 2 were
    # found in "recent" (recent caps at 1000 entries; not an issue for any
    # of our roster today, but keep this from silently returning 0/1).
    return out


def find_infotable_url(cik_int: str, accession_nodash: str) -> str:
    """Find the information-table XML inside a filing's directory.

    The filename is NOT standardized across filers/filing agents: it may be
    "infotable.xml", a filer-chosen name like "form13f_20260331.xml", a
    CamelCase name like "Form13FInfoTable.xml", or a bare accession-like
    number such as "53405.xml" (seen on Berkshire's own filings). We pick
    every *.xml candidate that isn't primary_doc.xml, and if more than one
    remains, fetch each and keep the one whose root element (by local name,
    namespace stripped) is informationTable / infoTable.
    """
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}"
    idx = json.loads(http_get(f"{base}/index.json"))
    items = idx["directory"]["item"]
    candidates = [
        it["name"] for it in items
        if it["name"].lower().endswith(".xml") and it["name"].lower() != "primary_doc.xml"
    ]
    if not candidates:
        raise ValueError(f"no infotable xml candidate found under {base}")
    if len(candidates) == 1:
        return f"{base}/{candidates[0]}"
    for name in candidates:
        url = f"{base}/{name}"
        try:
            head = http_get(url)[:2000].decode("utf-8", "ignore").lower()
        except Exception:
            continue
        if "informationtable" in head or "infotable" in head:
            return url
    # Fall back to the first candidate rather than crashing the whole investor.
    return f"{base}/{candidates[0]}"


def parse_infotable(xml_bytes: bytes):
    """Return a list of raw rows: dict(issuer, cusip, titleOfClass, value,
    shares, sshType, putCall)."""
    root = ET.fromstring(xml_bytes)
    rows = []
    # infoTable elements can appear anywhere under the root, namespaced or not.
    for el in root.iter():
        if local_tag(el) != "infoTable":
            continue
        issuer_el = find_child_text(el, "nameOfIssuer")
        cusip_el = find_child_text(el, "cusip")
        title_el = find_child_text(el, "titleOfClass")
        value_el = find_child_text(el, "value")
        shrs_el = find_child_text(el, "shrsOrPrnAmt")
        put_call_el = find_child_text(el, "putCall")
        ssh_amt, ssh_type = None, None
        if shrs_el is not None:
            amt_el = find_child_text(shrs_el, "sshPrnamt")
            type_el = find_child_text(shrs_el, "sshPrnamtType")
            ssh_amt = amt_el.text.strip() if amt_el is not None and amt_el.text else None
            ssh_type = type_el.text.strip() if type_el is not None and type_el.text else None
        rows.append({
            "issuer": (issuer_el.text or "").strip() if issuer_el is not None else "",
            "cusip": (cusip_el.text or "").strip() if cusip_el is not None else "",
            "titleOfClass": (title_el.text or "").strip() if title_el is not None and title_el.text else "",
            "value": int(round(float(value_el.text.strip()))) if value_el is not None and value_el.text else 0,
            "shares": int(round(float(ssh_amt))) if ssh_amt else 0,
            "sshType": ssh_type,
            "putCall": (put_call_el.text or "").strip() if put_call_el is not None and put_call_el.text else None,
        })
    return rows


class ValueUnitError(Exception):
    """Raised when a filing's <value> field can't be trusted even after the
    thousands-vs-dollars rescale (see fix_value_units). The caller treats
    this like any other per-investor fetch failure: ok=False + error, and
    nothing gets published for that filer rather than a bogus number."""


def fix_value_units(rows, filer_label: str = ""):
    """Detect filings whose <value> is reported in thousands of dollars
    instead of whole dollars (a legacy convention some filing agents still
    use even though current SEC guidance calls for whole dollars) and
    rescale.

    Heuristic: for common-stock rows with a nonzero share count, the
    implied price-per-share (value / shares) should be a plausible equity
    price. If the *median* implied price across the filing is under $2,
    real institutional 13F holdings essentially never look like that in
    aggregate, so we assume the filer reported thousands and multiply by
    1000. This only ever fires filing-wide (never per row), so it can't
    partially corrupt a table that's genuinely dollar-denominated.

    Safety net: if the median implied price is still implausible after
    this correction (under $1 or over $10,000), we don't guess further -
    we raise so the investor is marked failed instead of publishing a
    number that's probably wrong.
    """
    prices = []
    for r in rows:
        if r["sshType"] == "SH" and r["shares"] > 0 and not r["putCall"]:
            prices.append(r["value"] / r["shares"])
    if not prices:
        return rows
    prices.sort()
    median = prices[len(prices) // 2]
    scaled = False
    if median < 2:
        print(f"[warn] {filer_label}: value field looks like thousands of dollars "
              f"(median implied price/share was ${median:.4f}) - rescaling x1000",
              file=sys.stderr)
        for r in rows:
            r["value"] *= 1000
        scaled = True
        prices = [p * 1000 for p in prices]
        median = prices[len(prices) // 2]
    if median < 1 or median > 10000:
        raise ValueUnitError(
            f"{filer_label}: median implied price/share is ${median:,.2f} even after "
            f"the thousands-rescale check (rescaled={scaled}) - value field looks "
            f"wrong, refusing to publish this filer's numbers"
        )
    return rows


def group_by_cusip(rows):
    """Sum value/shares per CUSIP, excluding options (putCall set) and
    non-share amounts (sshPrnamtType != 'SH', e.g. bond face value 'PRN')."""
    groups = {}
    for r in rows:
        if r["putCall"]:
            continue
        if r["sshType"] != "SH":
            continue
        if not r["cusip"]:
            continue
        g = groups.setdefault(r["cusip"], {"issuer": r["issuer"], "titleOfClass": r["titleOfClass"], "value": 0, "shares": 0})
        g["value"] += r["value"]
        g["shares"] += r["shares"]
        # Keep the longest issuer name variant seen (rows sometimes differ in
        # punctuation/truncation); doesn't affect the number crunching.
        if len(r["issuer"]) > len(g["issuer"]):
            g["issuer"] = r["issuer"]
        if not g["titleOfClass"] and r["titleOfClass"]:
            g["titleOfClass"] = r["titleOfClass"]
    return groups


VALID_TICKER_SUFFIXES = (".us", ".ks", ".kq", ".jp", ".t")

# nameOfIssuer occasionally embeds a share-class marker itself (not just in
# titleOfClass); strip it before using the name as a merged/representative
# label so "FOO INC CLASS A" and "FOO INC CLASS C" collapse to "FOO INC".
_CLASS_SUFFIX_RE = re.compile(r"\s+(CLASS\s+[A-Z]|CL\s+[A-Z]|SER(?:IES)?\s+[A-Z])$", re.IGNORECASE)


def strip_class_suffix(name: str) -> str:
    return _CLASS_SUFFIX_RE.sub("", name).strip()


def normalize_ticker(raw):
    """Coerce a cusip_map ticker into the '{lowercase-symbol}.{suffix}' shape
    the worker's yahooSymbol() expects (worker/index.js:739 special-cases the
    '.us' suffix; other markets keep their own suffix).

    - Already-suffixed values (.us/.ks/.kq/.jp/.t) are just lowercased.
    - A bare alphanumeric symbol (e.g. "AMD", "BAC") gets ".us" appended,
      since every filer in INVESTORS is a US institutional manager and every
      13F holding is, by definition, a US-listed reportable security.
    - Anything else (dual-listing notations like "688981 / 0981", stray
      whitespace, etc.) is not a usable single ticker and is dropped (None)
      rather than guessed at.
    """
    if not raw:
        return None
    t = raw.strip()
    if not t or "/" in t or " " in t:
        return None
    low = t.lower()
    if low.endswith(VALID_TICKER_SUFFIXES):
        return low
    if re.fullmatch(r"[A-Za-z0-9]+", t):
        return f"{low}.us"
    return None


def merge_share_classes(groups: dict, cusip_map: dict):
    """Second aggregation pass on top of group_by_cusip().

    CUSIP-level grouping alone still leaves genuine duplicates on screen:
    the same company issues multiple share classes under different CUSIPs
    (Alphabet's GOOGL/GOOG being the obvious one). Two different fixes for
    two different situations:

      - If we have a ticker for the CUSIP (cusip_map), that ticker is the
        real identity: sum value/shares across every CUSIP that maps to the
        same ticker, keep the highest-value CUSIP as the representative
        "cusip" field, and use a class-suffix-stripped issuer name.
      - If there's no ticker (not in cusip_map) and two or more CUSIPs
        happen to share the exact issuer name, they are NOT merged (they
        really are different securities) but get titleOfClass appended in
        parens so the UI can tell them apart, e.g.
        "LIBERTY LIVE HOLDINGS INC (COM SHS SER C)".

    Returns a dict keyed by ("T", ticker) or ("C", cusip) -> {cusip, issuer,
    ticker, entity_key, value, shares}. The key (not just the cusip) is what
    quarter-over-quarter change detection matches on, so a company keeps its
    identity across quarters even if which specific class-CUSIP dominates
    shifts.
    """
    by_ticker = {}
    standalone = []
    for cusip, g in groups.items():
        mapping = cusip_map.get(cusip, {})
        ticker = normalize_ticker(mapping.get("ticker"))
        if ticker:
            bucket = by_ticker.setdefault(ticker, {"members": [], "value": 0, "shares": 0})
            bucket["members"].append((cusip, g, mapping.get("entity_key")))
            bucket["value"] += g["value"]
            bucket["shares"] += g["shares"]
        else:
            standalone.append((cusip, g, mapping.get("entity_key")))

    merged = {}
    for ticker, bucket in by_ticker.items():
        rep_cusip, rep_g, rep_entity_key = max(bucket["members"], key=lambda m: m[1]["value"])
        merged[("T", ticker)] = {
            "cusip": rep_cusip,
            "issuer": strip_class_suffix(rep_g["issuer"]),
            "ticker": ticker,
            "entity_key": rep_entity_key,
            "value": bucket["value"],
            "shares": bucket["shares"],
        }

    name_counts = {}
    for cusip, g, _ in standalone:
        key = g["issuer"].strip().upper()
        name_counts[key] = name_counts.get(key, 0) + 1
    for cusip, g, entity_key in standalone:
        issuer = g["issuer"]
        if name_counts[issuer.strip().upper()] > 1 and g.get("titleOfClass"):
            issuer = f"{issuer} ({g['titleOfClass']})"
        merged[("C", cusip)] = {
            "cusip": cusip,
            "issuer": issuer,
            "ticker": None,
            "entity_key": entity_key,
            "value": g["value"],
            "shares": g["shares"],
        }
    return merged


def compute_holdings(merged: dict, prev_merged):
    total_value = sum(g["value"] for g in merged.values())
    ranked = sorted(merged.items(), key=lambda kv: -kv[1]["value"])
    holdings = []
    seen_keys = set()
    for key, g in ranked[:TOP_N]:
        seen_keys.add(key)
        change, prev_shares = None, None
        if prev_merged is not None:
            prev = prev_merged.get(key)
            if prev is None:
                change = "new"
            else:
                prev_shares = prev["shares"]
                if g["shares"] > prev["shares"]:
                    change = "add"
                elif g["shares"] < prev["shares"]:
                    change = "trim"
                else:
                    change = "hold"
        holdings.append({
            "cusip": g["cusip"],
            "issuer": g["issuer"],
            "ticker": g["ticker"],
            "entity_key": g["entity_key"],
            "value": g["value"],
            "shares": g["shares"],
            "weight": round(g["value"] / total_value, 4) if total_value else 0,
            "change": change,
            "prev_shares": prev_shares,
        })
    # Positions that were in the *previous* quarter's top-N but vanished
    # entirely this quarter get an explicit exit row appended.
    if prev_merged is not None:
        prev_ranked_keys = [k for k, _ in sorted(prev_merged.items(), key=lambda kv: -kv[1]["value"])[:TOP_N]]
        for key in prev_ranked_keys:
            if key in seen_keys or key in merged:
                continue
            prev = prev_merged[key]
            holdings.append({
                "cusip": prev["cusip"],
                "issuer": prev["issuer"],
                "ticker": prev["ticker"],
                "entity_key": prev["entity_key"],
                "value": 0,
                "shares": 0,
                "weight": 0,
                "change": "exit",
                "prev_shares": prev["shares"],
            })
    return holdings, total_value, len(merged)


def fetch_one(investor: dict, cusip_map: dict):
    slug = investor["slug"]
    cik = investor["cik"]
    cik_int = str(int(cik))
    filings = find_two_recent_13f_hr(cik)
    if not filings:
        raise ValueError("no 13F-HR filings found")
    latest = filings[0]
    prev_merged = None
    if len(filings) > 1:
        prev_accession_nodash = filings[1]["accessionNumber"].replace("-", "")
        prev_url = find_infotable_url(cik_int, prev_accession_nodash)
        prev_rows = fix_value_units(parse_infotable(http_get(prev_url)), filer_label=f"{slug} (prev quarter)")
        prev_groups = group_by_cusip(prev_rows)
        prev_merged = merge_share_classes(prev_groups, cusip_map)

    accession_nodash = latest["accessionNumber"].replace("-", "")
    infotable_url = find_infotable_url(cik_int, accession_nodash)
    rows = fix_value_units(parse_infotable(http_get(infotable_url)), filer_label=slug)
    groups = group_by_cusip(rows)
    merged = merge_share_classes(groups, cusip_map)
    holdings, total_value, holdings_count = compute_holdings(merged, prev_merged)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "slug": investor["slug"],
        "cik": cik,
        "filer": investor["filer"],
        "name": investor["name"],
        "manager": investor["manager"],
        "entity_key": investor["entity_key"],
        "period": latest["reportDate"],
        "filed": latest["filingDate"],
        "accession": latest["accessionNumber"],
        "source_url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/",
        "total_value": total_value,
        "holdings_count": holdings_count,
        "holdings": holdings,
        "desc": investor["desc"],
        "checked_at": now,
        "ok": True,
        "error": None,
    }


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    cusip_map_raw = load_json(CUSIP_MAP_PATH, {})
    cusip_map = {}
    for k, v in cusip_map_raw.items():
        if k.startswith("_"):
            continue
        v = dict(v)
        v["ticker"] = normalize_ticker(v.get("ticker"))  # defense in depth; see normalize_ticker()
        cusip_map[k] = v

    prev_file = load_json(PORTFOLIOS_PATH, {"investors": []})
    prev_by_slug = {inv["slug"]: inv for inv in prev_file.get("investors", [])}

    now = datetime.now(timezone.utc).isoformat()
    results = []
    any_ok = False
    for investor in INVESTORS:
        slug = investor["slug"]
        try:
            result = fetch_one(investor, cusip_map)
            any_ok = True
            print(f"[ok] {slug}: {result['holdings_count']} holdings, "
                  f"total_value={result['total_value']:,} period={result['period']}")
            results.append(result)
        except Exception as e:  # noqa: BLE001 - one bad filer must not kill the run
            err = f"{type(e).__name__}: {e}"
            print(f"[fail] {slug}: {err}")
            prev = prev_by_slug.get(slug)
            if prev is not None:
                prev = dict(prev)
                prev["checked_at"] = now
                prev["ok"] = False
                prev["error"] = err
                results.append(prev)
            else:
                results.append({
                    "slug": slug,
                    "cik": investor["cik"],
                    "filer": investor["filer"],
                    "name": investor["name"],
                    "manager": investor["manager"],
                    "entity_key": investor["entity_key"],
                    "period": None,
                    "filed": None,
                    "accession": None,
                    "source_url": None,
                    "total_value": None,
                    "holdings_count": None,
                    "holdings": [],
                    "desc": investor["desc"],
                    "checked_at": now,
                    "ok": False,
                    "error": err,
                })

    if not any_ok and prev_file.get("investors"):
        # Every single fetch failed: leave the existing file alone rather
        # than overwrite good data with an all-error snapshot.
        print("[attention] every investor failed to fetch; leaving portfolios.json untouched")
        return

    out = {"generated_at": now, "investors": results}
    with open(PORTFOLIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"wrote {PORTFOLIOS_PATH}")


if __name__ == "__main__":
    main()

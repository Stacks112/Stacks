#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_term_coverage.py — 카드 본문의 전문용어가 entities/glossary에 색인되는지 검사.

발행 루틴 v4.3 [5] 필수 단계 (2026-07-28 신설, june 지시 "전문용어 색인이 빈번하게
문제로 일어나는데 근본적으로 해결"). 리라이트 세션도 배포 전에 돌린다.

원리: 앱(index.html linkifyEntities)과 SEO 페이지가 쓰는 것과 같은 별칭 매칭 규칙으로
본문을 훑어, (1) 한글·일문 본문 속 라틴 토큰(LPDDR6, DUV 같은 것은 거의 전부 전문용어다)
과 (2) 내장 감시 목록의 한국어 용어 중 어떤 별칭에도 걸리지 않는 것을 후보로 뽑는다.

사용:
  python3 scripts/check_term_coverage.py --latest 5        # 최신 5장 검사
  python3 scripts/check_term_coverage.py --ids id1,id2     # 특정 카드 검사
  python3 scripts/check_term_coverage.py --allow "TOKEN1,TOKEN2"  # 의식적 제외(사유는 보고에)

종료코드: 후보 0건이면 0, 있으면 1. 루틴은 1인 채로 커밋하지 않는다 —
각 후보를 entities에 등록하거나, --allow로 제외하고 그 사유를 [9] 보고에 적는다.
"""
import argparse
import json
import re
import sys

# 항상 허용 (색인 대상이 아닌 흔한 토큰). 등록 여부와 무관하게 후보로 뽑지 않는다.
STOPWORDS = {
    "AI", "IT", "OK", "TLDR", "URL", "PC", "TV", "APP", "VS", "Q1", "Q2", "Q3", "Q4",
    "CEO", "CFO", "CTO", "COO", "X", "SNS", "GDP", "USD", "KRW", "JPY", "CNY", "EU",
    "US", "UK", "FAQ", "PDF", "HTML", "API", "No", "A", "B", "C", "D", "E", "The",
    # 자기참조·모호 약어 (등록 대상 아님)
    "Stacks", "STACKS", "SK", "DC", "Meru",   # Meru = 소스 표시명(메르)의 로마자 표기
    # 매체명 — 기사 출처 표기는 색인 대상이 아니다 (REF 마커 밖 본문에 나올 때)
    "Bloomberg", "Reuters", "CNBC", "WSJ", "NYT", "FT", "Axios", "SCMP", "Nikkei",
    "DigiTimes", "Gizmochina", "TradingKey", "Yahoo", "TechTimes", "Tom", "Hardware",
    "WCCFtech", "Newspim", "Digitimes", "Benzinga", "PYMNTS", "UPI",
    # 매체명 2차 보강 (2026-08-04 — 245장 전수 스캔에서 실제로 후보로 올라온 것들)
    "Fortune", "StockStory", "OilPrice", "BeInCrypto", "WCCF", "IBTimes", "Quartz",
    "CNN", "CBS", "SBS", "KED", "TIME", "XenoSpectrum", "Hunterbrook", "DRAMeXchange",
    "Asia",
    # 여러 단어로 된 매체명의 조각 (Asia Times · China Daily · Wall Street Journal ·
    # Business Insider · The Information · Tom's Hardware …). 낱개로는 색인 대상이 아니다.
    "Times", "Daily", "News", "Business", "Information", "Insights", "Wall", "Street",
    "Journal", "Post", "Press", "Media", "Report", "Weekly", "Review", "Standard",
    # index.html 안의 인라인 용어집(GLOSS)이 이미 덮는 것 — 이 검사기는 items.json entities와
    # glossary.json만 보므로 여기 없으면 오탐이 난다. (2026-08-04 전수 대조에서 ARR 1건)
    "ARR",
}

# 한국어 전문용어 감시 목록 — 본문에 나오는데 어떤 별칭에도 안 걸리면 후보로 띄운다.
# v4.3 [4-C-1] 우선 등록 목록 + 운영 중 실제로 새어 나갔던 용어들. 하한이지 상한이 아니다.
WATCHLIST = [
    "기대인플레이션", "실질금리", "물가연동국채", "국채금리", "국채 입찰", "장기물",
    "기준금리", "대차대조표 축소", "재정적자", "이자비용", "자금조달", "통화량",
    "영업현금흐름", "감가상각", "영업이익률", "매출총이익", "일회성 비용", "희석",
    "괴리율", "강제 매도", "레버리지 ETF", "구인공고", "어닝시즌", "가이던스",
    "컨센서스", "공매도", "공매도잔고", "풋옵션", "콜옵션", "선물시장", "옵션시장",
    "시가총액 가중", "액면분할", "자사주 매입", "배당수익률", "무상증자", "유상증자",
    "전환우선주", "메자닌", "브리지론", "프로젝트 파이낸싱", "특수목적법인",
    "보호예수", "블록딜", "오버행", "손절매", "물타기", "패시브 자금", "액티브 펀드",
    "국부펀드", "연기금", "헤지펀드", "사모펀드", "벤처캐피털", "엔젤투자",
    "포워드 PER", "주가순자산비율", "PBR", "ROE", "자기자본이익률", "부채비율",
    "잉여현금흐름", "FCF", "EBITDA", "감손", "영업권", "무형자산",
    "파일럿 라인", "클린룸", "식각", "증착", "이온주입", "패터닝", "멀티패터닝",
    "인터포저", "칩렛", "서브스트레이트", "본딩", "언더필", "몰딩",
    "테스트베드", "램프업", "캐파", "생산능력", "가동률", "고정거래가격",
    # ⚠ "출하가"는 뺐다 (2026-08-04). 라이브 본문의 2건이 전부 "출하" + 주격조사 "가"였고
    #    ("루빈 울트라 2027년 출하가 갈리는 지점", "저가 갤럭시 출하가 실제로 늘어"),
    #    용어로 등록하면 그 자리에 엉뚱한 툴팁이 붙는다. 값을 뜻할 때는 "고정거래가격"·
    #    "현물가격"이 이미 감시 목록에 있다. (fix-queue 검사기 요청 ③ 처리)
    "액침", "자사주",   # fix-queue 검사기 요청 ② (2026-08-04 처리)
    "현물가격", "재고자산", "재고일수", "빗그로스", "비트그로스",
]

_STOP_UP = {s.upper() for s in STOPWORDS}

MARKER_PREFIXES = ("@@IMG@@", "@@REF@@", "@@CHK@@", "@@CMP@@")


def build_alias_patterns(*sources):
    """build_pages.py build_matcher()와 같은 규칙: \\b는 인접 문자가 ASCII \\w일 때만."""
    pats = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key, ent in src.items():
            if not isinstance(ent, dict):
                continue
            for a in ent.get("aliases", []) or []:
                if not a:
                    continue
                # 경계는 ASCII 영숫자 기준 룩어라운드로 건다. 파이썬 \b는 유니코드
                # \w 기준이라 "ASML이"의 L|이 사이에서 매칭이 깨진다(한글도 \w).
                # 앱(JS)의 \b는 ASCII 기준이라 걸린다 — 앱과 같은 동작이 정답이다.
                head = r"(?<![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]", a) else ""
                tail = r"(?![A-Za-z0-9])" if re.search(r"[A-Za-z0-9]$", a) else ""
                pats.append((re.compile(head + re.escape(a) + tail, re.I), key))
    return pats


# 본문에 그대로 박힌 URL·도메인. 여기서 나오는 조각(com·xyz·trade·note 등)은 용어가 아니다.
# ⚠ 도메인은 **TLD 화이트리스트**로만 잡는다. `\.[A-Za-z0-9-]+` 로 열어 두면 `1.5GW`·`V3.1`
#    같은 소수·판번호까지 통째로 먹어 검사 범위가 조용히 줄어든다.
_TLD = ("com|net|org|io|co|kr|jp|cn|us|uk|ai|dev|app|me|info|biz|news|blog|tv|xyz|"
        "gg|so|to|fm|link|site|cloud|tech|press|media|substack")
URL_RE = re.compile(r"https?://\S+|\bwww\.\S+|"
                    r"\b[A-Za-z0-9][A-Za-z0-9\-]*(?:\.[A-Za-z0-9\-]+)*\.(?:" + _TLD + r")\b(?:/\S*)?")


def strip_markers(text):
    """마커 줄(REF의 URL·매체명, IMG 캡션 출처 등)과 본문 URL은 검사 대상이 아니다."""
    kept = "\n".join(
        line for line in (text or "").split("\n")
        if not line.strip().startswith(MARKER_PREFIXES)
    )
    # 2026-08-04: 마커 밖 본문에 URL이 남아 있으면 도메인 조각이 라틴 토큰으로 잡혀
    # 매 회차 오탐이 됐다(trade·xyz·com·note·to5Mac …). 스캔 전에 지운다.
    return URL_RE.sub(" ", kept)


def covered_spans(text, pats):
    spans = []
    for rx, _key in pats:
        for m in rx.finditer(text):
            spans.append((m.start(), m.end()))
    return spans


def in_spans(start, end, spans):
    return any(s <= start and end <= e for s, e in spans)


# 라틴 토큰: 영숫자 연속(하이픈·&·+ 허용). 한글·일문 본문 안의 이런 토큰은
# 거의 전부 제품명·기술명·기관명이다. 숫자만인 토큰(연도·수치)은 제외.
LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9&+\-]*[A-Za-z0-9]|[A-Za-z]")
HAS_DIGIT_PREFIX = re.compile(r"\b\d+[A-Za-z][A-Za-z0-9]*\b")  # 2nm, 3D, 5G 류
# 단위 토큰. 2026-08-04 확장 — 길이·전력·속도·금리 단위가 전부 후보로 올라오고 있었다.
# ⚠ `25bp` · `1.5GW` 처럼 숫자가 앞에 붙은 형태는 사전에 **등록돼 있어도** 앱의 별칭 경계
#    규칙(`(?<![A-Za-z0-9])`)에 막혀 매칭되지 않는다. 그건 사전 누락이 아니라 매처의 한계라
#    이 검사기가 띄울 일이 아니다(용어 자체는 등록돼 있다). 매처 쪽 과제는 fix-queue 참조.
_UNITS = (r"Gb|GB|Tb|TB|Mb|MB|Gbps|Mbps|bps|bp|GHz|MHz|kHz|Hz|GWh|MWh|kWh|TWh|"
          r"GW|MW|kW|W|km|cm|mm|nm|pt|MT|bcf|K|D|G|T|X|x")
UNIT_TOKEN = re.compile(r"^(?:\d+(?:\.\d+)?(?:" + _UNITS + r")|H[12]|"
                        r"Gb|GB|TB|MB|Gbps|Mbps|GHz|MHz|kHz|GWh|MWh|kWh|TWh|"
                        r"km|cm|mm|pt|MT|bcf)$")


def candidates_for(text, pats, allow):
    text = strip_markers(text)
    spans = covered_spans(text, pats)
    out = {}
    for m in list(LATIN_TOKEN.finditer(text)) + list(HAS_DIGIT_PREFIX.finditer(text)):
        tok = m.group(0)
        # 숫자 바로 뒤에서 시작한 라틴 토큰은 건너뛴다. `25bp`의 "bp", `1.5GW`의 "GW"처럼
        # 잘린 조각이라 사전에 등록돼 있어도 그 자리에서는 별칭 경계에 막혀 매칭되지 않는다.
        # 온전한 토큰(`25bp`)은 HAS_DIGIT_PREFIX 쪽이 따로 잡으므로 검사 범위가 줄지 않는다.
        if m.re is LATIN_TOKEN and m.start() > 0 and text[m.start() - 1] in "0123456789.":
            continue
        if len(tok) < 2 or tok.upper() in _STOP_UP or tok in allow:
            continue
        if UNIT_TOKEN.match(tok):  # 24Gb, 300mm, H1 같은 단위·반기 표기
            continue
        if in_spans(m.start(), m.end(), spans):
            continue
        out.setdefault(tok, 0)
        out[tok] += 1
    for w in WATCHLIST:
        if w in allow:
            continue
        for m in re.finditer(re.escape(w), text):
            if not in_spans(m.start(), m.end(), spans):
                out.setdefault(w, 0)
                out[w] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", type=int, default=5)
    ap.add_argument("--ids", default="")
    ap.add_argument("--allow", default="", help="의식적으로 제외할 토큰(쉼표 구분) — 사유는 보고에 적을 것")
    ap.add_argument("--items", default="items.json")
    ap.add_argument("--glossary", default="glossary.json")
    args = ap.parse_args()

    data = json.load(open(args.items, encoding="utf-8"))
    try:
        gloss = json.load(open(args.glossary, encoding="utf-8"))
    except Exception:
        gloss = {}
    pats = build_alias_patterns(data.get("entities", {}), gloss)
    allow = {t.strip() for t in args.allow.split(",") if t.strip()}

    items = data["items"]
    if args.ids:
        want = {i.strip() for i in args.ids.split(",") if i.strip()}
        targets = [it for it in items if it["id"] in want]
    else:
        targets = sorted(items, key=lambda x: x.get("ts", ""), reverse=True)[: args.latest]

    total = 0
    for it in targets:
        gist = it.get("gist") or {}
        ko = gist.get("ko", "") if isinstance(gist, dict) else str(gist)
        ja = gist.get("ja", "") if isinstance(gist, dict) else ""
        title_ko = (it.get("title") or {}).get("ko", "") if isinstance(it.get("title"), dict) else ""
        cands = candidates_for(title_ko + "\n" + ko, pats, allow)
        for tok, n in candidates_for(ja, pats, allow).items():
            cands[tok] = max(cands.get(tok, 0), n)
        if cands:
            total += len(cands)
            print(f"[GAP] {it['id']}")
            for tok, n in sorted(cands.items(), key=lambda kv: -kv[1]):
                print(f"      {tok}  x{n}")
        else:
            print(f"[ok]  {it['id']}")

    if total:
        print(f"\n{total}개 후보. 각각 entities에 등록하거나 --allow로 제외하고 사유를 보고([9])에 적는다.")
        sys.exit(1)
    print("\n용어 커버리지 이상 없음.")
    sys.exit(0)


if __name__ == "__main__":
    main()

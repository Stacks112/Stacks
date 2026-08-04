#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_term_coverage.py — 카드 본문의 전문용어·기업명·인물명이 색인되는지 검사.

발행 루틴 v4.3 [5-B] 필수 단계 (2026-07-28 신설, june 지시 "전문용어 색인이 빈번하게
문제로 일어나는데 근본적으로 해결"). 리라이트 세션도 배포 전에 돌린다.

원리: 앱(index.html linkifyEntities)과 SEO 페이지가 쓰는 것과 같은 별칭 매칭 규칙으로
본문을 훑어, 어떤 별칭에도 걸리지 않는 것을 후보로 뽑는다. 검사는 두 갈래다.

  [용어]  (1) 한글·일문 본문 속 라틴 토큰(LPDDR6, DUV 같은 것은 거의 전부 전문용어다)
          (2) 내장 감시 목록(WATCHLIST)의 한국어 용어
  [이름]  (3) 직함이 붙은 사람 이름, 조직 접미사가 붙은 기관·회사 이름, 그리고
          줄머리에서 "~는 ... 전했다/밝혔다" 꼴로 주어 자리에 선 고유명사

2026-08-04 개정 (june 지시 "전문용어나 인물명 기업명 대부분 색인이 안 된다"):
  · 이때까지 이 검사기는 **전문용어만** 봤다. 회사·인물은 아무도 검사하지 않아서
    게이트가 exit 0을 줘도 카드의 주인공이 통째로 미색인인 채 나갔다
    (2026-08-03 `schiff-strategy-btc-sale-strc-buyback`: 스트래티지·마이클 세일러·
    비트코인 셋 다 미색인). 위 (3)이 그 구멍을 메운다.
  · 한국어 용어 감시 목록을 매크로·크레딧·외환·크립토·회계로 넓혔다.
  · 별칭 규칙을 앱과 다시 맞췄다 — 엔티티 키도 이름으로 치고(entity_alias_list),
    전부 대문자인 라틴 별칭은 대소문자를 구분한다(alias_is_case_sensitive).
  · 회차마다 같은 `--allow`를 다시 치지 않도록 상시 제외 목록을 레지스트리 파일
    `term_stopwords.json`으로 뺐다.

사용:
  python3 scripts/check_term_coverage.py --latest 5        # 최신 5장 검사
  python3 scripts/check_term_coverage.py --ids id1,id2     # 특정 카드 검사
  python3 scripts/check_term_coverage.py --allow "TOKEN1,TOKEN2"  # 1회성 제외
  python3 scripts/check_term_coverage.py --no-names        # 이름 검사만 끈다(진단용)

종료코드: 후보 0건이면 0, 있으면 1. 루틴은 1인 채로 커밋하지 않는다 —
각 후보를 entities(또는 glossary.json)에 등록하거나, --allow로 제외하고 그 사유를
[9] 보고에 적는다. 반복되는 제외는 `term_stopwords.json`에 넣어 영구화한다.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    import build_data as _bd
except Exception:                                    # 단독 실행 안전망
    _bd = None


def entity_alias_list(key, ent):
    if _bd and hasattr(_bd, "entity_alias_list"):
        return _bd.entity_alias_list(key, ent)
    return [a for a in (ent.get("aliases") or []) if a]


def alias_is_case_sensitive(a):
    if _bd and hasattr(_bd, "alias_is_case_sensitive"):
        return _bd.alias_is_case_sensitive(a)
    return False

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

# 한국어 매체명 — 위와 같은 이유로 [이름] 검사에서 제외한다. 하우스 룰:
# 기사 출처 표기는 색인 대상이 아니다.
MEDIA_KO = {
    "로이터", "블룸버그", "알자지라", "니혼게이자이", "닛케이", "니케이", "월스트리트저널",
    "파이낸셜타임스", "포브스", "포춘", "이코노미스트", "가디언", "AP통신", "AFP",
    "코인데스크", "더블록", "크립토슬레이트", "코인텔레그래프", "디크립트",
    "전자신문", "머니투데이", "한국경제", "매일경제", "서울경제", "헤럴드경제",
    "디지털타임스", "파이낸셜뉴스", "연합뉴스", "조선일보", "중앙일보", "동아일보",
    "이데일리", "아시아경제", "뉴시스", "뉴스핌", "더구루", "지디넷", "테크크런치",
    "재팬타임스", "요미우리", "아사히", "산케이", "마이니치", "신화통신", "차이신",
    "사우스차이나모닝포스트", "트렌드포스", "디지타임스", "비즈니스인사이더",
    "코리아타임스", "코리아헤럴드", "코리아중앙데일리", "닛케이아시아", "인베스팅닷컴",
    "톰스하드웨어", "오일프라이스닷컴", "모틀리풀", "스톡스토리", "KED글로벌",
    "비인크립토", "더버지", "아스테크니카",
}

# ---------------------------------------------------------------------------
# [이름] 검사 — 회사·인물·기관 (2026-08-04 신설)
# ---------------------------------------------------------------------------
# 규칙 A. 직함이 뒤에 붙으면 앞은 사람 이름이다. 오탐이 거의 없다.
TITLE_SUFFIX = ("장관", "차관", "의장", "총재", "부총재", "회장", "부회장", "사장",
                "위원장", "총리", "대통령", "교수", "애널리스트", "이코노미스트",
                "전략가", "창업자", "설립자", "최고경영자", "재무책임자")
RE_PERSON = re.compile(
    r"(?<![가-힣])([가-힣]{2,6}|[A-Z][A-Za-z.'\-]+(?:\s[A-Z][A-Za-z.'\-]+){0,2})\s?(?:%s)(?![가-힣])"
    % "|".join(TITLE_SUFFIX))

# 규칙 B. 조직 접미사가 붙으면 기관·회사다.
ORG_SUFFIX = ("증권", "은행", "자산운용", "투자자문", "중공업", "해운", "건설",
              "모터스", "홀딩스", "테크놀로지스", "일렉트로닉스", "재무부", "재무성",
              "중앙은행", "거래소", "경제연구원", "공사", "공단")
RE_ORG = re.compile(r"(?<![가-힣])([가-힣A-Za-z0-9]{2,10}(?:%s))(?![가-힣])" % "|".join(ORG_SUFFIX))

# 규칙 D. "X는 ... 전했다" 꼴에서 주어 자리에 선 고유명사. 발화·거래 동사만 본다.
# ★ 줄 맨 앞에 고정한다. 문장 중간의 "마무리하는"·"열리는" 같은 용언 활용형이
#   조사처럼 끝나 주어로 잡히던 오탐이 여기서 전부 사라진다(2026-08-04 실측).
#   이 사이트의 본문은 한 줄 한 문장이라 진짜 주어는 거의 항상 줄머리에 선다.
REPORT_VERB = ("전했다", "밝혔다", "보도했다", "적었다", "추정했다", "집계했다",
               "발표했다", "공시했다", "인수했다", "출시했다", "공개했다", "제시했다",
               "매입했다", "매도했다", "발행했다", "상장했다", "샀다", "팔았다",
               "되샀다", "내놨다", "올렸다", "낮췄다")
RE_SUBJECT = re.compile(
    r"^([가-힣]{2,12}|[A-Z][A-Za-z0-9.&'\-]{1,20})(?:는|은|이|가|도)\s"
    r"[^\n]{0,60}?(?:%s)" % "|".join(REPORT_VERB), re.M)

# 주어 자리에 흔히 서지만 고유명사가 아닌 것들.
COMMON_SUBJECT = {
    "회사", "시장", "정부", "당국", "업계", "투자자", "애널리스트", "전문가", "매체",
    "보고서", "자료", "지수", "주가", "가격", "수요", "공급", "실적", "매출", "이익",
    "저자", "원문", "기사", "이번", "지난", "올해", "내년", "작년", "최근", "현재",
    "지금", "결과", "문제", "이유", "배경", "상황", "사람", "우리", "그것", "이것",
    "여기", "거기", "관계자", "소식통", "일부", "대부분", "다수", "양쪽", "한쪽",
    "모두", "전부", "국내", "해외", "회사의", "그는", "그녀", "이들", "양사", "당사",
    "이곳", "그곳", "한편", "다만", "게다가", "그러나", "그래서", "이후", "이전",
    # 조직 같지만 특정 주체가 아닌 말
    "연합", "펀드", "협회", "컨소시엄", "재단", "조합", "기관", "단체", "본부",
    "위원회", "이사회", "노조", "규제당국", "감독당국", "중앙은행", "재무부",
    "거래소", "연은", "연준", "한은", "금통위", "지주", "본사", "자회사",
    # 부처 이름 조각 — "재무장관"에서 직함 앞을 이름으로 잘못 집던 것
    "재무", "경제", "외무", "국방", "국무", "산업", "기획재정", "산업통상",
    "국토교통", "보건복지", "행정안전", "과학기술",
    # 국가·지역 — 이 사이트는 국가를 엔티티로 색인하지 않는다(태그로만 쓴다)
    "일본", "미국", "중국", "한국", "대만", "유럽", "독일", "영국", "프랑스",
    "인도", "러시아", "사우디", "이란", "이스라엘", "브라질", "베트남", "호주",
    "캐나다", "멕시코", "네덜란드", "싱가포르", "홍콩", "도쿄", "베이징", "워싱턴",
    "서울", "뉴욕", "런던", "상하이", "선전", "허페이", "실리콘밸리",
}


def load_registry_stopwords(path):
    """상시 제외 목록. 회차마다 같은 --allow를 다시 치지 않기 위한 레지스트리 파일."""
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except Exception:
        return set()
    out = set()
    for bucket in ("terms", "names", "tokens"):
        for w in (raw.get(bucket) or []):
            if w:
                out.add(str(w))
    return out

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
            for a in entity_alias_list(key, ent):
                if not a:
                    continue
                # 경계는 ASCII 영숫자 기준 룩어라운드로 건다. 파이썬 \b는 유니코드
                # \w 기준이라 "ASML이"의 L|이 사이에서 매칭이 깨진다(한글도 \w).
                # 앱(JS)의 \b는 ASCII 기준이라 걸린다 — 앱과 같은 동작이 정답이다.
                head = r"(?<![A-Za-z0-9])" if re.match(r"[A-Za-z0-9]", a) else ""
                tail = r"(?![A-Za-z0-9])" if re.search(r"[A-Za-z0-9]$", a) else ""
                flags = 0 if alias_is_case_sensitive(a) else re.I
                pats.append((re.compile(head + re.escape(a) + tail, flags), key))
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


def overlaps(start, end, spans):
    return any(start < e and s < end for s, e in spans)


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


def name_candidates_for(text, pats, allow):
    """회사·인물·기관 후보. 매체명과 흔한 보통명사 주어는 뺀다."""
    text = strip_markers(text)
    spans = covered_spans(text, pats)
    out = {}

    def add(name, start, end):
        name = (name or "").strip()
        if len(name) < 2 or name in allow or name in MEDIA_KO or name in COMMON_SUBJECT:
            return
        if name.upper() in _STOP_UP:
            return
        # 관형형 어미로 끝나면 이름이 아니라 용언 활용형이다("열리는 의장 기자회견").
        if re.search(r"(?:는|은|던|한|된|릴|할|줄|킬)$", name) and not re.search(r"[A-Za-z0-9]$", name):
            return
        # 이름 자리가 이미 색인돼 있으면(별칭이 이름의 일부여도) 통과시킨다.
        if overlaps(start, end, spans):
            return
        out[name] = out.get(name, 0) + 1

    for m in RE_PERSON.finditer(text):
        add(m.group(1), m.start(1), m.end(1))
    for m in RE_ORG.finditer(text):
        add(m.group(1), m.start(1), m.end(1))
    for m in RE_SUBJECT.finditer(text):
        add(m.group(1), m.start(1), m.end(1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", type=int, default=5)
    ap.add_argument("--ids", default="")
    ap.add_argument("--allow", default="", help="의식적으로 제외할 토큰(쉼표 구분) — 사유는 보고에 적을 것")
    ap.add_argument("--items", default="items.json")
    ap.add_argument("--glossary", default="glossary.json")
    ap.add_argument("--stopwords", default="term_stopwords.json")
    ap.add_argument("--no-names", action="store_true", help="[이름] 검사를 끈다(진단용)")
    args = ap.parse_args()

    data = json.load(open(args.items, encoding="utf-8"))
    try:
        gloss = json.load(open(args.glossary, encoding="utf-8"))
    except Exception:
        gloss = {}
    entities = data.get("entities", {}) or {}
    # build_pages.py의 glossary 병합과 같은 규칙: 없으면 추가, 있으면 별칭만 합집합.
    merged = dict(entities)
    for k, v in (gloss or {}).items():
        if k in merged:
            base = merged[k].get("aliases") or []
            low = {str(a).lower() for a in base}
            merged[k] = dict(merged[k])
            merged[k]["aliases"] = base + [a for a in (v.get("aliases") or [])
                                           if a and str(a).lower() not in low]
        else:
            merged[k] = v
    pats = build_alias_patterns(merged)
    allow = {t.strip() for t in args.allow.split(",") if t.strip()}
    allow |= load_registry_stopwords(args.stopwords)

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
        body_ko = title_ko + "\n" + ko
        cands = candidates_for(body_ko, pats, allow)
        for tok, n in candidates_for(ja, pats, allow).items():
            cands[tok] = max(cands.get(tok, 0), n)
        names = {} if args.no_names else name_candidates_for(body_ko, pats, allow)
        if cands or names:
            total += len(cands) + len(names)
            print(f"[GAP] {it['id']}")
            for tok, n in sorted(cands.items(), key=lambda kv: -kv[1]):
                print(f"      [용어] {tok}  x{n}")
            for tok, n in sorted(names.items(), key=lambda kv: -kv[1]):
                print(f"      [이름] {tok}  x{n}")
        else:
            print(f"[ok]  {it['id']}")

    if total:
        print(f"\n{total}개 후보. 각각 entities(또는 glossary.json)에 등록하거나 "
              f"--allow로 제외하고 사유를 보고([9])에 적는다.\n"
              f"반복되는 제외는 {args.stopwords}에 넣어 영구화한다.")
        sys.exit(1)
    print("\n색인 커버리지 이상 없음 (용어·이름).")
    sys.exit(0)


if __name__ == "__main__":
    main()

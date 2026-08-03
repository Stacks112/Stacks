"""Per-article cover images — runs on GitHub Actions (open network).

WHY
---
Until now every card cover came from a generic pool: the company's
representative face (Wikimedia), the company logo, or a curated topic image.
A story about a specific document therefore showed a stock portrait, which
carries no information about the story itself.

This script fills `item.coverArt` with something that is actually *about*
the article, using a priority ladder ordered by how defensible each source
is. `coverImg()` in index.html already checks `item.coverArt` first, so no
renderer change is required for the image to appear.

PRIORITY LADDER
---------------
A. PRIMARY DOCUMENT (self-hosted)
   The post links a PDF / report / press release. Render pages 1-3 to a
   single strip PNG and commit it under covers/. This is the strongest
   case: the document was published for public distribution, and showing
   its opening pages next to a report about it is ordinary editorial
   practice (quotation). It is also the highest-information cover we can
   produce.

B. og:image OF THE LINKED PAGE (hotlinked, never re-hosted)
   The Open Graph protocol exists precisely so a publisher can nominate an
   image for third parties to display when linking to the page. We link to
   it from the publisher's own server and credit the domain; we do not copy
   it into this repo. If the publisher removes it, our card degrades to the
   existing fallback via coverImgFail().

C. SELF-GENERATED CHART (self-hosted, zero third-party rights)
   A·B 둘 다 실패한 카드는 주 종목의 최근 1개월 종가로 스파크라인 커버를
   직접 그린다. 기사 본문에서 숫자를 긁지 않고 검증된 시세만 쓴다.

NEVER
-----
x.com / twitter.com / pbs.twimg.com / t.co media is excluded by a hard
denylist. Lifting a post's attached image as our own cover art is a
reproduction of a third party's photograph with the weakest fair-use
argument of any option here, and X's developer policy does not permit
storing or re-serving that media. Tier A + B get most of the same value
from sources that are meant to be shown by others.

INPUT
-----
`item.docUrl` — the primary-source URL the post points at, recorded by the
publishing routine. Absent that, nothing happens for that item (the ladder
degrades silently to today's behaviour).

Idempotent: an item that already has coverArt, or whose covers/<id>.png
already exists, is skipped. Any failure is logged and leaves the item alone.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

import worker_url

ITEMS = "items.json"
WORKER = worker_url.worker_base()
COVER_DIR = "covers"
UA = {"User-Agent": "Mozilla/5.0 (compatible; StacksCoverBot/1.0; +https://stacksdaily.com/)"}
TIMEOUT = 25
MAX_BYTES = 25 * 1024 * 1024          # refuse absurd PDFs
PAGES = 3                              # pages rendered into the strip
TILE_W, TILE_H, GAP = 376, 480, 4      # strip geometry (matches the card at 568px wide)

# Hard denylist — see the NEVER section above. Substring match on the host.
BLOCKED_HOSTS = (
    "x.com", "twitter.com", "pbs.twimg.com", "video.twimg.com", "t.co",
    "instagram.com", "cdninstagram.com", "fbcdn.net",
)


def blocked(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return True
    return any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS)


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------
# Tier A — primary document
# --------------------------------------------------------------------------

def looks_like_pdf(url, head_ct=""):
    if url.lower().split("?")[0].endswith(".pdf"):
        return True
    return "application/pdf" in (head_ct or "").lower()


def fetch_bytes(url):
    r = requests.get(url, headers=UA, timeout=TIMEOUT, stream=True)
    r.raise_for_status()
    buf = b""
    for chunk in r.iter_content(65536):
        buf += chunk
        if len(buf) > MAX_BYTES:
            raise ValueError("too large")
    return buf, r.headers.get("content-type", "")


def render_pdf_strip(pdf_bytes, out_path):
    """pages 1..PAGES -> one horizontal strip PNG."""
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "doc.pdf")
        with open(src, "wb") as f:
            f.write(pdf_bytes)
        # poppler-utils; -r 110 is enough for a 376px-wide tile
        subprocess.run(
            ["pdftoppm", "-png", "-r", "110", "-f", "1", "-l", str(PAGES),
             src, os.path.join(td, "pg")],
            check=True, capture_output=True, timeout=120,
        )
        pages = sorted(p for p in os.listdir(td) if p.startswith("pg") and p.endswith(".png"))
        if not pages:
            raise ValueError("pdftoppm produced nothing")
        tiles = []
        for name in pages[:PAGES]:
            im = Image.open(os.path.join(td, name)).convert("RGB")
            sc = max(TILE_W / im.width, TILE_H / im.height)
            im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))))
            left = max(0, (im.width - TILE_W) // 2)
            tiles.append(im.crop((left, 0, left + TILE_W, TILE_H)))   # top-anchored: documents read from the top
        w = TILE_W * len(tiles) + GAP * (len(tiles) - 1)
        strip = Image.new("RGB", (w, TILE_H), (255, 255, 255))
        for i, t in enumerate(tiles):
            strip.paste(t, (i * (TILE_W + GAP), 0))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        strip.save(out_path, optimize=True)
    return True


# --------------------------------------------------------------------------
# Tier B — og:image of the linked page (hotlink only)
# --------------------------------------------------------------------------

class _OG(HTMLParser):
    def __init__(self):
        super().__init__()
        self.img = None
        self._done = False

    def handle_starttag(self, tag, attrs):
        if self._done or tag != "meta":
            return
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"):
            val = a.get("content")
            if val:
                self.img = val
                if key.startswith("og:"):
                    self._done = True          # prefer og: over twitter:

    def handle_endtag(self, tag):
        if tag == "head":
            self._done = True


def og_image(page_url):
    r = requests.get(page_url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    ct = r.headers.get("content-type", "")
    if "html" not in ct.lower():
        return None
    p = _OG()
    p.feed(r.text[:400000])
    if not p.img:
        return None
    img = urljoin(r.url, p.img)
    if blocked(img) or not img.startswith("https://"):
        return None
    # confirm it is a real image and not a tracking pixel
    try:
        h = requests.head(img, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        if not h.headers.get("content-type", "").lower().startswith("image"):
            return None
        n = int(h.headers.get("content-length") or 0)
        if 0 < n < 5000:
            return None
    except Exception:
        pass
    return img


# --------------------------------------------------------------------------
# Tier C — a cover we author ourselves (no third-party rights at all)
# --------------------------------------------------------------------------
"""사다리 C — 자체 생성 차트 커버.

왜 이게 필요한가
----------------
A(1차 문서 렌더)·B(og:image)는 원문이 링크를 걸어줘야 동작한다. 링크가 없는
글 — X 게시물 하나가 전부인 카드 — 은 여전히 커버가 없다. 그런 글에도
"이 기사에 대한" 그림을 붙이되, 제3자 저작물을 전혀 쓰지 않는 방법이
**우리가 직접 그리는 것**이다. 저작권 리스크 0이고, june이 말한
"2차 창작글이지만 읽을 가치가 있게"라는 목적에 가장 직접적으로 닿는다.

무엇을 그리나
--------------
기사 본문에서 숫자를 정규식으로 긁어 그리지 않는다. 금융 서비스에서 그건
틀린 차트를 만들 위험이 크다. 대신 **이미 검증된 구조화 데이터**를 쓴다:
카드의 주 종목(entities의 ticker) 종가 시계열을 워커의 `/quote`에서 받아
**그 기사가 나온 날을 표시한** 스파크라인 + 발행 후 등락률로 그린다.

- 사실 근거가 확실하다 (LLM이 추출한 숫자가 아니라 실제 시세)
- 기사와 관련이 있다 (그 기사가 다루는 회사, 그 기사가 나온 날)
- 독자에게 실제로 쓸모가 있다 ("이 뉴스 나온 뒤로 주가는 어땠나")

발행일 마커 — 왜 넣었나
------------------------
초판은 "최근 1개월"만 그렸다. 그러니 **같은 종목 기사는 커버가 전부 같았다.**
실측: 커버 51장 / 서로 다른 종목 27개 (SK HYNIX 11, AMD 7, NVIDIA 6 …).
발행일을 기준점으로 삼으면 (종목, 날짜) 조합이 45개로 늘어 반복이 거의 사라진다.
그리고 이건 단순한 차별화 장치가 아니다 — 앵커를 발행일로 옮기면 히어로 숫자가
"1개월 등락"에서 **"이 기사 나온 뒤 등락"**이 되고, 기존 '그 후 수익률' 기능과
같은 이야기를 하게 된다.

구간은 발행일 앞 10거래일(문맥) + 발행일 이후 전부. 발행 전은 muted 얇은 선,
발행 후는 status 색 굵은 선 + 옅은 면 채움 — **색과 굵기 두 채널**로 나눈다.

발행 직후(거래일 2일 미만) 기사는 "그 후"가 없어 마커를 못 그린다. 이때는
예전처럼 1개월 차트를 그리고 `coverKind: "data0"`으로 표시해뒀다가, 4일 뒤
워크플로가 돌 때 **딱 한 번** 마커판으로 다시 그린다(`_stale_data0`).

디자인 (dataviz 스킬 절차대로)
------------------------------
1. 형태: 단일 시계열 + 헤드라인 크기 → **스탯 타일 + 스파크라인**.
   시리즈가 하나라 범례 없음(제목이 시리즈를 지칭).
2. 색: 등락은 categorical이 아니라 **status**(good/critical).
   발행 전 구간은 시리즈가 아니라 문맥이라 muted ink를 쓴다.
3. 검증: `validate_palette.js "#0ca30c,#d03b3b" --mode light --surface #F4F5F7`
   → CVD separation **FAIL** (deutan ΔE 4.1). 빨강↔초록의 고전적 문제다.
   두 색이 한 차트에 같이 나오진 않지만, 색만으로는 등락을 구분할 수 없다.
   → 스킬이 규정한 완화책을 적용한다: **아이콘 + 라벨, 색 단독 금지.**
   등락률은 항상 `▲`/`▼` 화살표와 부호(+/-)를 함께 찍는다(중복 채널 2개).
   발행 전/후 구분도 색 단독이 아니라 **굵기 + 수직 마커선**을 같이 쓴다.
   나머지 검사(명도대·채도·정상시야 ΔE·대비)는 전부 PASS.
4. 마크: 선 2px(2x에서 4px), 끝점 마커 8px 이상, 기준선은 실선 헤어라인,
   그리드 없음(스파크라인), 점마다 숫자 찍지 않음.
5. 상호작용: 정적 PNG라 해당 없음.
6. 접근성: 시리즈 1개라 범례 불필요. 등락은 색 + 화살표 + 부호 3중 인코딩.
7. 렌더 후 눈으로 확인 — 아래 `_selftest()`가 마커판·신규판을 함께 뽑는다.

텍스트는 언어 중립으로 유지한다(종목 키·티커·날짜·퍼센트). 커버는 정적
이미지 한 장인데 앱은 3개국어라, 문장을 넣으면 반드시 어긋난다.
"""

# ── 팔레트 (dataviz references/palette.md 값) ──────────────────────────
SURFACE      = "#F4F5F7"            # Stacks의 기존 로고 커버 박스와 같은 면
INK_PRIMARY  = "#0b0b0b"
INK_SECOND   = "#52514e"
INK_MUTED    = "#898781"
BASELINE     = "#c3c2b7"
RING         = (11, 11, 11, 26)     # rgba(11,11,11,0.10)
GOOD         = "#0ca30c"            # status good
CRITICAL     = "#d03b3b"            # status critical
GOOD_TEXT    = "#006300"            # 라이트면 delta ↑ 텍스트
FLAT         = "#52514e"

S = 2                                # 2x 렌더 후 축소하지 않고 그대로 저장(레티나)
W, H = 568 * S, 200 * S              # 2.84:1 배너

COVER_GEN = 2                        # 자체 생성 커버 판(版). 올리면 기존 커버를 한 번씩 다시 그린다.
LEAD_DAYS = 10                       # 발행일 앞에 붙이는 문맥 거래일 수
MIN_AFTER = 2                        # 발행 후 이만큼 거래일이 있어야 "그 후 등락"이 성립
PLAIN_SPAN = 22                      # 마커를 못 그릴 때 보여줄 거래일 수(≈1개월)

FONT_DIRS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size, bold=False):
    """Noto CJK 우선(한글·일본어 종목명 대비), 없으면 DejaVu."""
    cands = ([FONT_DIRS[1], FONT_DIRS[0]] if bold else [FONT_DIRS[0]]) + \
            ([FONT_DIRS[3], FONT_DIRS[2]] if bold else [FONT_DIRS[2]])
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size, index=0)
            except Exception:
                continue
    return ImageFont.load_default()


def _window(closes, dates, pub_date):
    """발행일을 앵커로 삼는 표시 구간을 고른다.

    반환 (closes, dates, ai). `ai`가 None이면 앵커를 못 잡은 것 —
    예전처럼 최근 1개월만 그리는 '신규판'으로 떨어진다.
    """
    if not (pub_date and dates and len(dates) == len(closes)):
        return closes[-PLAIN_SPAN:], (dates or [])[-PLAIN_SPAN:], None
    # 발행일이 휴장일이면 그 다음 거래일이 앵커가 된다.
    ai = next((i for i, d in enumerate(dates) if d >= pub_date), None)
    if ai is None or (len(closes) - 1 - ai) < MIN_AFTER:
        return closes[-PLAIN_SPAN:], dates[-PLAIN_SPAN:], None
    st = max(0, ai - LEAD_DAYS)
    return closes[st:], dates[st:], ai - st


def render_quote_cover(out_path, entity, ticker, closes, dates=None, pub_date=None):
    """종가 시계열 하나를 스탯 타일 + 스파크라인 커버로 그린다.

    entity   : 표시할 종목명 (items.json entities 키, 예 "SK HYNIX")
    ticker   : 예 "000660.ks"
    closes   : 종가 리스트 (오래된 것 → 최신)
    dates    : 선택. closes와 같은 길이의 'YYYY-MM-DD' 리스트
    pub_date : 선택. 기사 발행일 'YYYY-MM-DD'. 주면 그날을 앵커로 삼아
               마커를 찍고 히어로 숫자를 "발행 후 등락"으로 바꾼다.

    반환: "marked" | "plain" | False
    """
    closes = [float(c) for c in closes if c is not None]
    if dates and len(dates) != len(closes):
        dates = None
    if len(closes) < 5:
        return False

    closes, dates, ai = _window(closes, dates, pub_date)
    if len(closes) < 5:
        return False

    anchor = closes[ai] if ai is not None else closes[0]
    last = closes[-1]
    if anchor <= 0:
        return False
    pct = (last - anchor) / anchor * 100.0

    if pct > 0.05:
        mark, delta_ink, arrow, sign = GOOD, GOOD_TEXT, "▲", "+"
    elif pct < -0.05:
        mark, delta_ink, arrow, sign = CRITICAL, CRITICAL, "▼", "-"
    else:
        mark, delta_ink, arrow, sign = FLAT, INK_SECOND, "–", ""

    im = Image.new("RGB", (W, H), SURFACE)
    d = ImageDraw.Draw(im, "RGBA")

    # 헤어라인 링
    d.rectangle([0, 0, W - 1, H - 1], outline=RING, width=S)

    pad = 22 * S
    left_w = int(W * 0.40)

    # ── 좌: 스탯 타일 ─────────────────────────────────────────────
    f_name = _font(19 * S, bold=True)
    f_tick = _font(12 * S)
    f_hero = _font(40 * S, bold=True)
    f_note = _font(11 * S)

    y = pad
    name = entity if len(entity) <= 18 else entity[:17] + "…"
    d.text((pad, y), name, font=f_name, fill=INK_PRIMARY)
    y += int(f_name.size * 1.25)
    d.text((pad, y), ticker.upper(), font=f_tick, fill=INK_MUTED)

    # 히어로: 화살표 + 부호 + 값 (색 단독 금지 — CVD 완화)
    hero = f"{arrow} {sign}{abs(pct):.1f}%"
    hy = int(H * 0.44)
    d.text((pad, hy), hero, font=f_hero, fill=delta_ink)

    # 노트 줄은 히어로 숫자가 "어디서부터"인지를 문장 없이 밝힌다.
    # 마커판이면 시작점이 발행일이다 — 이 한 줄이 앵커의 설명 전부다.
    note_y = hy + int(f_hero.size * 1.18)
    if dates:
        start = dates[ai] if ai is not None else dates[0]
        span = f"{start} → {dates[-1][5:]}"
    else:
        span = "1M"
    d.text((pad, note_y), f"{span}  ·  close", font=f_note, fill=INK_MUTED)

    # ── 우: 스파크라인 ────────────────────────────────────────────
    cx0, cx1 = left_w, W - pad
    cy0, cy1 = pad + 6 * S, H - pad - 10 * S
    lo, hi = min(closes), max(closes)
    # y축을 데이터에만 맞추면 0.5% 움직임도 폭락처럼 보인다(축 절단 왜곡).
    # 앵커가(= 히어로 숫자의 기준점) 중앙에 오도록 최소 ±2.5% 밴드를 보장한다.
    floor_lo, floor_hi = anchor * 0.975, anchor * 1.025
    lo, hi = min(lo, floor_lo), max(hi, floor_hi)
    rng = (hi - lo) or (hi * 0.02 or 1.0)
    lo -= rng * 0.12
    hi += rng * 0.12
    rng = hi - lo

    n = len(closes)
    pts = [(cx0 + (cx1 - cx0) * i / (n - 1),
            cy1 - (c - lo) / rng * (cy1 - cy0)) for i, c in enumerate(closes)]

    # 기준선(앵커 종가) — 등락의 기준점. 점선은 안티패턴(노이즈·"예측"으로 읽힘)이라
    # 면에서 한 톤 내려간 실선 헤어라인으로 그린다.
    by = cy1 - (anchor - lo) / rng * (cy1 - cy0)
    d.line([(cx0, by), (cx1, by)], fill=BASELINE, width=S)

    rgb = tuple(int(mark[i:i + 2], 16) for i in (1, 3, 5))

    if ai is None:
        # 신규판 — 앵커를 못 잡았다. 예전과 같은 단색 스파크라인.
        d.polygon([(cx0, cy1)] + pts + [(cx1, cy1)], fill=rgb + (30,))
        d.line(pts, fill=mark, width=2 * S, joint="curve")
    else:
        mx = pts[ai][0]
        # 발행일 수직 마커 — 선(위치) + 라벨(날짜) 두 채널.
        d.line([(mx, cy0 - 4 * S), (mx, cy1 + 4 * S)], fill=BASELINE, width=S)
        # 발행 전: 문맥이므로 muted·얇게. 발행 후: status 색·굵게 + 면 채움.
        if ai > 0:
            d.line(pts[:ai + 1], fill=INK_MUTED, width=S, joint="curve")
        post = pts[ai:]
        d.polygon([(mx, cy1)] + post + [(post[-1][0], cy1)], fill=rgb + (30,))
        d.line(post, fill=mark, width=2 * S, joint="curve")
        # 앵커 점 — 면 색 링을 둘러 선 위에서도 읽히게
        axp, ayp = pts[ai]
        ar = 4 * S
        d.ellipse([axp - ar - S, ayp - ar - S, axp + ar + S, ayp + ar + S], fill=SURFACE)
        d.ellipse([axp - ar, ayp - ar, axp + ar, ayp + ar], fill=INK_SECOND)
        # 날짜 라벨 — 마커선 오른쪽. 오른쪽 여백이 모자라면 왼쪽으로 뒤집는다.
        f_mark = _font(10 * S, bold=True)
        lab = dates[ai][5:] if dates else ""
        if lab:
            lw = d.textlength(lab, font=f_mark)
            lx = mx + 5 * S
            if lx + lw > cx1:
                lx = mx - 5 * S - lw
            d.text((lx, cy0 - 5 * S), lab, font=f_mark, fill=INK_MUTED)

    # 끝점 마커 (8px 이상) — 면 색 링을 둘러 겹침 방지
    ex, ey = pts[-1]
    r = 5 * S
    d.ellipse([ex - r - S, ey - r - S, ex + r + S, ey + r + S], fill=SURFACE)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=mark)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    im.save(out_path, optimize=True)
    return "marked" if ai is not None else "plain"


def _main_ticker(item, entities):
    """카드의 주 종목을 고른다. tags(대문자 엔티티 키) → cover.label 순."""
    keys = [str(t).upper() for t in (item.get("tags") or [])]
    lbl = ((item.get("cover") or {}).get("label") or "").upper()
    if lbl:
        keys.append(lbl)
    for k in keys:
        e = entities.get(k)
        if isinstance(e, dict) and e.get("ticker"):
            return k, e["ticker"]
    return None, None


def make_data_cover(item, out_path, entities=None):
    """사다리 C: 카드의 주 종목 종가로 발행일 마커가 붙은 커버를 그린다.

    실패(종목 없음·시세 없음·데이터 부족)하면 False를 돌려 사다리가
    기존 일반 커버로 떨어지게 한다. 성공하면 "marked"/"plain".

    ⚠ `r=6mo`를 받는 이유: 발행일이 한 달 넘은 기사도 앵커를 잡아야 한다.
    실제로 그리는 구간은 `_window()`가 발행일 기준으로 잘라낸다.
    워커가 지원하는 값은 1d·5d·1mo·6mo·1y 뿐이다(worker/index.js RANGES).
    """
    if not entities:
        return False
    name, ticker = _main_ticker(item, entities)
    if not ticker:
        return False
    try:
        url = f"{WORKER}/quote?s={ticker}&r=6mo"
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        closes = j.get("closes") or (j.get("data") or {}).get("closes")
        dates = j.get("dates") or (j.get("data") or {}).get("dates")
        if not closes or len(closes) < 5:
            return False
        pub = (item.get("date") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", pub or ""):
            pub = None
        return render_quote_cover(out_path, name, ticker, closes, dates, pub)
    except Exception as e:
        log(f"  [warn C] {item.get('id')}: {e}")
        return False


def _stale_data0(item):
    """마커 없이 그렸던 커버를 이제 다시 그려도 되는가.

    발행 후 4일(주말 포함)이면 거래일 2일은 확보된다. 이 조건 없이 매번
    다시 그리면 6시간마다 PNG가 바뀌어 커밋이 무한히 쌓인다.
    """
    from datetime import date
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", item.get("date") or "")
    if not m:
        return False
    try:
        return (date.today() - date(*(int(x) for x in m.groups()))).days >= 4
    except Exception:
        return False


def process(item, entities):
    """사다리 A → B → C. 하나라도 성공하면 그 결과를 돌려준다.

    ⚠ A·B는 `docUrl`이 있어야 동작하지만 **C는 필요 없다.**
    (초판은 docUrl이 없으면 곧장 return 해서 C가 영원히 안 돌았다.)
    """
    iid = item.get("id")
    if not iid:
        return None

    out_rel = f"{COVER_DIR}/{iid}.png"
    kind = item.get("coverKind") or ""

    # 자체 생성 차트만 다시 그릴 수 있다. 두 경우뿐이다:
    #  · 판(COVER_GEN)이 올랐다 → 전부 한 번씩 새 디자인으로 재렌더
    #  · "data0"(발행 직후라 마커를 못 그림)인데 기사가 나이를 먹었다 → 1회 승급
    # A(문서)·B(og:image) 커버는 절대 다시 만들지 않는다 — 외부 요청이 늘 뿐이다.
    redraw = kind in ("data", "data0") and (
        item.get("coverGen") != COVER_GEN or (kind == "data0" and _stale_data0(item))
    )

    if item.get("coverArt") and not redraw:
        return None
    if os.path.exists(out_rel) and not redraw:
        return {"coverArt": out_rel, "coverKind": kind or "doc"}

    if redraw:
        res = make_data_cover(item, out_rel, entities)
        if not res:
            return None                      # 시세를 못 받으면 기존 커버를 그대로 둔다
        log(f"  [C:{res}] {iid}: 차트 커버 재렌더 (gen {COVER_GEN})")
        return {"coverArt": out_rel, "coverGen": COVER_GEN,
                "coverKind": "data" if res == "marked" else "data0"}

    doc = item.get("docUrl") or ""
    doc_ok = bool(doc) and doc.startswith("http") and not blocked(doc)

    if doc_ok:
        # Tier A — 1차 문서 렌더
        try:
            head_ct = ""
            try:
                head_ct = requests.head(doc, headers=UA, timeout=TIMEOUT,
                                        allow_redirects=True).headers.get("content-type", "")
            except Exception:
                pass
            if looks_like_pdf(doc, head_ct):
                data, _ = fetch_bytes(doc)
                if data[:5] == b"%PDF-":
                    render_pdf_strip(data, out_rel)
                    log(f"  [A] {iid}: document strip <- {doc}")
                    return {"coverArt": out_rel, "coverKind": "doc",
                            "coverCredit": urlparse(doc).hostname}
        except Exception as e:
            log(f"  [warn A] {iid}: {e}")

        # Tier B — 링크된 페이지의 og:image (핫링크만)
        try:
            img = og_image(doc)
            if img:
                log(f"  [B] {iid}: og:image <- {img}")
                return {"coverArt": img, "coverKind": "og",
                        "coverCredit": urlparse(doc).hostname}
        except Exception as e:
            log(f"  [warn B] {iid}: {e}")

    # Tier C — 자체 생성 차트 (docUrl 불필요)
    try:
        res = make_data_cover(item, out_rel, entities)
        if res:
            log(f"  [C:{res}] {iid}: 자체 생성 차트 커버")
            return {"coverArt": out_rel, "coverGen": COVER_GEN,
                    "coverKind": "data" if res == "marked" else "data0"}
    except Exception as e:
        log(f"  [warn C] {iid}: {e}")

    return None


def main():
    if not os.path.exists(ITEMS):
        log("items.json missing — nothing to do")
        return 0
    with open(ITEMS, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"] if isinstance(data, dict) and "items" in data else data
    entities = data.get("entities", {}) if isinstance(data, dict) else {}

    changed = 0
    for item in items:
        got = process(item, entities)
        if got:
            item.update(got)
            changed += 1

    if changed:
        with open(ITEMS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
    log(f"cover assets: {changed} item(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

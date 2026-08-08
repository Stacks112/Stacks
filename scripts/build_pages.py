"""Stacks static-page + sitemap + RSS generator.

Reads items.json and produces, for search engines and syndication:
  p/{id}.html   one crawlable article page per item (title, summary in
                all 3 languages, structured data) that also links into
                the app for humans.
  articles.html a plain hub page linking every article (crawl entry).
  sitemap.xml   every page with lastmod, for Google/Naver.
  robots.txt    allow all + sitemap pointer.
  feed.xml      Stacks' own RSS (enables feed readers + no-code auto-
                posting to X/Threads/Telegram via Zapier/IFTTT/Make).

Run by GitHub Actions whenever items.json changes, so the SEO layer and
the RSS feed stay in lockstep with published content. No external deps.
"""

import html
import json
import re
import hashlib
import os
import urllib.parse
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE = "https://stacksdaily.com/"
SITE = "Stacks"
TAGLINE = {
    "ko": "전 세계 투자 고수들의 글을, 당신의 언어로",
    "en": "The world's best investing minds, in your language",
    "ja": "世界の投資の達人たちの記事を、あなたの言語で",
}
LANG_LABEL = {"ko": "한국어", "en": "English", "ja": "日本語"}
E = html.escape


def LD(obj):
    """Serialise a JSON-LD object for an inline <script> block.

    json.dumps escapes quotes and backslashes but never "<", so a title
    containing "</script>" closes the block early and everything after it is
    parsed as live HTML. Card text is produced by an automated publisher that
    reads third-party feeds, which is exactly the path an injected payload
    would take. Escaping the three characters as \\uXXXX keeps the JSON
    byte-identical to a parser while making it inert to the HTML tokenizer.
    """
    return (json.dumps(obj, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026"))


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{3,8}$")


def hexcolor(v, fallback):
    """A cover colour goes straight into a <style> block, so anything that is
    not a plain hex literal could close the declaration and add rules of its
    own (or a url() that phones home)."""
    v = str(v or "").strip()
    return v if HEX_RE.match(v) else fallback


def safe_href(u, fallback="#"):
    """Only plain http(s) links survive; javascript:/data: become dead."""
    s = str(u or "").strip()
    return s if re.match(r"^https?://", s, re.I) else fallback


NAME_ALIAS = {"메르": "메르 (ranto28)"}
def dispname(x):
    return NAME_ALIAS.get(x, x)


# ---- gist markers (see claude/prompts/publish-v4.3.md [4-E]) ----
# The publishing routine writes structure into the gist as line-leading
# markers so a new block type never needs a schema change. The app renders
# them in gistRich(); these pages have to do the same, or the raw markers show
# up as literal text on every SEO page and in every meta description.

# Emitted per page only when the body actually contains one of these blocks.
# Article pages inline their CSS, so an unconditional 1.3 KB would land in all
# 462 of them for the handful of cards that use a check or compare panel.
BLOCK_CSS = """:root{--s1:#2563EB;--s2:#F59E0B;--s3:#0D9488;--s4:#7C3AED;--track:#EEF0F4;--ring:#fff}
.gist+.gist{margin-top:1em}
h2.gsub{font-size:19px;line-height:1.4;margin:1.6em 0 .5em;padding-left:9px;border-left:3px solid #3B82F6}
.srcq{margin:0 0 20px;padding:12px 16px;border-left:3px solid #3B82F6;background:#F6F7F9;border-radius:0 10px 10px 0}
.srcq blockquote{margin:0;quotes:none}
.srcq p{margin:0 0 6px;font-size:15px;line-height:1.62;color:#3E414B}
.srcq-c{font-size:12.5px;color:#8E93A0}
.srcq-c a{color:#8E93A0}
.xreal{margin:0 0 20px}
.xemb{padding:12px 14px;border:1px solid #ECEDF1;border-radius:14px;background:#fff}
.xemb-top{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.xemb-av{width:34px;height:34px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#4b5563,#1f2937);color:#fff;font-weight:800;font-size:14px}
.xemb-nm{display:flex;flex-direction:column;line-height:1.25;min-width:0}
.xemb-nm b{font-size:13.5px;font-weight:800;color:#17181C}
.xemb-nm span{font-size:12px;color:#8E93A0}
.xemb-logo{margin-left:auto;font-size:15px;font-weight:900;color:#17181C;opacity:.7;text-decoration:none}
.xemb-body p{margin:0 0 7px;font-size:14px;line-height:1.6;color:#17181C}
.xemb-body p:last-child{margin-bottom:0}
.xemb-q{margin-top:8px;padding:9px 11px;border:1px solid #ECEDF1;border-radius:11px;font-size:12.5px;line-height:1.55;color:#5B6070}
.xemb-d{margin-top:9px;font-size:11.5px;color:#8E93A0}
.xemb-d a{color:#8E93A0;text-decoration:underline;text-underline-offset:2px}
.xreal-slot{display:none}
.xreal.x-on>.xemb{display:none}
.xreal.x-on>.xreal-slot{display:flow-root}
.xreal-slot iframe{max-width:100%!important}
.chk{margin:16px 0;border:1px solid #ECEDF1;border-radius:12px;overflow:hidden}
.chk-g{display:flex;flex-wrap:wrap}
.chk-c{flex:1 1 33%;min-width:110px;padding:12px 10px;text-align:center;border-right:1px solid #ECEDF1}
.chk-c i{display:block;font-style:normal;font-size:11.5px;color:#8E93A0;margin-bottom:4px}
.chk-c b{display:block;font-size:18px}
.chk-n{margin:0;padding:11px 13px;border-top:1px solid #ECEDF1;font-size:14.5px;line-height:1.6}
.chk-s{margin:0;padding:0 13px 10px;font-size:12px;color:#8E93A0}
.cmp{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}
.cmp-c{flex:1 1 240px;padding:12px 14px;border:1px solid #ECEDF1;border-radius:12px}
.cmp-c.cmp-b{border-color:#3B82F6}
.cmp-c i{display:block;font-style:normal;font-size:11.5px;font-weight:800;color:#8E93A0;margin-bottom:6px}
.cmp-c p{margin:0;font-size:14.5px;line-height:1.6}
.cmp-vs{align-self:center;width:32px;height:32px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:12px;color:#fff;background:linear-gradient(135deg,#EF4444,#3B82F6)}
.gimg{margin:16px 0}
.gimg img{display:block;width:100%;max-width:520px;border:1px solid #ECEDF1;border-radius:12px;background:#fff}
.gimg figcaption{margin-top:6px;font-size:12px;color:#8E93A0}
.gimg figcaption a{color:#8E93A0}
.gref{margin:6px 0 14px;font-size:13px}
.gref a{color:#8E93A0}
.gcardw{margin:12px 0 16px;max-width:520px}
.gcard{position:relative;display:block;border:1px solid #ECEDF1;border-radius:14px;overflow:hidden;text-decoration:none;background:#F6F7F9}
.gcard img{display:block;width:100%;max-height:250px;object-fit:cover}
.gcard-t{position:absolute;left:10px;right:10px;bottom:10px;padding:5px 10px;border-radius:8px;background:rgba(0,0,0,.65);color:#fff;font-size:13px;line-height:1.4;font-weight:600}
.gcard-src{margin-top:6px;font-size:12px;color:#8E93A0}
.dbk{margin:18px 0}
.dbk-n{margin:11px 0 0;font-size:14.5px;line-height:1.6}
.dbk-s{margin:6px 0 0;font-size:12px;color:#8E93A0;line-height:1.5}
.bar-r{margin:0 0 13px}
.bar-r:last-of-type{margin-bottom:0}
.bar-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 6px}
.bar-h i{font-style:normal;font-size:12.5px;line-height:1.45;color:#5B6070}
.bar-h b{font-size:15.5px;white-space:nowrap}
.bar-t{height:10px;border-radius:5px;background:var(--track)}
.bar-f{height:100%;border-radius:5px;background:var(--s1);min-width:3px}
.bar-x{display:inline-block;margin:2px 0 0;padding:3px 9px;border-radius:999px;background:var(--track);font-size:12.5px;font-weight:800;color:var(--s1)}
.shr-t{display:flex;height:26px;gap:2px;margin:2px 0 0}
.shr-g{height:100%;min-width:3px}
.shr-g:first-child{border-radius:6px 0 0 6px}
.shr-g:last-child{border-radius:0 6px 6px 0}
.shr-l{display:flex;flex-wrap:wrap;gap:7px 18px;margin:11px 0 0}
.shr-i{display:flex;align-items:center;gap:7px;font-size:12.5px;color:#5B6070}
.shr-d{width:9px;height:9px;border-radius:2px;flex:0 0 auto}
.shr-i b{color:#111318;font-weight:700}
.tml{margin:0;padding:2px 0 0 22px;list-style:none;position:relative}
.tml:before{content:"";position:absolute;left:4px;top:9px;bottom:9px;width:2px;background:#E7E9EE}
.tml li{position:relative;margin:0 0 15px}
.tml li:last-child{margin-bottom:0}
.tml li:before{content:"";position:absolute;left:-22px;top:4px;width:10px;height:10px;border-radius:50%;background:var(--s1);box-shadow:0 0 0 3px var(--ring)}
.tml li.fut:before{background:var(--ring);border:2px dashed #9AA1AE;box-shadow:none}
.tml i{display:block;font-style:normal;font-size:12px;font-weight:800;color:#5B6070;margin:0 0 3px}
.tml p{margin:0;font-size:14.5px;line-height:1.6}
.flw{display:flex;flex-wrap:wrap;align-items:stretch;gap:8px;margin:0}
.flw-s{flex:1 1 155px;min-width:0;padding:11px 13px;border:1px solid #E7E9EE;border-radius:11px;background:#FAFBFC}
.flw-s b{display:block;font-size:13.5px;line-height:1.45;margin:0 0 4px}
.flw-s span{display:block;font-size:12.5px;line-height:1.55;color:#5B6070}
.flw-a{flex:0 0 auto;align-self:center;color:#9AA1AE;font-size:15px;font-weight:800}
@media(max-width:520px){.flw{display:block}.flw-s{margin:0}.flw-a{display:block;margin:5px 0 5px 18px;transform:rotate(90deg);width:1em}}
@media(prefers-color-scheme:dark){.srcq,.cmp-c{background:#1A1B21}.srcq p{color:#C9CDD6}
  .chk,.chk-c,.chk-n,.cmp-c{border-color:#26272E}.otherlang{border-color:#26272E}
  :root{--s1:#3B82F6;--s2:#BC8404;--s3:#0FA391;--s4:#8257F0;--track:#26272E;--ring:#141519}
  .bar-x{color:#7FB0FA}
  .bar-h i,.shr-i,.tml i,.flw-s span{color:#9AA1AE}
  .shr-i b{color:#E8EAEE}
  .tml:before{background:#2E3038}
  .flw-s{background:#1A1B21;border-color:#26272E}}"""


def block_css_for(body):
    if not any(k in body for k in ('class="gsub"', 'class="srcq"', 'class="xemb"', 'class="xreal"', 'class="chk"', 'class="cmp"', 'class="gimg"', 'class="gref"', 'class="gcard', 'class="dbk')):
        return ""
    return BLOCK_CSS


def strip_markers(text):
    """Plain prose. Subheadings keep their text (they are real sentences);
    the data rows of a check/compare block are dropped, since a description
    made of "4.71%|2.28%" reads as noise in a search result."""
    out = []
    for line in str(text or "").split("\n"):
        if line.startswith("## "):
            out.append(line[3:].strip())
        elif line.startswith("@@"):
            # any block marker: CHK, CMP, IMG, future ones
            continue
        else:
            out.append(line)
    return "\n".join(out)


def lang_text(v, lang):
    """sum3 and split were Korean-only when introduced, so older cards store a
    bare string. A string still means Korean (hidden in en/ja, as the app does);
    an {en,ko,ja} dict gives each language its own text. No migration needed.
    Mirrors langText() in index.html -- if one changes, change both."""
    if not v:
        return ""
    if isinstance(v, str):
        return v if lang == "ko" else ""
    return (v.get(lang) or "") if isinstance(v, dict) else ""


def sum3_block(item, lang, U):
    """The three-line standing of the story. The app shows this above 'why' on
    lab cards; the indexed page had nothing, which is where it is worth the most
    -- it is the part a search result can actually use."""
    if not item.get("lab"):
        return ""
    txt = lang_text(item.get("sum3"), lang)
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    if not lines:
        return ""
    return ('<div class="sum3"><b>%s</b><ul>%s</ul></div>'
            % (E(U["sum3"]), "".join("<li>%s</li>" % E(l) for l in lines)))


def split_block(item, lang, U):
    """What would have to happen for either reading to be right. Only on cards
    that do not resolve the argument, and never on lab cards -- the app hides it
    there too, so the two renderers agree."""
    if item.get("lab"):
        return ""
    txt = lang_text(item.get("split"), lang)
    if not txt:
        return ""
    body = "".join("<p>%s</p>" % E(l) for l in txt.split("\n") if l.strip())
    return '<div class="splitb"><b>%s</b>%s</div>' % (E(U["split"]), body)


SUM3_CSS = """.sum3,.splitb{margin:20px 0 0;padding:13px 15px;border-radius:12px}
.sum3{background:#F6F7F9;border:1px solid #ECEDF1}
.splitb{border:1px dashed #D7DAE0}
.sum3>b,.splitb>b{display:block;font-size:12px;letter-spacing:.02em;color:#5B6070;margin-bottom:7px}
.sum3 ul{list-style:none;margin:0;padding:0}
.sum3 li{position:relative;padding-left:15px;margin:0 0 7px;font-size:15px;line-height:1.62}
.sum3 li:last-child{margin-bottom:0}
.sum3 li:before{content:"\u00B7";position:absolute;left:3px;color:#8E93A0;font-weight:700}
.splitb p{margin:0 0 5px;font-size:14.5px;line-height:1.6}
.splitb p:last-child{margin-bottom:0}
/* 세 줄 요약은 카드가 아니라 본문 끝의 구분선 다음에 온다 (편집 가이드 §6). */
.sum3{background:none;border:0;border-top:2px solid currentColor;border-radius:0;margin:34px 0 0;padding:17px 0 0}
.sum3>b{color:inherit;font-size:12.5px;font-weight:800;letter-spacing:.03em;margin-bottom:12px}
.sum3 li{padding-left:16px;margin:0 0 11px;font-size:15.5px;line-height:1.7}
.sum3 li:before{color:inherit;left:2px}"""


# ── 데이터 블록 (2026-08-04, 발행 규칙 v4.7) ──────────────────────────
# 그래픽 어휘가 표(@@CHK@@)와 VS(@@CMP@@) 둘뿐이라 모든 카드가 같은 모양으로
# 읽히던 것을 넓힌 것이다. 형태는 "독자가 어디서 막히는가"가 고른다:
#   @@BAR@@   이 숫자가 큰 건가 작은 건가   라벨|표시값|숫자 …@@각주@@출처
#   @@SHARE@@ 무엇이 얼마를 차지하나       라벨|표시값|숫자 …@@각주@@출처
#   @@TIME@@  언제 무슨 일이 있었나         날짜|사건 …@@각주@@출처  (날짜 앞 > = 예정)
#   @@FLOW@@  무엇이 어디로 가나            단계|설명 …@@각주
# 렌더러가 세 곳(앱 index.html · 이 파일 · scripts/weekly_email.py)이다.
# 하나를 고치면 나머지 둘도 같이 본다 — check_email_render.py 가 셋의 마커
# 목록이 갈라지는 것을 막고 있다.

# 색각 이상·명암 검증을 통과한 순서다(dataviz 팔레트 검사기, 명도대 L 0.43~0.77,
# 인접쌍 CVD ΔE 최소 16.6). 순서를 섞거나 5번째 색을 만들어 쓰지 않는다.
SERIES = ("var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)")


def _dnum(s):
    """표시값과 별개로 막대 길이에 쓸 숫자. 쉼표·단위는 버린다."""
    try:
        return float(re.sub(r"[^0-9.\-]", "", str(s or "")) or "x")
    except ValueError:
        return None


def _dcells(s, n):
    """'a|b|c|a|b|c' -> [(a,b,c), …]. 모자란 꼬리 조각은 버린다."""
    p = [x.strip() for x in str(s or "").split("|")]
    return [tuple(p[i:i + n]) for i in range(0, len(p) - n + 1, n)]


def _dtail(parts):
    note = ('<p class="dbk-n">%s</p>' % E(parts[1])) if len(parts) > 1 and parts[1] else ""
    src = ('<p class="dbk-s">%s</p>' % E(parts[2])) if len(parts) > 2 and parts[2] else ""
    return note + src


def _blk_bar(payload):
    parts = payload.split("@@")
    rows = _dcells(parts[0], 3)
    if not rows:
        return ""
    animated = len(parts) > 3 and parts[3].strip().lower() == "animate"
    vals = [_dnum(v) for _, _, v in rows]
    top = max([v for v in vals if v is not None] or [0])
    bars = []
    for i, ((lab, disp, _), v) in enumerate(zip(rows, vals)):
        w = max((v / top * 100) if (top and v is not None) else 0, 0.4)
        style = ("--bar-w:%.4g%%;--bar-delay:%dms" % (w, i * 110)
                 if animated else "width:%.4g%%" % w)
        bars.append(
            '<div class="bar-r"><div class="bar-h"><i>%s</i><b>%s</b></div>'
            '<div class="bar-t"><div class="bar-f" style="%s"></div></div></div>'
            % (E(lab), E(disp), style))
    body = "".join(bars)
    # 두 값을 재는 블록에서 배수는 독자가 암산할 것이 아니라 우리가 보여줄 것이다.
    badge, ok = "", [v for v in vals if v]
    if len(rows) == 2 and len(ok) == 2 and min(ok) > 0:
        r = max(ok) / min(ok)
        if r >= 1.5:
            badge = '<div class="bar-x">&#215;%s</div>' % ("%.1f" % r).rstrip("0").rstrip(".")
    anim_css = ""
    if animated:
        anim_css = ('<style>.bar-anim .bar-f{width:var(--bar-w,0%);transform-origin:left center;'
                    'animation:bar-grow .82s cubic-bezier(.22,1,.36,1) both;animation-delay:var(--bar-delay,0ms)}'
                    '.bar-anim .bar-r:nth-child(2) .bar-f{background:color-mix(in srgb,var(--s1) 72%,#fff)}'
                    '.bar-anim .bar-r:nth-child(3) .bar-f{background:color-mix(in srgb,var(--s1) 46%,#fff)}'
                    '@keyframes bar-grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}'
                    '@media(prefers-reduced-motion:reduce){.bar-anim .bar-f{animation:none;transform:none}}'
                    '@media(prefers-color-scheme:dark){.bar-anim .bar-r:nth-child(2) .bar-f{background:color-mix(in srgb,var(--s1) 72%,#141519)}'
                    '.bar-anim .bar-r:nth-child(3) .bar-f{background:color-mix(in srgb,var(--s1) 46%,#141519)}}</style>')
    return '%s<div class="dbk%s">%s%s%s</div>' % (
        anim_css, " bar-anim" if animated else "", body, badge, _dtail(parts))


def _blk_share(payload):
    parts = payload.split("@@")
    rows = _dcells(parts[0], 3)
    if not rows:
        return ""
    vals = [(_dnum(v) or 0) for _, _, v in rows]
    tot = sum(vals) or 1.0
    segs = "".join('<span class="shr-g" style="width:%.4g%%;background:%s"></span>'
                   % (max(v / tot * 100, 0.8), SERIES[i % len(SERIES)])
                   for i, v in enumerate(vals))
    # 조각 안에 글자를 넣지 않는다 — 값과 이름은 아래 범례가 본문 색으로 진다.
    leg = "".join('<span class="shr-i"><span class="shr-d" style="background:%s"></span>%s <b>%s</b></span>'
                  % (SERIES[i % len(SERIES)], E(r[0]), E(r[1])) for i, r in enumerate(rows))
    return ('<div class="dbk"><div class="shr-t">%s</div><div class="shr-l">%s</div>%s</div>'
            % (segs, leg, _dtail(parts)))


def _blk_time(payload):
    parts = payload.split("@@")
    rows = _dcells(parts[0], 2)
    if not rows:
        return ""
    lis = "".join('<li%s><i>%s</i><p>%s</p></li>'
                  % (' class="fut"' if w.startswith(">") else "",
                     E(w.lstrip(">").strip()), E(what))
                  for w, what in rows)
    return '<div class="dbk"><ul class="tml">%s</ul>%s</div>' % (lis, _dtail(parts))


def _blk_flow(payload):
    parts = payload.split("@@")
    rows = _dcells(parts[0], 2)
    if not rows:
        return ""
    steps = []
    for i, (t, d) in enumerate(rows):
        if i:
            steps.append('<div class="flw-a">&#8594;</div>')
        steps.append('<div class="flw-s"><b>%s</b>%s</div>'
                     % (E(t), ('<span>%s</span>' % E(d)) if d else ""))
    return '<div class="dbk"><div class="flw">%s</div>%s</div>' % ("".join(steps), _dtail(parts))


def gist_blocks(gist):
    """Marked-up gist -> page HTML. Same markers as the app."""
    html, buf = [], []

    def flush():
        t = "\n".join(buf).strip("\n")
        del buf[:]
        if t:
            html.append('<p class="gist">%s</p>' % E(t))

    for line in str(gist or "").split("\n"):
        if line.startswith("## "):
            flush()
            html.append("<h2 class=\"gsub\">%s</h2>" % E(line[3:].strip()))
        elif line.startswith("@@CHK@@"):
            flush()
            parts = line[7:].split("@@")
            cells = (parts[0] or "").split("|")
            rows = "".join(
                "<div class=\"chk-c\"><i>%s</i><b>%s</b></div>" % (E(cells[j]), E(cells[j + 1]))
                for j in range(0, len(cells) - 1, 2)
            )
            html.append(
                '<div class="chk"><div class="chk-g">%s</div>%s%s</div>' % (
                    rows,
                    ('<p class="chk-n">%s</p>' % E(parts[1])) if len(parts) > 1 and parts[1] else "",
                    ('<p class="chk-s">%s</p>' % E(parts[2])) if len(parts) > 2 and parts[2] else "",
                )
            )
        elif line.startswith("@@CMP@@"):
            flush()
            c = (line[7:].split("|") + ["", "", "", ""])[:4]
            html.append(
                '<div class="cmp"><div class="cmp-c"><i>%s</i><p>%s</p></div>'
                '<div class="cmp-vs">VS</div>'
                '<div class="cmp-c cmp-b"><i>%s</i><p>%s</p></div></div>'
                % (E(c[0]), E(c[1]), E(c[2]), E(c[3]))
            )
        elif line.startswith("@@BAR@@"):
            flush()
            html.append(_blk_bar(line[7:]))
        elif line.startswith("@@SHARE@@"):
            flush()
            html.append(_blk_share(line[9:]))
        elif line.startswith("@@TIME@@"):
            flush()
            html.append(_blk_time(line[8:]))
        elif line.startswith("@@FLOW@@"):
            flush()
            html.append(_blk_flow(line[8:]))
        elif line.startswith("@@REF@@"):
            flush()
            r = (line[7:].split("|") + ["", "", ""])[:3]
            host = ""
            m2 = re.match(r"https?://(?:www\.)?([^/]+)", r[1] or "")
            if m2:
                host = m2.group(1)
            if r[2]:
                html.append(
                    '<div class="gcardw"><a class="gcard" href="%s" rel="noopener" target="_blank">'
                    '<img src="%s" alt="" loading="lazy"><span class="gcard-t">%s</span></a>'
                    '%s</div>'
                    % (E(r[1] or "#"), E(r[2]), E(r[0]),
                       ('<div class="gcard-src">출처: %s</div>' % E(host)) if host else ""))
            else:
                html.append('<div class="gref"><a href="%s" rel="noopener" target="_blank">%s &#8599;</a></div>'
                            % (E(r[1] or "#"), E(r[0])))
        elif line.startswith("@@IMG@@"):
            flush()
            m = (line[7:].split("|") + ["", "", "", ""])[:4]
            cap = ""
            if m[1]:
                credit = (' · <a href="%s" rel="noopener" target="_blank">%s</a>'
                          % (E(m[3] or "#"), E(m[2]))) if m[2] else ""
                cap = "<figcaption>%s%s</figcaption>" % (E(m[1]), credit)
            html.append('<figure class="gimg"><img src="%s" alt="%s" loading="lazy">%s</figure>'
                        % (E(m[0]), E(m[1]), cap))
        else:
            buf.append(line)
    flush()
    return "".join(html)


QUOTE_EXCERPT_LIMIT = 110


def _excerpt_lines(lines, limit=QUOTE_EXCERPT_LIMIT):
    """Cap an EMBEDS-sourced quote to a genuine short excerpt.

    embeds.json stores the oEmbed text verbatim for the app's live tweet
    widget, which for most posts runs close to X's 280-character limit --
    2026-07-29 data: 99 of 122 entries are 200+ chars, i.e. effectively the
    whole tweet. That's fine for the widget (X's own embed, author's own
    surface) but not for a quoted excerpt on a static page, which about.html
    promises is kept to "the minimum needed to show the argument." Only
    called for the EMBEDS fallback -- hand-written quote.lines are already
    curated short and pass through untouched."""
    joined = " ".join(l.strip() for l in lines if l.strip())
    if len(joined) <= limit:
        return lines
    cut = joined[:limit]
    sp = cut.rfind(" ")
    if sp > limit * 0.6:
        cut = cut[:sp]
    return [cut.rstrip(" ,.;:\u3001\u3002") + "\u2026"]


# 인용문을 독자 언어로 옮겼을 때 캡션에 붙는 표기 (2026-07-30).
# 바깥 키는 페이지 언어, 안쪽 키는 원문 언어다. 원문 언어와 페이지 언어가 같으면
# 붙이지 않는다 -- 그때 화면에 있는 것은 번역이 아니라 원문이기 때문이다.
TRANSLATED_NOTE = {
    "ko": {"ko": "한국어 원문 옮김", "en": "영어 원문 옮김", "ja": "일본어 원문 옮김"},
    "en": {"ko": "translated from the Korean",
           "en": "translated from the English",
           "ja": "translated from the Japanese"},
    "ja": {"ko": "韓国語の原文より翻訳", "en": "英語の原文より翻訳",
           "ja": "日本語の原文より翻訳"},
}


def pick_quote_lines(raw, lang, slang):
    """어느 언어의 인용문을 보여줄지 고른다.

    `quote.lines`에는 두 가지 모양이 있다. 그냥 배열이면 옛 형태 -- 원문 언어
    문장 한 벌을 세 언어 페이지에 똑같이 실었다. `{en,ko,ja}` 객체면 언어별
    번역이 들어 있고, 2026-07-30 이후 카드는 전부 이쪽이다(발행 규칙 [4-F]).

    (문장 목록, 그 문장의 언어)를 돌려준다. 두 번째 값이 `lang` 속성과 "옮김"
    표기를 함께 결정하므로, 번역이 비어 있는 언어는 아무것도 안 보여주는 대신
    원문으로 내려앉되 그것을 번역이라고 말하지 않는다."""
    if isinstance(raw, dict):
        for cand in (lang, slang, "en", "ko", "ja"):
            got = [l for l in (raw.get(cand) or []) if l]
            if got:
                return got, cand
        return [], ""
    return [l for l in (raw or []) if l], slang


X_LIVE_SCRIPT = """<script>
(function(){
  var hosts = document.querySelectorAll('.xreal[data-xid]');
  if (!hosts.length) return;
  var sc = document.createElement('script');
  sc.async = true;
  sc.src = 'https://platform.twitter.com/widgets.js';
  sc.onload = function(){
    if (!window.twttr || !twttr.widgets || !twttr.widgets.createTweet) return;
    Array.prototype.forEach.call(hosts, function(host){
      var id = host.getAttribute('data-xid');
      var slot = host.querySelector('.xreal-slot');
      if (!id || !slot) return;
      try {
        Promise.resolve(twttr.widgets.createTweet(id, slot, {
          dnt: true, conversation: 'none', align: 'left'
        })).then(function(node){
          if (!node) { slot.innerHTML = ''; return; }
          var frame = slot.querySelector('iframe');
          if (!frame) { slot.innerHTML = ''; return; }
          var settled = false;
          function reveal(){
            if (settled) return;
            settled = true;
            host.classList.add('x-on');
          }
          function abandon(){
            if (settled) return;
            settled = true;
            slot.innerHTML = '';
          }
          frame.addEventListener('load', function(){
            requestAnimationFrame(function(){
              var r = frame.getBoundingClientRect();
              if (r.width > 0 && r.height > 0) reveal(); else abandon();
            });
          }, {once: true});
          setTimeout(abandon, 5000);
        }).catch(function(){ slot.innerHTML = ''; });
      } catch (e) { slot.innerHTML = ''; }
    });
  };
  sc.onerror = function(){};
  document.head.appendChild(sc);
}());
</script>"""


def x_embed_block(item):
    """Render the same X evidence card as the app, with an official widget
    enhancement when the reader's browser can load widgets.js.

    The static card is intentionally the fallback. X's script can be blocked by
    privacy tools, regional networks, or a slow third-party connection; the
    source must still be visible and linked in those cases.
    """
    e = EMBEDS.get(item.get("id"), {}) or {}
    lines = [l for l in (e.get("lines") or []) if l]
    if not lines:
        return ""
    href = safe_href(e.get("url") or item.get("sourceUrl"), "")
    m = re.search(r"/status/(\d+)", e.get("url") or item.get("sourceUrl") or "")
    xid = m.group(1) if m else ""
    name = e.get("name") or item.get("source") or ""
    handle = e.get("handle") or ""
    date = e.get("date") or item.get("date") or ""
    url_attr = E(href or "#")
    head = ('<div class="xemb-top"><div class="xemb-av">%s</div>'
            '<div class="xemb-nm"><b>%s</b><span>%s</span></div>'
            '<a class="xemb-logo" href="%s" target="_blank" rel="noopener nofollow" aria-label="X">𝕏</a></div>'
            % (E(str(name)[:1] or "?"), E(name), E(handle), url_attr))
    body = '<div class="xemb-body">%s%s</div>' % (
        "".join("<p>%s</p>" % E(line) for line in lines),
        ('<div class="xemb-q">%s</div>' % E(e.get("quoted"))) if e.get("quoted") else "",
    )
    tail = ('<div class="xemb-d"><a href="%s" target="_blank" rel="noopener nofollow">%s</a></div>'
            % (url_attr, E(date)))
    card = '<div class="xemb">%s%s%s</div>' % (head, body, tail)
    if not xid:
        return card
    return '<div class="xreal" data-xid="%s">%s<div class="xreal-slot"></div></div>' % (E(xid), card)


def quote_block(item, lang):
    """The author's own words, above our reading.

    Shown on ALL three language pages. Until 2026-07-30 it was shown in the
    source language on every one of them, on the reasoning that translating a
    quotation defeats the point of quoting it. That reasoning traded one
    reader's problem for another's: a Japanese reader landing on /p/ja/ met a
    block of Korean above the take and simply could not read the evidence the
    take rests on. Untranslated evidence is not evidence to someone who cannot
    read it. So the quote now carries a per-language translation and each page
    shows its own, with the caption saying it was translated and the source URL
    one click away for anyone who wants the original wording.
    (Until 2026-07-27 this returned "" for en/ja, so 30 pages carried the
    reading with no evidence at all.)

    Falls back to EMBEDS (embeds.json) when there is no hand-written "quote" --
    the same oEmbed text the app's live tweet widget uses (2026-07-29: about.html
    claimed every X post shows its original alongside, but this page never read
    that file, so 96 of 126 X-sourced articles carried nothing). The fallback
    text is trimmed to a short excerpt via _excerpt_lines() (2026-07-29): the
    raw oEmbed text runs near the full tweet, which about.html's "minimum
    needed" wording doesn't cover.

    Marked up as figure + blockquote + figcaption so the caption is bound to
    the quotation rather than merely sitting next to it, with the source URL in
    the `cite` attribute. `lang` on the blockquote matters here specifically
    because the quote is often NOT in the page's language."""
    q = item.get("quote") or {}
    slang = (item.get("sourceLang") or "").lower()
    if slang not in ("ko", "en", "ja"):
        slang = ""
    lines, llang = pick_quote_lines(q.get("lines"), lang, slang)
    cite = q.get("cite")
    if not lines:
        # The EMBEDS fallback is X's own oEmbed text, collected automatically,
        # so there is no translation to pick from -- it stays in the source
        # language by design (2026-07-30 decision).
        raw = [l for l in (EMBEDS.get(item["id"], {}).get("lines") or []) if l]
        lines = _excerpt_lines(raw) if raw else []
        llang = slang
    if not lines:
        return ""
    if not cite:
        # Match the hand-written convention ("메르 · 2026.07.29"): author byline
        # + dotted date, so a reader can't tell which path supplied the quote.
        src = item.get("source") or ""
        d = (item.get("date") or "").replace("-", ".")
        cite = (src + " · " + d) if (src and d) else (src or d)
    href = safe_href(item.get("sourceUrl"), "")
    lattr = ' lang="%s"' % E(llang) if llang in ("ko", "en", "ja") else ""
    cattr = ' cite="%s"' % E(href) if href else ""
    body = "".join("<p>%s</p>" % E(l) for l in lines)
    tail = ('<a href="%s" rel="nofollow noopener" target="_blank">%s</a>'
            % (E(href), E(cite))) if href else E(cite)
    if llang and slang and llang != slang:
        note = TRANSLATED_NOTE.get(lang, TRANSLATED_NOTE["en"]).get(slang)
        if note:
            tail += " · " + E(note)
    return ('<figure class="srcq"><blockquote%s%s>%s</blockquote>'
            '<figcaption class="srcq-c">%s</figcaption></figure>'
            % (cattr, lattr, body, tail))


def clip(text, n):
    t = re.sub(r"\s+", " ", text or "").strip()
    return t[: n - 1].rstrip() + "…" if len(t) > n else t


# ---- entity (company / person) association + slugs ----
SLUG_OVERRIDE = {"메르": "meru"}


# 슬러그 소유권 레지스트리 (같은 키는 항상 같은 슬러그, 충돌은 결정적으로 분리)
_SLUG_BY_KEY = {}
_KEY_BY_SLUG = {}


def _ascii_slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _claim(key, base):
    """base 슬러그를 key에 배정. 다른 키가 이미 그 슬러그를 쓰면 접미사로 분리."""
    slug = base
    if _KEY_BY_SLUG.get(slug, key) != key:
        slug = base + "-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:6]
    _SLUG_BY_KEY[key] = slug
    _KEY_BY_SLUG[slug] = key
    return slug


def register_slugs_from_aliases(entities):
    """비ASCII 엔티티 키의 슬러그를 엔티티 aliases의 영어 표기에서 자동 도출한다.
    (SLUG_OVERRIDE를 손으로 유지할 필요 없음.) 정렬 순서로 처리해 실행 간 안정적."""
    for key in sorted(entities):
        if key in _SLUG_BY_KEY:
            continue
        if key in SLUG_OVERRIDE:
            _claim(key, SLUG_OVERRIDE[key])
            continue
        base = _ascii_slug(key)
        if base:  # ASCII 키는 기존 슬러그 그대로 (하위호환)
            _claim(key, base)
            continue
        cand = ""  # 비ASCII: 첫 ASCII 별칭에서 슬러그 도출
        for al in (entities.get(key) or {}).get("aliases", []):
            s = _ascii_slug(al)
            if s:
                cand = s
                break
        if not cand:  # 쓸 만한 영어 별칭이 없으면 안정적 해시로 폴백
            cand = "k-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
        _claim(key, cand)


_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[぀-ヿ]")
_CJK = re.compile(r"[一-鿿]")
_LATIN_ONLY = re.compile(r"^[\x20-\x7e]+$")


def ent_label(key, ent, lang):
    """엔티티 칩 라벨을 페이지 언어에 맞게 고른다.

    ko는 이미 색인된 표기를 흔들지 않으려고 키를 그대로 쓴다.
    라틴 문자 키(NVIDIA 등)는 어느 언어에서든 그대로 쓰는 게 자연스럽다.
    그 외(밸류에이션 같은 한글 키)만 aliases에서 언어에 맞는 표기를 찾는다.
    """
    if lang == "ko" or _LATIN_ONLY.match(key or ""):
        return key
    aliases = (ent or {}).get("aliases") or []
    if lang == "en":
        for a in aliases:
            if _LATIN_ONLY.match(a):
                return a
        return key
    for a in aliases:  # ja: 가나 우선, 한글 없는 한자 표기까지 허용
        if _KANA.search(a) or (_CJK.search(a) and not _HANGUL.search(a)):
            return a
    for a in aliases:
        if _LATIN_ONLY.match(a):
            return a
    return key


def slugify(key):
    cached = _SLUG_BY_KEY.get(key)
    if cached is not None:
        return cached
    if key in SLUG_OVERRIDE:
        base = SLUG_OVERRIDE[key]
    else:
        base = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
        if not base:
            # 별칭 등록 전 비ASCII 키가 여기 오면 안정적 해시로 폴백.
            base = "k-" + hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    return _claim(key, base)


def build_matcher(entities):
    """[(compiled_regex, key)] over every alias. Word boundaries only where
    the adjacent character is ASCII \\w — otherwise \\b can never match
    (e.g. trailing \\b after 하이닉스 in "SK하이닉스"). A bare alias with no
    boundary at all on its Hangul side can also match as a substring of an
    unrelated longer word ("애플" inside "애플리케이션") — HANGUL_PARTICLES
    lets a real particle ("하이닉스가") still attach, while rejecting a
    same-script word that just continues ("애플" + "리케이션"). Mirrors
    build_entity_matcher() in build_data.py and buildEntityMatcher() in
    index.html; keep all three in sync."""
    hangul_particles = ["은", "는", "이", "가", "을", "를", "의", "에", "와", "과",
                         "도", "만", "로", "께", "이나", "나"]
    particle_alt = "|".join(hangul_particles)
    # entity_alias_list()/alias_is_case_sensitive() live in build_data.py so the
    # three matchers (app, build_data, build_pages) cannot drift. Without it we
    # keep the old alias-only, case-insensitive behaviour rather than crash.
    bd = _build_data()
    if bd is None or not hasattr(bd, "entity_alias_list"):
        class _Fallback(object):
            @staticmethod
            def entity_alias_list(key, e):
                return [a for a in (e.get("aliases") or []) if a]

            @staticmethod
            def alias_is_case_sensitive(a):
                return False
        bd = _Fallback()
    pats = []
    for key, e in entities.items():
        for a in bd.entity_alias_list(key, e):
            if not a:
                continue
            head = r"\b" if re.match(r"[A-Za-z0-9]", a) else r"(?<![가-힣])"
            if re.search(r"[A-Za-z0-9]$", a):
                tail = r"\b"
            else:
                tail = r"(?=$|[^가-힣]|(?:%s)(?![가-힣]))" % particle_alt
            # all-caps Latin aliases are acronyms; matching them case-insensitively
            # is what made the term PER light up on the English preposition "per".
            flags = 0 if bd.alias_is_case_sensitive(a) else re.I
            pats.append((re.compile(head + re.escape(a) + tail, flags), key))
    return pats


def item_entities(item, entities, pats):
    s = set()
    cov = (item.get("cover") or {}).get("label")
    if cov in entities:
        s.add(cov)
    for t in item.get("tags", []) or []:
        if t in entities:
            s.add(t)
    if item.get("source") in entities:
        s.add(item["source"])
    text = " ".join(
        [item["title"].get(l, "") or "" for l in ("en", "ko", "ja")]
        + [item["gist"].get(l, "") or "" for l in ("en", "ko", "ja")]
        + [item["why"].get(l, "") or "" for l in ("en", "ko", "ja")]
    )
    # 마커 줄(@@REF@@·@@IMG@@)의 URL은 색인 대상이 아니다. URL 안의 단어가
    # 별칭에 우연히 걸려 엉뚱한 엔티티에 카드가 딸려 붙는다
    # (예: .../hyperliquid-sk-hynix-perp-oracle-liquidations/ → ORACLE).
    # 캡션·제목 같은 사람이 읽는 본문은 색인에 남기고 URL만 걷어낸다.
    text = re.sub(r"https?://\S+", " ", text)
    for rx, key in pats:
        if rx.search(text):
            s.add(key)
    return s


def rfc822(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        d = datetime.now(timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


# ---- social share images (1200x630 PNG per article) ----
OG_W, OG_H = 1200, 630


def _hex(c, fb=(17, 18, 20)):
    c = (c or "").lstrip("#")
    try:
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except Exception:
        return fb


def _og_setup():
    """Return drawing helpers if Pillow + a CJK font are available, else None."""
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa
    except Exception:
        try:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                            "--break-system-packages", "pillow"], check=True)
            from PIL import Image, ImageDraw, ImageFont  # noqa
        except Exception:
            return None
    import glob, os
    def pick(*globs):
        for g in globs:
            for p in sorted(glob.glob(g, recursive=True)):
                if os.path.exists(p):
                    return p
        return None
    bold = pick("/usr/share/fonts/**/NotoSansCJK*Bold*.ttc",
                "/usr/share/fonts/**/NotoSansCJK*.ttc",
                "/usr/share/fonts/**/*CJK*.ttc")
    reg = pick("/usr/share/fonts/**/NotoSansCJK*Regular*.ttc") or bold
    if not bold:
        return None
    return (Image, ImageDraw, ImageFont, bold, reg)


def _wrap(draw, text, font, max_w, max_lines):
    words = list(text.strip())  # char-level wrap works for KO/JA/EN alike
    lines, cur = [], ""
    for ch in words:
        t = cur + ch
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = ch
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and draw.textlength(lines[-1] + "…", font=font) > max_w:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def _og_tile(Image, ImageDraw, src_path, is_logo, size):
    """A rounded-square thumbnail: photos are cover-filled; logos sit on a
    white tile, contained with padding."""
    im = Image.open(src_path).convert("RGBA")
    if is_logo:
        tile = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        pad = int(size * 0.17)
        maxd = size - 2 * pad
        w0, h0 = im.size
        sc = min(maxd / w0, maxd / h0)
        nw, nh = max(1, int(w0 * sc)), max(1, int(h0 * sc))
        im2 = im.resize((nw, nh), Image.LANCZOS)
        tile.paste(im2, ((size - nw) // 2, (size - nh) // 2), im2)
    else:
        w0, h0 = im.size
        s = min(w0, h0)
        tile = im.crop(((w0 - s) // 2, (h0 - s) // 2, (w0 - s) // 2 + s, (h0 - s) // 2 + s)).resize((size, size), Image.LANCZOS).convert("RGBA")
    rad = int(size * 0.13)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=rad, fill=255)
    tile.putalpha(mask)
    return tile


AV_CACHE = {}  # url -> local ogsrc path (downloaded author avatars)


def _download_avatars(items):
    """Author avatarImg may be a full URL (e.g. unavatar.io). Cache each one
    locally under ogsrc/ so share cards can show the face. Best-effort."""
    import os, hashlib, urllib.request
    os.makedirs("ogsrc", exist_ok=True)
    urls = {i.get("avatarImg") for i in items
            if (i.get("avatarImg") or "").startswith("http")}
    for u in urls:
        loc = "ogsrc/av-" + hashlib.md5(u.encode()).hexdigest()[:12] + ".png"
        if os.path.exists(loc):
            AV_CACHE[u] = loc
            continue
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=20).read()
            if len(data) > 500:
                open(loc, "wb").write(data)
                AV_CACHE[u] = loc
        except Exception as e:
            print(f"[avatar-skip] {u}: {e}")


def _og_source(item):
    """Return (path, is_logo) for the card thumbnail, or (None, False)."""
    import os
    av = item.get("avatarImg")
    if av and os.path.exists(av):
        return av, False
    if av and av.startswith("http") and os.path.exists(AV_CACHE.get(av, "")):
        return AV_CACHE[av], False
    ph = f"ogsrc/{item['id']}.photo.png"
    lg = f"ogsrc/{item['id']}.logo.png"
    if os.path.exists(ph):
        return ph, False
    if os.path.exists(lg):
        return lg, True
    return None, False


def make_og(item, og):
    Image, ImageDraw, ImageFont, boldp, regp = og
    import os
    W, H, M = OG_W, OG_H, 64
    frm = _hex((item.get("cover") or {}).get("from"))
    to = _hex((item.get("cover") or {}).get("to"))
    # diagonal gradient (small then upscaled = smooth + fast)
    sm = (64, 34)
    gmask = Image.new("L", sm)
    gmask.putdata([int(255 * ((x / (sm[0] - 1)) + (y / (sm[1] - 1))) / 2)
                   for y in range(sm[1]) for x in range(sm[0])])
    base = Image.new("RGB", (W, H), frm)
    top = Image.new("RGB", (W, H), to)
    img = Image.composite(top, base, gmask.resize((W, H)))
    # darken bottom for legible text
    ov = Image.new("L", (1, H))
    ov.putdata([int(205 * max(0, (y - H * 0.30) / (H * 0.70))) for y in range(H)])
    img = Image.composite(Image.new("RGB", (W, H), (12, 13, 16)), img, ov.resize((W, H)))

    # subject thumbnail on the LEFT (photo of the person/company the story is about)
    src, is_logo = _og_source(item)
    TH = 384
    ty0 = (H - TH) // 2
    tx0 = M
    have_img = False
    if src:
        try:
            tile = _og_tile(Image, ImageDraw, src, is_logo, TH)
            # soft shadow
            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle((tx0, ty0 + 8, tx0 + TH, ty0 + TH + 8), radius=int(TH * 0.13), fill=(0, 0, 0, 90))
            img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"), (0, 0))
            img.paste(tile, (tx0, ty0), tile)
            have_img = True
        except Exception:
            have_img = False

    d = ImageDraw.Draw(img)
    textX = (tx0 + TH + 52) if have_img else M
    textW = W - textX - M
    fTitle = ImageFont.truetype(boldp, 54 if have_img else 60)
    fMeta = ImageFont.truetype(regp, 28)
    fBrand = ImageFont.truetype(boldp, 30)
    fLabel = ImageFont.truetype(boldp, 40 if have_img else 44)
    # brand + cover label (top of the text column)
    d.text((textX, M - 6), "◆ STACKS", font=fBrand, fill=(255, 255, 255))
    label = (item.get("cover") or {}).get("label", "")
    if label:
        d.text((textX, M + 42), _wrap(d, label, fLabel, textW, 1)[0], font=fLabel, fill=(232, 232, 238))
    # title, bottom-aligned above the source line
    title = item["title"].get("ko") or item["title"]["en"]
    lh = 68 if have_img else 74
    lines = _wrap(d, title, fTitle, textW, 3)
    ty = H - M - 42 - lh * len(lines)
    for i, ln in enumerate(lines):
        d.text((textX, ty + i * lh), ln, font=fTitle, fill=(255, 255, 255))
    # source · date
    meta = f"{dispname(item.get('source',''))}  ·  {item.get('date','')}"
    d.text((textX, H - M - 2), meta, font=fMeta, fill=(226, 232, 240))
    os.makedirs("og", exist_ok=True)
    img.save(f"og/{item['id']}.png", optimize=True)


MIN_RATE_N = 5  # 적중률을 공개할 최소 채점 표본

# 색인에 내보낼 엔티티 페이지의 최소 관련 글 수.
# /e/ 는 기사에 한 번이라도 언급된 엔티티면 무조건 만들어진다. 그래서 관련 글이
# 1건인 페이지가 104개 생겼고, 본문 중앙값이 565자, 71%가 800자 미만이었다.
# 사람에게는 쓸모 있는 이동 경로지만(내부 링크로 계속 남긴다), 검색 색인에
# 내보내면 "자동 생성된 껍데기 페이지 대량 생산"으로 읽힌다 — 2026-07-27
# 애드센스가 「가치가 별로 없는 콘텐츠」로 사이트를 반려한 근거가 이것이다.
# 기준 미만은 noindex,follow + 사이트맵 제외. 글이 쌓이면 자동으로 색인에 돌아온다.
ENTITY_MIN_ARTICLES = 3


def week_window(items):
    """(wk_items, label) for the last 7 days, same rule week_page() uses."""
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=7)).isoformat()
    wk = [i for i in items if i.get("date", "") >= cutoff]
    if len(wk) < 3:
        wk = items[:6]
    iso = today.isocalendar()
    return sorted(wk, key=lambda x: x.get("date", ""), reverse=True), f"{iso[0]} W{iso[1]:02d}"


def scoreboard_stats(items):
    """Weekly numbers behind the share card.

    적중률은 채점이 끝난 콜(hit/miss)에서만 계산한다. 채점 대기(pending)를 분모에
    넣으면 초반에 0%처럼 보여서 오히려 신뢰를 깎아먹는다.
    """
    wk, label = week_window(items)
    rows, agg = {}, dict(posts=len(wk), calls=0, hit=0, miss=0, pending=0)
    for i in wk:
        name = i.get("source", "")
        r = rows.setdefault(name, dict(name=name, calls=0, hit=0, miss=0, pending=0,
                                       avatar=i.get("avatarImg") or ""))
        if i.get("stance") in ("bull", "bear"):
            r["calls"] += 1
            agg["calls"] += 1
        st = (i.get("outcome") or {}).get("status")
        if st in ("hit", "miss", "pending"):
            r[st] += 1
            agg[st] += 1
    order = sorted((r for r in rows.values() if r["name"]),
                   key=lambda r: (-(r["hit"] + r["miss"]), -r["calls"], -r["pending"], r["name"]))
    return dict(label=label, agg=agg, rows=order, week=wk)


def make_scoreboard(items, og, out="og/scoreboard.png"):
    """Render the weekly 1200x630 scoreboard card (this-week.html의 og:image).

    이 카드가 없으면 this-week.html 공유 시 twitter:card summary_large_image가
    빈 이미지로 뜬다. 매 빌드마다 다시 그려서 항상 이번 주 숫자를 보여준다.
    """
    if not og:
        return False
    Image, ImageDraw, ImageFont, boldp, regp = og
    import os
    s = scoreboard_stats(items)
    a = s["agg"]
    W, H, M = OG_W, OG_H, 64
    frm, to = _hex("#0B1220"), _hex("#26324A")
    sm = (64, 34)
    gmask = Image.new("L", sm)
    gmask.putdata([int(255 * ((x / (sm[0] - 1)) + (y / (sm[1] - 1))) / 2)
                   for y in range(sm[1]) for x in range(sm[0])])
    img = Image.composite(Image.new("RGB", (W, H), to), Image.new("RGB", (W, H), frm),
                          gmask.resize((W, H)))
    d = ImageDraw.Draw(img)
    fBrand = ImageFont.truetype(boldp, 30)
    fKick = ImageFont.truetype(regp, 26)
    fH1 = ImageFont.truetype(boldp, 54)
    fNum = ImageFont.truetype(boldp, 56)
    fLab = ImageFont.truetype(regp, 24)
    fName = ImageFont.truetype(boldp, 32)
    fRec = ImageFont.truetype(regp, 26)
    fFoot = ImageFont.truetype(regp, 24)

    d.text((M, 50), "◆ STACKS", font=fBrand, fill=(255, 255, 255))
    kick = s["label"]
    d.text((W - M - d.textlength(kick, font=fKick), 56), kick, font=fKick, fill=(148, 163, 184))
    d.text((M, 106), "이번 주 필진 스코어보드", font=fH1, fill=(255, 255, 255))

    # 표본이 얇을 때 "100%"를 띄우면 자랑이 아니라 허세로 읽힌다.
    # 채점 5건 미만이면 적중률 대신 대기 건수를 보여준다.
    graded = a["hit"] + a["miss"]
    if graded >= MIN_RATE_N:
        val4, lab4, col4 = f"{round(100 * a['hit'] / graded)}%", "적중률", (52, 211, 153)
    else:
        val4, lab4, col4 = str(a["pending"]), "채점 대기", (255, 255, 255)
    stats = [(str(a["posts"]), "글", (255, 255, 255)), (str(a["calls"]), "방향성 콜", (255, 255, 255)),
             (str(graded), "채점 완료", (255, 255, 255)), (val4, lab4, col4)]
    for n, (val, lab, col) in enumerate(stats):
        x = M + n * 272
        d.text((x, 192), val, font=fNum, fill=col)
        d.text((x, 260), lab, font=fLab, fill=(148, 163, 184))
    d.line((M, 312, W - M, 312), fill=(51, 65, 85), width=2)

    y, TH = 332, 60
    for r in s["rows"][:3]:
        src, is_logo = _og_source({"id": "_sb", "avatarImg": r["avatar"]})
        tx = M
        if src:
            try:
                tile = _og_tile(Image, ImageDraw, src, is_logo, TH)
                img.paste(tile, (tx, y), tile)
            except Exception:
                src = None
        g = r["hit"] + r["miss"]
        rec = (f"적중 {r['hit']} · 빗나감 {r['miss']}" if g
               else f"콜 {r['calls']} · 채점 대기 {r['pending']}")
        recw = d.textlength(rec, font=fRec)
        nx = tx + (TH + 22 if src else 0)
        name = _wrap(d, dispname(r["name"]), fName, W - M - recw - 28 - nx, 1)[0]
        d.text((nx, y + 12), name, font=fName, fill=(255, 255, 255))
        d.text((W - M - recw, y + 18), rec, font=fRec,
               fill=(52, 211, 153) if g and r["hit"] > r["miss"] else (203, 213, 225))
        y += 76

    foot = "누가 맞았는지 기록으로 남는다 · stacksdaily.com/this-week.html"
    d.text((M, H - M - 4), foot, font=fFoot, fill=(148, 163, 184))
    os.makedirs("og", exist_ok=True)
    img.save(out, optimize=True)
    print(f"[og] scoreboard: 글 {a['posts']} · 콜 {a['calls']} · 채점 {graded} · {lab4} {val4}")
    return True


# ---- one publisher identity, reused by every JSON-LD block on the site ----
# Google treats `publisher` as an entity: giving it a stable @id, the site URL
# and a logo lets Search tie all 400+ pages to a single brand instead of a
# bare name string that matches nothing else on the web.
def publisher_ld():
    # @id MUST match the Organization node already declared in index.html
    # (https://stacksdaily.com/#org) so the homepage graph and all 400+ article
    # pages resolve to one entity instead of two unrelated ones.
    return {
        "@type": "Organization",
        "@id": BASE + "#org",
        "name": SITE,
        # Every name this site is known by. "Stacks" is a common noun and an
        # existing brand elsewhere, so Google needs the domain-shaped forms
        # ("Stacks Daily", "stacksdaily.com") tied to the same entity as the
        # brand name, or it falls back to showing the bare domain.
        "alternateName": ["Stacks Daily", "StacksDaily", "stacksdaily.com",
                          "\uc2a4\ud0dd\uc2a4", "\uc2a4\ud0dd\uc2a4\ub370\uc77c\ub9ac", "\u30b9\u30bf\u30c3\u30af\u30b9"],
        "url": BASE,
        "logo": {"@type": "ImageObject", "url": BASE + "icon-512.png",
                 "width": 512, "height": 512},
        # Stacks 자신의 프로필만 넣는다. 다른 이름의 프로필을 섞으면
        # 구글이 두 이름을 한 엔티티로 못 묶는다.
        "sameAs": ["https://x.com/Stacks0g"],
    }


# ---- static article page chrome, per language ----
# The p/ layer used to be one Korean page carrying all three languages at once,
# which reads to Google as "a Korean page with foreign text in it" and leaves the
# English/Japanese search markets unreachable. Each language now gets its own URL
# (p/{id}.html, p/en/{id}.html, p/ja/{id}.html) and the three are tied together
# with reciprocal hreflang.
UI = {
    "ko": dict(app="Stacks 앱에서 보기 →", src="원문 보기 ↗", paid="$ 원문은 유료 구독",
               origlang="원문", ents="관련 종목·인물", related="관련 글",
               other="다른 언어로 읽기", why="투자 포인트", ask="짚어볼 점",
               sum3="세 줄 요약", split="구분 기준",
               home=SITE + " 홈", allp="전체 글", about="소개",
               week="이번 주", latest="최신 글", allmore="전체 글 보기 →",
               disc="요약·해설은 " + SITE + "의 창작물입니다. 원문의 저작권은 원저작자에게 있으며, "
                    "각 항목은 출처를 표기하고 원문으로 링크합니다. 투자 자문이 아니며, "
                    "투자 판단과 그 책임은 이용자 본인에게 있습니다."),
    "en": dict(app="Open in the Stacks app →", src="Read the original ↗",
               paid="$ Original is paywalled", origlang="original",
               ents="Companies & people", related="Related",
               other="Read this in another language", why="Why it matters",
               sum3="In three lines", split="How to tell which",
               ask="Worth asking", home=SITE + " home", allp="All articles", about="About",
               week="This week", latest="Latest", allmore="Browse all articles →",
               disc="Summaries and commentary are original work by " + SITE + ". Copyright in the "
                    "source material remains with its author; every item credits the source and "
                    "links to the original. This is information and commentary, not investment advice."),
    "ja": dict(app="Stacksアプリで見る →", src="元記事を読む ↗", paid="$ 元記事は有料購読",
               origlang="原文", ents="関連銘柄・人物", related="関連記事",
               other="他の言語で読む", why="Why it matters", ask="考えるべき点",
               sum3="3行まとめ", split="見分ける基準",
               home=SITE + " ホーム", allp="記事一覧", about="Stacksについて",
               week="今週", latest="最新記事", allmore="記事一覧を見る →",
               disc="要約・解説は" + SITE + "の著作物です。元記事の著作権は原著者に帰属し、各項目は"
                    "出典を明記して原文にリンクしています。投資助言ではなく、投資判断とその責任は"
                    "利用者本人にあります。"),
}

# ---- record blocks (author track record / graded outcome / opposing cards) ----
# The app already owns all three; until now they lived only behind the SPA, so
# the pages Google actually indexes carried the summary and nothing else. These
# put the record on the crawlable page. They borrow no prose from the source
# post: every line is our own aggregate over items.json, which is the point
# (claude/strategy-originality-2026-07-25.md - "요약은 미끼고 기록이 제품이다").
REC_UI = {
    "ko": dict(rec="이 필진의 기록", posts="글", calls="방향성 콜",
               bull="강세", bear="약세", watch="관점", hit="적중", miss="빗나감",
               more="전체 기록 보기 →", oc="그 후 어떻게 됐나",
               pending="채점 대기", opp="같은 사안, 다른 관점",
               dlt="같은 종목, 이 필진의 이전 글",
               dltTheme="같은 주제, 이 필진의 이전 글"),
    "en": dict(rec="This author's record", posts="posts", calls="directional calls",
               bull="Bull", bear="Bear", watch="Watch", hit="Hit", miss="Miss",
               more="See the full record →", oc="What happened next",
               pending="Awaiting grading", opp="Same story, other views",
               dlt="Earlier from this author on this stock",
               dltTheme="Earlier from this author on this theme"),
    "ja": dict(rec="この筆者の記録", posts="記事", calls="方向性コール",
               bull="強気", bear="弱気", watch="観点", hit="的中", miss="外れ",
               more="記録をすべて見る →", oc="その後どうなったか",
               pending="採点待ち", opp="同じ話題、別の見方",
               dlt="同じ銘柄、この筆者の以前の記事",
               dltTheme="同じテーマ、この筆者の以前の記事"),
}
# 채점 카드(구조화 행)와 출처 목록에 쓰는 라벨. 기존 키를 건드리지 않으려고
# 리터럴 밖에서 덧붙인다.
REC_UI["ko"].update(srcs="출처", ocSched="채점 예정", ocMetric="지표",
                    ocNow="현재", ocWhen="채점일", ocHit="맞음", ocMiss="틀림")
REC_UI["en"].update(srcs="Sources", ocSched="Scheduled for grading", ocMetric="Metric",
                    ocNow="Now", ocWhen="Grading date", ocHit="Hit", ocMiss="Miss")
REC_UI["ja"].update(srcs="出典", ocSched="採点予定", ocMetric="指標",
                    ocNow="現在", ocWhen="採点日", ocHit="的中", ocMiss="外れ")
LANGS = ("ko", "en", "ja")
LANG_DIR = {"ko": "p", "en": "p/en", "ja": "p/ja"}
LANG_REL = {"ko": "../", "en": "../../", "ja": "../../"}
OG_LOCALE = {"ko": "ko_KR", "en": "en_US", "ja": "ja_JP"}
FEED_FILE = {"ko": "feed.xml", "en": "feed-en.xml", "ja": "feed-ja.xml"}


def page_url(iid, lang):
    """Canonical URL of one article in one language. Korean keeps the original
    p/{id}.html path so every existing backlink and indexed URL stays valid."""
    return BASE + ("p/%s.html" % iid if lang == "ko" else "p/%s/%s.html" % (lang, iid))


def item_langs(item):
    """Languages this item can actually be published in (needs a summary)."""
    return [lg for lg in LANGS if (item.get("gist") or {}).get(lg)]


def hreflang_tags(iid, langs):
    """Reciprocal hreflang set. Every page in the cluster lists every page in the
    cluster (itself included) or Google ignores the annotation entirely."""
    if len(langs) < 2:
        return ""
    tags = "".join(
        '<link rel="alternate" hreflang="%s" href="%s">' % (lg, E(page_url(iid, lg)))
        for lg in langs
    )
    dflt = "en" if "en" in langs else ("ko" if "ko" in langs else langs[0])
    return tags + '<link rel="alternate" hreflang="x-default" href="%s">' % E(page_url(iid, dflt))


# Filled once by main(); read by the record blocks below. Module state for the
# same reason AV_CACHE is: threading four more parameters through page_html()
# for data that is identical on every page buys nothing.
TITLES = {}      # id -> {"ko":..., "en":..., "ja":...}
ITEM_META = {}   # id -> {"stance":..., "date":..., "source":...}
REC_OF = {}      # author display name -> aggregate dict (see build_records)
OPP_OF = {}      # id -> {"k": ticker key, "ids": [...]} from build_data
PRIOR_OF = {}    # id -> {"k": ticker key, "ids": [...]} from build_data.pick_priors
# Newest-first [(id, (langs,...)), ...]. An article page reached from Search is
# an island: the reader has no feed, so without a list of what else exists the
# only exits are the two or three related links we happened to pick. This is the
# "there is more here, and it is current" signal, and it doubles as a crawl path
# from every deep page back into the newest content.
LATEST = []
# id -> {date, handle, lines, name, url}, loaded once by main() from
# embeds.json (scripts/fetch_embeds.py, X's oEmbed endpoint). This is the SAME
# data index.html's srcBlockHtml() uses for the live tweet widget -- until now
# build_pages.py never read the file, so any X post without a hand-written
# "quote" field showed no original text at all on the crawlable /p/ page (96 of
# 126 X-sourced articles, 2026-07-29 audit). quote_block() below falls back to
# it so the static page carries the same evidence the app does.
EMBEDS = {}


def title_of(iid, lang):
    """Headline in `lang`, falling back to any language we do have. Opposing and
    related cards may not exist in all three languages, and a blank link label
    is worse than a Korean headline on an English page."""
    t = TITLES.get(iid) or {}
    return t.get(lang) or t.get("ko") or t.get("en") or t.get("ja") or ""


def stance_tag(st, R):
    if st == "bull":
        return '<i class="bl">%s</i>' % E(R["bull"])
    if st == "bear":
        return '<i class="be">%s</i>' % E(R["bear"])
    return '<i class="wa">%s</i>' % E(R["watch"])


def _card_rows(ids, lang, R, limit=3):
    rows = ""
    for iid in ids[:limit]:
        t = title_of(iid, lang)
        if not t:
            continue
        m = ITEM_META.get(iid, {})
        rows += ('<li>%s<a href="%s.html">%s</a><time>%s</time></li>'
                 % (stance_tag(m.get("stance"), R), E(iid), E(clip(t, 80)),
                    E((m.get("date") or "")[5:])))
    return rows


def record_block(item, lang, R, REL):
    """Author track record: how many calls this writer has made, which way they
    lean, how the graded ones landed. None of this is in the source post."""
    rec = REC_OF.get(item.get("source") or "")
    if not rec or rec["total"] < 3:
        return ""
    chips = ('<span><b>%d</b>%s</span><span><b>%d</b>%s</span>'
             % (rec["total"], E(R["posts"]), len(rec["calls"]), E(R["calls"])))
    if rec["bull"]:
        chips += '<span class="bl"><b>%d</b>%s</span>' % (rec["bull"], E(R["bull"]))
    if rec["bear"]:
        chips += '<span class="be"><b>%d</b>%s</span>' % (rec["bear"], E(R["bear"]))
    if rec["hits"] or rec["miss"]:
        chips += ('<span class="bl"><b>%d</b>%s</span><span class="be"><b>%d</b>%s</span>'
                  % (rec["hits"], E(R["hit"]), rec["miss"], E(R["miss"])))
    rows = _card_rows([i for i in rec["calls"] if i != item["id"]], lang, R)
    lst = '<ul class="rec-l">%s</ul>' % rows if rows else ""
    more = ('<a class="rec-m" href="%sr/%s.html" data-app="?l=%s#record-%s">%s</a>'
            % (REL, E(rec["slug"]), lang,
               E(urllib.parse.quote(item.get("source") or "")), E(R["more"])))
    return ('<section class="rec"><h3>%s</h3><div class="rec-s">%s</div>%s%s</section>'
            % (E(R["rec"]), chips, lst, more))


def outcome_block(item, lang, R):
    """This card's own prediction and, once the weekly grader has run, whether
    it landed. `outcome` is written by the publishing routine, graded later."""
    oc = item.get("outcome") or {}
    note = (oc.get("note") or {}).get(lang) or (oc.get("note") or {}).get("ko") or ""
    if not note:
        return ""
    st = oc.get("status") or "pending"
    label = {"hit": R["hit"], "miss": R["miss"]}.get(st, R["pending"])
    card = oc.get("card") or {}
    if card:
        # 판별 조건을 본문 밖 카드로 뺀다 (편집 가이드 §7). 행이 하나라도
        # 차 있을 때만 카드로, 아니면 아래 기존 문장형으로 떨어진다.
        def _row(key, lbl, cls=""):
            v = lang_text(card.get(key), lang) or ""
            if not v:
                return ""
            v = ('<span class="%s">%s</span>' % (cls, E(v))) if cls else E(v)
            return '<div class="occ-r"><div class="k">%s</div><div class="v">%s</div></div>' % (E(lbl), v)
        rows = (_row("metric", R["ocMetric"]) + _row("now", R["ocNow"])
                + _row("when", R["ocWhen"]) + _row("hit", R["ocHit"], "hit")
                + _row("miss", R["ocMiss"], "miss"))
        if rows:
            title = R["ocSched"] if st == "pending" else R["oc"]
            return ('<section class="oc occ oc-%s"><h3>%s<i>%s</i></h3>%s</section>'
                    % (E(st), E(title), E(label), rows))
    return ('<section class="oc oc-%s"><h3>%s</h3><p><i>%s</i>%s</p></section>'
            % (E(st), E(R["oc"]), E(label), E(note)))


def sources_block(item, lang, R):
    """글 끝 출처 목록. 본문은 문장 안 매체명으로 귀속하고 추적성은 여기서
    전수 보존한다 (편집 가이드 §8). `sources`가 없는 카드에는 아무것도 안 낸다."""
    srcs = item.get("sources") or []
    if not srcs:
        return ""
    lis = []
    for s in srcs:
        name = lang_text(s.get("name"), lang) or lang_text(s.get("name"), "ko") or ""
        desc = lang_text(s.get("desc"), lang) or lang_text(s.get("desc"), "ko") or ""
        if not (name or desc):
            continue
        inner = ("<b>%s</b> " % E(name) if name else "") + E(desc)
        url = s.get("url") or ""
        if url:
            inner = '<a href="%s" rel="noopener nofollow" target="_blank">%s</a>' % (E(url), inner)
        lis.append("<li>%s</li>" % inner)
    if not lis:
        return ""
    asof = lang_text(item.get("sourcesAsOf"), lang) or ""
    tail = ('<p class="srcs-a">%s</p>' % E(asof)) if asof else ""
    return ('<section class="srcs"><h3>%s</h3><ol>%s</ol>%s</section>'
            % (E(R["srcs"]), "".join(lis), tail))


def opp_block(item, lang, R):
    """Cards that took the other side on the same company. The debate is the
    product, so a reader arriving from search should land on both sides."""
    ids = (OPP_OF.get(item["id"]) or {}).get("ids") or []
    rows = _card_rows(ids, lang, R, limit=2)
    if not rows:
        return ""
    return '<section class="opp"><h3>%s</h3><ul>%s</ul></section>' % (E(R["opp"]), rows)


def prior_block(item, lang, R):
    """This author's earlier cards on the same declared company - the
    trajectory. Pairing comes from build_data.pick_priors (same author, same
    explicit_key, 180-day window); nothing is recomputed here for the same
    reason opp_block doesn't recompute pairings."""
    rec = PRIOR_OF.get(item["id"]) or {}
    ids = rec.get("ids") or []
    rows = _card_rows(ids, lang, R, limit=2)
    if not rows:
        return ""
    # Two kinds of subject come out of pick_priors; saying "same stock" over a
    # theme pairing would be a claim the data does not make.
    head = R["dltTheme"] if rec.get("kind") == "theme" else R["dlt"]
    return '<section class="dlt"><h3>%s</h3><ul>%s</ul></section>' % (E(head), rows)


def _build_data():
    """build_data.py owns the canonical opposite-card pairing and the
    back-catalogue stance map. Import it rather than reimplement either."""
    import os as _os, sys as _sys
    here = _os.path.dirname(_os.path.abspath(__file__))
    if here not in _sys.path:
        _sys.path.insert(0, here)
    try:
        import build_data
        return build_data
    except Exception as e:
        print("[rec] build_data unavailable: " + str(e))
        return None


def author_slug_map():
    """Feed id per display name, so a record link points at r/serenity.html and
    not at a slugified display name. Mirrors build_extra_pages()."""
    try:
        srcmeta = json.load(open("sources.json", encoding="utf-8"))
    except Exception:
        srcmeta = {}
    out = {}
    for k, v in srcmeta.items():
        if isinstance(v, dict) and v.get("source"):
            out.setdefault(v["source"], k)  # first feed wins (serenity, not serenity_substack)
    return out


def build_records(items, entities=None):
    """Populate TITLES / ITEM_META / REC_OF / OPP_OF once for the whole build."""
    TITLES.clear(); ITEM_META.clear(); REC_OF.clear(); OPP_OF.clear(); PRIOR_OF.clear()
    # items arrive newest-first; keep the per-item language list so a page never
    # links to a language edition that was not written.
    LATEST[:] = [(i["id"], tuple(item_langs(i))) for i in items]
    entities = entities or {}
    name2slug = author_slug_map()

    # Back-catalogue cards predate the `stance` field; index.html carries a map
    # that fills them in and build_data reads it. Resolve stance the same way
    # here, or the badges disagree with the pairing that put a card in the block.
    bd, stance_map = _build_data(), {}
    if bd:
        try:
            stance_map = bd.load_stance_map(open("index.html", encoding="utf-8").read())
        except Exception as e:
            print("[rec] stance map unavailable: " + str(e))

    def _stance(i):
        return i.get("stance") or stance_map.get(i["id"])

    for i in items:
        TITLES[i["id"]] = i.get("title") or {}
        ITEM_META[i["id"]] = {"stance": _stance(i), "date": i.get("date", ""),
                              "source": i.get("source", "")}

    by_author = {}
    for i in items:  # items arrive newest-first, so call lists stay newest-first
        by_author.setdefault(i.get("source", ""), []).append(i)
    for name, its in by_author.items():
        if not name:
            continue
        calls = [i for i in its if _stance(i) in ("bull", "bear")]
        REC_OF[name] = {
            "slug": name2slug.get(name) or slugify(name),
            "total": len(its),
            "calls": [i["id"] for i in calls],
            "bull": sum(1 for i in its if _stance(i) == "bull"),
            "bear": sum(1 for i in its if _stance(i) == "bear"),
            "hits": sum(1 for i in its if (i.get("outcome") or {}).get("status") == "hit"),
            "miss": sum(1 for i in its if (i.get("outcome") or {}).get("status") == "miss"),
        }

    # Opposing cards are NOT recomputed here. build_data.pick_opposites() is the
    # single source of truth for the pairing (CLAUDE.md "반대편") and it is
    # deliberately strict: both sides must DECLARE the same company in a cover
    # label or tag, both must take a real side, within 45 days, and one post may
    # serve as at most three foils. Matching on merely-mentioned entities - the
    # obvious shortcut - pairs a macro ETF-flows card with an Intel analysis
    # because Intel got named once, and a card that claims two authors disagree
    # when they don't is worse than a card that stays quiet. Reusing it also
    # keeps this page and the app showing the SAME two cards.
    if bd:
        try:
            _rx, alias2key = bd.build_entity_matcher(entities)
            OPP_OF.update(bd.pick_opposites(items, entities, stance_map, alias2key))
            PRIOR_OF.update(bd.pick_priors(items, entities, alias2key))
        except Exception as e:
            print("[rec] opposites unavailable: " + str(e))


REC_CSS = """.rec,.oc,.opp,.dlt{margin-top:26px}
.rec h3,.oc h3,.opp h3,.dlt h3{font-size:14px;margin:0 0 10px}
.rec-s{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.rec-s span{display:inline-block;padding:7px 12px;border-radius:10px;background:#F6F7F9;border:1px solid #ECEDF1;font-size:12px;color:#8E93A0}
.rec-s b{display:block;font-size:17px;color:#17181C;line-height:1.25}
.rec-s .bl b{color:#1C7A42}.rec-s .be b{color:#B02525}
.rec-l,.opp ul,.dlt ul{list-style:none;margin:0;padding:0;font-size:14px}
.rec-l li,.opp li,.dlt li{display:flex;gap:8px;align-items:baseline;padding:8px 0;border-top:1px solid #ECEDF1}
.rec-l li:first-child,.opp li:first-child,.dlt li:first-child{border-top:0}
.rec-l i,.opp i,.dlt i{flex:none;font-style:normal;font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px}
.bl{background:#E8F5EC;color:#1C7A42}.be{background:#FDEAEA;color:#B02525}.wa{background:#EEF1F5;color:#4B5563}
.rec-l a,.opp a,.dlt a{color:#17181C;text-decoration:none;flex:1}
.rec-l a:hover,.opp a:hover,.dlt a:hover{text-decoration:underline}
.rec-l time,.opp time,.dlt time{flex:none;font-size:12px;color:#8E93A0}
.rec-m{display:inline-block;margin-top:10px;font-size:13px;font-weight:600;color:#17181C}
.oc p{margin:0;padding:12px 14px;border-radius:12px;background:#F6F7F9;font-size:14.5px}
.oc i{display:inline-block;font-style:normal;font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px;margin-right:8px;background:#FFF4E0;color:#A16207}
.oc-hit i{background:#E8F5EC;color:#1C7A42}.oc-miss i{background:#FDEAEA;color:#B02525}
@media(prefers-color-scheme:dark){.rec-s span{background:#141519;border-color:#2E3037}
  .rec-s b,.rec-l a,.opp a,.dlt a,.rec-m{color:#ECEDF1}
  .rec-l li,.opp li,.dlt li{border-color:#26272E}.oc p{background:#1A1B21}}
.occ{border:1px solid #ECEDF1;border-radius:12px;background:#F6F7F9;overflow:hidden}
.occ h3{display:flex;align-items:center;gap:9px;margin:0;padding:11px 14px;border-bottom:1px solid #ECEDF1}
.occ h3 i{font-style:normal;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;background:#FFF4E0;color:#A16207}
.occ.oc-hit h3 i{background:#E8F5EC;color:#1C7A42}.occ.oc-miss h3 i{background:#FDEAEA;color:#B02525}
.occ-r{display:flex;gap:12px;padding:8px 14px;border-bottom:1px solid #ECEDF1;font-size:14px;line-height:1.6}
.occ-r:last-child{border-bottom:0}
.occ-r .k{flex:0 0 64px;font-size:12.5px;font-weight:700;color:#8E93A0;padding-top:2px}
.occ-r .v{flex:1}
.occ-r .v .hit{color:#1C7A42;font-weight:700}.occ-r .v .miss{color:#B02525;font-weight:700}
.srcs{margin-top:26px;border:1px solid #ECEDF1;border-radius:12px;padding:14px 16px}
.srcs h3{font-size:12.5px;letter-spacing:.03em;color:#8E93A0;margin:0 0 10px}
.srcs ol{margin:0;padding-left:18px}
.srcs li{font-size:13.5px;line-height:1.7;margin-bottom:5px;color:#5B6070;border:0;padding:0}
.srcs li b{color:#17181C}
.srcs a{color:inherit;text-decoration:none}.srcs a:hover{text-decoration:underline}
.srcs-a{margin:11px 0 0;font-size:12px;color:#8E93A0}
@media(prefers-color-scheme:dark){
  .occ{background:#141519;border-color:#2E3037}.occ h3,.occ-r{border-color:#2E3037}
  .occ.oc-hit h3 i{background:rgba(14,159,94,.14)}.occ.oc-miss h3 i{background:rgba(224,68,56,.14)}
  .srcs{border-color:#2E3037}.srcs li b{color:#ECEDF1}}"""


# One app, not a pile of leaves. Every generated page here is a dead end for a
# human: the reader arrives from Search, and until now every link out of it led
# to ANOTHER static page. So a plain left-click on anything that has a live
# equivalent is rerouted into the app instead.
#
# The href is deliberately left alone. Crawlers, copied links, middle-click and
# JS-off browsers all still get the real static URL, which is what keeps the
# internal link graph (the thing that gets deep pages indexed) intact and keeps
# the pages substantial enough for AdSense. Only the click is intercepted.
#
# The target language is read from the LINK's own path, not the page's, so the
# "English / 日本語" links open the app in that language rather than this one.
APP_LINK_JS = """<script>
(function(){var B="__BASE__",L="__LANG__";
function tgt(a){var d=a.getAttribute("data-app");if(d!==null)return d;
var u;try{u=new URL(a.getAttribute("href"),location.href);}catch(e){return null;}
if(u.origin!==location.origin)return null;
var p=u.pathname.replace(/^\\/+/,""),m;
if((m=p.match(/^p\\/(en|ja)\\/([^\\/]+)\\.html$/)))return "?c="+encodeURIComponent(m[2])+"&l="+m[1];
if((m=p.match(/^p\\/([^\\/]+)\\.html$/)))return "?c="+encodeURIComponent(m[1])+"&l=ko";
if(p===""||p==="index.html"||p==="articles.html")return "?l="+L;
return null;}
document.addEventListener("click",function(e){
if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
var a=e.target;while(a&&a.nodeName!=="A")a=a.parentNode;
if(!a||!a.getAttribute("href")||a.target==="_blank"||a.hasAttribute("download"))return;
var d=tgt(a);if(d===null)return;
e.preventDefault();location.href=B+d;},false);})();
</script>
"""


def app_link_js(lang="ko"):
    return APP_LINK_JS.replace("__BASE__", BASE).replace("__LANG__", lang)


def latest_block(cur_id, lang, U, skip=(), limit=8):
    """Newest articles in this language, excluding the current one and anything
    already linked above (related / opposing), so the block never repeats a
    headline the reader just saw. Links are siblings in the same directory,
    exactly like the related list."""
    rows, n = "", 0
    for iid, lgs in LATEST:
        if n >= limit or iid == cur_id or iid in skip or lang not in lgs:
            continue
        t = title_of(iid, lang)
        if not t:
            continue
        d = (ITEM_META.get(iid) or {}).get("date", "")
        rows += ('<li><a href="%s.html">%s</a><time>%s</time></li>'
                 % (E(iid), E(clip(t, 90)), E(d[5:] if len(d) >= 10 else d)))
        n += 1
    if not rows:
        return ""
    return ('<nav class="latest"><h3>%s</h3><ul>%s</ul>'
            '<a class="latest-all" href="%sarticles.html">%s</a></nav>'
            % (E(U["latest"]), rows, LANG_REL[lang], E(U["allmore"])))


def page_html(item, ent_links=None, og_img=None, lang="ko", langs=None, rel_titles=None):
    iid = item["id"]
    langs = langs or [lang]
    U = UI[lang]
    REL = LANG_REL[lang]
    url = page_url(iid, lang)
    # Every language now opens the POST. Korean used to get "#sig-<id>", which
    # only scrolls the home feed to the card; a reader who clicked through from
    # an article expects the article.
    app_url = BASE + "?c=" + iid + "&l=" + lang
    cov = item.get("cover", {}) or {}
    grad = f"linear-gradient(135deg,{hexcolor(cov.get('from'), '#111')},{hexcolor(cov.get('to'), '#333')})"
    title = item["title"].get(lang) or item["title"].get("ko") or item["title"]["en"]
    gist = (item.get("gist") or {}).get(lang) or ""
    why = (item.get("why") or {}).get(lang) or ""
    ask = (item.get("ask") or {}).get(lang) or ""
    desc = clip(strip_markers(gist), 160)
    kw = ", ".join(item.get("tags", []) + [item.get("source", "")])

    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title,
        "description": desc,
        "datePublished": item.get("date", "") + "T00:00:00Z",
        "dateModified": item.get("date", "") + "T00:00:00Z",
        "inLanguage": lang,
        "author": {"@type": "Person", "name": item.get("source", "Stacks")},
        "publisher": publisher_ld(),
        "mainEntityOfPage": url,
        "isBasedOn": safe_href(item.get("sourceUrl"), ""),
        "url": url,
    }
    # isBasedOn carries the bare URL. `citation` says what that URL IS and who
    # wrote it, so "this article quotes an X post by The Kobeissi Letter" is one
    # statement a machine can read, rather than something a human has to infer
    # from the page. Matters for attribution when an AI summary reuses us.
    _src = safe_href(item.get("sourceUrl"), "")
    # Author profile URL, reused below for both the citation's author and the
    # article's own author (see `_profile_url` further down). Prefer
    # extracting the handle straight out of the source post URL itself (works
    # for any X/Twitter/Truth Social citation regardless of avatar), falling
    # back to the avatar's unavatar.io twitter handle otherwise.
    _profile_url = ""
    _mh = re.search(r"^https?://(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)/", _src)
    if _mh:
        _profile_url = "https://x.com/" + _mh.group(1)
    else:
        _mt = re.search(r"^https?://truthsocial\.com/(@[A-Za-z0-9_]+)/", _src)
        if _mt:
            _profile_url = "https://truthsocial.com/" + _mt.group(1)
    if _src:
        _cit = {"@type": ("SocialMediaPosting"
                          if re.search(r"//(x\.com|twitter\.com|truthsocial\.com)/", _src)
                          else "Article"),
                "url": _src,
                # GSC's "discussion forum" structured-data check flags
                # SocialMediaPosting citations missing datePublished/author.url
                # as errors even though the wrapping NewsArticle already has
                # both -- the citation is its own schema.org node. We don't
                # track the source post's own timestamp separately, so reuse
                # our publish date (same convention as the NewsArticle above).
                "datePublished": item.get("date", "") + "T00:00:00Z"}
        _name = dispname(item.get("source", ""))
        if _name:
            _cit["author"] = {"@type": "Person", "name": _name}
            if _profile_url:
                _cit["author"]["url"] = _profile_url
        ld["citation"] = _cit

    try:
        import build_data as _bd
        gist = _bd.expand_img_markers(gist, lang)
    except Exception:
        pass
    # X cards use the fetched oEmbed evidence first, exactly like the app.
    # Hand-written quote.lines remains the safe fallback when X is unavailable.
    source_block = x_embed_block(item) or quote_block(item, lang)
    body_blocks = source_block + gist_blocks(gist)
    block_css = block_css_for(body_blocks)
    block_css = (block_css + "\n") if block_css else ""
    x_script = X_LIVE_SCRIPT if 'class="xreal"' in source_block else ""
    _extra = split_block(item, lang, U) + sum3_block(item, lang, U)
    if _extra:
        body_blocks += _extra
        block_css += SUM3_CSS + "\n"
    # v4.5 [L]: foldWhy cards weave why/ask into the gist's final section, so the
    # standalone boxes would duplicate them. Fields stay populated for the app's
    # compressed card views, which don't show the full gist.
    _fold = bool(item.get("foldWhy"))
    if why and not _fold:
        body_blocks += f'<p class="why"><b>{E(U["why"])}</b> · {E(why)}</p>'
    if ask and not _fold:
        body_blocks += f'<p class="ask"><b>{E(U["ask"])}</b> · {E(ask)}</p>'

    # record blocks: our own aggregate, not a retelling of the source post. The
    # CSS rides along only when at least one of them rendered, for the same
    # reason BLOCK_CSS is conditional (this is inlined into ~500 pages).
    R = REC_UI[lang]
    rec_html = (outcome_block(item, lang, R) + sources_block(item, lang, R)
                + record_block(item, lang, R, REL)
                + opp_block(item, lang, R) + prior_block(item, lang, R))
    if rec_html:
        block_css += REC_CSS + "\n"

    # other languages of the same article (user value + a crawl path between
    # the three URLs that does not depend on the sitemap alone)
    others = [lg for lg in langs if lg != lang]
    other_html = ""
    if others:
        links = " · ".join(
            f'<a href="{E(page_url(iid, lg))}" hreflang="{lg}" lang="{lg}">{E(LANG_LABEL[lg])}</a>'
            for lg in others
        )
        other_html = f'<nav class="otherlang">{E(U["other"])}: {links}</nav>'

    related = ""
    # opp/prior blocks already show these cards with stance and date; listing
    # them again under Related would be pure duplication (june, 2026-07-30).
    _shown = set(((OPP_OF.get(item["id"]) or {}).get("ids")) or []) \
           | set(((PRIOR_OF.get(item["id"]) or {}).get("ids")) or [])
    rel_ids = [r for r in (item.get("related") or [])
               if (rel_titles or {}).get(r) and r not in _shown]
    if rel_ids:
        links = "".join(
            f'<li><a href="{E(r)}.html">{E(clip(rel_titles[r], 90))}</a></li>' for r in rel_ids
        )
        related = f'<nav class="related"><h3>{E(U["related"])}</h3><ul>{links}</ul></nav>'

    ent_html = ""
    if ent_links:
        chips = "".join(
            f'<a class="ent-chip" href="{REL}e/{E(slug)}.html">{E(label)}</a>'
            for label, slug in ent_links
        )
        ent_html = (f'<nav class="ent-nav"><h3>{E(U["ents"])}</h3>'
                    f'<div class="ent-chips">{chips}</div></nav>')

    # Feed substitute for search traffic. Skips what "related" and the opposing
    # block already show so the reader gets eight NEW headlines, not a reprint.
    _skip = set(rel_ids) | set((OPP_OF.get(iid) or {}).get("ids", []))
    latest_html = latest_block(iid, lang, U, skip=_skip)

    img_url = BASE + "og/" + iid + ".png" if og_img else ""
    # Recommended NewsArticle fields for richer Google results:
    #   image  -> the article's OG card (enables a large thumbnail in Search/News)
    #   author.url -> the author's X profile, when the avatar is an X-handle avatar
    if img_url:
        ld["image"] = img_url
    if not _profile_url:
        _ma = re.search(r"unavatar\.io/twitter/([A-Za-z0-9_]+)", item.get("avatarImg", "") or "")
        if _ma:
            _profile_url = "https://x.com/" + _ma.group(1)
    if _profile_url:
        ld["author"]["url"] = _profile_url
    og_img_tags = (
        f'<meta property="og:image" content="{E(img_url)}">'
        f'<meta property="og:image:width" content="1200">'
        f'<meta property="og:image:height" content="630">'
        f'<meta name="twitter:image" content="{E(img_url)}">'
    ) if og_img else ""
    tw_card = "summary_large_image" if og_img else "summary"

    paywall = f'<span class="paid">{E(U["paid"])}</span>' if item.get("paywall") else ""
    og_locale = (f'<meta property="og:locale" content="{OG_LOCALE[lang]}">'
                 + "".join(f'<meta property="og:locale:alternate" content="{OG_LOCALE[lg]}">'
                           for lg in others))
    feed_rel = REL + FEED_FILE[lang]
    applink = app_link_js(lang)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>/* shared link (?l=xx): bounce a human into the live app in the sharer's language. No ?l = organic/SEO visit, so this stays a normal crawlable page. */
(function(){{try{{var l=new URLSearchParams(location.search).get('l');if(!l)return;location.replace('{BASE}?c={iid}&l='+encodeURIComponent(l));}}catch(e){{}}}})();</script>
<title>{E(title)} · {SITE}</title>
<meta name="description" content="{E(desc)}">
<meta name="keywords" content="{E(kw)}">
<link rel="canonical" href="{E(url)}">
{hreflang_tags(iid, langs)}
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">
{og_locale}
<meta property="article:published_time" content="{item.get('date','')}">
{og_img_tags}
<meta name="twitter:card" content="{tw_card}">
<meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="{REL}favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="{feed_rel}">
<script type="application/ld+json">{LD(ld)}</script>
<script src="{REL}assets/manual-overrides.js" defer></script>
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,"Segoe UI",Roboto,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.7;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}.card{{background:#141519!important}}.gist{{color:#C9CDD6!important}}}}
.wrap{{max-width:720px;margin:0 auto;padding:0 20px 60px}}
.topbar{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding:14px 0;margin-bottom:6px;border-bottom:1px solid #ECEDF1}}
.topbar a{{color:inherit;text-decoration:none}}
.topbar .brand{{font-weight:800;font-size:16px}}
.topbar .sitenav{{display:flex;gap:14px;margin-left:auto;flex-wrap:wrap}}
.topbar .sitenav a{{font-size:13.5px;font-weight:600;color:#8E93A0}}
.topbar .sitenav a:hover{{color:#17181C}}
@media(prefers-color-scheme:dark){{.topbar{{border-color:#26272E}}.topbar .sitenav a:hover{{color:#ECEDF1}}}}
.cover{{height:120px;border-radius:16px;background:{grad};display:flex;align-items:flex-end;padding:16px;margin:8px 0 20px}}
.cover .label{{font-family:ui-monospace,Menlo,monospace;color:rgba(255,255,255,.85);font-size:26px;letter-spacing:.05em}}
.meta{{font-size:13px;color:#8E93A0;margin-bottom:4px}}
h1{{font-size:26px;line-height:1.3;letter-spacing:-.02em;margin:.2em 0 .6em}}
.gist{{color:#3E414B;white-space:pre-line;font-size:16px}}
@media(prefers-color-scheme:dark){{.gist{{color:#C9CDD6}}}}
{block_css}.why,.ask{{background:#F6F7F9;border-radius:12px;padding:12px 14px;font-size:14.5px}}
.ask{{margin-top:10px}}
@media(prefers-color-scheme:dark){{.why,.ask{{background:#1A1B21}}}}
.otherlang{{margin:22px 0 0;font-size:13px;color:#8E93A0;border-top:1px solid #ECEDF1;padding-top:16px}}
.otherlang a{{color:#17181C;font-weight:600}}
@media(prefers-color-scheme:dark){{.otherlang{{border-color:#26272E}}.otherlang a{{color:#ECEDF1}}}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}}
.btn{{display:inline-block;padding:11px 18px;border-radius:999px;text-decoration:none;font-weight:700;font-size:14px}}
.btn.app{{background:#111214;color:#fff}}
.btn.src{{background:#F6F7F9;color:#17181C;border:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{.btn.app{{background:#1E1F26;color:#fff}}.btn.src{{background:#141519;color:#ECEDF1;border-color:#2E3037}}}}
.paid{{font-size:12px;color:#8E93A0;align-self:center}}
.related{{margin-top:30px;font-size:14px}}
.related ul{{padding-left:18px}}
.ent-nav{{margin-top:28px}}
.ent-nav h3{{font-size:14px;margin:0 0 10px}}
.ent-chips{{display:flex;flex-wrap:wrap;gap:8px}}
.ent-chip{{display:inline-block;padding:6px 12px;border-radius:999px;background:#F6F7F9;border:1px solid #ECEDF1;font-size:13px;font-weight:600;text-decoration:none;color:#17181C}}
.ent-chip:hover{{border-color:#111214}}
@media(prefers-color-scheme:dark){{.ent-chip{{background:#141519;color:#ECEDF1;border-color:#2E3037}}}}
.latest{{margin-top:34px;padding-top:22px;border-top:1px solid #ECEDF1}}
.latest h3{{font-size:14px;margin:0 0 10px}}
.latest ul{{list-style:none;margin:0;padding:0}}
.latest li{{display:flex;gap:12px;align-items:baseline;padding:8px 0;border-bottom:1px solid #F2F3F6}}
.latest li a{{flex:1;font-size:14.5px;font-weight:600;color:#17181C;text-decoration:none}}
.latest li a:hover{{text-decoration:underline}}
.latest time{{flex:none;font-size:12px;color:#8E93A0}}
.latest-all{{display:inline-block;margin-top:14px;font-size:13.5px;font-weight:700;color:#17181C;text-decoration:none}}
@media(prefers-color-scheme:dark){{.latest{{border-color:#26272E}}.latest li{{border-bottom-color:#1E1F25}}.latest li a,.latest-all{{color:#ECEDF1}}}}
footer{{margin-top:40px;padding-top:20px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
{applink}
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <a class="brand" href="{REL}">◆ {SITE}</a>
    <nav class="sitenav"><a href="{REL}articles.html">{E(U['allp'])}</a> · <a href="{REL}this-week.html">{E(U['week'])}</a> · <a href="{REL}about.html">{E(U['about'])}</a></nav>
  </div>
  <div class="cover"><span class="label">{E(cov.get('label',''))}</span></div>
  <div class="meta">{E(dispname(item.get('source','')))} · {E(item.get('date',''))} · {E(U['origlang'])}: {E(item.get('sourceLang',''))}</div>
  <h1>{E(title)}</h1>
  <div class="actions">
    <a class="btn app" href="{E(app_url)}">{E(U['app'])}</a>
    <a class="btn src" href="{E(safe_href(item.get('sourceUrl')))}" target="_blank" rel="noopener nofollow">{E(U['src'])}</a>
    {paywall}
  </div>
  {body_blocks}
  {rec_html}
  {other_html}
  {ent_html}
  {related}
  {latest_html}
  <footer>
    {E(U['disc'])}<br>
    <a href="{REL}">{E(U['home'])}</a> · <a href="{REL}articles.html">{E(U['allp'])}</a> · <a href="{REL}about.html">{E(U['about'])}</a> · <a href="{feed_rel}">RSS</a>
  </footer>
</div>
{x_script}
</body>
</html>
"""


def ent_url(slug, lang):
    """Canonical URL of one entity page in one language.
    Korean keeps e/{slug}.html so existing indexed URLs and backlinks stay valid."""
    return BASE + ("e/%s.html" % slug if lang == "ko" else "e/%s/%s.html" % (lang, slug))


def ent_hreflang(slug, langs):
    """Reciprocal hreflang for the ko/en/ja versions of one entity page.
    x-default = English so visitors we can't language-match get English
    (Korean -> ko, Japanese -> ja, everyone else -> en)."""
    tags = "".join(
        '<link rel="alternate" hreflang="%s" href="%s">' % (lg, E(ent_url(slug, lg)))
        for lg in langs
    )
    dflt = "en" if "en" in langs else langs[0]
    return tags + '<link rel="alternate" hreflang="x-default" href="%s">' % E(ent_url(slug, dflt))


# Entity-page labels per language (facts rows, section headers, title/desc).
# Stance / outcome labels are reused from REC_UI.
ENT_UI = {
    "ko": dict(ceo="대표", founded="설립", listed="상장", hq="본사", exchange="거래소",
               website="웹사이트", profile="프로필 ↗",
               relatedN="관련 글 {n}건", preds="예측 · 적중 기록 {n}건",
               holders="이 종목을 보유한 투자 고수", holderSub="최신 SEC 13F 공시 기준 · 미국 상장 주식 롱 포지션", holderAsOf="{period} 공시 기준", holderWaiting="업데이트 대기", holderWaitingTip="다음 분기 13F 공시를 기다리는 중입니다.",
               holderPeriod="{period} 공시", holderValue="포트폴리오 비중 {weight}",
               holderCount="{n}명", holderChanges={"hold": "보유", "new": "신규·매수", "add": "신규·매수", "increase": "늘림", "trim": "줄임"},
               metafb="{name} 관련 투자 읽을거리 모음",
               title="{name} · 관련 글 {n}건 · " + SITE),
    "en": dict(ceo="CEO", founded="Founded", listed="Listed", hq="HQ", exchange="Exchange",
               website="Website", profile="Profile ↗",
               relatedN="{n} related posts", preds="Predictions & track record ({n})",
               holders="Notable investors holding this stock", holderSub="Latest SEC 13F filing · U.S. long equity positions", holderAsOf="Based on {period} filing", holderWaiting="Update pending", holderWaitingTip="Waiting for the next quarterly 13F filing.",
               holderPeriod="{period} filing", holderValue="{weight} of portfolio",
               holderCount="{n} investors", holderChanges={"hold": "Held", "new": "New / bought", "add": "New / bought", "increase": "Increased", "trim": "Trimmed"},
               metafb="Investing reads about {name}, curated by " + SITE + ".",
               title="{name} · {n} related posts · " + SITE),
    "ja": dict(ceo="代表", founded="設立", listed="上場", hq="本社", exchange="取引所",
               website="ウェブサイト", profile="プロフィール ↗",
               relatedN="関連記事 {n}件", preds="予測・的中記録 {n}件",
               holders="この銘柄を保有する著名投資家", holderSub="最新のSEC 13F提出 · 米国上場株のロングポジション", holderAsOf="{period}提出時点", holderWaiting="更新待ち", holderWaitingTip="次回の四半期13F提出を待っています。",
               holderPeriod="{period}提出", holderValue="ポートフォリオ比率 {weight}",
               holderCount="{n}人", holderChanges={"hold": "保有", "new": "新規・購入", "add": "新規・購入", "increase": "買い増し", "trim": "削減"},
               metafb="{name} に関する投資の読み物。",
               title="{name} · 関連記事 {n}件 · " + SITE),
}


def load_13f_holder_index():
    """Build entity_key -> current 13F holders for static company pages."""
    try:
        with open(os.path.join(ROOT, "portfolios.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for investor in data.get("investors", []):
        if not isinstance(investor, dict) or not investor.get("slug"):
            continue
        rows = investor.get("all_holdings") or investor.get("holdings") or []
        for holding in rows:
            if not isinstance(holding, dict):
                continue
            key = holding.get("entity_key")
            if (not key or holding.get("change") == "exit"
                    or holding.get("put_call") in ("PUT", "CALL")):
                continue
            out.setdefault(key, []).append({
                "slug": investor["slug"],
                "name": investor.get("name") or {},
                "manager": investor.get("manager") or {},
                "period": investor.get("period") or "",
                "filed": investor.get("filed") or "",
                "weight": holding.get("weight"),
                "change": holding.get("change") or "hold",
            })
    for key in out:
        out[key].sort(key=lambda x: (x.get("weight") is not None, x.get("weight") or 0), reverse=True)
    return out


def _13f_period_label(period, lang):
    try:
        year, month, _ = (int(x) for x in str(period).split("-")[:3])
        quarter = ((month - 1) // 3) + 1
    except (TypeError, ValueError):
        return str(period or "")
    if lang == "en":
        return "Q%d %d" % (quarter, year)
    if lang == "ja":
        return "%d年第%d四半期" % (year, quarter)
    return "%d년 %d분기" % (year, quarter)


def _13f_freshness(period, today=None):
    """Return whether the next quarter's 45-day filing window has closed."""
    try:
        year, month, _ = (int(x) for x in str(period).split("-")[:3])
        quarter_start = ((month - 1) // 3) * 3 + 1
        next_q_month = quarter_start + 6
        next_q_year = year
        if next_q_month > 12:
            next_q_month -= 12
            next_q_year += 1
        next_q_end = date(next_q_year, next_q_month, 1) - timedelta(days=1)
        due = next_q_end + timedelta(days=45)
    except (TypeError, ValueError):
        return None
    return {"waiting": (today or date.today()) >= due, "due": due}


def _13f_weight(weight):
    try:
        return "%.1f%%" % (float(weight) * 100)
    except (TypeError, ValueError):
        return "—"


def entity_page(key, e, ent_items, lang="ko", holder_index=None):
    L = REC_UI[lang]
    U = ENT_UI[lang]
    disc = UI[lang]
    slug = slugify(key)
    name = ent_label(key, e, lang)
    url = ent_url(slug, lang)
    pfx = "../" if lang == "ko" else "../../"

    def art_href(iid):
        return pfx + ("p/%s.html" % iid if lang == "ko" else "p/%s/%s.html" % (lang, iid))

    def _title(i):
        return i["title"].get(lang) or i["title"].get("ko") or i["title"]["en"]

    kind = e.get("kind")
    sec = e.get("sector", {}) or {}
    sector = sec.get(lang) or sec.get("en") or sec.get("ko") or ""
    dd = e.get("longDesc") or {}
    de = e.get("desc") or {}
    desc = (dd.get(lang) or de.get(lang) or dd.get("en") or de.get("en")
            or dd.get("ko") or de.get("ko") or "")
    ticker = (e.get("ticker") or "").upper()

    def _loc(v):  # field may be a {en,ko,ja} object or a plain string
        return (v.get(lang) or v.get("en") or v.get("ko") or "") if isinstance(v, dict) else str(v)

    facts = []
    for lbl, k in ((U["ceo"], "ceo"), (U["founded"], "founded"), (U["listed"], "listed"),
                   (U["hq"], "hq"), (U["exchange"], "exchange")):
        if e.get(k):
            facts.append(f"<span><b>{E(lbl)}</b> {E(_loc(e[k]))}</span>")
    if e.get("website"):
        w = e["website"]
        facts.append(f'<span><b>{E(U["website"])}</b> <a href="{E(w)}" target="_blank" rel="noopener nofollow">{E(w.replace("https://","").replace("www.",""))}</a></span>')
    facts_html = f'<p class="facts">{" · ".join(facts)}</p>' if facts else ""
    metadesc = clip(desc or U["metafb"].format(name=name), 160)
    rows = "".join(
        f'<li>{("<b class=sp-" + i.get("stance") + ">" + E(L.get(i.get("stance"), L["watch"])) + "</b> ") if i.get("stance") else ""}'
        f'<a href="{E(art_href(i["id"]))}">{E(_title(i))}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in ent_items
    )
    # consensus tally + explicit predictions (v79)
    _b = sum(1 for i in ent_items if i.get("stance") == "bull")
    _r = sum(1 for i in ent_items if i.get("stance") == "bear")
    _w = sum(1 for i in ent_items if i.get("stance") == "watch")
    tally_html = ""
    if _b or _r or _w:
        tally_html = ('<div class="tally">'
                      + (f'<b class="bl">{E(L["bull"])} {_b}</b>' if _b else "")
                      + (f'<b class="wa">{E(L["watch"])} {_w}</b>' if _w else "")
                      + (f'<b class="be">{E(L["bear"])} {_r}</b>' if _r else "")
                      + "</div>")
    _oc_lbl = {"pending": L["pending"], "hit": L["hit"], "miss": L["miss"]}
    _preds = [i for i in ent_items if i.get("outcome") and i["outcome"].get("status")]
    preds_html = ""
    if _preds:
        _li = []
        for i in _preds:
            oc = i["outcome"]
            note = oc.get("note") or {}
            nt = note.get(lang) or note.get("en") or note.get("ko") or ""
            _li.append(f'<li><span class="oc oc-{E(oc["status"])}">{E(_oc_lbl.get(oc["status"], L["pending"]))}</span> '
                       f'<a href="{E(art_href(i["id"]))}">{E(_title(i))}</a>'
                       f'<span class="d">{E(nt)}</span></li>')
        preds_html = f'<h2>{E(U["preds"].format(n=len(_preds)))}</h2><ul class="preds">{"".join(_li)}</ul>'

    holders = (holder_index or {}).get(key, []) if kind == "company" else []
    holders_html = ""
    if holders:
        latest_period = max((str(h.get("period") or "") for h in holders), default="")
        latest_label = _13f_period_label(latest_period, lang)
        freshness = _13f_freshness(latest_period)
        holder_badge = ""
        if freshness and freshness["waiting"]:
            holder_badge = (f'<span class="holder-fresh holder-fresh-wait" title="{E(U["holderWaitingTip"])}">'
                            f'{E(U["holderWaiting"])}</span>')
        holder_status = (f'<div class="holder-status"><span class="holder-asof">'
                         f'{E(U["holderAsOf"].format(period=latest_label))}</span>{holder_badge}</div>')
        _holder_rows = []
        for h in holders:
            manager = _loc(h.get("manager")) or _loc(h.get("name"))
            fund = _loc(h.get("name"))
            detail = E(fund) if fund and fund != manager else ""
            period = _13f_period_label(h.get("period"), lang)
            change = E(U["holderChanges"].get(h.get("change"), h.get("change") or ""))
            meta = E(U["holderPeriod"].format(period=period))
            if h.get("weight") is not None:
                meta += " · " + E(U["holderValue"].format(weight=_13f_weight(h.get("weight"))))
            if change:
                meta += " · " + change
            href = BASE + "#investor-" + urllib.parse.quote(str(h.get("slug") or ""), safe="")
            _holder_rows.append(
                f'<li><a class="holder-name" href="{E(href)}">{E(manager)}</a>'
                + (f'<span class="holder-fund">{detail}</span>' if detail else "")
                + f'<span class="d">{meta}</span></li>'
            )
        holders_html = (f'<section class="holder-box"><h2>{E(U["holders"])} '
                        f'<span class="holder-count">{E(U["holderCount"].format(n=len(holders)))}</span></h2>'
                        f'{holder_status}<p class="holder-sub">{E(U["holderSub"])}</p><ul class="holders">'
                        + "".join(_holder_rows) + "</ul></section>")
    holder_css = """
.holder-box{margin:26px 0 4px;padding:16px 0 2px;border-top:1px solid #ECEDF1}
.holder-box h2{margin:0;font-size:16px}
.holder-count{font-size:12px;font-weight:600;color:#8E93A0;margin-left:5px}
.holder-status{display:flex;align-items:center;gap:7px;margin-top:3px}
.holder-asof{font-size:12px;color:#8E93A0}
.holder-fresh{font-size:10px;font-weight:800;border-radius:999px;padding:2px 7px;color:#9A6700;background:#FFF4CC}
.holder-sub{margin:3px 0 4px;font-size:12px;color:#8E93A0}
.holders{margin:0}
.holders li{padding:10px 0}
.holder-name{font-weight:700;text-decoration:none}
.holder-fund{display:block;font-size:12px;color:#8E93A0;margin-top:2px}
@media(prefers-color-scheme:dark){.holder-box{border-color:#26272E}.holder-fresh{color:#FFD666;background:#4A3710}}
""" if holders else ""

    about = {"@type": "Organization" if kind == "company" else ("DefinedTerm" if kind == "term" else "Person"), "name": name}
    if kind == "company" and ticker:
        about["tickerSymbol"] = ticker.split(".")[0]
    if e.get("url"):
        about["url"] = e["url"]
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": name, "description": metadesc, "url": url, "about": about,
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"}, "inLanguage": lang,
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(ent_items),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1,
                 "url": page_url(i["id"], lang),
                 "name": _title(i)}
                for n, i in enumerate(ent_items)
            ],
        },
    }
    tk = f'<span class="tk">{E(ticker)}</span>' if ticker else ""
    prof = f'<a class="prof" href="{E(e["url"])}" target="_blank" rel="noopener nofollow">{E(U["profile"])}</a>' if e.get("url") else ""
    # follow 를 남기는 이유: 이 페이지가 가리키는 글은 계속 크롤되어야 한다.
    # 색인에서만 빼고 링크는 그대로 흐르게 둔다. (언어 무관 — 글 수가 기준)
    thin_robots = ("" if len(ent_items) >= ENTITY_MIN_ARTICLES
                   else '\n<meta name="robots" content="noindex,follow">')
    hreflang = ent_hreflang(slug, LANGS)
    og_locale = (f'<meta property="og:locale" content="{OG_LOCALE[lang]}">'
                 + "".join(f'<meta property="og:locale:alternate" content="{OG_LOCALE[lg]}">'
                           for lg in LANGS if lg != lang))
    applink = app_link_js(lang)
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(U["title"].format(name=name, n=len(ent_items)))}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(url)}">{thin_robots}
{hreflang}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(name)} · {SITE}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(url)}">
{og_locale}
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="{pfx}favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="{pfx}{FEED_FILE[lang]}">
<script type="application/ld+json">{LD(ld)}</script>
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
.top{{font-weight:800;text-decoration:none}}
.sector{{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}}
h1{{font-size:26px;letter-spacing:-.02em;margin:0 0 6px}}
.tk{{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:#8E93A0;margin-left:8px}}
.desc{{color:#3E414B;font-size:15px;margin:8px 0 4px}}
@media(prefers-color-scheme:dark){{.desc{{color:#C9CDD6}}}}
.prof{{display:inline-block;margin:8px 0 2px;font-size:13px;font-weight:600;color:#2E5BFF;text-decoration:none}}
.facts{{font-size:12.5px;color:#8E93A0;line-height:1.9}}
.facts b{{color:#3E414B;font-weight:600;margin-right:2px}}
@media(prefers-color-scheme:dark){{.facts b{{color:#C9CDD6}}}}
.facts a{{color:#2E5BFF;text-decoration:none}}
.tally{{display:flex;gap:8px;margin:14px 0 2px;flex-wrap:wrap}}
.tally b{{padding:6px 14px;border-radius:999px;font-size:13px;color:#fff;font-weight:700}}
.tally .bl{{background:#0E9F5E}}.tally .wa{{background:#6B7280}}.tally .be{{background:#E04438}}
b.sp-bull{{color:#0E9F5E}}b.sp-bear{{color:#E04438}}b.sp-watch{{color:#8E93A0}}
.preds .oc{{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;margin-right:6px}}
.oc-pending{{background:#F1F2F4;color:#6B7280}}.oc-hit{{background:rgba(14,159,94,.12);color:#0E9F5E}}.oc-miss{{background:rgba(224,68,56,.12);color:#E04438}}
@media(prefers-color-scheme:dark){{.oc-pending{{background:#20222A;color:#9AA0AC}}}}
h2{{font-size:16px;margin:26px 0 8px}}
ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
.d{{display:block;font-size:12px;color:#8E93A0;margin-top:3px}}
{holder_css}footer{{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
{applink}
</head>
<body>
<a class="top" href="{pfx}">◆ {SITE}</a>
<div class="sector">{E(sector)}</div>
<h1>{E(name)}{tk}</h1>
<p class="desc">{E(desc)}</p>
{facts_html}
{prof}
{tally_html}
{preds_html}{holders_html}
<h2>{E(U["relatedN"].format(n=len(ent_items)))}</h2>
<ul>{rows}</ul>
<footer>
  {E(disc["disc"])}<br>
  <a href="{pfx}">{E(disc["home"])}</a> · <a href="{pfx}articles.html">{E(disc["allp"])}</a> · <a href="{pfx}{FEED_FILE[lang]}">RSS</a>
</footer>
</body>
</html>
"""


def articles_index(items):
    rows = "".join(
        f'<li><a href="p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in items
    )
    applink = app_link_js("ko")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>전체 글 · {SITE}</title>
<meta name="description" content="{E(TAGLINE['ko'])}. 전체 글 목록.">
<link rel="canonical" href="{BASE}articles.html">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="alternate" type="application/rss+xml" title="Stacks" href="feed.xml">
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
h1{{font-size:22px}}
ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
.d{{display:block;font-size:12px;color:#8E93A0;margin-top:3px}}
</style>
{applink}
</head>
<body>
<h1><a href="./" style="text-decoration:none">◆ {SITE}</a> 전체 글</h1>
<p style="color:#8E93A0">{E(TAGLINE['ko'])}</p>
<ul>{rows}</ul>
</body>
</html>
"""


def week_page(items, entities, item_ents, canonical_slug):
    """Public 'This week on Stacks' recap: shareable + SEO. Regenerated
    every build so this-week.html is always current; dated archives
    accumulate under week/."""
    import os
    from datetime import date, timedelta
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=7)).isoformat()
    wk_items = [i for i in items if i.get("date", "") >= cutoff]
    if len(wk_items) < 3:  # thin week: show the latest handful instead
        wk_items = items[:6]
    wk_items = sorted(wk_items, key=lambda x: x.get("date", ""), reverse=True)
    iso = today.isocalendar()
    wk_label = f"{iso[0]} W{iso[1]:02d}"
    dated_url = BASE + "week/" + canonical_slug + ".html"

    # hottest entity this week (most appearances among week items)
    ent_count = {}
    for i in wk_items:
        for k in item_ents.get(i["id"], []):
            if entities.get(k, {}).get("kind") == "company":
                ent_count[k] = ent_count.get(k, 0) + 1
    hot_ents = sorted(ent_count.items(), key=lambda x: -x[1])[:5]
    # stance tally
    bull = sum(1 for i in wk_items if i.get("stance") == "bull")
    bear = sum(1 for i in wk_items if i.get("stance") == "bear")

    rows = "".join(
        f'<li><a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in wk_items[:10]
    )
    hot_html = ""
    if hot_ents:
        chips = "".join(
            f'<a class="chip" href="../e/{slugify(k)}.html">{E(k)} <b>{n}</b></a>'
            for k, n in hot_ents
        )
        hot_html = f'<h2>이번 주 가장 많이 다뤄진 종목</h2><div class="chips">{chips}</div>'
    stance_html = ""
    if bull or bear:
        stance_html = (f'<p class="stance">이번 주 방향성 콜 '
                       f'<b class="bl">강세 {bull}</b> · <b class="be">약세 {bear}</b>. '
                       f'각 콜의 실제 성과는 <a href="../#">앱의 적중 기록</a>에서 확인.</p>')
    metadesc = clip(f"이번 주 Stacks에 올라온 투자 읽을거리 {len(wk_items)}편 요약: "
                    + ", ".join(i["title"].get("ko") or i["title"]["en"] for i in wk_items[:3]), 160)
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": f"이번 주 Stacks · {wk_label}", "description": metadesc, "url": dated_url,
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"}, "inLanguage": "ko",
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(wk_items[:10]),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1,
                 "url": BASE + "p/" + i["id"] + ".html",
                 "name": i["title"].get("ko") or i["title"]["en"]}
                for n, i in enumerate(wk_items[:10])
            ],
        },
    }
    applink = app_link_js("ko")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>이번 주 Stacks · {wk_label}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(dated_url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="이번 주 Stacks · {wk_label}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(dated_url)}">
<meta property="og:image" content="{BASE}og/scoreboard.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{BASE}og/scoreboard.png">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{LD(ld)}</script>
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
.top{{font-weight:800;text-decoration:none}}
.kicker{{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}}
h1{{font-size:28px;letter-spacing:-.02em;margin:0 0 6px}}
.lead{{color:#3E414B;font-size:15px;margin:8px 0 4px}}
@media(prefers-color-scheme:dark){{.lead{{color:#C9CDD6}}}}
h2{{font-size:16px;margin:28px 0 10px}}
ul{{list-style:none;padding:0}}
li{{padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
li a{{font-weight:600;text-decoration:none}}
.d{{display:block;font-size:12px;color:#8E93A0;margin-top:3px}}
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{display:inline-flex;align-items:center;gap:6px;text-decoration:none;font-size:13px;font-weight:700;padding:6px 12px;border-radius:999px;border:1px solid #ECEDF1;color:#17181C}}
@media(prefers-color-scheme:dark){{.chip{{border-color:#26272E;color:#ECEDF1}}}}
.chip b{{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:#8E93A0}}
.stance{{font-size:14px;color:#3E414B;margin-top:18px}}
@media(prefers-color-scheme:dark){{.stance{{color:#C9CDD6}}}}
.stance .bl{{color:#0E9F5E}}.stance .be{{color:#E04438}}
.cta{{display:inline-block;margin-top:24px;font-weight:700;text-decoration:none;background:#111;color:#fff;padding:11px 20px;border-radius:999px}}
@media(prefers-color-scheme:dark){{.cta{{background:#fff;color:#111}}}}
footer{{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
{applink}
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="kicker">이번 주 · {wk_label}</div>
<h1>이번 주 Stacks</h1>
<p class="lead">한 주 동안 메르·에민·둠버그·Serenity·CEO들의 글에서 추린 투자 읽을거리 {len(wk_items)}편. 같은 종목의 상반된 견해를, 당신의 언어로.</p>
<h2>이번 주 읽을거리</h2>
<ul>{rows}</ul>
{hot_html}
{stance_html}
<a class="cta" href="../">Stacks에서 더 읽기 →</a>
<footer>
  요약·해설은 Stacks의 창작물이며, 투자 자문이 아닌 정보 제공·논평입니다. 투자 판단과 그 책임은 이용자 본인에게 있습니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def calendar_page(events, items, ent_indexable):
    """실적 발표·경제 일정 캘린더 (calendar.html, 매 빌드 덮어씀).

    근거(2026-08-03): GSC에 "인텔 실적 발표일" 같은 일정형 한국어 쿼리가 실제로
    잡히기 시작했는데(순위 80), 이벤트 데이터는 앱 SPA 안에만 있어 검색봇이 못
    본다. 같은 데이터(items.json events, 주간 캘린더 봇이 관리)를 정적으로 렌더해
    "[기업명] 실적 발표일" 쿼리군의 착지 페이지를 만든다. 쿼리마다 페이지를 만드는
    게 아니라 이 한 페이지가 이벤트 전체를 커버하고, 봇이 events를 갱신할 때마다
    og-assets 빌드가 자동으로 다시 그린다 — 유지비 0."""
    from datetime import date as _date
    today = datetime.now(timezone.utc).date()
    ids = {i["id"] for i in items}
    KIND = {"earnings": "실적", "macro": "매크로", "policy": "정책"}
    WD = ["월", "화", "수", "목", "금", "토", "일"]
    evs = sorted((e for e in (events or []) if e.get("date")), key=lambda e: e["date"])
    up = [e for e in evs if e["date"] >= today.isoformat()]
    past = [e for e in evs if e["date"] < today.isoformat()][::-1]  # 최근 것부터

    def _label(e):
        return (e.get("label") or {}).get("ko") or (e.get("title") or {}).get("ko") or ""

    def row(e):
        d = _date.fromisoformat(e["date"])
        dd = (d - today).days
        badge = "오늘" if dd == 0 else (f"D-{dd}" if dd > 0 else f"{-dd}일 전")
        kind = KIND.get(e.get("kind"), "일정")
        links = ""
        ent = e.get("entity")
        if ent and slugify(ent) in ent_indexable:
            links += f' <a class="lnk" href="e/{E(slugify(ent))}.html">{E(ent)} 관련 글 →</a>'
        iid = e.get("itemId")
        if iid and iid in ids:
            links += f' <a class="lnk" href="p/{E(iid)}.html">해설 읽기 →</a>'
        return (f'<li><span class="dd{" dd-past" if dd < 0 else ""}">{E(badge)}</span>'
                f'<span class="dt">{d.month}월 {d.day}일({WD[d.weekday()]})</span>'
                f'<span class="k">{E(kind)}</span>'
                f'<span class="lb">{E(_label(e))}</span>{links}</li>')

    up_rows = "".join(row(e) for e in up) or '<li class="none">예정된 일정이 없습니다. 매주 갱신됩니다.</li>'
    past_html = ""
    if past:
        past_html = "<h2>지난 일정</h2><ul>" + "".join(row(e) for e in past) + "</ul>"
    # 제목 뒤에 붙는 회사명: entity가 있으면 그걸, 없으면 라벨에서 연도 이후를 잘라낸다
    ern_names = []
    for e in up:
        if e.get("kind") != "earnings":
            continue
        nm = re.sub(r"\s*20\d\d년.*$", "", _label(e)).strip() or (e.get("entity") or "")
        if nm:
            ern_names.append(nm)
    metadesc = clip("실적 발표일과 주요 경제 일정을 한 페이지에서 확인하세요. "
                    + ("다가오는 일정: " + ", ".join(
                        _label(e) if re.search(r"\(\d{1,2}/\d{1,2}\)", _label(e))
                        else _label(e) + f" ({int(e['date'][5:7])}/{int(e['date'][8:10])})"
                        for e in up[:5]) + ". " if up else "")
                    + "매주 자동 갱신, 각 일정의 관련 분석 글 링크 포함.", 160)
    url = BASE + "calendar.html"
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "실적 발표·경제 일정 캘린더", "description": metadesc, "url": url,
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"}, "inLanguage": "ko",
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(up),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1, "name": _label(e) + " (" + e["date"] + ")"}
                for n, e in enumerate(up)
            ],
        },
    }
    applink = app_link_js("ko")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>실적 발표 일정·경제 캘린더{(" · " + ", ".join(ern_names[:3])) if ern_names else ""} | {SITE}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="실적 발표 일정·경제 캘린더 | {SITE}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(url)}">
<meta property="og:image" content="{BASE}og-home.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="feed.xml">
<script type="application/ld+json">{LD(ld)}</script>
<style>
body{{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}}}
a{{color:inherit}}
.top{{font-weight:800;text-decoration:none}}
.kicker{{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}}
h1{{font-size:28px;letter-spacing:-.02em;margin:0 0 6px}}
.lead{{color:#3E414B;font-size:15px;margin:8px 0 4px}}
@media(prefers-color-scheme:dark){{.lead{{color:#C9CDD6}}}}
h2{{font-size:16px;margin:28px 0 10px}}
ul{{list-style:none;padding:0}}
li{{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;padding:12px 0;border-bottom:1px solid #ECEDF1}}
@media(prefers-color-scheme:dark){{li{{border-color:#26272E}}}}
li.none{{color:#8E93A0;font-size:14px}}
.dd{{flex:none;font-family:ui-monospace,Menlo,monospace;font-size:12px;font-weight:700;color:#0E9F5E;min-width:44px}}
.dd-past{{color:#8E93A0}}
.dt{{flex:none;font-size:13px;color:#8E93A0}}
.k{{flex:none;font-size:11px;font-weight:700;border:1px solid #ECEDF1;border-radius:999px;padding:1px 8px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{.k{{border-color:#26272E}}}}
.lb{{font-weight:600}}
.lnk{{font-size:12.5px;font-weight:700;text-decoration:none;color:#4A6CF7}}
.cta{{display:inline-block;margin-top:24px;font-weight:700;text-decoration:none;background:#111;color:#fff;padding:11px 20px;border-radius:999px}}
@media(prefers-color-scheme:dark){{.cta{{background:#fff;color:#111}}}}
footer{{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
{applink}
</head>
<body>
<a class="top" href="./">◆ {SITE}</a>
<div class="kicker">경제 캘린더 · {today.isoformat()} 갱신</div>
<h1>실적 발표·경제 일정 캘린더</h1>
<p class="lead">주요 기업의 실적 발표일과 FOMC·CPI 같은 경제 일정을 한곳에 모았습니다. 매주 자동 갱신되며, 각 일정에는 전 세계 투자 고수들의 관련 분석 글이 연결됩니다.</p>
<h2>다가오는 일정</h2>
<ul>{up_rows}</ul>
{past_html}
<a class="cta" href="./">Stacks에서 관련 글 읽기 →</a>
<footer>
  요약·해설은 Stacks의 창작물이며, 투자 자문이 아닌 정보 제공·논평입니다. 투자 판단과 그 책임은 이용자 본인에게 있습니다.<br>
  <a href="./">{SITE} 홈</a> · <a href="articles.html">전체 글</a> · <a href="this-week.html">이번 주 Stacks</a> · <a href="feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def sitemap(items, entity_slugs=None, week_slugs=None, theme_slugs=None, record_slugs=None):
    """Sitemap with xhtml:link alternates on every article URL. Sitemap-level
    hreflang is what lets Google discover the en/ja pages as translations rather
    than as near-duplicate orphans."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # (url, lastmod, priority, alternates) — alternates only for article pages
    # Hand-written static pages belong in here too. about.html and privacy.html
    # are not generated, so nothing else would ever list them, and an AdSense or
    # policy reviewer landing on a single /p/ page has no other route to the
    # site-level context. this-week.html is a human-facing alias whose canonical
    # points at the dated archive below, so only the canonical URL belongs here.
    urls = [(BASE, now, "1.0", None),
            (BASE + "calendar.html", now, "0.7", None),
            (BASE + "articles.html", now, "0.6", None),
            (BASE + "about.html", now, "0.6", None),
            (BASE + "privacy.html", now, "0.3", None)]
    for i in items:
        lgs = item_langs(i)
        alts = lgs if len(lgs) > 1 else None
        for lg in (lgs or ["ko"]):
            urls.append((page_url(i["id"], lg), i.get("date", now),
                         "0.8" if lg == "ko" else "0.7", (i["id"], alts) if alts else None))
    for slug in (entity_slugs or []):
        for lg in LANGS:
            urls.append((ent_url(slug, lg), now, "0.7" if lg == "ko" else "0.6", ("E", slug)))
    for slug in (week_slugs or []):
        urls.append((BASE + "week/" + slug + ".html", now, "0.6", None))
    for slug in (theme_slugs or []):
        urls.append((BASE + "t/" + slug + ".html", now, "0.8", None))
    for slug in (record_slugs or []):
        urls.append((BASE + "r/" + slug + ".html", now, "0.8", None))

    def _alt(a):
        if not a:
            return ""
        if a[0] == "E":
            eslug = a[1]
            eout = "".join(
                f'<xhtml:link rel="alternate" hreflang="{lg}" href="{E(ent_url(eslug, lg))}"/>'
                for lg in LANGS)
            return eout + f'<xhtml:link rel="alternate" hreflang="x-default" href="{E(ent_url(eslug, "en"))}"/>'
        iid, lgs = a
        out = "".join(
            f'<xhtml:link rel="alternate" hreflang="{lg}" href="{E(page_url(iid, lg))}"/>'
            for lg in lgs
        )
        dflt = "en" if "en" in lgs else ("ko" if "ko" in lgs else lgs[0])
        return out + f'<xhtml:link rel="alternate" hreflang="x-default" href="{E(page_url(iid, dflt))}"/>'

    body = "".join(
        f"<url><loc>{E(u)}</loc><lastmod>{E(m)}</lastmod><priority>{p}</priority>{_alt(a)}</url>"
        for u, m, p, a in urls
    )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + body + "</urlset>\n")


def feed(items, lang="ko"):
    """RSS in one language. Feed readers, Telegram/X auto-posting and news
    aggregators all key off <language>, so a single Korean feed was capping
    syndication to Korean-language consumers."""
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    entries = []
    for i in items[:30]:
        if not (i.get("gist") or {}).get(lang):
            continue
        link = page_url(i["id"], lang)
        title = i["title"].get(lang) or i["title"].get("ko") or i["title"]["en"]
        desc = clip(strip_markers(i["gist"][lang]), 400)
        entries.append(
            "<item>"
            f"<title>{E(title)}</title>"
            f"<link>{E(link)}</link>"
            f"<guid isPermaLink=\"true\">{E(link)}</guid>"
            f"<dc:creator>{E(i.get('source',''))}</dc:creator>"
            f"<pubDate>{rfc822(i.get('date',''))}</pubDate>"
            f"<description>{E(desc)}</description>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">\n<channel>'
        f"<title>{SITE}</title><link>{BASE}</link>"
        f"<description>{E(TAGLINE[lang])}</description>"
        f"<language>{lang}</language><lastBuildDate>{now}</lastBuildDate>"
        f'<atom:link xmlns:atom="http://www.w3.org/2005/Atom" href="{BASE}{FEED_FILE[lang]}" rel="self" type="application/rss+xml"/>'
        + "".join(entries)
        + "</channel></rss>\n"
    )


def robots():
    return f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n"


# ---- theme debate pages + author track-record pages (v78 SEO layer) ----
# Keys and keyword patterns MUST stay in sync with THEMES in index.html.
THEMES = {
    "rates":   {"icon": "🏛️", "ko": "금리·인플레", "en": "Rates & inflation", "ja": "金利・インフレ", "flags": re.I,
                "kw": r"기준금리|인플레|국채|연준|\bFed\b|FOMC|inflation|interest rates?|rate (?:cut|hike)|treasur|bond yield|\byields?\b|利上げ|利下げ|インフレ|国債|中央銀行"},
    "dollar":  {"icon": "💵", "ko": "달러·환율", "en": "Dollar & FX", "ja": "ドル・為替", "flags": re.I,
                "kw": r"달러|환율|원화|엔화|\bdollar\b|\bDXY\b|debasement|exchange rate|\byen\b|為替|円安|円高|ドル|통화"},
    "aicapex": {"icon": "⚡", "ko": "AI 투자 사이클", "en": "AI capex", "ja": "AI設備投資", "flags": 0,
                "kw": r"\bAI\b|인공지능|데이터센터|datacenter|data center|\bGPU\b|hyperscaler|capex|설비투자|人工知能|データセンター|設備投資"},
    "semis":   {"icon": "🔬", "ko": "반도체·메모리", "en": "Semis & memory", "ja": "半導体・メモリ", "flags": re.I,
                "kw": r"반도체|메모리|파운드리|semiconductor|\bchips?\b|foundry|\bDRAM\b|\bNAND\b|\bHBM\b|\bCXL\b|lithograph|半導体|メモリ"},
    "energy":  {"icon": "🛢️", "ko": "에너지", "en": "Energy", "ja": "エネルギー", "flags": re.I,
                "kw": r"에너지|원유|천연가스|전력|원전|\boil\b|natural gas|\bLNG\b|uranium|nuclear|power grid|electricity|\benergy\b|原油|エネルギー|電力|原発"},
    "crypto":  {"icon": "🪙", "ko": "크립토·금", "en": "Crypto & gold", "ja": "暗号資産・金", "flags": re.I,
                "kw": r"비트코인|크립토|암호화폐|금값|\bBitcoin\b|\bBTC\b|crypto|stablecoin|\bgold\b|bullion|ビットコイン|暗号資産|金価格"},
    "trade":   {"icon": "🚢", "ko": "관세·무역", "en": "Tariffs & trade", "ja": "関税・貿易", "flags": re.I,
                "kw": r"관세|무역|수출\s?규제|수출통제|tariffs?|trade war|export controls?|sanctions?|보호무역|通商|関税|貿易|制裁"},
    "japan":   {"icon": "🗾", "ko": "일본 시장", "en": "Japan", "ja": "日本市場", "flags": 0,
                "kw": r"일본|닛케이|엔저|\bJapan(?:ese)?\b|\bNikkei\b|\bBOJ\b|日銀|日本株|東証|日経"},
}


def _theme_hay(i):
    g = i.get("gist") or {}
    return " ".join([(i.get("title") or {}).get(l, "") or "" for l in ("en", "ko", "ja")]
                    + [g.get("en", "") or ""] + [" ".join(i.get("tags") or [])])


def theme_matches(items, key):
    th = THEMES[key]
    rx = re.compile(th["kw"], th["flags"])
    return [i for i in items if rx.search(_theme_hay(i))]


STANCE_KO = {"bull": "강세", "bear": "약세", "watch": "관점"}


def _item_rows(its, rel=".."):
    return "".join(
        f'<li>{"<b class=sp-" + i.get("stance","watch") + ">" + STANCE_KO.get(i.get("stance") or "watch","관점") + "</b> " if i.get("stance") else ""}'
        f'<a href="{rel}/p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(dispname(i.get("source","")))} · {E(i.get("date",""))}</span></li>'
        for i in its
    )


_HUB_CSS = """
body{font-family:-apple-system,"Segoe UI","Noto Sans KR",sans-serif;max-width:720px;margin:0 auto;padding:24px 20px 60px;line-height:1.6;color:#17181C;background:#fff}
@media(prefers-color-scheme:dark){body{background:#0E0F12;color:#ECEDF1}}
a{color:inherit}.top{font-weight:800;text-decoration:none}
.kicker{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8E93A0;margin:18px 0 4px}
h1{font-size:26px;letter-spacing:-.02em;margin:0 0 6px}
.lead{color:#3E414B;font-size:15px;margin:8px 0 4px}
@media(prefers-color-scheme:dark){.lead{color:#C9CDD6}}
.tally{display:flex;gap:8px;margin:14px 0}
.tally b{padding:6px 14px;border-radius:999px;font-size:13px;color:#fff}
.tally .bl{background:#0E9F5E}.tally .wa{background:#6B7280}.tally .be{background:#E04438}
h2{font-size:16px;margin:26px 0 8px}
ul{list-style:none;padding:0}
li{padding:12px 0;border-bottom:1px solid #ECEDF1}
@media(prefers-color-scheme:dark){li{border-color:#26272E}}
li a{font-weight:600;text-decoration:none}
.d{display:block;font-size:12px;color:#8E93A0;margin-top:3px}
b.sp-bull{color:#0E9F5E}b.sp-bear{color:#E04438}b.sp-watch{color:#8E93A0}
.cta{display:inline-block;margin-top:24px;font-weight:700;text-decoration:none;background:#111;color:#fff;padding:11px 20px;border-radius:999px}
@media(prefers-color-scheme:dark){.cta{background:#fff;color:#111}}
footer{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}
@media(prefers-color-scheme:dark){footer{border-color:#26272E}}
footer a{color:#8E93A0}
"""


def _hub_page(url, title, metadesc, kicker, h1, lead, body_html, app_url, og_id=None):
    import os
    hub_ld = LD({
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": title, "description": metadesc, "url": url, "inLanguage": "ko",
        "publisher": publisher_ld(), "isPartOf": {"@id": BASE + "#website"},
    })
    og_tags = ""
    tw = "summary"
    if og_id and os.path.exists(f"og/{og_id}.png"):
        img = BASE + "og/" + og_id + ".png"
        og_tags = (f'<meta property="og:image" content="{E(img)}">'
                   f'<meta property="og:image:width" content="1200">'
                   f'<meta property="og:image:height" content="630">'
                   f'<meta name="twitter:image" content="{E(img)}">')
        tw = "summary_large_image"
    applink = app_link_js("ko")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(title)}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(url)}">
{og_tags}
<meta name="twitter:card" content="{tw}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{hub_ld}</script>
<style>{_HUB_CSS}</style>
{applink}
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="kicker">{E(kicker)}</div>
<h1>{h1}</h1>
<p class="lead">{E(lead)}</p>
{body_html}
<a class="cta" href="{E(app_url)}">Stacks 앱에서 라이브로 보기 →</a>
<footer>
  요약·해설은 Stacks의 창작물이며, 투자 자문이 아닌 정보 제공·논평입니다. 투자 판단과 그 책임은 이용자 본인에게 있습니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def _pseudo_og(og, iid, label, title_ko, avatar_local=None, frm="#0B1220", to="#3B4256"):
    """Render a 1200x630 share card for a hub page via make_og()."""
    import os
    if not og or os.path.exists(f"og/{iid}.png"):
        return
    try:
        make_og({"id": iid, "cover": {"from": frm, "to": to, "label": label},
                 "title": {"ko": title_ko, "en": title_ko},
                 "avatarImg": avatar_local or "", "source": "stacksdaily.com",
                 "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")}, og)
    except Exception as e:
        print(f"[og-skip] {iid}: {e}")


def build_extra_pages(items, og):
    """Generate t/{theme}.html + r/{author}.html (+ share cards). Returns
    (theme_slugs, record_slugs)."""
    import os, urllib.parse
    # --- themes ---
    os.makedirs("t", exist_ok=True)
    theme_slugs = []
    for key, th in THEMES.items():
        t_items = sorted(theme_matches(items, key), key=lambda x: x.get("date", ""), reverse=True)
        if not t_items:
            continue
        theme_slugs.append(key)
        b = sum(1 for i in t_items if i.get("stance") == "bull")
        r = sum(1 for i in t_items if i.get("stance") == "bear")
        w = len(t_items) - b - r
        url = BASE + "t/" + key + ".html"
        app_url = BASE + "#theme-" + key
        title = f"{th['ko']} 강세 {b} · 약세 {r} 논쟁 · {SITE}"
        lead = (f"{th['ko']}를 둘러싼 전 세계 투자 논객들의 견해 {len(t_items)}건. "
                f"강세 {b} · 관점 {w} · 약세 {r}. 누가 맞았는지는 적중 기록으로 검증됩니다.")
        metadesc = clip(lead, 160)
        tally = (f'<div class="tally">{"<b class=bl>강세 " + str(b) + "</b>" if b else ""}'
                 f'{"<b class=wa>관점 " + str(w) + "</b>" if w else ""}'
                 f'{"<b class=be>약세 " + str(r) + "</b>" if r else ""}</div>')
        body = tally + f"<h2>관련 글 {len(t_items)}건</h2><ul>" + _item_rows(t_items) + "</ul>"
        _pseudo_og(og, "theme-" + key, th["en"].upper(),
                   f"{th['icon']} {th['ko']} 강세 {b} · 약세 {r}")
        html_out = _hub_page(url, title, metadesc, "THEME DEBATE", f"{th['icon']} {E(th['ko'])}",
                             lead, body, app_url, og_id="theme-" + key)
        open(f"t/{key}.html", "w", encoding="utf-8").write(html_out)
    for fn in os.listdir("t"):
        if fn.endswith(".html") and fn[:-5] not in theme_slugs:
            os.remove(f"t/{fn}")

    # --- author record pages ---
    try:
        srcmeta = json.load(open("sources.json", encoding="utf-8"))
    except Exception:
        srcmeta = {}
    name2slug = {}
    for k, v in srcmeta.items():
        if isinstance(v, dict) and v.get("source"):
            name2slug.setdefault(v["source"], k)  # first feed wins (serenity, not serenity_substack)
    os.makedirs("r", exist_ok=True)
    by_author = {}
    for i in items:
        by_author.setdefault(i.get("source", ""), []).append(i)
    record_slugs = []
    for name, its in by_author.items():
        if not name:
            continue
        slug = name2slug.get(name) or slugify(name)
        record_slugs.append(slug)
        its = sorted(its, key=lambda x: x.get("date", ""), reverse=True)
        calls = [i for i in its if i.get("stance") in ("bull", "bear")]
        hits = sum(1 for i in its if (i.get("outcome") or {}).get("status") == "hit")
        miss = sum(1 for i in its if (i.get("outcome") or {}).get("status") == "miss")
        url = BASE + "r/" + slug + ".html"
        app_url = BASE + "#record-" + urllib.parse.quote(name)
        title = f"{dispname(name)} 적중 기록 · 콜 {len(calls)}건 · {SITE}"
        lead = (f"{dispname(name)}의 글 {len(its)}건, 방향성 콜 {len(calls)}건. "
                + (f"검증된 예측 적중 {hits} · 빗나감 {miss}. " if (hits or miss) else "")
                + "각 콜의 '그 후 수익률'은 앱의 적중 기록에서 실시간으로 확인됩니다.")
        metadesc = clip(lead, 160)
        body = ""
        if calls:
            body += f"<h2>방향성 콜 {len(calls)}건</h2><ul>" + _item_rows(calls) + "</ul>"
        rest = [i for i in its if i not in calls]
        if rest:
            body += f"<h2>전체 글</h2><ul>" + _item_rows(rest[:20]) + "</ul>"
        av = its[0].get("avatarImg") or ""
        av_local = av if (av and not av.startswith("http") and os.path.exists(av)) else AV_CACHE.get(av)
        _pseudo_og(og, "record-" + slug, "TRACK RECORD",
                   f"{dispname(name)} 적중 기록", avatar_local=av_local,
                   frm="#111827", to="#334155")
        html_out = _hub_page(url, title, metadesc, "TRACK RECORD", E(dispname(name)),
                             lead, body, app_url, og_id="record-" + slug)
        open(f"r/{slug}.html", "w", encoding="utf-8").write(html_out)
    for fn in os.listdir("r"):
        if fn.endswith(".html") and fn[:-5] not in record_slugs:
            os.remove(f"r/{fn}")
    print(f"[extra] {len(theme_slugs)} theme pages + {len(record_slugs)} record pages")
    return theme_slugs, record_slugs


def _ping_indexnow(items):
    """Notify IndexNow (Bing, Naver, Yandex...) of recent URLs so new cards are
    discovered fast. Google does NOT use IndexNow (submit via Search Console)."""
    key = "stacks-f26ebf24-6bfbfb6a-bce6cc32-30287033"
    urls = [BASE, BASE + "articles.html"] + [BASE + "p/" + i["id"] + ".html" for i in items[:12]]
    import urllib.request
    payload = json.dumps({"host": "stacksdaily.com", "key": key,
                          "keyLocation": BASE + key + ".txt", "urlList": urls}).encode("utf-8")
    try:
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=payload,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=15) as r:
            print("[indexnow] pinged " + str(len(urls)) + " urls, status " + str(r.status))
    except Exception as e:
        print("[indexnow] skip: " + str(e))


def _normalize_source_media(doc):
    """Repair stale per-card avatar paths from the source registry.

    The publisher occasionally left an old relative filename on one card even
    though the same source had a valid avatar URL in sources.json. Keep
    items.json as the publisher's input, but self-heal that metadata during the
    normal build so the app, SEO pages, and OG cards all use the same source of
    truth. Existing local files and valid URLs are preserved.
    """
    try:
        srcmeta = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    except Exception:
        return False
    by_source = {}
    for rec in srcmeta.values():
        if isinstance(rec, dict) and rec.get("source"):
            by_source.setdefault(rec["source"], rec)
    changed = False
    for item in doc.get("items", []):
        rec = by_source.get(item.get("source"))
        if not rec:
            continue
        avatar = item.get("avatarImg") or ""
        is_url = isinstance(avatar, str) and avatar.startswith(("http://", "https://"))
        exists = bool(avatar) and os.path.exists(os.path.join(ROOT, avatar))
        replacement = rec.get("avatarImg") or ""
        if replacement and avatar and (not is_url and not exists) and replacement != avatar:
            item["avatarImg"] = replacement
            changed = True
    return changed


def main():
    import os
    d = json.load(open("items.json", encoding="utf-8"))
    if _normalize_source_media(d):
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[media] stale source avatar paths normalized from sources.json")
    # --- Stacks house rule: em/en dashes are BANNED site-wide. Strip them at
    # build time so the site self-heals no matter what the generator produced. ---
    def _dedash(t, lang):
        if not t:
            return t
        sep = "\u3001" if lang == "ja" else ", "
        t = re.sub(r"\s+[\u2014\u2013\u2015]\s+", sep, t)
        t = re.sub(r"[\u2014\u2013\u2015]", "-", t)
        if lang == "ja":
            t = t.replace("\u3001\u3001", "\u3001")
        else:
            t = re.sub(r",\s*,", ", ", t)
            t = t.replace(" ,", ",")
        return t.strip()
    def _sanitize_dashes(doc):
        changed = False
        for it in doc.get("items", []):
            fields = [it.get("title"), it.get("gist"), it.get("why"), it.get("ask")]
            oc = it.get("outcome")
            if isinstance(oc, dict):
                fields.append(oc.get("note"))
            for val in fields:
                if isinstance(val, dict):
                    for lg in list(val.keys()):
                        nv = _dedash(val.get(lg) or "", lg)
                        if nv != val.get(lg):
                            val[lg] = nv; changed = True
            cov = it.get("cover")
            if isinstance(cov, dict) and isinstance(cov.get("label"), str):
                nl = re.sub(r"[\u2014\u2013\u2015]", " ", cov["label"]).strip()
                if nl != cov["label"]:
                    cov["label"] = nl; changed = True
        ents = doc.get("entities", {})
        if isinstance(ents, dict):
            for e in ents.values():
                if isinstance(e, dict):
                    for fld in ("desc", "longDesc", "sector", "ceo", "hq"):
                        val = e.get(fld)
                        if isinstance(val, dict):
                            for lg in list(val.keys()):
                                nv = _dedash(val.get(lg) or "", lg)
                                if nv != val.get(lg):
                                    val[lg] = nv; changed = True
        return changed
    if _sanitize_dashes(d):
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[dedash] em/en dashes stripped from items.json")
    # --- ts backfill: the app shows "N hours ago" for items <24h old, which needs
    # a per-item publish timestamp. Stamp any item missing `ts`: today's items get
    # "now" (approx. when they were carded, which is when this build runs on publish);
    # older items get their date at noon UTC so the app cleanly falls back to the date.
    # This guarantees ts regardless of which path added the card (scout or the
    # auto-publish session). Items that already carry ts are left untouched. ---
    def _stamp_ts(doc):
        changed = False
        now_dt = datetime.now(timezone.utc)
        today = now_dt.strftime("%Y-%m-%d")
        now_iso = now_dt.isoformat()
        for it in doc.get("items", []):
            if it.get("ts"):
                continue
            dt = it.get("date") or today
            candidate = now_iso if dt == today else (dt + "T12:00:00+00:00")
            try:
                if datetime.fromisoformat(candidate) > now_dt:
                    candidate = now_iso
            except Exception:
                candidate = now_iso
            it["ts"] = candidate
            changed = True
        return changed
    if _stamp_ts(d):
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[ts] backfilled publish timestamps in items.json")
    items = d["items"]
    entities = d.get("entities", {}) or {}
    # --- Curated static glossary: a durable term index independent of the
    # generator. glossary.json terms are merged into entities so BOTH the app
    # (linkifyEntities tooltips) and the SEO pages link them. This lowers the
    # bar for what gets a definition without editing the publishing routine. ---
    try:
        _gloss = json.load(open("glossary.json", encoding="utf-8"))
    except Exception:
        _gloss = {}
    _gadd = _gpatch = 0
    for _gk, _gv in _gloss.items():
        if _gk not in entities:
            entities[_gk] = _gv; _gadd += 1
            continue
        # Alias-only patch for an entity that already exists. A company that
        # renames itself (MicroStrategy -> Strategy) leaves its old aliases
        # behind and goes unindexed under the name the cards actually print;
        # before this, the only way to fix that was to edit items.json, which
        # only the publishing routine may write. Union, never remove.
        _have = entities[_gk].get("aliases") or []
        _low = {str(a).lower() for a in _have}
        _new = [a for a in (_gv.get("aliases") or []) if a and str(a).lower() not in _low]
        if _new:
            entities[_gk]["aliases"] = _have + _new
            _gpatch += 1
    if _gadd or _gpatch:
        d["entities"] = entities
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[glossary] merged " + str(_gadd) + " curated terms, patched aliases on "
              + str(_gpatch) + " existing entities")
    global EMBEDS
    try:
        EMBEDS = json.load(open("embeds.json", encoding="utf-8"))
    except Exception as e:
        EMBEDS = {}
        print("[embeds] embeds.json unavailable (" + str(e) + ") -- quote_block falls back to hand-written quotes only")

    items = sorted(items, key=lambda x: x.get("date", ""), reverse=True)
    register_slugs_from_aliases(entities)
    pats = build_matcher(entities)

    # which entities each item touches (for internal links)
    item_ents = {i["id"]: item_entities(i, entities, pats) for i in items}
    # group articles per entity
    ent_items = {}
    for i in items:
        for key in item_ents[i["id"]]:
            ent_items.setdefault(key, []).append(i)

    # aggregates behind the record blocks on every article page
    build_records(items, entities)

    ids = {i["id"] for i in items}
    # social share images (best-effort: skipped if Pillow/fonts unavailable)
    og = _og_setup()
    _download_avatars(items)
    og_ok = set()
    if og:
        os.makedirs("og", exist_ok=True)
        for i in items:
            path = f"og/{i['id']}.png"
            if not os.path.exists(path):
                try:
                    make_og(i, og)
                except Exception as e:
                    print(f"[og-skip] {i['id']}: {e}")
            if os.path.exists(path):
                og_ok.add(i["id"])
        for fn in os.listdir("og"):
            if (fn.endswith(".png") and fn[:-4] not in ids
                    and not fn.startswith(("theme-", "record-"))):
                os.remove(f"og/{fn}")
    else:
        print("[og] Pillow/CJK font unavailable — skipping share images")

    for _lg in LANGS:
        os.makedirs(LANG_DIR[_lg], exist_ok=True)
    # write per-article pages, one URL per available language (with entity links
    # + share image). Titles of related items are resolved per language so the
    # "Related" list shows headlines instead of raw slugs.
    langs_of = {i["id"]: item_langs(i) for i in items}
    title_by_lang = {
        lg: {i["id"]: (i["title"].get(lg) or "") for i in items if lg in langs_of[i["id"]]}
        for lg in LANGS
    }
    written = {lg: set() for lg in LANGS}
    for i in items:
        keys = sorted(k for k in item_ents[i["id"]] if k in ent_items)
        lgs = langs_of[i["id"]] or ["ko"]
        for lg in lgs:
            links = [(ent_label(k, entities.get(k), lg), slugify(k)) for k in keys]
            path = f"{LANG_DIR[lg]}/{i['id']}.html"
            with open(path, "w", encoding="utf-8") as f:
                f.write(page_html(i, links, og_img=(i["id"] in og_ok), lang=lg,
                                  langs=lgs, rel_titles=title_by_lang[lg]))
            written[lg].add(i["id"])
    for lg in LANGS:
        for fn in os.listdir(LANG_DIR[lg]):
            if fn.endswith(".html") and fn[:-5] not in written[lg]:
                os.remove(f"{LANG_DIR[lg]}/{fn}")
    print("[pages] " + " · ".join(f"{lg}:{len(written[lg])}" for lg in LANGS))

    # write per-entity pages in ko/en/ja (only entities that actually have articles)
    holder_index = load_13f_holder_index()
    for _ed in ("e", "e/en", "e/ja"):
        os.makedirs(_ed, exist_ok=True)
    ent_slugs = {}
    ent_indexable = []      # 사이트맵에 올릴 것 = ENTITY_MIN_ARTICLES 이상 (언어 무관)
    for key, its in ent_items.items():
        slug = slugify(key)
        ent_slugs[slug] = key
        if len(its) >= ENTITY_MIN_ARTICLES:
            ent_indexable.append(slug)
        for _lg in LANGS:
            _ep = f"e/{slug}.html" if _lg == "ko" else f"e/{_lg}/{slug}.html"
            with open(_ep, "w", encoding="utf-8") as f:
                f.write(entity_page(key, entities[key], its, _lg, holder_index=holder_index))
    for _ed in ("e", "e/en", "e/ja"):
        for fn in os.listdir(_ed):
            if fn.endswith(".html") and fn[:-5] not in ent_slugs:
                os.remove(f"{_ed}/{fn}")

    open("articles.html", "w", encoding="utf-8").write(articles_index(items))

    # theme debate + author record hub pages (SEO for #theme-/#record- views)
    theme_slugs, record_slugs = build_extra_pages(items, og)

    # weekly recap page (current week + dated archive) + its share card.
    # 카드는 매 빌드마다 덮어쓴다 (기사 OG와 달리 "이미 있으면 skip"이 아니다).
    try:
        make_scoreboard(items, og)
    except Exception as e:
        print(f"[og-skip] scoreboard: {e}")
    os.makedirs("week", exist_ok=True)
    iso = datetime.now(timezone.utc).date().isocalendar()
    wk_slug = f"{iso[0]}-w{iso[1]:02d}"
    wk_html = week_page(items, entities, item_ents, wk_slug)
    open(f"week/{wk_slug}.html", "w", encoding="utf-8").write(wk_html)
    open("this-week.html", "w", encoding="utf-8").write(
        wk_html.replace('<a class="top" href="../">', '<a class="top" href="./">')
               .replace('href="../p/', 'href="p/').replace('href="../e/', 'href="e/')
               .replace('href="../"', 'href="./"').replace('href="../articles.html"', 'href="articles.html"')
               .replace('href="../feed.xml"', 'href="feed.xml"').replace('href="../favicon-32.png"', 'href="favicon-32.png"')
    )
    week_slugs = sorted(fn[:-5] for fn in os.listdir("week") if fn.endswith(".html"))

    open("calendar.html", "w", encoding="utf-8").write(
        calendar_page(d.get("events") or [], items, set(ent_indexable)))

    open("sitemap.xml", "w", encoding="utf-8").write(
        sitemap(items, ent_indexable, week_slugs, theme_slugs, record_slugs))
    for _lg in LANGS:
        open(FEED_FILE[_lg], "w", encoding="utf-8").write(feed(items, _lg))
    open("robots.txt", "w", encoding="utf-8").write(robots())
    _ping_indexnow(items)
    print(f"[ok] {len(items)} article pages + {len(ent_slugs)} entity pages "
          f"({len(ent_indexable)} indexed, {len(ent_slugs) - len(ent_indexable)} noindex) "
          f"+ sitemap + feed + robots")


if __name__ == "__main__":
    main()

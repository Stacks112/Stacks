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
from datetime import datetime, timezone

BASE = "https://stacksdaily.com/"
SITE = "Stacks"
TAGLINE = {
    "ko": "전 세계 투자 고수들의 글을, 당신의 언어로",
    "en": "The world's best investing minds, in your language",
    "ja": "世界の投資の達人たちの記事を、あなたの言語で",
}
LANG_LABEL = {"ko": "한국어", "en": "English", "ja": "日本語"}
E = html.escape
NAME_ALIAS = {"메르": "메르 (ranto28)"}
def dispname(x):
    return NAME_ALIAS.get(x, x)


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
    (e.g. trailing \\b after 하이닉스 in "SK하이닉스")."""
    pats = []
    for key, e in entities.items():
        for a in e.get("aliases", []) or []:
            if not a:
                continue
            head = r"\b" if re.match(r"[A-Za-z0-9]", a) else ""
            tail = r"\b" if re.search(r"[A-Za-z0-9]$", a) else ""
            pats.append((re.compile(head + re.escape(a) + tail, re.I), key))
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


def page_html(item, ent_links=None, og_img=None):
    iid = item["id"]
    url = BASE + "p/" + iid + ".html"
    app_url = BASE + "#sig-" + iid
    cov = item.get("cover", {}) or {}
    grad = f"linear-gradient(135deg,{cov.get('from', '#111')},{cov.get('to', '#333')})"
    title_ko = item["title"].get("ko") or item["title"]["en"]
    desc = clip(item["gist"].get("ko") or item["gist"]["en"], 160)
    kw = ", ".join(item.get("tags", []) + [item.get("source", "")])

    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title_ko,
        "description": desc,
        "datePublished": item.get("date", "") + "T00:00:00Z",
        "dateModified": item.get("date", "") + "T00:00:00Z",
        "inLanguage": ["ko", "en", "ja"],
        "author": {"@type": "Person", "name": item.get("source", "Stacks")},
        "publisher": {"@type": "Organization", "name": "The Infrastructure Thesis"},
        "mainEntityOfPage": url,
        "isBasedOn": item.get("sourceUrl", ""),
        "url": url,
    }

    # summary blocks in each language present
    blocks = []
    for lang in ("ko", "en", "ja"):
        t = item["title"].get(lang)
        g = item["gist"].get(lang)
        w = item["why"].get(lang)
        if not g:
            continue
        blocks.append(
            f'<section class="lang" lang="{lang}">'
            f'<div class="lang-tag">{LANG_LABEL[lang]}</div>'
            f"<h2>{E(t)}</h2>"
            f'<p class="gist">{E(g)}</p>'
            f'<p class="why"><b>Why it matters</b> · {E(w)}</p>'
            f"</section>"
        )

    related = ""
    rel_ids = item.get("related") or []
    if rel_ids:
        links = "".join(
            f'<li><a href="{E(r)}.html">{E(r)}</a></li>' for r in rel_ids
        )
        related = f'<nav class="related"><h3>Related</h3><ul>{links}</ul></nav>'

    ent_html = ""
    if ent_links:
        chips = "".join(
            f'<a class="ent-chip" href="../e/{E(slug)}.html">{E(label)}</a>'
            for label, slug in ent_links
        )
        ent_html = f'<nav class="ent-nav"><h3>관련 종목·인물</h3><div class="ent-chips">{chips}</div></nav>'

    img_url = BASE + "og/" + iid + ".png" if og_img else ""
    # Recommended NewsArticle fields for richer Google results:
    #   image  -> the article's OG card (enables a large thumbnail in Search/News)
    #   author.url -> the author's X profile, when the avatar is an X-handle avatar
    if img_url:
        ld["image"] = img_url
    _m = re.search(r"unavatar\.io/twitter/([A-Za-z0-9_]+)", item.get("avatarImg", "") or "")
    if _m:
        ld["author"]["url"] = "https://x.com/" + _m.group(1)
    og_img_tags = (
        f'<meta property="og:image" content="{E(img_url)}">'
        f'<meta property="og:image:width" content="1200">'
        f'<meta property="og:image:height" content="630">'
        f'<meta name="twitter:image" content="{E(img_url)}">'
    ) if og_img else ""
    tw_card = "summary_large_image" if og_img else "summary"

    paywall = '<span class="paid">$ 원문은 유료 구독</span>' if item.get("paywall") else ""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>/* shared link (?l=xx): bounce a human into the live app in the sharer's language. No ?l = organic/SEO visit, so this stays a normal crawlable page. */
(function(){{try{{var l=new URLSearchParams(location.search).get('l');if(!l)return;location.replace('{BASE}?c={iid}&l='+encodeURIComponent(l));}}catch(e){{}}}})();</script>
<title>{E(title_ko)} · {SITE}</title>
<meta name="description" content="{E(desc)}">
<meta name="keywords" content="{E(kw)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(title_ko)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">
<meta property="article:published_time" content="{item.get('date','')}">
{og_img_tags}
<meta name="twitter:card" content="{tw_card}">
<meta name="twitter:title" content="{E(title_ko)}">
<meta name="twitter:description" content="{E(desc)}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,"Segoe UI",Roboto,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.7;color:#17181C;background:#fff}}
@media(prefers-color-scheme:dark){{body{{background:#0E0F12;color:#ECEDF1}}.card{{background:#141519!important}}.gist{{color:#C9CDD6!important}}}}
.wrap{{max-width:720px;margin:0 auto;padding:0 20px 60px}}
.topbar{{padding:16px 0;font-weight:800}}
.topbar a{{color:inherit;text-decoration:none}}
.cover{{height:120px;border-radius:16px;background:{grad};display:flex;align-items:flex-end;padding:16px;margin:8px 0 20px}}
.cover .label{{font-family:ui-monospace,Menlo,monospace;color:rgba(255,255,255,.85);font-size:26px;letter-spacing:.05em}}
.meta{{font-size:13px;color:#8E93A0;margin-bottom:4px}}
h1{{font-size:26px;line-height:1.3;letter-spacing:-.02em;margin:.2em 0 .6em}}
.lang{{border-top:1px solid #ECEDF1;padding-top:18px;margin-top:22px}}
@media(prefers-color-scheme:dark){{.lang{{border-color:#26272E}}}}
.lang-tag{{font-family:ui-monospace,Menlo,monospace;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#8E93A0}}
.lang h2{{font-size:18px;margin:.3em 0 .5em}}
.gist{{color:#3E414B;white-space:pre-line}}
.why{{background:#F6F7F9;border-radius:12px;padding:12px 14px;font-size:14.5px}}
@media(prefers-color-scheme:dark){{.why{{background:#1A1B21}}}}
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
footer{{margin-top:40px;padding-top:20px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar"><a href="../">◆ {SITE}</a></div>
  <div class="cover"><span class="label">{E(cov.get('label',''))}</span></div>
  <div class="meta">{E(dispname(item.get('source','')))} · {E(item.get('date',''))} · 원문: {E(item.get('sourceLang',''))}</div>
  <h1>{E(title_ko)}</h1>
  <div class="actions">
    <a class="btn app" href="{E(app_url)}">Stacks 앱에서 보기 →</a>
    <a class="btn src" href="{E(item.get('sourceUrl','#'))}" target="_blank" rel="noopener nofollow">원문 보기 ↗</a>
    {paywall}
  </div>
  {''.join(blocks)}
  {ent_html}
  {related}
  <footer>
    요약·해설은 The Infrastructure Thesis의 창작물입니다. 원문의 저작권은 원저작자에게 있으며, 각 항목은 출처를 표기하고 원문으로 링크합니다. 투자 자문이 아닙니다.<br>
    <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
  </footer>
</div>
</body>
</html>
"""


def entity_page(key, e, ent_items):
    slug = slugify(key)
    url = BASE + "e/" + slug + ".html"
    kind = e.get("kind")
    sector = (e.get("sector", {}) or {}).get("ko") or (e.get("sector", {}) or {}).get("en", "")
    desc = ((e.get("longDesc") or {}).get("ko")
            or (e.get("desc", {}) or {}).get("ko")
            or (e.get("desc", {}) or {}).get("en", ""))
    ticker = (e.get("ticker") or "").upper()
    facts = []
    def _loc(v):  # field may be a {en,ko,ja} object or a plain string
        return (v.get("ko") or v.get("en") or "") if isinstance(v, dict) else str(v)
    for label, k in (("대표", "ceo"), ("설립", "founded"), ("상장", "listed"), ("본사", "hq"), ("거래소", "exchange")):
        if e.get(k):
            facts.append(f"<span><b>{label}</b> {E(_loc(e[k]))}</span>")
    if e.get("website"):
        w = e["website"]
        facts.append(f'<span><b>웹사이트</b> <a href="{E(w)}" target="_blank" rel="noopener nofollow">{E(w.replace("https://","").replace("www.",""))}</a></span>')
    facts_html = f'<p class="facts">{" · ".join(facts)}</p>' if facts else ""
    metadesc = clip(desc or f"{key} 관련 투자 읽을거리 모음", 160)
    rows = "".join(
        f'<li>{("<b class=sp-" + i.get("stance") + ">" + STANCE_KO.get(i.get("stance"), "관점") + "</b> ") if i.get("stance") else ""}'
        f'<a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
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
                      + (f'<b class="bl">강세 {_b}</b>' if _b else "")
                      + (f'<b class="wa">관점 {_w}</b>' if _w else "")
                      + (f'<b class="be">약세 {_r}</b>' if _r else "")
                      + "</div>")
    _st_ko = {"pending": "채점 대기", "hit": "적중", "miss": "빗나감"}
    _preds = [i for i in ent_items if i.get("outcome") and i["outcome"].get("status")]
    preds_html = ""
    if _preds:
        _li = []
        for i in _preds:
            oc = i["outcome"]; note = oc.get("note") or {}
            nt = note.get("ko") or note.get("en") or ""
            _li.append(f'<li><span class="oc oc-{E(oc["status"])}">{_st_ko.get(oc["status"], "채점 대기")}</span> '
                       f'<a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
                       f'<span class="d">{E(nt)}</span></li>')
        preds_html = f'<h2>예측 · 적중 기록 {len(_preds)}건</h2><ul class="preds">{"".join(_li)}</ul>'

    about = {"@type": "Organization" if kind == "company" else ("DefinedTerm" if kind == "term" else "Person"), "name": key}
    if kind == "company" and ticker:
        about["tickerSymbol"] = ticker.split(".")[0]
    if e.get("url"):
        about["url"] = e["url"]
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": key, "description": metadesc, "url": url, "about": about,
        "mainEntity": {
            "@type": "ItemList", "numberOfItems": len(ent_items),
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1,
                 "url": BASE + "p/" + i["id"] + ".html",
                 "name": i["title"].get("ko") or i["title"]["en"]}
                for n, i in enumerate(ent_items)
            ],
        },
    }
    tk = f'<span class="tk">{E(ticker)}</span>' if ticker else ""
    prof = f'<a class="prof" href="{E(e["url"])}" target="_blank" rel="noopener nofollow">프로필 ↗</a>' if e.get("url") else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{E(key)} — 관련 글 {len(ent_items)}건 · {SITE}</title>
<meta name="description" content="{E(metadesc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{E(key)} · {SITE}">
<meta property="og:description" content="{E(metadesc)}">
<meta property="og:url" content="{E(url)}">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
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
footer{{margin-top:34px;padding-top:18px;border-top:1px solid #ECEDF1;font-size:12px;color:#8E93A0}}
@media(prefers-color-scheme:dark){{footer{{border-color:#26272E}}}}
footer a{{color:#8E93A0}}
</style>
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="sector">{E(sector)}</div>
<h1>{E(key)}{tk}</h1>
<p class="desc">{E(desc)}</p>
{facts_html}
{prof}
{tally_html}
{preds_html}
<h2>관련 글 {len(ent_items)}건</h2>
<ul>{rows}</ul>
<footer>
  요약·해설은 The Infrastructure Thesis의 창작물이며 투자 자문이 아닙니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
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
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>전체 글 · {SITE}</title>
<meta name="description" content="{E(TAGLINE['ko'])} — 전체 글 목록.">
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
</head>
<body>
<h1><a href="./" style="text-decoration:none">◆ {SITE}</a> — 전체 글</h1>
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
        stance_html = (f'<p class="stance">이번 주 방향성 콜 — '
                       f'<b class="bl">강세 {bull}</b> · <b class="be">약세 {bear}</b>. '
                       f'각 콜의 실제 성과는 <a href="../#">앱의 적중 기록</a>에서 확인.</p>')
    metadesc = clip(f"이번 주 Stacks에 올라온 투자 읽을거리 {len(wk_items)}편 요약 — "
                    + ", ".join(i["title"].get("ko") or i["title"]["en"] for i in wk_items[:3]), 160)
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": f"이번 주 Stacks · {wk_label}", "description": metadesc, "url": dated_url,
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
<meta name="twitter:card" content="summary_large_image">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1656582515648973" crossorigin="anonymous"></script>
<link rel="icon" href="../favicon-32.png">
<link rel="alternate" type="application/rss+xml" title="Stacks" href="../feed.xml">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
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
  요약·해설은 The Infrastructure Thesis의 창작물이며 투자 자문이 아닙니다.<br>
  <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
</footer>
</body>
</html>
"""


def sitemap(items, entity_slugs=None, week_slugs=None, theme_slugs=None, record_slugs=None):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [(BASE, now, "1.0"), (BASE + "this-week.html", now, "0.7"),
            (BASE + "articles.html", now, "0.6")]
    for i in items:
        urls.append((BASE + "p/" + i["id"] + ".html", i.get("date", now), "0.8"))
    for slug in (entity_slugs or []):
        urls.append((BASE + "e/" + slug + ".html", now, "0.7"))
    for slug in (week_slugs or []):
        urls.append((BASE + "week/" + slug + ".html", now, "0.6"))
    for slug in (theme_slugs or []):
        urls.append((BASE + "t/" + slug + ".html", now, "0.8"))
    for slug in (record_slugs or []):
        urls.append((BASE + "r/" + slug + ".html", now, "0.8"))
    body = "".join(
        f"<url><loc>{E(u)}</loc><lastmod>{E(m)}</lastmod><priority>{p}</priority></url>"
        for u, m, p in urls
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def feed(items):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    entries = []
    for i in items[:30]:
        link = BASE + "p/" + i["id"] + ".html"
        title = i["title"].get("ko") or i["title"]["en"]
        desc = clip(i["gist"].get("ko") or i["gist"]["en"], 400)
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
        f"<description>{E(TAGLINE['ko'])}</description>"
        f"<language>ko</language><lastBuildDate>{now}</lastBuildDate>"
        f'<atom:link xmlns:atom="http://www.w3.org/2005/Atom" href="{BASE}feed.xml" rel="self" type="application/rss+xml"/>'
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
    og_tags = ""
    tw = "summary"
    if og_id and os.path.exists(f"og/{og_id}.png"):
        img = BASE + "og/" + og_id + ".png"
        og_tags = (f'<meta property="og:image" content="{E(img)}">'
                   f'<meta property="og:image:width" content="1200">'
                   f'<meta property="og:image:height" content="630">'
                   f'<meta name="twitter:image" content="{E(img)}">')
        tw = "summary_large_image"
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
<style>{_HUB_CSS}</style>
</head>
<body>
<a class="top" href="../">◆ {SITE}</a>
<div class="kicker">{E(kicker)}</div>
<h1>{h1}</h1>
<p class="lead">{E(lead)}</p>
{body_html}
<a class="cta" href="{E(app_url)}">Stacks 앱에서 라이브로 보기 →</a>
<footer>
  요약·해설은 The Infrastructure Thesis의 창작물이며 투자 자문이 아닙니다.<br>
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
        title = f"{th['ko']} — 강세 {b} · 약세 {r} 논쟁 · {SITE}"
        lead = (f"{th['ko']}를 둘러싼 전 세계 투자 논객들의 견해 {len(t_items)}건. "
                f"강세 {b} · 관점 {w} · 약세 {r}. 누가 맞았는지는 적중 기록으로 검증됩니다.")
        metadesc = clip(lead, 160)
        tally = (f'<div class="tally">{"<b class=bl>강세 " + str(b) + "</b>" if b else ""}'
                 f'{"<b class=wa>관점 " + str(w) + "</b>" if w else ""}'
                 f'{"<b class=be>약세 " + str(r) + "</b>" if r else ""}</div>')
        body = tally + f"<h2>관련 글 {len(t_items)}건</h2><ul>" + _item_rows(t_items) + "</ul>"
        _pseudo_og(og, "theme-" + key, th["en"].upper(),
                   f"{th['icon']} {th['ko']} — 강세 {b} · 약세 {r}")
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


def main():
    import os
    d = json.load(open("items.json", encoding="utf-8"))
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
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_iso = datetime.now(timezone.utc).isoformat()
        for it in doc.get("items", []):
            if it.get("ts"):
                continue
            dt = it.get("date") or today
            it["ts"] = now_iso if dt == today else (dt + "T12:00:00+00:00")
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
    _gadd = 0
    for _gk, _gv in _gloss.items():
        if _gk not in entities:
            entities[_gk] = _gv; _gadd += 1
    if _gadd:
        d["entities"] = entities
        json.dump(d, open("items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[glossary] merged " + str(_gadd) + " curated terms into entities")
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

    os.makedirs("p", exist_ok=True)
    # write per-article pages (with entity links + share image)
    for i in items:
        links = [(k, slugify(k)) for k in item_ents[i["id"]] if k in ent_items]
        links.sort(key=lambda x: x[0])
        with open(f"p/{i['id']}.html", "w", encoding="utf-8") as f:
            f.write(page_html(i, links, og_img=(i["id"] in og_ok)))
    for fn in os.listdir("p"):
        if fn.endswith(".html") and fn[:-5] not in ids:
            os.remove(f"p/{fn}")

    # write per-entity pages (only entities that actually have articles)
    os.makedirs("e", exist_ok=True)
    ent_slugs = {}
    for key, its in ent_items.items():
        slug = slugify(key)
        ent_slugs[slug] = key
        with open(f"e/{slug}.html", "w", encoding="utf-8") as f:
            f.write(entity_page(key, entities[key], its))
    for fn in os.listdir("e"):
        if fn.endswith(".html") and fn[:-5] not in ent_slugs:
            os.remove(f"e/{fn}")

    open("articles.html", "w", encoding="utf-8").write(articles_index(items))

    # theme debate + author record hub pages (SEO for #theme-/#record- views)
    theme_slugs, record_slugs = build_extra_pages(items, og)

    # weekly recap page (current week + dated archive)
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

    open("sitemap.xml", "w", encoding="utf-8").write(
        sitemap(items, list(ent_slugs.keys()), week_slugs, theme_slugs, record_slugs))
    open("feed.xml", "w", encoding="utf-8").write(feed(items))
    open("robots.txt", "w", encoding="utf-8").write(robots())
    _ping_indexnow(items)
    print(f"[ok] {len(items)} article pages + {len(ent_slugs)} entity pages + sitemap + feed + robots")


if __name__ == "__main__":
    main()

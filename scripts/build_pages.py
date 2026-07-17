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


def clip(text, n):
    t = re.sub(r"\s+", " ", text or "").strip()
    return t[: n - 1].rstrip() + "…" if len(t) > n else t


# ---- entity (company / person) association + slugs ----
SLUG_OVERRIDE = {"메르": "meru"}


def slugify(key):
    if key in SLUG_OVERRIDE:
        return SLUG_OVERRIDE[key]
    s = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return s or "x"


def build_matcher(entities):
    """[(compiled_regex, key)] over every alias; ASCII aliases are word-bounded."""
    pats = []
    for key, e in entities.items():
        for a in e.get("aliases", []) or []:
            if not a:
                continue
            if re.match(r"[\x00-\x7f]", a):
                pats.append((re.compile(r"\b" + re.escape(a) + r"\b", re.I), key))
            else:
                pats.append((re.compile(re.escape(a)), key))
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


def make_og(item, og):
    Image, ImageDraw, ImageFont, boldp, regp = og
    W, H, M = OG_W, OG_H, 70
    frm = _hex((item.get("cover") or {}).get("from"))
    to = _hex((item.get("cover") or {}).get("to"))
    # diagonal gradient (small then upscaled = smooth + fast)
    sm = (64, 34)
    mask = Image.new("L", sm)
    mask.putdata([int(255 * ((x / (sm[0] - 1)) + (y / (sm[1] - 1))) / 2)
                  for y in range(sm[1]) for x in range(sm[0])])
    base = Image.new("RGB", (W, H), frm)
    top = Image.new("RGB", (W, H), to)
    img = Image.composite(top, base, mask.resize((W, H)))
    # darken bottom for legible text
    ov = Image.new("L", (1, H))
    ov.putdata([int(210 * max(0, (y - H * 0.34) / (H * 0.66))) for y in range(H)])
    img = Image.composite(Image.new("RGB", (W, H), (12, 13, 16)), img, ov.resize((W, H)))
    d = ImageDraw.Draw(img)
    fTitle = ImageFont.truetype(boldp, 60)
    fMeta = ImageFont.truetype(regp, 30)
    fBrand = ImageFont.truetype(boldp, 30)
    fLabel = ImageFont.truetype(boldp, 44)
    # brand + cover label (top)
    d.text((M, M - 8), "◆ STACKS", font=fBrand, fill=(255, 255, 255))
    label = (item.get("cover") or {}).get("label", "")
    if label:
        d.text((M, M + 44), label, font=fLabel, fill=(232, 232, 238))
    # title (bottom, up to 3 lines)
    title = item["title"].get("ko") or item["title"]["en"]
    lines = _wrap(d, title, fTitle, W - 2 * M, 3)
    lh = 74
    ty = H - M - 46 - lh * len(lines)
    for i, ln in enumerate(lines):
        d.text((M, ty + i * lh), ln, font=fTitle, fill=(255, 255, 255))
    # source · date
    meta = f"{item.get('source','')}  ·  {item.get('date','')}"
    d.text((M, H - M - 4), meta, font=fMeta, fill=(226, 232, 240))
    import os
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
  <div class="meta">{E(item.get('source',''))} · {E(item.get('date',''))} · 원문: {E(item.get('sourceLang',''))}</div>
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
    desc = (e.get("desc", {}) or {}).get("ko") or (e.get("desc", {}) or {}).get("en", "")
    ticker = (e.get("ticker") or "").upper()
    metadesc = clip(desc or f"{key} 관련 투자 읽을거리 모음", 160)
    rows = "".join(
        f'<li><a href="../p/{E(i["id"])}.html">{E(i["title"].get("ko") or i["title"]["en"])}</a>'
        f' <span class="d">{E(i.get("source",""))} · {E(i.get("date",""))}</span></li>'
        for i in ent_items
    )
    about = {"@type": "Organization" if kind == "company" else "Person", "name": key}
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
{prof}
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
        f' <span class="d">{E(i.get("source",""))} · {E(i.get("date",""))}</span></li>'
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


def sitemap(items, entity_slugs=None):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [(BASE, now, "1.0"), (BASE + "articles.html", now, "0.6")]
    for i in items:
        urls.append((BASE + "p/" + i["id"] + ".html", i.get("date", now), "0.8"))
    for slug in (entity_slugs or []):
        urls.append((BASE + "e/" + slug + ".html", now, "0.7"))
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


def main():
    import os
    d = json.load(open("items.json", encoding="utf-8"))
    items = d["items"]
    entities = d.get("entities", {}) or {}
    items = sorted(items, key=lambda x: x.get("date", ""), reverse=True)
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
            if fn.endswith(".png") and fn[:-4] not in ids:
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
    open("sitemap.xml", "w", encoding="utf-8").write(sitemap(items, list(ent_slugs.keys())))
    open("feed.xml", "w", encoding="utf-8").write(feed(items))
    open("robots.txt", "w", encoding="utf-8").write(robots())
    print(f"[ok] {len(items)} article pages + {len(ent_slugs)} entity pages + sitemap + feed + robots")


if __name__ == "__main__":
    main()

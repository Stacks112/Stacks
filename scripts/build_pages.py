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


def rfc822(date_str):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        d = datetime.now(timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


def page_html(item):
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
<meta name="twitter:card" content="summary">
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
  {related}
  <footer>
    요약·해설은 The Infrastructure Thesis의 창작물입니다. 원문의 저작권은 원저작자에게 있으며, 각 항목은 출처를 표기하고 원문으로 링크합니다. 투자 자문이 아닙니다.<br>
    <a href="../">{SITE} 홈</a> · <a href="../articles.html">전체 글</a> · <a href="../feed.xml">RSS</a>
  </footer>
</div>
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


def sitemap(items):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [(BASE, now, "1.0"), (BASE + "articles.html", now, "0.6")]
    for i in items:
        urls.append((BASE + "p/" + i["id"] + ".html", i.get("date", now), "0.8"))
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
    items = sorted(items, key=lambda x: x.get("date", ""), reverse=True)
    os.makedirs("p", exist_ok=True)
    ids = {i["id"] for i in items}
    # write per-article pages
    for i in items:
        with open(f"p/{i['id']}.html", "w", encoding="utf-8") as f:
            f.write(page_html(i))
    # prune orphan pages whose item no longer exists
    for fn in os.listdir("p"):
        if fn.endswith(".html") and fn[:-5] not in ids:
            os.remove(f"p/{fn}")
    open("articles.html", "w", encoding="utf-8").write(articles_index(items))
    open("sitemap.xml", "w", encoding="utf-8").write(sitemap(items))
    open("feed.xml", "w", encoding="utf-8").write(feed(items))
    open("robots.txt", "w", encoding="utf-8").write(robots())
    print(f"[ok] {len(items)} article pages + sitemap + feed + robots + articles.html")


if __name__ == "__main__":
    main()

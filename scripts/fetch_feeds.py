"""Stacks feed sync — runs on GitHub Actions every 2 hours.

Pulls the public RSS feeds of the sources Stacks curates and stores a
clean JSON snapshot in feeds/, where the publishing pipeline can read
them. Naver blog posts additionally get their full text from the mobile
page (public posts only); if that fails, the RSS description is kept as
a fallback so the pipeline always has something to work with.

Feeds are official syndication endpoints; every item keeps its source
link, and the app publishes summaries with attribution only.
"""

import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
KEEP_DAYS = 7          # only keep items from the last week
MAX_ITEMS = 15         # per feed
MAX_CONTENT = 20000    # chars of body text per item

FEEDS = [
    {"id": "meru", "url": "https://rss.blog.naver.com/ranto28.xml", "naver": True},
    {"id": "doomberg", "url": "https://newsletter.doomberg.com/feed", "naver": False},
    {"id": "netinterest", "url": "https://www.netinterest.co/feed", "naver": False},
    {"id": "emin", "url": "https://note.com/eminyurumazu/rss", "naver": False},
    {"id": "trump", "url": "https://trumpstruth.org/feed", "naver": False},
    # Serenity's X posts via RSS.app (the real firehose — tweets with full
    # text; item links point at the original x.com posts)
    {"id": "serenity", "url": "https://rss.app/feeds/l9RrQptvTxFq0UP4.xml", "naver": False},
    {"id": "serenity_substack", "url": "https://aleabitoreddit.substack.com/feed", "naver": False},
    {"id": "goto", "url": "https://note.com/goto_finance/rss", "naver": False},
    {"id": "semianalysis", "url": "https://newsletter.semianalysis.com/feed", "naver": False},
    {"id": "tesuta", "url": "https://rss.app/feeds/u6twTSFkvGHn7Tlw.xml", "naver": False},
]


def strip_tags(s: str) -> str:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def parse_rss(xml_text: str):
    """Return [{title, link, published, description}] from RSS or Atom."""
    root = ET.fromstring(xml_text)
    out = []
    # RSS 2.0
    for item in root.iter("item"):
        def g(tag):
            el = item.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        content = ""
        for child in item:
            if child.tag.endswith("encoded") and child.text:  # content:encoded
                content = child.text
                break
        out.append({
            "title": g("title"),
            "link": g("link"),
            "published": g("pubDate"),
            "description": content or g("description"),
        })
    if out:
        return out
    # Atom fallback
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in root.findall("a:entry", ns):
        link_el = e.find("a:link", ns)
        content_el = e.find("a:content", ns)
        if content_el is None:  # note: empty Elements are falsy, so test None explicitly
            content_el = e.find("a:summary", ns)
        out.append({
            "title": (e.findtext("a:title", "", ns) or "").strip(),
            "link": link_el.get("href", "") if link_el is not None else "",
            "published": (e.findtext("a:published", "", ns) or e.findtext("a:updated", "", ns) or "").strip(),
            "description": content_el.text if content_el is not None and content_el.text else "",
        })
    return out


def parse_date(s: str):
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def naver_full_text(link: str) -> str:
    """Public Naver blog post -> plain text via the mobile page."""
    m = re.search(r"blog\.naver\.com/([^/?]+)[/?].*?(\d{9,})", link) or \
        re.search(r"blog\.naver\.com/([^/]+)/(\d+)", link)
    if not m:
        return ""
    url = f"https://m.blog.naver.com/{m.group(1)}/{m.group(2)}"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    body = re.search(r'<div[^>]+class="[^"]*se-main-container[^"]*"[^>]*>(.*?)</div>\s*<div[^>]+class="[^"]*(?:post_btn|blog_btn|section_t1)', r.text, re.S)
    if not body:
        body = re.search(r'<div[^>]+class="[^"]*se-main-container[^"]*"[^>]*>(.*)', r.text, re.S)
    return strip_tags(body.group(1))[:MAX_CONTENT] if body else ""


def main():
    os.makedirs("feeds", exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)

    for feed in FEEDS:
        path = f"feeds/{feed['id']}.json"
        try:
            r = requests.get(feed["url"], headers=UA, timeout=25)
            r.raise_for_status()
            items = parse_rss(r.text)[:MAX_ITEMS]

            cleaned = []
            for it in items:
                dt = parse_date(it["published"])
                if dt is not None and dt < cutoff:
                    continue
                content = strip_tags(it.get("description") or "")[:MAX_CONTENT]
                if feed["naver"]:
                    try:
                        full = naver_full_text(it["link"])
                        if len(full) > len(content):
                            content = full
                    except Exception:
                        pass  # keep RSS description as fallback
                cleaned.append({
                    "title": it["title"],
                    "link": it["link"],
                    "published": dt.isoformat() if dt else it["published"],
                    "content": content,
                })

            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"source": feed["id"], "fetched_at": datetime.now(timezone.utc).isoformat(), "items": cleaned},
                    f, ensure_ascii=False, indent=1,
                )
            print(f"[ok] {feed['id']}: {len(cleaned)} items")
        except Exception as e:
            # never fail the whole run because one source hiccuped;
            # leave the previous snapshot in place
            print(f"[skip] {feed['id']}: {e}")


if __name__ == "__main__":
    main()

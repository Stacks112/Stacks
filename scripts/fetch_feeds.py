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
KEEP_DAYS = 7          # default retention; per-feed "keep_days" overrides it
MAX_ITEMS = 15         # per feed
MAX_CONTENT = 20000    # chars of body text per item

# Authors who publish weekly or monthly need a longer window than the daily
# firehoses, otherwise a single quiet fortnight empties their feed entirely.
SLOW_DAYS = 30

FEEDS = [
    {"id": "meru", "url": "https://rss.blog.naver.com/ranto28.xml", "naver": True},
    {"id": "doomberg", "url": "https://newsletter.doomberg.com/feed", "keep_days": SLOW_DAYS, "naver": False},
    {"id": "netinterest", "url": "https://www.netinterest.co/feed", "keep_days": SLOW_DAYS, "naver": False},
    {"id": "emin", "url": "https://note.com/eminyurumazu/rss", "naver": False},
    {"id": "trump", "url": "https://trumpstruth.org/feed", "naver": False},
    # The sitting Treasury Secretary. First-party voice on issuance, tariffs, the
    # dollar and the deficit, which the roster otherwise only gets second hand
    # through Kobeissi. Posts most days, so unlike the weekly longform sources it
    # actually clears the 48h publishing window. The three handling rules that
    # keep this from becoming a press-release feed live in sources.json.
    {"id": "bessent", "url": "https://rss.app/feeds/SgkcwvGZgvrR8L8l.xml", "naver": False},
    # Serenity's X posts via RSS.app (the real firehose — tweets with full
    # text; item links point at the original x.com posts)
    {"id": "serenity", "url": "https://rss.app/feeds/l9RrQptvTxFq0UP4.xml", "naver": False},
    # (serenity_substack removed 2026-08-03. A plain *.substack.com host answers
    # the Actions IP with 403, and unlike macroalf this entry had no RSS.app
    # mirror to fall back to, so it never fetched successfully once since it was
    # added. The Substack itself has also been quiet since 2026-05-19. The X feed
    # above already covers this author. Do not re-add without a mirror URL.)
    {"id": "goto", "url": "https://note.com/goto_finance/rss", "naver": False},
    {"id": "semianalysis", "url": "https://newsletter.semianalysis.com/feed", "keep_days": SLOW_DAYS, "naver": False},
    {"id": "tesuta", "url": "https://rss.app/feeds/u6twTSFkvGHn7Tlw.xml", "naver": False},
    {"id": "damodaran", "url": "https://aswathdamodaran.blogspot.com/feeds/posts/default?alt=rss",
     "alt": ["https://aswathdamodaran.blogspot.com/feeds/posts/default"], "keep_days": SLOW_DAYS, "naver": False},
    # The Diff is paywalled: its own Ghost feed only exposes a handful of old
    # free posts, so the RSS.app mirror of the archive stays the primary source.
    # (Mirror replaced 2026-07-25 after the previous one expired on 07-21.)
    {"id": "thediff", "url": "https://rss.app/feeds/z6fS0HqcbN8wsqBX.xml",
     "alt": ["https://www.thediff.co/rss/"],
     "keep_days": SLOW_DAYS, "naver": False},
    {"id": "lynalden", "url": "https://www.lynalden.com/feed/",
     "alt": ["https://www.lynalden.com/?feed=rss2", "https://www.lynalden.com/rss"],
     "keep_days": SLOW_DAYS, "naver": False},
    {"id": "jukan", "url": "https://rss.app/feeds/omtVLSiXRcVmtR6o.xml", "naver": False},
    # The Macro Compass publishes on Substack; the RSS.app mirror never returned an item.
    {"id": "macroalf", "url": "https://themacrocompass.substack.com/feed",
     "alt": ["https://rss.app/feeds/eGT8EYReWt302sdv.xml"], "keep_days": SLOW_DAYS, "naver": False},
    {"id": "bilello", "url": "https://bilello.blog/feed",
     "alt": ["https://bilello.blog/feed/", "https://bilello.blog/?feed=rss2", "https://bilello.blog/rss"],
     "keep_days": SLOW_DAYS, "naver": False},
    # Ming-Chi Kuo publishes his supply chain surveys on Medium in full, which
    # gives us a first-party feed with no RSS.app dependency.
    {"id": "kuo", "url": "https://medium.com/feed/@mingchikuo",
     "alt": ["https://medium.com/@mingchikuo/feed"], "keep_days": SLOW_DAYS, "naver": False},
    # Kuo's X posts are often standalone survey findings rather than Medium
    # teasers, so they come in as a second intake for the same author.
    {"id": "kuo_x", "url": "https://rss.app/feeds/5oPJGdosE6WHIdfW.xml",
     "keep_days": SLOW_DAYS, "naver": False},
    {"id": "kobeissi", "url": "https://rss.app/feeds/J2DSUc2Rd6QylcPV.xml", "naver": False},
    {"id": "camillo", "url": "https://rss.app/feeds/pMv7wgdkXM18ya8j.xml", "naver": False},
    # CEO accounts post a handful of times a year, so the 7-day default empties
    # their feed between posts and the author silently drops out of the candidate
    # pool. jensen fell to zero items on 2026-08-03 because its newest post
    # (07-27 11:07) sat 51 minutes on the wrong side of that day's cutoff.
    # Handle verification still matters here: the RSS.app mirror carries old spam
    # from impersonator accounts, so the publishing routine keeps taking only
    # items whose link is exactly x.com/<handle>/.
    {"id": "pichai", "url": "https://rss.app/feeds/ZvZmzc2japqBY4kW.xml",
     "keep_days": SLOW_DAYS, "naver": False},
    {"id": "jensen", "url": "https://rss.app/feeds/tLWYaMsky2fJ8tkW.xml",
     "keep_days": SLOW_DAYS, "naver": False},
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


def load_previous(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def fetch_entries(feed: dict):
    """Try the feed's URL then its fallbacks. Returns (url, entries, error).

    A 200 response that parses to zero entries counts as a miss, not a
    success: a blog whose /feed path has been disabled usually answers with
    the homepage HTML, which is indistinguishable from a healthy but empty
    feed unless we keep looking.
    """
    urls = [feed["url"]] + list(feed.get("alt") or [])
    last_err = None
    for url in urls:
        try:
            r = requests.get(url, headers=UA, timeout=25)
            r.raise_for_status()
            entries = parse_rss(r.text)
            if entries:
                return url, entries, None
            last_err = "parsed 0 entries (endpoint may not be a feed)"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
    return urls[0], [], last_err


def main():
    os.makedirs("feeds", exist_ok=True)
    now = datetime.now(timezone.utc)
    stale = []

    for feed in FEEDS:
        path = f"feeds/{feed['id']}.json"
        prev = load_previous(path)
        keep_days = feed.get("keep_days", KEEP_DAYS)
        cutoff = now - timedelta(days=keep_days)

        url, entries, error = fetch_entries(feed)
        raw_count = len(entries)

        cleaned = []
        newest = None
        for it in entries[:MAX_ITEMS]:
            dt = parse_date(it["published"])
            if dt is not None and (newest is None or dt > newest):
                newest = dt
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

        ok = error is None
        # A failed fetch keeps the last good items so the publisher still has
        # something to read, but it must never look fresh: fetched_at only
        # moves on success, and checked_at records that we did try.
        snapshot = {
            "source": feed["id"],
            "fetched_at": now.isoformat() if ok else (prev.get("fetched_at") or now.isoformat()),
            "checked_at": now.isoformat(),
            "ok": ok,
            "url_used": url,
            "keep_days": keep_days,
            "raw_count": raw_count,
            # Newest item the feed offered, whatever the retention window. Without
            # it a kept_count of 0 cannot tell a quiet author from a stale mirror.
            "newest_published": newest.isoformat() if newest else prev.get("newest_published"),
            "kept_count": len(cleaned) if ok else len(prev.get("items", [])),
            "error": error,
            "items": cleaned if ok else prev.get("items", []),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=1)

        if ok:
            note = f"[ok] {feed['id']}: {len(cleaned)} items (of {raw_count} in feed)"
            if not cleaned:
                note += f" — nothing newer than {keep_days}d (newest: {newest.date() if newest else '?'})"
                stale.append(feed["id"])
            print(note)
        else:
            stale.append(feed["id"])
            print(f"[fail] {feed['id']}: {error} (kept previous {len(snapshot['items'])} items)")

    if stale:
        # Surfaced in the Actions log so a dead source cannot sit unnoticed.
        print(f"\n[attention] no fresh items from: {', '.join(stale)}")


if __name__ == "__main__":
    main()

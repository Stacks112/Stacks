#!/usr/bin/env python3
"""Pull the original X post for every X-sourced item into embeds.json.

Why this exists
---------------
Our cards carry a translated reading of somebody else's post. Without the
original visible, the card reads as if the argument came from nowhere, and the
attribution sits at the bottom where nobody looks. Putting the author's own
words at the top fixes both, and sends the click to them rather than to us.

Why oEmbed and not scraping
---------------------------
publish.twitter.com/oembed is X's own endpoint, needs no key, and returns text
the author published, which is exactly the material we are allowed to quote. It
also gives us the canonical author name and permalink instead of whatever the
RSS mirror decided to call them.

Why we do not ship X's widgets.js
---------------------------------
The oEmbed response includes a <script> that renders the post client-side. It
costs ~120 KB on a cross-origin connection, paints after our card, and reflows
it. We parse the returned blockquote into fields and render them with our own
CSS (omit_script=1 asks X not to send the script at all).

Where it runs
-------------
On a GitHub runner, not in the publishing sandbox — the sandbox has no route to
X. Failure is not fatal: an item with no embed falls back to the plain `quote`
block, so a bad network day degrades one block instead of breaking a build.
"""

import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS = os.path.join(ROOT, "items.json")
OUT = os.path.join(ROOT, "embeds.json")

OEMBED = "https://publish.twitter.com/oembed"
UA = "stacksdaily.com embed fetcher (+https://stacksdaily.com)"
TIMEOUT = 15
PAUSE = 0.7          # be a polite neighbour; ~100 posts is ~70s
MAX_NEW = 40         # per run, so a cold start spreads over a few runs
MAX_LINES = 4        # paragraphs kept from the post body
STATUS_RE = re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/(\d+)", re.I)


def log(msg):
    print("fetch_embeds: " + msg, flush=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except Exception as e:
        log("could not read %s (%s)" % (os.path.basename(path), e))
        return default


def oembed(url):
    q = urllib.parse.urlencode({
        "url": url,
        "omit_script": "1",
        "dnt": "1",
        "hide_thread": "0",
        "lang": "en",
    })
    req = urllib.request.Request(OEMBED + "?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def parse(payload, url):
    """oEmbed html -> the handful of fields the card actually renders.

    The html is a <blockquote> holding <p> paragraphs of post text, then a
    trailing "— Name (@handle) Date" attribution line. A quoted post shows up
    as a second, shorter paragraph after the first; we keep it separately so
    the card can box it the way X does.
    """
    raw = payload.get("html") or ""
    body = re.search(r"<blockquote[^>]*>(.*?)</blockquote>", raw, re.S)
    inner = body.group(1) if body else raw

    paras = re.findall(r"<p[^>]*>(.*?)</p>", inner, re.S)
    lines = []
    for p in paras:
        p = re.sub(r"<br\s*/?>", "\n", p)
        p = re.sub(r"<[^>]+>", "", p)
        p = htmllib.unescape(p)
        # X puts the whole post in one <p> and separates the author's own
        # paragraphs with <br><br>. Split them back apart so the card can
        # space them the way the author wrote them.
        for chunk in re.split(r"\n\s*\n", p):
            # trailing media / permalink shortlink, in either rendered form
            chunk = re.sub(
                r"\s*(?:https?://)?(?:t\.co|pic\.(?:twitter|x)\.com)/\w+\s*$",
                "", chunk).strip()
            if chunk:
                lines.append(chunk)

    date = ""
    tail = re.search(r"</p>\s*&mdash;.*?\)\s*<a[^>]*>(.*?)</a>", inner, re.S)
    if tail:
        date = htmllib.unescape(re.sub(r"<[^>]+>", "", tail.group(1))).strip()

    name = (payload.get("author_name") or "").strip()
    handle = ""
    m = re.search(r"(?:x|twitter)\.com/([^/?#]+)", payload.get("author_url") or url)
    if m:
        handle = "@" + m.group(1)

    if not lines:
        return None
    return {
        "name": name,
        "handle": handle,
        "date": date,
        "url": payload.get("url") or url,
        "lines": lines[:MAX_LINES],
    }


def main():
    doc = load_json(ITEMS, None)
    if doc is None:
        log("items.json missing — nothing to do")
        return 0
    items = doc["items"] if isinstance(doc, dict) else doc
    have = load_json(OUT, {})
    if not isinstance(have, dict):
        have = {}

    targets = []
    for it in items:
        url = it.get("sourceUrl") or ""
        if not STATUS_RE.match(url):
            continue
        if it["id"] in have:
            continue
        targets.append((it["id"], url))

    if not targets:
        log("nothing new (%d cached)" % len(have))
        return 0

    # Newest first: items.json is date-ordered, and the cards a reader is most
    # likely to hit today should be the ones that fill in first.
    todo = targets[:MAX_NEW]
    log("%d X posts to fetch (%d queued, %d cached)"
        % (len(todo), len(targets), len(have)))

    ok = fail = 0
    for i, (iid, url) in enumerate(todo):
        try:
            got = parse(oembed(url), url)
        except Exception as e:
            fail += 1
            log("  %s: %s" % (iid, str(e)[:120]))
            got = None
        if got:
            have[iid] = got
            ok += 1
        if i + 1 < len(todo):
            time.sleep(PAUSE)

    # Drop entries whose item is gone, so the file cannot grow without bound.
    live = {it["id"] for it in items}
    have = {k: v for k, v in have.items() if k in live}

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(have, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    log("wrote %d entries (+%d new, %d failed)" % (len(have), ok, fail))
    # A failed fetch is a missing block, not a broken site. Never fail the job.
    return 0


if __name__ == "__main__":
    sys.exit(main())

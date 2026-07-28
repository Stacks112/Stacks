"""Fill the missing image on in-body article links — runs on GitHub Actions
(open network; the publishing sandbox is proxy-blocked and cannot reach news
sites).

WHY
---
An article the post cites in its body is written as a marker line in the gist:

    @@REF@@Headline (Publisher, 2026-07-28)|https://publisher.example/story

The renderer (index.html and scripts/build_pages.py) turns that into a
Twitter-style link card *with the article's picture* when — and only when — a
third `|image` field is present:

    @@REF@@Headline …|https://…/story|https://…/og-image.jpg   → image card
    @@REF@@Headline …|https://…/story                          → plain text link

The publishing routine records the headline and URL reliably but often omits
the image (the sandbox it runs in cannot fetch the publisher's page), so many
recent posts show their article links as bare text instead of image cards.

WHAT THIS DOES
--------------
For every `@@REF@@title|url` line that has no image field, fetch the linked
page's og:image and rewrite the line to `@@REF@@title|url|image`. The image is
hotlinked from the publisher's own server (never re-hosted) and the card
credits the source domain — the same Open Graph practice tier B of
fetch_cover_assets.py already uses for card covers. Reuses that module's
`og_image()` extractor and host denylist so there is one source of truth.

Idempotent: a REF that already carries an image is left alone; a URL whose
og:image cannot be fetched (blocked host, no tag, dead link) is left as a bare
link and retried on the next run. One network fetch per unique URL, cached
across items and languages, so the same article shared by several cards — or
present in ko/en/ja of one card — is fetched once.
"""

import json
import os
import re
import sys

# Reuse the OG extractor + denylist from the cover pipeline (same directory,
# same workflow step). Importing is safe: it is __main__-guarded.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_cover_assets import og_image, blocked  # noqa: E402

ITEMS = "items.json"
REF = "@@REF@@"


def log(*a):
    print(*a, flush=True)


def _fetch_cached(url, cache):
    """og:image for `url`, memoised. cache maps url -> image|None (None = tried
    and failed, so we never re-fetch a dead link within one run)."""
    if url in cache:
        return cache[url]
    img = None
    if url.startswith("http") and not blocked(url):
        try:
            img = og_image(url)
        except Exception as e:
            log(f"  [warn] {url}: {e}")
            img = None
    cache[url] = img
    return img


def backfill_text(text, cache):
    """Rewrite bare @@REF@@ lines in one gist string. Returns (new_text, n)."""
    if not text or REF not in text:
        return text, 0
    out = []
    n = 0
    for line in text.split("\n"):
        if line.startswith(REF):
            parts = line[len(REF):].split("|")
            # already has a non-empty image field -> leave untouched
            if len(parts) >= 3 and parts[2].strip():
                out.append(line)
                continue
            title = parts[0] if len(parts) >= 1 else ""
            url = (parts[1].strip() if len(parts) >= 2 else "")
            if not url:
                out.append(line)
                continue
            img = _fetch_cached(url, cache)
            if img:
                out.append(REF + "|".join([title, url, img]))
                n += 1
                log(f"  [ref] {url} <- {img}")
            else:
                out.append(line)
        else:
            out.append(line)
    return "\n".join(out), n


def main():
    if not os.path.exists(ITEMS):
        log("items.json missing — nothing to do")
        return 0
    with open(ITEMS, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"] if isinstance(data, dict) and "items" in data else data

    cache = {}
    filled = 0
    touched = 0
    for it in items:
        gist = it.get("gist")
        if not isinstance(gist, dict):
            continue
        item_hit = False
        for lang, txt in list(gist.items()):
            if not isinstance(txt, str):
                continue
            new, n = backfill_text(txt, cache)
            if n:
                gist[lang] = new
                filled += n
                item_hit = True
        if item_hit:
            touched += 1

    if filled:
        with open(ITEMS, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
    log(f"ref images: {filled} link(s) across {touched} item(s) upgraded "
        f"to image cards ({len(cache)} URLs checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

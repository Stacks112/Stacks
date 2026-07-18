"""Fetch subject images for OG share cards — runs on GitHub Actions (which
has open network; the publishing sandbox does not).

For every item that has no bundled local avatar, grab a representative
image and cache it under ogsrc/ so make_og() can composite it into the
1200x630 share card. Cached files are committed, so later sandbox builds
reuse them with no network needed.

Priority per item: a Wikipedia photo (item.wiki / item.thumbWiki) →
otherwise the company logo (item.logo domain). Best-effort: any failure
just leaves that card as the plain gradient.
"""

import json
import os
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (StacksOG/1.0; +https://stacksdaily.com/)"}
LOCAL_AVATARS = {"meru.png", "trump.webp", "serenity.jpg", "nadella.jpg",
                 "timcook.jpg", "zuckerberg.jpg", "nebius.jpg"}


def save(url, path):
    if os.path.exists(path):
        return True
    try:
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
        if not r.headers.get("content-type", "").startswith("image") or len(r.content) < 800:
            return False
        os.makedirs("ogsrc", exist_ok=True)
        with open(path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"  [warn] {url}: {e}")
        return False


def wiki_thumb(title):
    try:
        r = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(title.replace(" ", "_")),
            headers=UA, timeout=25)
        r.raise_for_status()
        src = ((r.json().get("thumbnail") or {}).get("source")) or ""
        if not src:
            return None
        # ask the thumbnailer for a larger render when the URL encodes a size
        m = re.search(r"/(\d+)px-", src)
        return src.replace(f"/{m.group(1)}px-", "/500px-") if m else src
    except Exception as e:
        print(f"  [warn] wiki {title}: {e}")
        return None


def main():
    d = json.load(open("items.json", encoding="utf-8"))
    ok = skip = 0
    for it in d["items"]:
        iid = it["id"]
        if it.get("avatarImg") in LOCAL_AVATARS:
            continue
        photo = f"ogsrc/{iid}.photo.png"
        logo = f"ogsrc/{iid}.logo.png"
        if os.path.exists(photo) or os.path.exists(logo):
            continue
        got = False
        wt = it.get("wiki") or it.get("thumbWiki")
        if wt:
            u = wiki_thumb(wt)
            if u and save(u, photo):
                got = True
        if not got and it.get("logo"):
            dom = it["logo"]
            if save(f"https://logo.clearbit.com/{dom}", logo):
                got = True
            elif save(f"https://www.google.com/s2/favicons?domain={dom}&sz=256", logo):
                got = True
        print(("[ok] " if got else "[skip] ") + iid + (f"  ({wt or it.get('logo','')})" if got else ""))
        ok += got
        skip += (not got)
    # prune cache for items that no longer exist
    ids = {i["id"] for i in d["items"]}
    if os.path.isdir("ogsrc"):
        for fn in os.listdir("ogsrc"):
            base = fn.split(".")[0]
            if base not in ids:
                os.remove(os.path.join("ogsrc", fn))
    print(f"[done] fetched {ok}, skipped {skip}")


if __name__ == "__main__":
    main()

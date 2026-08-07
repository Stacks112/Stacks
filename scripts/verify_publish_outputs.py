#!/usr/bin/env python3
"""Fail an automatic publish if its reader-facing artifacts are incomplete."""

import glob
import json
import os
import re
import sys


X_STATUS = re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/\d+", re.I)


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def main(ids):
    items_doc = load("items.json", {}) or {}
    items = {item.get("id"): item for item in items_doc.get("items", [])}
    core_doc = load("data/core.json", {}) or {}
    core = {item.get("id"): item for item in core_doc.get("items", [])}
    embeds = load("embeds.json", {}) or {}
    errors = []

    gist_docs = {lang: [] for lang in ("ko", "en", "ja")}
    for path in glob.glob("data/gist.*.*.json"):
        m = re.search(r"data/gist\.(ko|en|ja)\.\d+\.json$", path)
        if m:
            doc = load(path, {}) or {}
            gist_docs[m.group(1)].append(doc)

    for iid in ids:
        item = items.get(iid)
        if not item:
            errors.append("items.json missing %s" % iid)
            continue
        if not os.path.exists("p/%s.html" % iid):
            errors.append("Korean article page missing %s" % iid)
        for lang in ("en", "ja"):
            if not os.path.exists("p/%s/%s.html" % (lang, iid)):
                errors.append("%s article page missing %s" % (lang, iid))
            if not any(iid in doc for doc in gist_docs[lang]):
                errors.append("gist.%s chunk missing %s" % (lang, iid))
        if not any(iid in doc for doc in gist_docs["ko"]):
            errors.append("gist.ko chunk missing %s" % iid)

        if X_STATUS.match(item.get("sourceUrl") or ""):
            fetched = embeds.get(iid) or {}
            if not fetched.get("url") or not fetched.get("lines"):
                errors.append("embeds.json missing X post %s" % iid)
            built = core.get(iid) or {}
            if not (built.get("embed") or {}).get("lines"):
                errors.append("data/core.json missing X embed %s" % iid)
            page_paths = ["p/%s.html" % iid,
                          "p/en/%s.html" % iid,
                          "p/ja/%s.html" % iid]
            for path in page_paths:
                try:
                    with open(path, encoding="utf-8") as fh:
                        html = fh.read()
                except OSError:
                    continue
                if 'class="xemb"' not in html:
                    errors.append("static X card missing in %s" % path)

    if errors:
        for error in errors:
            print("::error::" + error)
        return 1
    print("publish output verification passed for %d card(s)" % len(ids))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: verify_publish_outputs.py ID [ID ...]")
    raise SystemExit(main(sys.argv[1:]))

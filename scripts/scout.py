"""Stacks scout — draft cards from fetched feeds with Claude, then open a PR.

Pipeline position:  fetch_feeds.py -> feeds/*.json -> [THIS] -> items.json (via PR)

What it does, each run:
  1. Read every feeds/*.json snapshot (produced by fetch_feeds.py).
  2. Skip any feed item already carded in items.json (matched by sourceUrl).
  3. Skip items older than LOOKBACK_DAYS or with no usable body text.
  4. Take the newest MAX_NEW_ITEMS fresh items across all sources, spreading
     across sources so one loud feed (meru) can't crowd the others out.
  5. Ask Claude to turn each into a Stacks stance-card: trilingual
     title/gist/why/ask, tags, cover, stance, category.
  6. Prepend the new cards to items.json.

It NEVER commits to main directly. The workflow opens a pull request so a
human reviews the drafted cards before they go live. Quality gate + safety.

Env:
  ANTHROPIC_API_KEY  (required)   MODEL (default claude-opus-4-8)
  MAX_NEW_ITEMS (3)  LOOKBACK_DAYS (4)  ITEMS_PATH (items.json)
  PER_SOURCE_CAP (2)  -> at most N new cards from any single source per run
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("MODEL", "claude-sonnet-5")
MAX_NEW = int(os.environ.get("MAX_NEW_ITEMS", "3"))
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "4"))
PER_SOURCE_CAP = int(os.environ.get("PER_SOURCE_CAP", "2"))
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
FEEDS_DIR = "feeds"

# feed id -> fixed card fields. Keeps display name / language / category /
# avatar consistent with the entities already in items.json.
def _load_sources():
    """Source registry lives in sources.json (repo root) - the single source
    of truth. Add or rename an author there; no code/prompt edits elsewhere."""
    try:
        with open("sources.json", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    meta = {}
    for k, v in raw.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        m = {"source": v.get("source", k), "lang": v.get("lang", "EN"),
             "category": v.get("category", "investor")}
        if v.get("avatarImg"): m["avatarImg"] = v["avatarImg"]
        if v.get("wiki"): m["wiki"] = v["wiki"]
        meta[k] = m
    return meta

SOURCE_META = _load_sources()


def norm_url(u):
    """Loose URL key for dedup: drop scheme, trailing slash, query."""
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = u.split("?", 1)[0].split("#", 1)[0]
    return u.rstrip("/")


def slugify(text, maxlen=40):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:maxlen].strip("-") or "item"


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def load_items():
    with open(ITEMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def existing_urls(doc):
    urls = set()
    for it in doc.get("items", []):
        if it.get("sourceUrl"):
            urls.add(norm_url(it["sourceUrl"]))
    return urls


def existing_ids(doc):
    return {it.get("id") for it in doc.get("items", []) if it.get("id")}


def gather_candidates(seen_urls):
    """Return fresh, un-carded feed items sorted newest-first."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    out = []
    for fn in sorted(os.listdir(FEEDS_DIR)):
        if not fn.endswith(".json"):
            continue
        feed_id = fn[:-5]
        if feed_id not in SOURCE_META:
            continue
        with open(os.path.join(FEEDS_DIR, fn), encoding="utf-8") as f:
            snap = json.load(f)
        for it in snap.get("items", []):
            link = it.get("link", "")
            body = (it.get("content") or "").strip()
            if not link or norm_url(link) in seen_urls:
                continue
            if len(body) < 200:          # too thin to card responsibly
                continue
            dt = parse_dt(it.get("published"))
            if dt is not None and dt < cutoff:
                continue
            out.append({
                "feed_id": feed_id,
                "title": it.get("title", ""),
                "link": link,
                "published": it.get("published", ""),
                "dt": dt,
                "content": body[:12000],
            })
    out.sort(key=lambda x: (x["dt"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return out


def pick(candidates):
    """Newest-first, but cap per source so the roster stays diverse."""
    chosen, per = [], {}
    for c in candidates:
        if len(chosen) >= MAX_NEW:
            break
        if per.get(c["feed_id"], 0) >= PER_SOURCE_CAP:
            continue
        chosen.append(c)
        per[c["feed_id"]] = per.get(c["feed_id"], 0) + 1
    return chosen


PROMPT = """You are the editor of Stacks (stacksdaily.com), a trilingual (Korean/Japanese/English) investing-opinion digest. Turn ONE source post into a Stacks stance-card.

The card explains, for a global retail investor, what the writer is saying and why it matters — faithfully, no invented facts. You output ONLY a JSON object (no prose, no markdown fence) with EXACTLY these keys:

{
  "title":  {"en": "...", "ko": "...", "ja": "..."},   // one sharp headline, ~12-18 words, same meaning in all three
  "gist":   {"en": "...", "ko": "...", "ja": "..."},   // 150-230 words EN; ko/ja are faithful translations of the SAME text. Neutral, concrete, names the writer once.
  "why":    {"en": "...", "ko": "...", "ja": "..."},   // 1-2 sentences: why an investor should care
  "ask":    {"en": "...", "ko": "...", "ja": "..."},   // one debate question ending in "?"
  "tags":   ["UPPER", "UPPER", "UPPER"],                 // 2-3 uppercase topical tags (tickers/themes)
  "cover":  {"from": "#0B2447", "to": "#19376D", "label": "SHORT LABEL"},  // dark hex gradient + <=18 char UPPERCASE label
  "stance": "bull",                                       // one of: bull | bear | watch  (watch = neutral/uncertain)
  "category": "investor",                                 // investor | politician | ceo
  "hot": true,                                            // true if timely/high-impact
  "thumbWiki": "Wikipedia Article Title"                  // OPTIONAL main subject for the cover image; omit if unsure
}

Rules:
- Translate faithfully; do not add facts not in the source. If the source is thin, keep the gist shorter rather than padding.
- ko and ja must carry the same meaning as en, natural in each language.
- Never fabricate numbers. Prefer the writer's own figures.
- Return JSON only.

SOURCE LANGUAGE: {lang}
SOURCE WRITER: {writer}
SOURCE TITLE: {title}
SOURCE BODY:
{body}
"""


def call_claude(item, meta):
    prompt = (PROMPT
              .replace("{lang}", meta["lang"])
              .replace("{writer}", meta["source"])
              .replace("{title}", item["title"])
              .replace("{body}", item["content"]))
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    text = "".join(b.get("text", "") for b in resp.get("content", []))
    text = text.strip()
    # tolerate an accidental ```json fence
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def build_card(item, meta, gen, used_ids):
    dt = item["dt"]
    date = (dt or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    base = f"{item['feed_id']}-{slugify(gen.get('tags', ['item'])[0] if gen.get('tags') else item['title'])}"
    cid, n = base, 2
    while cid in used_ids:
        cid = f"{base}-{n}"; n += 1
    used_ids.add(cid)

    card = {
        "id": cid,
        "date": date,
        "source": meta["source"],
        "sourceUrl": item["link"],
        "sourceLang": meta["lang"],
        "category": gen.get("category") or meta["category"],
        "hot": bool(gen.get("hot", True)),
        "cover": gen["cover"],
        "tags": gen["tags"],
        "title": gen["title"],
        "gist": gen["gist"],
        "why": gen["why"],
        "ask": gen["ask"],
        "stance": gen.get("stance", "watch"),
    }
    if gen.get("thumbWiki"):
        card["thumbWiki"] = gen["thumbWiki"]
    if meta.get("avatarImg"):
        card["avatarImg"] = meta["avatarImg"]
    if meta.get("wiki"):
        card["wiki"] = meta["wiki"]
    return card


REQUIRED = ("title", "gist", "why", "ask", "tags", "cover")


def valid(gen):
    if not all(k in gen for k in REQUIRED):
        return False
    for k in ("title", "gist", "why", "ask"):
        if not all(lang in gen[k] and gen[k][lang].strip() for lang in ("en", "ko", "ja")):
            return False
    if not (isinstance(gen["tags"], list) and gen["tags"]):
        return False
    if not all(x in gen["cover"] for x in ("from", "to", "label")):
        return False
    return True


def main():
    doc = load_items()
    seen = existing_urls(doc)
    used_ids = existing_ids(doc)

    picks = pick(gather_candidates(seen))
    if not picks:
        print("No fresh un-carded items. Nothing to draft.")
        return

    new_cards = []
    for it in picks:
        meta = SOURCE_META[it["feed_id"]]
        try:
            gen = call_claude(it, meta)
        except Exception as e:
            print(f"[skip] {it['feed_id']} {it['link']}: model error: {e}")
            continue
        if not valid(gen):
            print(f"[skip] {it['feed_id']} {it['link']}: invalid card shape")
            continue
        card = build_card(it, meta, gen, used_ids)
        new_cards.append(card)
        print(f"[draft] {card['id']}  <- {it['feed_id']}  ({card['stance']})")

    if not new_cards:
        print("Nothing valid drafted this run.")
        return

    # newest cards on top
    doc["items"] = new_cards + doc.get("items", [])
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    # hand the PR body to the workflow
    titles = "\n".join(f"- {c['source']}: {c['title']['en']}" for c in new_cards)
    with open(".scout_pr_body.md", "w", encoding="utf-8") as f:
        f.write(f"Auto-drafted {len(new_cards)} card(s) from fetched feeds.\n\n{titles}\n\n"
                f"Review the trilingual copy and stance, then merge to publish.")
    print(f"Drafted {len(new_cards)} card(s) -> {ITEMS_PATH}")


if __name__ == "__main__":
    main()

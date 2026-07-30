"""Stacks front-end data builder.

items.json is the publisher's single source of truth (the v4.3 routine is the
only writer). It is also 1.33 MB, and the app used to block its first paint on
downloading the whole thing: every card's full summary, in three languages, for
every article ever published, before a single pixel appeared.

This script derives what the app actually needs to paint, and defers the rest:

  data/core.<lang>.json   list + card fields for ALL items, one language,
                          summaries truncated to a preview. This is the only
                          blocking fetch.
  data/gist.<lang>.<n>.json
                          full summaries, newest first, in chunks. Fetched
                          after first paint and merged into the cards in place.
  data/elong.<lang>.json  entity long descriptions, fetched when an entity
                          page is first opened.
  data/manifest.json      chunk counts + a generation stamp.

Three things that the app used to compute at runtime by scanning the full
three-language text of every item are precomputed here instead, because the
truncated summaries can no longer support them and because the answer never
changes between page loads:

  themes  which of the eight browse themes an item belongs to
  ents    which entities an item mentions (drives entity pages)
  _mk     the item's main ticker (share card, cover-logo choice)
  _mks    up to MAIN_KEYS tickers, most central first ("since this post" badge)

The theme regexes and the back-catalogue stance map are READ OUT OF
index.html rather than copied here, so index.html stays the single source of
truth and the two can never drift. If the extraction stops matching, the build
fails loudly instead of silently shipping empty themes.

  opp     the opposite-stance counterpart cards (see pick_opposites)

Run by .github/workflows/og-assets.yml whenever items.json changes.
No external dependencies.
"""

import io
import json
import os
import re
import sys
import hashlib
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS = os.path.join(ROOT, "items.json")
INDEX = os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "data")

LANGS = ("ko", "en", "ja")
GIST_PREVIEW = 150      # characters kept in core; enough for the clamped card
CHUNK = 24              # items per gist chunk
MAIN_KEYS = 4           # companies the "since this post" badge may price
OPP_WINDOW_DAYS = 45    # how far apart two opposing takes may sit
OPP_MAX = 2
OPP_USE_CAP = 3         # times one post may serve as somebody else's counterpart
PRIOR_WINDOW_DAYS = 180  # how far back "what this author said last time" reaches
PRIOR_MAX = 2

# Fields dropped from core entirely: the full text lives in the gist chunks.
LANG_FIELDS = ("gist", "why", "ask")


def die(msg):
    print("build_data: FATAL " + msg, file=sys.stderr)
    sys.exit(1)


def js_unicode(pattern):
    r"""Turn a JS regex source into a Python one.

    Only \uXXXX is decoded. Using codecs 'unicode_escape' here would also eat
    \b and turn it into a backspace character, which silently destroys every
    word boundary in the pattern and quietly drops ~40% of theme matches.
    """
    return re.sub(r"\\u([0-9a-fA-F]{4})",
                  lambda m: chr(int(m.group(1), 16)), pattern)


def load_themes(src):
    """Pull the THEMES keyword regexes out of index.html."""
    try:
        start = src.index("const THEMES = {")
        block = src[start:src.index("\n};", start)]
    except ValueError:
        die("could not locate the THEMES block in index.html")
    keys = re.findall(r"^\s{2}(\w+):\s*\{", block, re.M)
    kws = re.findall(r"kw:/(.*)/([a-z]*)\s*\}", block)
    if not keys or len(keys) != len(kws):
        die("THEMES extraction mismatch: %d keys vs %d patterns" % (len(keys), len(kws)))
    out = {}
    for key, (pat, flags) in zip(keys, kws):
        # re.A makes \b and \w ASCII-only, which is what JS does. Without it
        # Python treats Korean and Japanese as word characters and \bAI\b
        # stops matching inside CJK text.
        f = re.A | (re.I if "i" in flags else 0)
        try:
            out[key] = re.compile(js_unicode(pat), f)
        except re.error as e:
            die("theme %r regex failed to compile: %s" % (key, e))
    print("  themes: %d (%s)" % (len(out), ", ".join(out)))
    return out


IMAGES = os.path.join(ROOT, "images.json")
_IMG_REG = None


def _img_registry():
    """Curated Wikimedia images, keyed by concept. Same idea as sources.json and
    glossary.json: data that grows lives in a file, not in the routine prompt."""
    global _IMG_REG
    if _IMG_REG is None:
        try:
            with io.open(IMAGES, encoding="utf-8") as f:
                _IMG_REG = (json.load(f) or {}).get("images") or {}
        except Exception:
            _IMG_REG = {}
    return _IMG_REG


def expand_img_markers(text, lang="ko"):
    """@@IMG@@key|caption  ->  @@IMG@@url|caption|credit|creditUrl

    The publishing routine picks a key and never writes a URL, so a card can no
    longer ship a broken image: an unknown key drops the line instead of leaving
    a dead <img> on the page. The four-field form still passes through untouched,
    so the cards written before the registry existed keep working.
    Resolution happens here, once, for both the app (build_data) and the static
    pages (build_pages imports this)."""
    if not text or "@@IMG@@" not in text:
        return text
    reg = _img_registry()
    out = []
    for line in str(text).split("\n"):
        if line.startswith("@@IMG@@"):
            parts = line[7:].split("|")
            if len(parts) < 3:                       # key form
                key = (parts[0] or "").strip()
                rec = reg.get(key)
                if not rec:
                    continue                          # unknown key: drop the line
                cap = (parts[1].strip() if len(parts) > 1 and parts[1].strip()
                       else (rec.get("caption") or {}).get(lang)
                       or (rec.get("caption") or {}).get("ko") or "")
                line = "@@IMG@@%s|%s|%s|%s" % (rec.get("url", ""), cap,
                                               rec.get("credit", "Wikimedia Commons"),
                                               rec.get("page", ""))
        out.append(line)
    return "\n".join(out)


def load_stance_map(src):
    """Pull the back-catalogue stance map out of index.html.

    Newer items carry their own "stance" field; older ones are covered by this
    map. Absent means the item simply has no stance.
    """
    m = re.search(r"const STANCE = \{(.*?)\n\};", src, re.S)
    if not m:
        return {}
    out = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1)))
    print("  stance map: %d back-catalogue entries" % len(out))
    return out


def re_esc(s):
    return re.escape(s)


def build_entity_matcher(entities):
    """Mirror of buildEntityMatcher() in index.html.

    Longest alias wins, and a word boundary is only attached on the side where
    it can actually match: "SK하이닉스" must not get a trailing \\b or the full
    name never matches and only "하이닉스" lights up. But a bare alias with no
    boundary at all on its Hangul side can also match as a substring of an
    unrelated longer word ("애플" inside "애플리케이션") — HANGUL_PARTICLES lets
    a real particle ("하이닉스가") still attach, while rejecting a same-script
    word that just continues ("애플" + "리케이션"). Mirrors buildEntityMatcher()
    in index.html; keep both in sync.
    """
    alias2key, raw = {}, []
    for key, ent in entities.items():
        for a in (ent.get("aliases") or []):
            if not a:
                continue
            low = a.lower()
            if low not in alias2key:
                alias2key[low] = key
                raw.append(a)
    raw.sort(key=len, reverse=True)
    hangul_particles = ["은", "는", "이", "가", "을", "를", "의", "에", "와", "과",
                         "도", "만", "로", "께", "이나", "나"]
    particle_alt = "|".join(hangul_particles)
    pats = []
    for a in raw:
        head = r"\b" if re.match(r"^[A-Za-z0-9]", a) else r"(?<![가-힣])"
        if re.search(r"[A-Za-z0-9]$", a):
            tail = r"\b"
        else:
            tail = r"(?=$|[^가-힣]|(?:%s)(?![가-힣]))" % particle_alt
        pats.append(head + re_esc(a) + tail)
    rx = re.compile("(" + "|".join(pats) + ")", re.I | re.A) if pats else None
    return rx, alias2key


def item_text(item):
    """Everything itemEntities() used to scan at runtime: all three languages
    of title, gist and why."""
    parts = []
    for f in ("title", "gist", "why"):
        d = item.get(f) or {}
        for lang in LANGS:
            parts.append(d.get(lang) or "")
    return "  ".join(parts)


def theme_hay(item):
    """Mirror of themeHay() in index.html."""
    t = item.get("title") or {}
    g = item.get("gist") or {}
    return " ".join([t.get("en") or "", t.get("ko") or "", t.get("ja") or "",
                     g.get("en") or "", " ".join(item.get("tags") or [])])


def entity_set(item, entities, rx, alias2key):
    """Mirror of itemEntities() in index.html, computed on the full text."""
    out = set()
    cover = item.get("cover") or {}
    if cover.get("label") in entities:
        out.add(cover["label"])
    for t in (item.get("tags") or []):
        if t in entities:
            out.add(t)
    if item.get("source") in entities:
        out.add(item["source"])
    if rx:
        for m in rx.finditer(item_text(item)):
            key = alias2key.get(m.group(0).lower())
            if key:
                out.add(key)
    return out


def is_company(entities, k):
    e = entities.get(k)
    return bool(e and e.get("kind") == "company" and e.get("ticker"))


def explicit_key(item, entities, alias2key=None):
    """The one company this post is declared to be primarily about.

    Only the cover label and the tags count, because both are set deliberately
    when the card is written. Deliberately NOT the text scan that main_key
    falls back on: a macro post about ETF inflows that mentions Intel once in
    passing would otherwise come back as an Intel post, and get paired against
    a real Intel post as though the two disagreed.

    Two details that decide whether a pairing is right or embarrassing:

    * Tags are resolved through the alias table, so a card tagged "NVDA" is
      recognised as NVIDIA. Without that, the first tag the matcher recognised
      on a post that is bearish on NVIDIA was its second tag, AMD - and the
      post got served to readers as the bear case on AMD when it was in fact
      arguing the bull case for AMD.
    * Only the FIRST resolved company counts. "stance" describes the post's
      view of its main asset, so pairing on any shared tag compares one
      author's view of NVIDIA against another's view of AMD.

    Returns None rather than guess. A wrong pairing is worse than no pairing.
    """
    alias2key = alias2key or {}
    tick2key = {}
    for k, e in entities.items():
        t = str(e.get("ticker") or "").split(".")[0].strip().lower()
        # "nvda.us" -> "nvda", so a card tagged NVDA resolves to NVIDIA even
        # though NVDA is not one of that entity's aliases.
        if t and is_company(entities, k):
            tick2key.setdefault(t, k)

    def listed(k, seen=None):
        """A tagged company that has no ticker of its own still has a price:
        its listed parent's. JASM is TSMC's Kumamoto joint venture and is not
        traded, so a card tagged JASM used to fall through to the text scan and
        come back with whichever company sorted first alphabetically."""
        seen = seen or set()
        if is_company(entities, k):
            return k
        e = entities.get(k)
        if not e or e.get("kind") != "company" or k in seen:
            return None
        seen.add(k)
        p = e.get("parent")
        return listed(p, seen) if p else None

    def resolve(v):
        if not v:
            return None
        k = listed(v)
        if k:
            return k
        low = str(v).strip().lower()
        k = alias2key.get(low) or tick2key.get(low)
        return listed(k) if k else None

    return resolve((item.get("cover") or {}).get("label")) or next(
        (k for k in map(resolve, item.get("tags") or []) if k), None)


def mention_rank(item, entities, ents, rx, alias2key):
    """The companies a post mentions, ordered by how much the post is about them.

    The old picker was `sorted(ents)[0]`, i.e. alphabetical order. On the
    Kumamoto earthquake post - headline TSMC, body about its JASM fab, with
    Sony and Fujifilm named once each as neighbouring plants - that handed the
    "since this post" badge to FUJIFILM, because F sorts before S and T.

    Alphabetical order carries no information about the post. Prominence does,
    so rank by it: named in the headline first, then how often the body names
    it, then who is named earliest. Alphabetical survives only as the last
    tie-break, to keep the build deterministic.
    """
    cands = sorted(k for k in ents if is_company(entities, k))
    if len(cands) < 2 or not rx:
        return cands

    def tally(text):
        hits, first = {}, {}
        for m in rx.finditer(text):
            k = alias2key.get(m.group(0).lower())
            if k:
                hits[k] = hits.get(k, 0) + 1
                first.setdefault(k, m.start())
        return hits, first

    head, _ = tally("  ".join(
        (item.get("title") or {}).get(lang) or "" for lang in LANGS))
    body, at = tally(item_text(item))
    # cands is already sorted, and sort() is stable, so a genuine three-way
    # tie still resolves the same way on every build.
    return sorted(cands, key=lambda k: (
        -head.get(k, 0), -body.get(k, 0), at.get(k, 1 << 30)))


def main_keys(item, entities, ents, alias2key=None, rx=None, n=MAIN_KEYS):
    """Mirror of itemMainKeys(): the companies the "since this post" badge
    prices, most central to the post first.

    Looser than explicit_key on purpose - a near-miss on the badge costs the
    reader nothing, whereas a near-miss on an opposite-stance pairing puts
    words in an author's mouth.

    Capped at n because the badge sits on one line under the card, and past
    a handful of tickers it stops reading as "who this post is about" and
    starts reading as a watchlist.
    """
    out = []
    for k in [explicit_key(item, entities, alias2key)] + \
            mention_rank(item, entities, ents, rx, alias2key or {}):
        if k and k not in out:
            out.append(k)
    return out[:n]


def main_key(item, entities, ents, alias2key=None, rx=None):
    """The single most central company - the one the share card names."""
    ks = main_keys(item, entities, ents, alias2key, rx, 1)
    return ks[0] if ks else None


def stance_of(item, stance_map):
    s = item.get("stance") or stance_map.get(item["id"])
    return s if s in ("bull", "bear") else None


def parse_date(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d")
    except Exception:
        return None


def pick_opposites(items, entities, stance_map, alias2key):
    """The other side of the argument, chosen mechanically.

    A reader who only ever sees the bull case leaves with the bull case. For
    every post that takes a side on a specific company, this finds the nearest
    posts that took the opposite side on the SAME company within a window, so
    the card can carry its own counterargument.

    No human curator can hold 150 posts across 24 authors and three languages
    in their head to do this; a build step does it in a millisecond. It is also
    derived entirely from facts already on the page - who said what, when, about
    which ticker - so it survives a source being removed later.

    Deliberately conservative: both sides must DECLARE the same company (cover
    label or tag), both must take a real side, and they must sit within a few
    weeks of each other. Anything less certain gets no counterpart at all,
    because a card that claims two authors disagree when they don't is worse
    than a card that stays quiet.
    """
    buckets, key_of, st_of, d_of, src_of = {}, {}, {}, {}, {}
    for it in items:
        k = explicit_key(it, entities, alias2key)
        st = stance_of(it, stance_map)
        d = parse_date(it.get("date"))
        key_of[it["id"]], st_of[it["id"]] = k, st
        d_of[it["id"]], src_of[it["id"]] = d, it.get("source") or ""
        if k and st and d:
            buckets.setdefault(k, []).append(it["id"])

    # Newest first, so the freshest cards get first claim on the usage budget.
    order = sorted(items, key=lambda i: str(i.get("date") or ""), reverse=True)
    used = {}
    out, paired = {}, 0
    for it in order:
        iid = it["id"]
        k, st, d = key_of[iid], st_of[iid], d_of[iid]
        if not (k and st and d):
            continue
        want = "bear" if st == "bull" else "bull"
        cands = []
        for oid in buckets.get(k, []):
            if oid == iid or st_of[oid] != want:
                continue
            if used.get(oid, 0) >= OPP_USE_CAP:
                continue          # stop one post becoming everyone's designated foil
            gap = abs((d - d_of[oid]).days)
            if gap <= OPP_WINDOW_DAYS:
                cands.append((gap, -d_of[oid].toordinal(), oid))
        if not cands:
            continue
        cands.sort()
        chosen, seen_src = [], set()
        # First pass takes one per author, so two slots are two voices.
        for _, _, oid in cands:
            if src_of[oid] in seen_src:
                continue
            seen_src.add(src_of[oid])
            chosen.append(oid)
            if len(chosen) >= OPP_MAX:
                break
        for _, _, oid in cands:
            if len(chosen) >= OPP_MAX:
                break
            if oid not in chosen:
                chosen.append(oid)
        for oid in chosen:
            used[oid] = used.get(oid, 0) + 1
        out[iid] = {"k": k, "ids": chosen}
        paired += 1
    print("  opposites: %d of %d items carry a counterpart "
          "(%d tickers in play, most-cited foil used %dx)"
          % (paired, len(items), len(buckets), max(used.values()) if used else 0))
    return out


def pick_priors(items, entities, alias2key):
    """This author's earlier posts on the same declared company.

    A single card is one frame; the trajectory - what this writer said about
    this stock last time, and the time before - is the part no source post
    contains and no source can take away. Pairing mirrors pick_opposites and
    is deliberately conservative: only the DECLARED company (cover label or
    tag, via explicit_key) counts, only the same author, only within a window.
    A wrong "here is what they said before" link is worse than none.
    """
    key_of, d_of = {}, {}
    for it in items:
        key_of[it["id"]] = explicit_key(it, entities, alias2key)
        d_of[it["id"]] = parse_date(it.get("date"))
    buckets = {}
    for it in items:
        k = key_of[it["id"]]
        if k and d_of[it["id"]]:
            buckets.setdefault((it.get("source") or "", k), []).append(it["id"])
    res = {}
    for it in items:
        iid = it["id"]
        k, d = key_of[iid], d_of[iid]
        if not (k and d):
            continue
        prevs = [oid for oid in buckets.get((it.get("source") or "", k), [])
                 if oid != iid and d_of[oid] < d
                 and (d - d_of[oid]).days <= PRIOR_WINDOW_DAYS]
        if not prevs:
            continue
        prevs.sort(key=lambda oid: d_of[oid], reverse=True)
        res[iid] = {"k": k, "ids": prevs[:PRIOR_MAX]}
    print("  priors: %d of %d items carry same-author history on the same ticker"
          % (len(res), len(items)))
    return res


# Line-leading markers the app turns into subheadings, verification panels and
# two-column comparisons. The 150-character preview that ships in core.json is
# painted before the full text arrives, so it has to come out as plain prose:
# a preview cut in the middle of "@@CHK@@10년물 금리|4.71%|..." would sit on the
# card as visible garbage for the first few seconds of every visit.
MARKER_RE = re.compile(r"^(?:##\s+|@@CHK@@.*|@@CMP@@.*)$", re.M)


def strip_markers(text):
    """Plain-prose form of a gist, for previews and for anything that measures
    length. Subheading text is kept (it is a real sentence); the data rows of a
    check or compare block are dropped, since they only read as a table."""
    out = []
    for line in str(text or "").split("\n"):
        if line.startswith("## "):
            out.append(line[3:].strip())
        elif line.startswith("@@"):
            # any block marker: CHK, CMP, IMG, future ones
            continue
        else:
            out.append(line)
    return "\n".join(out)


def truncate(text, n=GIST_PREVIEW):
    text = strip_markers(text)
    if len(text) <= n:
        return text
    cut = text[:n].rstrip()
    return cut + "…"


def pick(d, lang):
    """One language out of a {en,ko,ja} bag, falling back to English."""
    if not isinstance(d, dict):
        return d
    return d.get(lang) or d.get("en") or ""


def main():
    print("build_data: reading items.json")
    with open(ITEMS, encoding="utf-8") as f:
        data = json.load(f)
    with open(INDEX, encoding="utf-8") as f:
        src = f.read()

    items = data.get("items") or []
    entities = data.get("entities") or {}
    events = data.get("events") or []
    if len(items) < 5:
        die("items.json has only %d items - refusing to build" % len(items))

    themes = load_themes(src)
    stance_map = load_stance_map(src)
    rx, alias2key = build_entity_matcher(entities)

    # ---- precompute, on the full three-language text ----
    ents_of, mk_of, themes_of = {}, {}, {}
    for it in items:
        es = entity_set(it, entities, rx, alias2key)
        ents_of[it["id"]] = sorted(es)
        mk_of[it["id"]] = main_keys(it, entities, es, alias2key, rx)
        hay = theme_hay(it)
        themes_of[it["id"]] = [k for k, r in themes.items() if r.search(hay)]
    print("  entities matched: %d items, %.1f keys/item"
          % (len(items), sum(len(v) for v in ents_of.values()) / max(len(items), 1)))
    opp = pick_opposites(items, entities, stance_map, alias2key)
    prior = pick_priors(items, entities, alias2key)

    # newest first, so chunk 0 is what the reader sees first
    ordered = sorted(items, key=lambda i: str(i.get("date") or ""), reverse=True)

    gen = hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()[:12]

    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.startswith(("core.", "gist.", "elong.")) and old.endswith(".json"):
            os.remove(os.path.join(OUT, old))

    n_chunks = (len(ordered) + CHUNK - 1) // CHUNK
    sizes = {}

    # core keeps all three languages. Splitting it per language would save
    # another ~130 KB gzipped, but every place the app reads item.gist[LANG]
    # would then need a fallback for the two languages that are not loaded,
    # and switching language would need a blocking refetch. Not worth the blast
    # radius for a file that is already small enough. Only the FULL summaries
    # are language-split, because only one language's text is ever displayed.
    embeds = {}
    ep = os.path.join(ROOT, "embeds.json")
    if os.path.exists(ep):
        try:
            with open(ep, encoding="utf-8") as fh:
                embeds = json.load(fh) or {}
        except Exception as e:
            print("  embeds.json unreadable (%s) — cards will fall back to the "
                  "plain quote block" % e)
    print("  embeds: %d X posts" % len(embeds))

    core = []
    for it in ordered:
        c = {}
        for k, v in it.items():
            if k == "gist":
                continue
            c[k] = v
        full = {lang: pick(it.get("gist"), lang) for lang in LANGS}
        c["gist"] = {lang: truncate(full[lang]) for lang in LANGS}
        # The card reserves the clamped height up front for anything whose
        # summary is going to grow. Without it the preview paints short, the
        # full text lands a few seconds later, and the page both shifts and
        # hands Chrome a fresh (much later) LCP candidate.
        if any(len(full[lang]) > GIST_PREVIEW for lang in LANGS):
            c["clip"] = True
        c["themes"] = themes_of[it["id"]]
        c["ents"] = ents_of[it["id"]]
        mks = mk_of[it["id"]]
        c["_mk"] = mks[0] if mks else None
        if len(mks) > 1:
            c["_mks"] = mks
        if it["id"] in opp:
            c["opp"] = opp[it["id"]]
        if it["id"] in prior:
            c["prior"] = prior[it["id"]]
        # The X post itself, fetched by scripts/fetch_embeds.py on a runner.
        # items.json never carries it: the publishing sandbox has no route to
        # X, and re-fetching on every build would rate-limit us.
        if it["id"] in embeds:
            c["embed"] = embeds[it["id"]]
        core.append(c)

    ents_lite = {k: {kk: vv for kk, vv in e.items() if kk != "longDesc"}
                 for k, e in entities.items()}

    sizes["core.json"] = write(os.path.join(OUT, "core.json"), {
        "gen": gen, "chunks": n_chunks, "chunk": CHUNK,
        "items": core, "events": events, "entities": ents_lite,
    })

    for lang in LANGS:
        for ci in range(n_chunks):
            part = {it["id"]: expand_img_markers(pick(it.get("gist"), lang), lang)
                    for it in ordered[ci * CHUNK:(ci + 1) * CHUNK]}
            n = write(os.path.join(OUT, "gist.%s.%d.json" % (lang, ci)), part)
            if ci == 0:
                sizes["gist.%s.0.json" % lang] = n

    elong = {k: e["longDesc"] for k, e in entities.items() if e.get("longDesc")}
    sizes["elong.json"] = write(os.path.join(OUT, "elong.json"), elong)

    write(os.path.join(OUT, "manifest.json"),
          {"gen": gen, "chunks": n_chunks, "chunk": CHUNK,
           "langs": list(LANGS), "count": len(ordered),
           "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})

    src_size = os.path.getsize(ITEMS)
    print("build_data: %d items, %d chunks, gen %s" % (len(ordered), n_chunks, gen))
    print("  items.json      %9d B  (was the whole blocking fetch)" % src_size)
    for k in sorted(sizes):
        print("  %-16s %9d B" % (k, sizes[k]))
    print("  blocking fetch is now core.json: %.1f%% of the old payload"
          % (sizes["core.json"] / src_size * 100))


def write(path, obj):
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return len(body.encode())


if __name__ == "__main__":
    main()

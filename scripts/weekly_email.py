"""Stacks weekly — HTML email renderer.

Produces an email-client-safe (table-based, inline CSS) HTML newsletter of the
week's best items. Used both to PREVIEW what subscribers will receive and, via
weekly.py:send_newsletter() / weekly_send.py, as the message body.

The heavy, network-dependent enrichment (view counts for ranking, /quote for
the "since this post" badge) is done ONCE via enrich(); render_email() is a
pure function of the resulting context, so it can run per-recipient cheaply.

Public:
  select_hot(items, days=7, limit=8, today=None) -> list        (legacy preview)
  build_matcher(alias_source) -> (compiled_regex|None, alias2key)
  since_calc(quote, date_str) -> {pct,base,last,cur} | None
  enrich(items, entities, glossary, views, quote_fn, ...) -> ctx
  subject_line(lang, top_item) -> str
  render_email(lang, ctx, site, unsub="{{unsubscribe}}") -> str  (full HTML doc)
"""
import html
import re
from calendar import timegm
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# The real Stacks app icon (served at the site root). The old email drew a
# CSS "S" glyph, which is not the brand mark.
ICON_PATH = "/apple-touch-icon.png"
BRAND = "#2E5BFF"

STANCE = {
    "bull":    {"ko": "강세", "en": "Bull",    "ja": "強気", "fg": "#0B7A4B", "bg": "#E7F7EF"},
    "bear":    {"ko": "약세", "en": "Bear",    "ja": "弱気", "fg": "#B42318", "bg": "#FDECEA"},
    "neutral": {"ko": "중립", "en": "Neutral", "ja": "中立", "fg": "#4B5563", "bg": "#F1F2F4"},
}

L = {
    "ko": {"best": "이번 주 Stacks 베스트", "sub": "이번 주 가장 많이 읽힌 글 3편을 전문으로 담았어요.",
           "why": "왜 중요한가", "orig": "원문 보기", "read": "Stacks에서 읽기",
           "more": "Stacks에서 전체 보기", "tail": "매일 업데이트는 Stacks에서 확인하세요.",
           "unsub": "수신거부", "range": "기간", "since": "이 글 이후",
           "attn": "이번 주 쏠린 곳"},
    "en": {"best": "This week on Stacks", "sub": "The three most-read pieces this week, in full.",
           "why": "Why it matters", "orig": "Read original", "read": "Open in Stacks",
           "more": "See everything on Stacks", "tail": "Daily updates live on Stacks.",
           "unsub": "Unsubscribe", "range": "Week", "since": "Since this post",
           "attn": "Where attention moved"},
    "ja": {"best": "今週のStacksベスト", "sub": "今週最も読まれた3本を全文でお届けします。",
           "why": "なぜ重要か", "orig": "原文を読む", "read": "Stacksで読む",
           "more": "Stacksですべて見る", "tail": "毎日の更新はStacksで。",
           "unsub": "配信停止", "range": "今週", "since": "投稿後",
           "attn": "今週の注目"},
}


# ---------------------------------------------------------------- small utils
def _t(d, lang):
    if not isinstance(d, dict):
        return d or ""
    return d.get(lang) or d.get("en") or d.get("ko") or ""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _lang(lang):
    return lang if lang in L else "ko"


# ---------------------------------------------------------------- legacy pick
def select_hot(items, days=7, limit=8, today=None):
    if today is None:
        today = datetime.now(KST).date()
    cutoff = (today - timedelta(days=days)).isoformat()
    hot = [i for i in items if i.get("hot") and i.get("date", "") >= cutoff]
    hot.sort(key=lambda i: i.get("date", ""), reverse=True)
    return hot[:limit]


# ---------------------------------------------------------------- entity index
def build_matcher(alias_source):
    """alias_source: {key: [alias, ...]}. Returns (regex, alias2key) mirroring
    the site's buildEntityMatcher: longest alias wins, ASCII word boundaries
    only where they can actually match."""
    a2k = {}
    raw = []
    for key, aliases in alias_source.items():
        for a in (aliases or []):
            if not a:
                continue
            low = a.lower()
            if low not in a2k:
                a2k[low] = key
                raw.append(a)
    raw.sort(key=len, reverse=True)
    pats = []
    for a in raw:
        head = r"\b" if (a[:1].isascii() and a[:1].isalnum()) else ""
        tail = r"\b" if (a[-1:].isascii() and a[-1:].isalnum()) else ""
        pats.append(head + re.escape(a) + tail)
    rx = re.compile("(" + "|".join(pats) + ")", re.IGNORECASE) if pats else None
    return rx, a2k


def _matcher_from_entities(entities):
    return build_matcher({k: v.get("aliases") for k, v in entities.items()})


def _matcher_from_glossary(glossary):
    src = {}
    for k, v in (glossary or {}).items():
        al = list(v.get("aliases") or [])
        if k not in al:
            al.append(k)
        src[k] = al
    return build_matcher(src)


def item_entities(item, entities, ent_rx=None, ent_a2k=None):
    """Company/person keys attached to an item (tags/cover/source + text scan)."""
    s = set()
    cover = (item.get("cover") or {}).get("label")
    if cover in entities:
        s.add(cover)
    for t in (item.get("tags") or []):
        if t in entities:
            s.add(t)
    if item.get("source") in entities:
        s.add(item["source"])
    if ent_rx is not None:
        parts = []
        for fld in ("title", "gist", "why"):
            d = item.get(fld) or {}
            for lg in ("en", "ko", "ja"):
                if d.get(lg):
                    parts.append(d[lg])
        text = "  ".join(parts)
        for m in ent_rx.finditer(text):
            k = ent_a2k.get(m.group(0).lower())
            if k:
                s.add(k)
    return s


def item_main_key(item, entities, ent_rx=None, ent_a2k=None):
    """Primary company (with ticker) for the 'since this post' badge."""
    def co(k):
        e = entities.get(k)
        return bool(e and e.get("kind") == "company" and e.get("ticker"))

    cover = (item.get("cover") or {}).get("label")
    if cover and co(cover):
        return cover
    for t in (item.get("tags") or []):
        if co(t):
            return t
    for e in item_entities(item, entities, ent_rx, ent_a2k):
        if co(e):
            return e
    return None


# ---------------------------------------------------------------- linkify
def _term_html(text, url):
    return ('<a href="%s" style="color:%s;font-weight:700;text-decoration:none;'
            'border-bottom:1px dotted #A9BEFF;">%s</a>' % (url, BRAND, text))


def _link_pass(runs, rx, a2k, used, url):
    if rx is None:
        return runs
    out = []
    for kind, content in runs:
        if kind != "text":
            out.append((kind, content))
            continue
        s = content
        last = 0
        pieces = []
        for m in rx.finditer(s):
            key = a2k.get(m.group(0).lower())
            if not key or key in used:
                continue
            used.add(key)
            pieces.append(("text", s[last:m.start()]))
            pieces.append(("html", _term_html(m.group(0), url)))
            last = m.end()
        pieces.append(("text", s[last:]))
        out.extend(pieces)
    return out


def linkify(text, ctx, url):
    """Escape plain text, then wrap entity + glossary terms (once each) as links
    to the article. Newlines become <br>."""
    runs = [("text", _esc(text))]
    used = set()
    runs = _link_pass(runs, ctx.get("ent_rx"), ctx.get("ent_a2k", {}), used, url)
    runs = _link_pass(runs, ctx.get("gloss_rx"), ctx.get("gloss_a2k", {}), used, url)
    joined = "".join(c for _, c in runs)
    return joined.replace("\n", "<br>")


# ---------------------------------------------------------------- since calc
def since_calc(q, date_str):
    """pct change from the first close on/after the article date to the latest
    price, given a worker /quote?r=1y payload. Mirrors the site's sinceCalc."""
    if not q or q.get("error") or not q.get("closes") or not q.get("t"):
        return None
    t, closes = q["t"], q["closes"]
    if not t:
        return None
    try:
        dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
    except Exception:
        return None
    target = timegm(dt.timetuple()) - 43200
    if t[0] > target + 86400 * 10:
        return None  # article predates the data window
    idx = next((i for i, ti in enumerate(t) if ti >= target), -1)
    if idx < 0:
        return None
    base = closes[idx]
    last = q.get("price")
    if last is None:
        last = closes[-1]
    try:
        base = float(base)
        last = float(last)
    except (TypeError, ValueError):
        return None
    if not base:
        return None
    return {"pct": (last - base) / base * 100.0, "base": base, "last": last,
            "cur": q.get("currency", "")}


# ---------------------------------------------------------------- ranking
def select_top(items, views, days=7, limit=3, today=None):
    """Last `days` hot items, ranked by view count desc (recency tiebreak)."""
    if today is None:
        today = datetime.now(KST).date()
    lo = (today - timedelta(days=days)).isoformat()
    hi = today.isoformat()
    views = views or {}
    win = [i for i in items
           if i.get("hot") and lo <= i.get("date", "") <= hi]
    win.sort(key=lambda i: (views.get(i.get("id", ""), 0), i.get("date", "")),
             reverse=True)
    return win[:limit]


# ---------------------------------------------------------------- attention
def attention(items, entities, ent_rx, ent_a2k, today=None, top=3):
    if today is None:
        today = datetime.now(KST).date()

    def freq(lo, hi):
        c = {}
        for it in items:
            d = it.get("date", "")
            if it.get("hot") and lo <= d < hi:
                for e in item_entities(it, entities, ent_rx, ent_a2k):
                    if entities.get(e, {}).get("kind") == "company":
                        c[e] = c.get(e, 0) + 1
        return c

    this_lo = (today - timedelta(days=7)).isoformat()
    this_hi = (today + timedelta(days=1)).isoformat()
    last_lo = (today - timedelta(days=14)).isoformat()
    cthis, clast = freq(this_lo, this_hi), freq(last_lo, this_lo)

    def rank(c):
        return [k for k, _ in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]

    return {"this": rank(cthis)[:top], "last": rank(clast)[:top]}


# ---------------------------------------------------------------- subject
def shorten_title(s, maxlen=38):
    s = (s or "").strip()
    if len(s) <= maxlen:
        return s
    cut = s[:maxlen]
    for sep in ("，", ",", "、", " "):
        idx = cut.rfind(sep)
        if idx >= maxlen * 0.5:
            return cut[:idx].rstrip(" ,、，") + "…"
    return cut.rstrip() + "…"


def subject_line(lang, top_item):
    base = L[_lang(lang)]["best"]
    if not top_item:
        return base
    t = shorten_title(_t(top_item.get("title"), lang))
    return "%s: %s" % (base, t) if t else base


# ---------------------------------------------------------------- enrich
def enrich(items, entities, glossary, views, quote_fn,
           days=7, limit=3, today=None, lang="ko"):
    """Build the render context once (does the heavy lifting). quote_fn(ticker)
    -> worker /quote payload dict (or {'error':True}); may be a no-op that
    returns {} to skip the since-badge."""
    if today is None:
        today = datetime.now(KST).date()
    ent_rx, ent_a2k = _matcher_from_entities(entities)
    gloss_rx, gloss_a2k = _matcher_from_glossary(glossary)

    top = select_top(items, views, days=days, limit=limit, today=today)

    since = {}
    for it in top:
        k = item_main_key(it, entities, ent_rx, ent_a2k)
        if not k:
            continue
        tk = entities.get(k, {}).get("ticker")
        if not tk:
            continue
        try:
            q = quote_fn(tk)
        except Exception:
            q = None
        r = since_calc(q, it.get("date", ""))
        if r:
            since[it.get("id", "")] = {"k": k, "pct": r["pct"],
                                       "up": r["pct"] >= 0, "cur": r["cur"]}

    attn = attention(items, entities, ent_rx, ent_a2k, today=today)

    return {
        "items": top,
        "since": since,
        "attn": attn,
        "entities": entities,
        "ent_rx": ent_rx, "ent_a2k": ent_a2k,
        "gloss_rx": gloss_rx, "gloss_a2k": gloss_a2k,
        "today": today,
    }


# ---------------------------------------------------------------- HTML pieces
def _icon_img(site, size, radius, mr):
    return ('<img src="%s%s" width="%d" height="%d" alt="Stacks" '
            'style="border-radius:%dpx;display:inline-block;vertical-align:middle;'
            'margin-right:%dpx;border:0;">' % (site, ICON_PATH, size, size, radius, mr))


def _since_html(T, badge):
    up = badge["up"]
    color = "#12B76A" if up else "#F04438"
    arrow = "▲ +" if up else "▼ "
    return (
        '<div style="margin:16px 0 0;padding:11px 13px;background:#F6F8FB;'
        'border:1px solid #EBEEF3;border-radius:10px;font-size:13px;color:#3B3F46;">'
        '<span style="color:#8B93A1;font-weight:700;letter-spacing:.02em;">%s</span>'
        '<b style="margin:0 7px;color:#111318;">%s</b>'
        '<b style="color:%s;">%s%.1f%%</b>'
        '</div>'
        % (_esc(T["since"]), _esc(badge["k"]), color, arrow, badge["pct"])
    )


def _card_html(lang, ctx, site, it):
    T = L[_lang(lang)]
    st = STANCE.get(it.get("stance") or "neutral", STANCE["neutral"])
    item_id = it.get("id", "")
    url = "%s/#sig-%s" % (site, item_id)
    orig = it.get("sourceUrl", "") or url
    og = "%s/og/%s.png" % (site, item_id)

    badge = (
        '<span style="display:inline-block;font-size:12px;font-weight:700;line-height:1;'
        'padding:5px 9px;border-radius:999px;color:%s;background:%s;">%s</span>'
        % (st["fg"], st["bg"], st[_lang(lang)])
    )
    title = _esc(_t(it.get("title"), lang))
    gist = linkify(_t(it.get("gist"), lang), ctx, url)
    why = linkify(_t(it.get("why"), lang), ctx, url)
    src = _esc(it.get("source", ""))
    date = _esc(it.get("date", ""))

    tags = it.get("tags") or []
    tag_html = ""
    if tags:
        chips = "".join(
            '<span style="display:inline-block;font-size:11px;color:#6B7280;'
            'font-family:Menlo,Consolas,monospace;letter-spacing:.04em;margin:0 8px 0 0;">#%s</span>'
            % _esc(t) for t in tags[:4]
        )
        tag_html = '<div style="margin:12px 0 0;">%s</div>' % chips

    since_html = ""
    if item_id in ctx.get("since", {}):
        since_html = _since_html(T, ctx["since"][item_id])

    return (
        '<tr><td style="padding:0 0 16px;">'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" '
        'style="border:1px solid #E5E7EB;border-radius:14px;background:#FFFFFF;overflow:hidden;">'
        # content image
        '<tr><td style="padding:0;">'
        '<a href="%s" style="text-decoration:none;">'
        '<img src="%s" width="600" alt="" style="width:100%%;max-width:600px;display:block;border:0;">'
        '</a></td></tr>'
        # body
        '<tr><td style="padding:18px 20px 20px;">'
        '<div style="margin:0 0 10px;">%s'
        '<span style="font-size:12px;color:#9AA0A6;margin-left:10px;">%s &middot; %s</span></div>'
        '<a href="%s" style="text-decoration:none;color:#111318;">'
        '<div style="font-size:19px;line-height:1.4;font-weight:800;letter-spacing:-.01em;margin:0 0 12px;">%s</div>'
        '</a>'
        # full gist
        '<div style="font-size:14.5px;line-height:1.7;color:#2C2F36;">%s</div>'
        # why band
        '<div style="font-size:11px;font-weight:700;color:#8B93A1;letter-spacing:.06em;text-transform:uppercase;margin:16px 0 4px;">%s</div>'
        '<div style="font-size:14px;line-height:1.65;color:#3B3F46;">%s</div>'
        '%s'   # tags
        '%s'   # since badge
        # links
        '<div style="margin:16px 0 0;">'
        '<a href="%s" style="display:inline-block;font-size:13px;font-weight:700;color:%s;text-decoration:none;margin-right:16px;">%s &rarr;</a>'
        '<a href="%s" style="display:inline-block;font-size:13px;font-weight:700;color:#6B7280;text-decoration:none;">%s &nearr;</a>'
        '</div>'
        '</td></tr></table>'
        '</td></tr>'
        % (url, og, badge, src, date, url, title, gist,
           _esc(T["why"]).upper(), why, tag_html, since_html,
           url, BRAND, _esc(T["read"]), orig, _esc(T["orig"]))
    )


def _attn_sentence(lang, this, last):
    def nm(keys):
        return "·".join('<b style="color:#111318;">%s</b>' % _esc(k) for k in keys[:2])
    if not this:
        return ""
    lg = _lang(lang)
    if last:
        if lg == "en":
            return "Last week attention clustered on %s; this week it shifted to %s." % (nm(last), nm(this))
        if lg == "ja":
            return "先週は%sに関心が集まっていましたが、今週は%sへ移りました。" % (nm(last), nm(this))
        return "지난주엔 %s에 관심이 몰렸는데, 이번주엔 %s로 옮겨갔어요." % (nm(last), nm(this))
    if lg == "en":
        return "This week attention clustered on %s." % nm(this)
    if lg == "ja":
        return "今週は%sに関心が集まりました。" % nm(this)
    return "이번주엔 %s에 관심이 몰렸어요." % nm(this)


def _attn_html(lang, ctx):
    T = L[_lang(lang)]
    attn = ctx.get("attn") or {}
    sentence = _attn_sentence(lang, attn.get("this") or [], attn.get("last") or [])
    if not sentence:
        return ""
    return (
        '<tr><td style="padding:2px 0 16px;">'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" '
        'style="border:1px solid #E5E7EB;border-radius:14px;background:#FBFCFE;">'
        '<tr><td style="padding:18px 20px;">'
        '<div style="font-size:11px;font-weight:700;color:%s;letter-spacing:.08em;text-transform:uppercase;margin:0 0 8px;">%s</div>'
        '<div style="font-size:14.5px;line-height:1.65;color:#3B3F46;">%s</div>'
        '</td></tr></table></td></tr>'
        % (BRAND, _esc(T["attn"]), sentence)
    )


# ---------------------------------------------------------------- render
def render_email(lang, ctx, site, unsub="{{unsubscribe}}"):
    T = L[_lang(lang)]
    site = site.rstrip("/")
    items = ctx.get("items", [])
    dates = sorted(i.get("date", "") for i in items if i.get("date"))
    rng = ""
    if dates:
        rng = dates[0][5:].replace("-", ".") + " – " + dates[-1][5:].replace("-", ".")

    cards_html = "".join(_card_html(lang, ctx, site, it) for it in items)
    attn_html = _attn_html(lang, ctx)

    doc = (
        '<!DOCTYPE html><html lang="%s"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light only">'
        '<title>%s</title></head>'
        '<body style="margin:0;padding:0;background:#F3F4F6;">'
        '<div style="display:none;max-height:0;overflow:hidden;opacity:0;">%s — %s</div>'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="background:#F3F4F6;">'
        '<tr><td align="center" style="padding:28px 12px 40px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="width:600px;max-width:100%%;font-family:-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',\'Segoe UI\',Roboto,\'Helvetica Neue\',Arial,sans-serif;">'
        # header (real app icon)
        '<tr><td style="padding:6px 6px 18px;">'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="font-size:22px;font-weight:800;letter-spacing:-.02em;color:#111318;">'
        '%s Stacks</td>'
        '<td align="right" style="font-size:12px;color:#9AA0A6;">%s %s</td>'
        '</tr></table></td></tr>'
        # title band (icon + heading)
        '<tr><td style="padding:0 6px 6px;">'
        '<div style="font-size:26px;line-height:1.3;font-weight:800;letter-spacing:-.02em;color:#111318;">%s%s</div>'
        '<div style="font-size:14.5px;line-height:1.6;color:#6B7280;margin:8px 0 20px;">%s</div>'
        '</td></tr>'
        # cards
        '<tr><td><table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0">%s</table></td></tr>'
        # attention shift
        '<tr><td><table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0">%s</table></td></tr>'
        # cta
        '<tr><td align="center" style="padding:12px 6px 8px;">'
        '<a href="%s" style="display:inline-block;background:#111318;color:#fff;font-size:14.5px;font-weight:800;'
        'text-decoration:none;padding:14px 26px;border-radius:999px;">%s</a></td></tr>'
        # footer
        '<tr><td style="padding:26px 6px 0;border-top:1px solid #E5E7EB;margin-top:20px;">'
        '<div style="font-size:12.5px;line-height:1.7;color:#9AA0A6;text-align:center;">'
        '%s<br>'
        '<a href="%s" style="color:#9AA0A6;text-decoration:underline;">stacksdaily.com</a>'
        ' &middot; <a href="%s" style="color:#9AA0A6;text-decoration:underline;">%s</a>'
        '</div></td></tr>'
        '</table></td></tr></table></body></html>'
        % (_lang(lang), _esc(T["best"]), _esc(T["best"]), _esc(T["sub"]),
           _icon_img(site, 26, 7, 9), _esc(T["range"]), _esc(rng),
           _icon_img(site, 24, 6, 10), _esc(T["best"]), _esc(T["sub"]),
           cards_html, attn_html,
           site + "/", _esc(T["more"]),
           _esc(T["tail"]), site + "/", unsub, _esc(T["unsub"]))
    )
    return doc


# ---------------------------------------------------------------- preview
if __name__ == "__main__":
    import json
    import os
    data = json.load(open(os.environ.get("ITEMS_PATH", "items.json"), encoding="utf-8"))
    glossary = {}
    try:
        glossary = json.load(open(os.environ.get("GLOSSARY_PATH", "glossary.json"), encoding="utf-8"))
    except Exception:
        pass
    items = data.get("items", [])
    entities = data.get("entities", {})
    site = os.environ.get("SITE_URL", "https://stacksdaily.com")
    outdir = os.environ.get("OUT_DIR", "/tmp/weekly-email")
    os.makedirs(outdir, exist_ok=True)

    def _noquote(_ticker):
        return {}

    ctx = {"items": []}
    for lang in ("ko", "en", "ja"):
        ctx = enrich(items, entities, glossary, views={}, quote_fn=_noquote, lang=lang)
        p = os.path.join(outdir, "weekly-email.%s.html" % lang)
        open(p, "w", encoding="utf-8").write(render_email(lang, ctx, site))
        print("wrote", p, "| subject:", subject_line(lang, ctx["items"][0] if ctx["items"] else None))
    print("top items:", len(ctx["items"]))

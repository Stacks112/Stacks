"""Stacks weekly — HTML email renderer.

Produces an email-client-safe (table-based, inline CSS) HTML newsletter of the
week's best items. Used both to PREVIEW what subscribers will receive and, once
an ESP send is wired into weekly.py:send_newsletter(), as the message body.

Public:
  select_hot(items, days=7, limit=8, today=None) -> list
  render_email(lang, hot, site, unsub="{{unsubscribe}}") -> str  (full HTML doc)
"""
import html
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

STANCE = {
    "bull":    {"ko": "강세", "en": "Bull",    "ja": "強気", "fg": "#0B7A4B", "bg": "#E7F7EF"},
    "bear":    {"ko": "약세", "en": "Bear",    "ja": "弱気", "fg": "#B42318", "bg": "#FDECEA"},
    "neutral": {"ko": "중립", "en": "Neutral", "ja": "中立", "fg": "#4B5563", "bg": "#F1F2F4"},
}

L = {
    "ko": {"best": "이번 주 Stacks 베스트", "sub": "이번 주 가장 중요한 읽을거리를 골라 정리했어요.",
           "why": "왜 중요한가", "orig": "원문 보기", "read": "Stacks에서 읽기",
           "more": "Stacks에서 전체 보기", "tail": "매일 업데이트는 Stacks에서 확인하세요.",
           "unsub": "수신거부", "range": "기간"},
    "en": {"best": "This week on Stacks", "sub": "The week's most important reads, curated.",
           "why": "Why it matters", "orig": "Read original", "read": "Open in Stacks",
           "more": "See everything on Stacks", "tail": "Daily updates live on Stacks.",
           "unsub": "Unsubscribe", "range": "Week"},
    "ja": {"best": "今週のStacksベスト", "sub": "今週の最も重要な読みものをまとめました。",
           "why": "なぜ重要か", "orig": "原文を読む", "read": "Stacksで読む",
           "more": "Stacksですべて見る", "tail": "毎日の更新はStacksで。",
           "unsub": "配信停止", "range": "今週"},
}


def select_hot(items, days=7, limit=8, today=None):
    if today is None:
        today = datetime.now(KST).date()
    cutoff = (today - timedelta(days=days)).isoformat()
    hot = [i for i in items if i.get("hot") and i.get("date", "") >= cutoff]
    hot.sort(key=lambda i: i.get("date", ""), reverse=True)
    return hot[:limit]


def _t(d, lang):
    if not isinstance(d, dict):
        return d or ""
    return d.get(lang) or d.get("en") or d.get("ko") or ""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def render_email(lang, hot, site, unsub="{{unsubscribe}}"):
    T = L.get(lang, L["ko"])
    site = site.rstrip("/")
    dates = sorted(i.get("date", "") for i in hot if i.get("date"))
    rng = ""
    if dates:
        rng = dates[0][5:].replace("-", ".") + " – " + dates[-1][5:].replace("-", ".")

    # --- item cards ---
    cards = []
    for it in hot:
        st = STANCE.get(it.get("stance") or "neutral", STANCE["neutral"])
        badge = (
            '<span style="display:inline-block;font-size:12px;font-weight:700;line-height:1;'
            'padding:5px 9px;border-radius:999px;color:%s;background:%s;">%s</span>'
            % (st["fg"], st["bg"], st[lang])
        )
        title = _esc(_t(it.get("title"), lang))
        why = _esc(_t(it.get("why"), lang))
        src = _esc(it.get("source", ""))
        date = _esc(it.get("date", ""))
        url = "%s/#sig-%s" % (site, it.get("id", ""))
        orig = _esc(it.get("sourceUrl", "") or url)
        tags = it.get("tags") or []
        tag_html = ""
        if tags:
            chips = "".join(
                '<span style="display:inline-block;font-size:11px;color:#6B7280;'
                'font-family:Menlo,Consolas,monospace;letter-spacing:.04em;margin:0 8px 0 0;">#%s</span>'
                % _esc(t) for t in tags[:4]
            )
            tag_html = '<div style="margin:10px 0 0;">%s</div>' % chips

        cards.append(
            '<tr><td style="padding:0 0 14px;">'
            '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" '
            'style="border:1px solid #E5E7EB;border-radius:14px;background:#FFFFFF;">'
            '<tr><td style="padding:18px 20px 18px;">'
            '<div style="margin:0 0 10px;">%s'
            '<span style="font-size:12px;color:#9AA0A6;margin-left:10px;">%s &middot; %s</span></div>'
            '<a href="%s" style="text-decoration:none;color:#111318;">'
            '<div style="font-size:18px;line-height:1.4;font-weight:800;letter-spacing:-.01em;margin:0 0 8px;">%s</div>'
            '</a>'
            '<div style="font-size:11px;font-weight:700;color:#8B93A1;letter-spacing:.06em;text-transform:uppercase;margin:0 0 4px;">%s</div>'
            '<div style="font-size:14.5px;line-height:1.62;color:#3B3F46;">%s</div>'
            '%s'
            '<div style="margin:14px 0 0;">'
            '<a href="%s" style="display:inline-block;font-size:13px;font-weight:700;color:#2E5BFF;text-decoration:none;margin-right:16px;">%s &rarr;</a>'
            '<a href="%s" style="display:inline-block;font-size:13px;font-weight:700;color:#6B7280;text-decoration:none;">%s &nearr;</a>'
            '</div>'
            '</td></tr></table>'
            '</td></tr>'
            % (badge, src, date, url, title, T["why"].upper(), why, tag_html,
               url, T["read"], orig, T["orig"])
        )

    cards_html = "".join(cards)

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
        # header
        '<tr><td style="padding:6px 6px 18px;">'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="font-size:22px;font-weight:800;letter-spacing:-.02em;color:#111318;">'
        '<span style="display:inline-block;width:26px;height:26px;border-radius:7px;background:#111318;color:#fff;'
        'text-align:center;line-height:26px;font-size:15px;margin-right:9px;vertical-align:middle;">S</span>Stacks</td>'
        '<td align="right" style="font-size:12px;color:#9AA0A6;">%s %s</td>'
        '</tr></table></td></tr>'
        # title band
        '<tr><td style="padding:0 6px 6px;">'
        '<div style="font-size:26px;line-height:1.3;font-weight:800;letter-spacing:-.02em;color:#111318;">%s</div>'
        '<div style="font-size:14.5px;line-height:1.6;color:#6B7280;margin:8px 0 20px;">%s</div>'
        '</td></tr>'
        # cards
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
        % (lang, _esc(T["best"]), _esc(T["best"]), _esc(T["sub"]),
           _esc(T["range"]), _esc(rng),
           _esc(T["best"]), _esc(T["sub"]),
           cards_html,
           site + "/", _esc(T["more"]),
           _esc(T["tail"]), site + "/", unsub, _esc(T["unsub"]))
    )
    return doc


if __name__ == "__main__":
    import json
    import os
    import sys
    data = json.load(open(os.environ.get("ITEMS_PATH", "items.json"), encoding="utf-8"))
    hot = select_hot(data.get("items", []),
                     days=int(os.environ.get("DAYS", "7")),
                     limit=int(os.environ.get("LIMIT", "8")))
    site = os.environ.get("SITE_URL", "https://stacksdaily.com")
    outdir = os.environ.get("OUT_DIR", "/tmp/weekly-email")
    os.makedirs(outdir, exist_ok=True)
    for lang in ("ko", "en", "ja"):
        p = os.path.join(outdir, "weekly-email.%s.html" % lang)
        open(p, "w", encoding="utf-8").write(render_email(lang, hot, site))
        print("wrote", p)
    print("items:", len(hot))

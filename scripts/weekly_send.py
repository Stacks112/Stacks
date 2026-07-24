"""Stacks weekly — subscriber fetch (worker D1) + email send (Resend).

Design (chosen with June, 2026-07 — all-country broadcast, one sender):
  - Subscribers (email + language) live in the Cloudflare worker's D1 store.
    The site signup form (all languages) POSTs to the worker /subscribe route;
    the worker /unsub route flips unsubscribed=1. Resend's Audiences product is
    deprecated, so we keep the list in infra we fully control and use Resend
    purely as the transactional sender.
  - The weekly digest is rendered as HTML (weekly_email.render_email) and sent
    through Resend, one message per subscriber with a personalized one-click
    unsubscribe (worker /unsub). weekly.py calls send_weekly() once per lang;
    each call fetches that language's active subscribers from the worker.

Env:
  RESEND_API_KEY        Resend API key (required to send)
  RESEND_FROM           e.g. "Stacks Weekly <weekly@stacksdaily.com>"
  STACKS_WORKER_URL     worker base, e.g. https://stacks-comments...workers.dev
  STACKS_NOTIFY_SECRET  shared secret that guards the worker /subscribers read
  SITE_URL              https://stacksdaily.com
  UNSUB_BASE            worker unsubscribe URL, e.g. https://.../unsub  (optional)
  UNSUB_SECRET          HMAC secret shared with the worker /unsub route  (optional)
  WEEKLY_LANG           email language: ko|en|ja  (default ko)
  WEEKLY_TEST_TO        if set, send ONLY to this address (test mode)
  DRY_RUN=1             build messages + print, do not call Resend

Usage:
  RESEND_API_KEY=... RESEND_FROM=... STACKS_WORKER_URL=... STACKS_NOTIFY_SECRET=... \\
    python scripts/weekly_send.py
  WEEKLY_TEST_TO=you@example.com RESEND_API_KEY=... python scripts/weekly_send.py
"""
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weekly_email import (  # noqa: E402
    render_email, select_hot, enrich, subject_line)

# A real browser-ish User-Agent: Cloudflare (in front of api.resend.com /
# api.stibee.com) 403s the default "Python-urllib/x" signature (error 1010).
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
# secret that guards the worker's /subscribers read (same value as /notify)
NOTIFY_SECRET = os.environ.get("STACKS_NOTIFY_SECRET", "").strip()
RESEND_FROM = os.environ.get("RESEND_FROM", "Stacks Weekly <weekly@stacksdaily.com>")
SITE = os.environ.get("SITE_URL", "https://stacksdaily.com").rstrip("/")
UNSUB_BASE = os.environ.get("UNSUB_BASE", "").rstrip("/")
UNSUB_SECRET = os.environ.get("UNSUB_SECRET", "")
LANG = os.environ.get("WEEKLY_LANG", "ko")
TEST_TO = os.environ.get("WEEKLY_TEST_TO", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
GLOSSARY_PATH = os.environ.get("GLOSSARY_PATH", "glossary.json")
# worker base for /views (ranking) and /quote (the "since this post" badge)
WORKER = os.environ.get(
    "STACKS_WORKER_URL",
    "https://stacks-comments.wnrakrhdn128.workers.dev").rstrip("/")

# Fallback subject if there are no items to name.
SUBJECT_FALLBACK = {
    "ko": "이번 주 Stacks 베스트",
    "en": "This week on Stacks",
    "ja": "今週のStacksベスト",
}


def _get_json(url):
    """Best-effort GET -> parsed JSON, or None. Uses a real UA so Cloudflare
    (in front of the worker) doesn't 403 the request."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print("[warn] GET %s failed: %s" % (url, e))
        return None


def fetch_views():
    """Article view counts {id: n} from the worker, for ranking. {} on failure."""
    if not WORKER:
        return {}
    j = _get_json(WORKER + "/views")
    data = (j or {}).get("data") or {}
    return data if isinstance(data, dict) else {}


_QUOTE_CACHE = {}


def fetch_quote(ticker):
    """Worker /quote?r=1y payload for a ticker (cached). {'error':True} on fail."""
    if not ticker or not WORKER:
        return {"error": True}
    if ticker in _QUOTE_CACHE:
        return _QUOTE_CACHE[ticker]
    j = _get_json(WORKER + "/quote?s=" + urllib.parse.quote(str(ticker)) + "&r=1y")
    out = j if (j and j.get("closes")) else {"error": True}
    _QUOTE_CACHE[ticker] = out
    return out

def fetch_subscribers(lang):
    """Return a de-duplicated list of active (not unsubscribed) subscriber
    emails for `lang` from the worker's D1 store. The secret is sent as a
    Bearer header (never in the URL). Raises on missing config or a hard error."""
    if not WORKER:
        raise RuntimeError("STACKS_WORKER_URL not set")
    if not NOTIFY_SECRET:
        raise RuntimeError("STACKS_NOTIFY_SECRET not set")
    url = WORKER + "/subscribers?lang=" + urllib.parse.quote(lang)
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + NOTIFY_SECRET,
                      "User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError("subscriber fetch failed for %s: HTTP %s %s"
                           % (lang, e.code, e.read()[:200]))
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("unexpected /subscribers payload for %s" % lang)
    active = {}
    for e in rows:
        e = str(e or "").strip().lower()
        if e and "@" in e:
            active[e] = True
    return sorted(active)


def unsub_link(email):
    if UNSUB_BASE and UNSUB_SECRET:
        sig = hmac.new(UNSUB_SECRET.encode(), email.lower().encode(),
                       hashlib.sha256).hexdigest()[:24]
        return "%s?e=%s&t=%s" % (UNSUB_BASE, urllib.parse.quote(email), sig)
    # fallback if the worker /unsub route isn't configured yet: the site itself
    return SITE


def build_messages(recipients, html_by_email, subject):
    msgs = []
    for email in recipients:
        msgs.append({
            "from": RESEND_FROM,
            "to": [email],
            "subject": subject,
            "html": html_by_email[email],
            "headers": {
                "List-Unsubscribe": "<%s>" % unsub_link(email),
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        })
    return msgs


def resend_batch(messages):
    """Send messages (<=100) via Resend batch. Returns response dict."""
    if not RESEND_KEY:
        raise RuntimeError("RESEND_API_KEY not set")
    body = json.dumps(messages).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails/batch", data=body, method="POST",
        headers={"Authorization": "Bearer " + RESEND_KEY,
                 "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def _load_corpus():
    data = json.load(open(ITEMS_PATH, encoding="utf-8"))
    glossary = {}
    try:
        glossary = json.load(open(GLOSSARY_PATH, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print("[warn] glossary load failed: %s" % e)
    return data.get("items", []), data.get("entities", {}), glossary


def send_weekly(hot=None, lang=None):
    """Render + send the weekly digest. Returns (sent_count, errors).

    Selects the last 7 days' top-3 hot items by view count, enriches them with
    OG images, the 'since this post' stock badge, indexed terms and a weekly
    attention-shift note, and names the subject after the most-read piece."""
    lang = lang or LANG

    items, entities, glossary = _load_corpus()
    views = fetch_views()
    print("ranking by views: %d counted" % len(views))
    ctx = enrich(items, entities, glossary, views, fetch_quote,
                 days=7, limit=3, lang=lang)
    top = ctx.get("items", [])
    if not top:
        print("no hot items in the last 7 days; skipping")
        return 0, []
    subject = subject_line(lang, top[0]) or SUBJECT_FALLBACK.get(lang, SUBJECT_FALLBACK["ko"])
    print("top-3: %s | since-badges: %d | subject=%r"
          % ([i.get("id") for i in top], len(ctx.get("since", {})), subject))

    if TEST_TO:
        recipients = [TEST_TO.lower()]
        print("TEST MODE → sending only to %s" % TEST_TO)
    else:
        recipients = fetch_subscribers(lang)
        print("fetched %d subscribers (%s)" % (len(recipients), lang))
    if not recipients:
        print("no recipients; skipping")
        return 0, []

    # one personalized HTML per recipient (only the unsub link differs)
    html_by_email = {e: render_email(lang, ctx, SITE, unsub=unsub_link(e))
                     for e in recipients}
    messages = build_messages(recipients, html_by_email, subject)

    if DRY_RUN:
        print("DRY_RUN: %d messages built (subject=%r, from=%r). First recipient=%s"
              % (len(messages), subject, RESEND_FROM, recipients[0]))
        return 0, []

    sent, errors = 0, []
    for i in range(0, len(messages), 100):
        chunk = messages[i:i + 100]
        try:
            resp = resend_batch(chunk)
            n = len(resp.get("data", chunk))
            sent += n
            print("batch %d: sent %d" % (i // 100 + 1, n))
        except urllib.error.HTTPError as e:
            err = "HTTP %s: %s" % (e.code, e.read()[:300])
            errors.append(err)
            print("batch %d FAILED: %s" % (i // 100 + 1, err))
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
            print("batch %d FAILED: %s" % (i // 100 + 1, e))
        time.sleep(0.6)  # stay well under rate limits
    return sent, errors


def main():
    items_path = os.environ.get("ITEMS_PATH", "items.json")
    data = json.load(open(items_path, encoding="utf-8"))
    hot = select_hot(data.get("items", []),
                     days=int(os.environ.get("DAYS", "7")),
                     limit=int(os.environ.get("LIMIT", "8")))
    if not hot:
        print("no hot items in the window; skipping")
        return 0
    sent, errors = send_weekly(hot)
    print("done. sent=%d errors=%d" % (sent, len(errors)))
    return 1 if errors and sent == 0 else 0


if __name__ == "__main__":
    sys.exit(main())

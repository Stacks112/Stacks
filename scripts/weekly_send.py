"""Stacks weekly — subscriber fetch (Stibee) + email send (Resend).

Design (chosen with June, 2026-07):
  - Subscribers are collected & consent-managed in Stibee (the signup form).
  - The weekly digest is rendered as HTML (weekly_email.render_email) and sent
    through Resend (full HTML control, easy to test), one message per
    subscriber with a personalized one-click unsubscribe.

Env:
  RESEND_API_KEY      Resend API key (required to send)
  RESEND_FROM         e.g. "Stacks Weekly <weekly@stacksdaily.com>"
  STIBEE_API_KEY      Stibee API AccessToken (required to fetch subscribers)
  STIBEE_LIST_ID      Stibee list id (default = the site's signup list)
  SITE_URL            https://stacksdaily.com
  UNSUB_BASE          worker unsubscribe URL, e.g. https://.../unsub  (optional)
  UNSUB_SECRET        HMAC secret shared with the worker /unsub route  (optional)
  WEEKLY_LANG         email language: ko|en|ja  (default ko)
  WEEKLY_TEST_TO      if set, send ONLY to this address (test mode)
  DRY_RUN=1           build messages + print, do not call Resend

Usage:
  STIBEE_API_KEY=... RESEND_API_KEY=... RESEND_FROM=... python scripts/weekly_send.py
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

STIBEE_KEY = os.environ.get("STIBEE_API_KEY", "")
STIBEE_LIST = os.environ.get("STIBEE_LIST_ID", "mK4zRfYXD3P_8shW-ErZAF-hNA_XYQ==")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
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

_EMAIL_RE_KEYS = ("email", "Email", "emailAddress", "subscriber")


def _walk_emails(obj, out):
    """Robustly pull every email + unsub status out of Stibee's JSON,
    regardless of the exact envelope shape."""
    if isinstance(obj, dict):
        email = None
        for k in _EMAIL_RE_KEYS:
            v = obj.get(k)
            if isinstance(v, str) and "@" in v:
                email = v.strip().lower()
                break
        if email:
            status = str(obj.get("status") or obj.get("subscribeStatus")
                         or obj.get("subscribed") or "").lower()
            # treat explicit unsubscribe/bounce as excluded; everything else = active
            bad = any(s in status for s in ("unsub", "delete", "bounce", "false", "n"))
            out[email] = out.get(email, True) and not bad
        for v in obj.values():
            _walk_emails(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_emails(v, out)


def fetch_subscribers():
    """Return a de-duplicated list of active subscriber emails from Stibee.
    Tries the known v1 list-subscribers endpoints; raises if none respond."""
    if not STIBEE_KEY:
        raise RuntimeError("STIBEE_API_KEY not set")
    headers = {"AccessToken": STIBEE_KEY, "Content-Type": "application/json",
               "User-Agent": UA, "Accept": "application/json"}
    candidates = [
        "https://api.stibee.com/v1/lists/%s/subscribers?page=%d&size=500",
        "https://api.stibee.com/v1/lists/%s/subscribers/all?page=%d&size=500",
    ]
    last_err = None
    for tmpl in candidates:
        try:
            active = {}
            for page in range(0, 40):  # up to 20k subscribers
                url = tmpl % (STIBEE_LIST, page)
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode("utf-8"))
                before = len(active)
                _walk_emails(data, active)
                if len(active) == before:
                    break  # no new emails on this page → done
            emails = sorted(e for e, ok in active.items() if ok)
            if emails:
                return emails
        except urllib.error.HTTPError as e:
            last_err = "HTTP %s on %s: %s" % (e.code, tmpl, e.read()[:200])
        except Exception as e:  # noqa: BLE001
            last_err = "%s on %s" % (e, tmpl)
    raise RuntimeError("could not fetch Stibee subscribers. last: %s" % last_err)


def unsub_link(email):
    if UNSUB_BASE and UNSUB_SECRET:
        sig = hmac.new(UNSUB_SECRET.encode(), email.lower().encode(),
                       hashlib.sha256).hexdigest()[:24]
        return "%s?e=%s&t=%s" % (UNSUB_BASE, urllib.parse.quote(email), sig)
    # fallback: Stibee-hosted list unsubscribe page (until the worker route is live)
    return "https://page.stibee.com/subscriptions/505211"


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
        recipients = fetch_subscribers()
        print("fetched %d Stibee subscribers" % len(recipients))
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

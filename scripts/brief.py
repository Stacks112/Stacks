"""Stacks daily push brief + event D-1 reminders.

Runs on GitHub Actions once a day (see stacks-brief.yml). Reads items.json,
picks the day's featured read, and sends ONE OneSignal push to everyone
(tag `daily`) through the Cloudflare worker's /notify route. Then it scans
the `events` array and sends a D-1 reminder for anything happening tomorrow.

A tiny state file (scripts/.brief_state.json) is committed back by the
workflow so the same item/event is never pushed twice.

Env:
  STACKS_WORKER_URL     e.g. https://stacks-comments.xxxx.workers.dev
  STACKS_NOTIFY_SECRET  the worker's NOTIFY_SECRET
  ITEMS_PATH            optional, default "items.json"
  SITE_URL              optional, default "https://stacksdaily.com"
  STATE_PATH            optional, default "scripts/.brief_state.json"
No API key needed — this only reads JSON and calls the worker.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
WORKER = os.environ.get("STACKS_WORKER_URL", "").rstrip("/")
SECRET = os.environ.get("STACKS_NOTIFY_SECRET", "")
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
SITE = os.environ.get("SITE_URL", "https://stacksdaily.com").rstrip("/")
STATE_PATH = os.environ.get("STATE_PATH", "scripts/.brief_state.json")


def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def notify(tag, title, msg, url):
    """Fire a push through the worker. Returns True on success."""
    if not WORKER or not SECRET:
        print("[skip] worker url / secret not set")
        return False
    params = urllib.parse.urlencode({
        "secret": SECRET, "tag": tag,
        "title": title[:120], "msg": msg[:300], "url": url,
    })
    req = urllib.request.Request(WORKER + "/notify?" + params, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            out = json.loads(r.read().decode("utf-8"))
        ok = bool(out.get("sent"))
        print(("[ok] " if ok else "[fail] ") + tag + " :: " + title)
        return ok
    except Exception as e:
        print("[error] notify " + tag + ": " + str(e))
        return False


def main():
    data = load_json(ITEMS_PATH, {})
    items = data.get("items", [])
    events = data.get("events", [])
    if not items:
        print("no items; nothing to do")
        return

    state = load_json(STATE_PATH, {})
    pushed_events = set(state.get("pushed_events", []))
    last_item = state.get("last_item")

    today = datetime.now(KST).date()
    changed = False

    # ---- daily featured read -------------------------------------------
    # newest item; prefer a hot one on the same date; only if it's fresh
    # (published within the last 2 days) and not already pushed.
    def keyf(it):
        return (it.get("date", ""), 1 if it.get("hot") else 0)
    newest = max(items, key=keyf)
    ndate = newest.get("date", "")
    fresh = ndate >= (today - timedelta(days=2)).isoformat()
    if fresh and newest.get("id") != last_item:
        t = newest.get("title", {})
        w = newest.get("why", {})
        title = "\U0001F4C8 오늘의 한 편"  # 📈 오늘의 한 편
        msg = t.get("ko") or t.get("en") or ""
        detail = w.get("ko") or w.get("en") or ""
        if detail:
            msg = msg + " — " + detail
        url = SITE + "/#sig-" + newest.get("id", "")
        if notify("daily", title, msg, url):
            state["last_item"] = newest.get("id")
            changed = True
    else:
        print("daily: nothing fresh to push (newest=%s, %s)" % (newest.get("id"), ndate))

    # ---- event D-1 reminders -------------------------------------------
    tomorrow = (today + timedelta(days=1)).isoformat()
    for ev in events:
        if ev.get("date") != tomorrow:
            continue
        key = ev.get("date", "") + "|" + ev.get("itemId", "")
        if key in pushed_events:
            continue
        label = ev.get("label", {})
        lab = label.get("ko") or label.get("en") or "이벤트"
        title = "⏰ 내일: " + lab  # ⏰ 내일:
        msg = "D-1 · " + lab  # D-1 ·
        url = SITE + "/#sig-" + ev.get("itemId", "")
        if notify("daily", title, msg, url):
            pushed_events.add(key)
            changed = True

    if changed:
        # prune old event keys (keep last 60)
        state["pushed_events"] = sorted(pushed_events)[-60:]
        save_state(state)
        print("state saved")
    else:
        print("no pushes sent; state unchanged")


if __name__ == "__main__":
    sys.exit(main())

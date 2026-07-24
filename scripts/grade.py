"""Stacks prediction grader — runs on GitHub Actions (see grade.yml).

Pipeline position:  items.json (pending outcomes) -> [THIS] -> items.json (graded)

Why Actions and not the Cowork session: git push from the scheduled Cowork
session is blocked with 403 (the GitHub App repo grant is missing for that
account). Actions runs on a real headless runner with a native GITHUB_TOKEN,
so it can web-search AND push. Same pattern as scout.py / brief.py / stats.py.

What it does each run (KST morning):
  1. Read items.json, find outcome.status == "pending" items.
  2. For any whose outcome.due (ISO check date) is today or earlier, ask Claude
     to research the REAL outcome with the native web_search server tool and
     grade it hit / miss, or defer (push due out) if the result isn't known yet.
  3. For pending items with NO due, estimate a due date (no web search) and
     backfill it only (graded on a later run).
  4. Write items.json. The workflow commits + pushes; og-assets rebuilds pages.

Pushes: OFF here by default. Follower push for a freshly graded prediction is
handled by the Cloudflare worker's cron (it detects the hit/miss in items.json
and notifies), so grading here does not double-push. Set GRADE_PUSH=1 to have
this script push through the worker /notify instead.

Env:
  ANTHROPIC_API_KEY   (required)
  MODEL               (default claude-sonnet-5)
  ITEMS_PATH          (default items.json)
  MAX_GRADE           (default 12)  cap on API calls per run
  WEB_SEARCH_USES     (default 4)   max web searches per prediction
  GRADE_PUSH          (default "0") "1" -> push graded results via the worker
  STACKS_WORKER_URL / STACKS_NOTIFY_SECRET / SITE_URL   (only if GRADE_PUSH=1)
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("MODEL", "claude-sonnet-5")
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
MAX_GRADE = int(os.environ.get("MAX_GRADE", "12"))
WS_USES = int(os.environ.get("WEB_SEARCH_USES", "4"))
GRADE_PUSH = os.environ.get("GRADE_PUSH", "0") == "1"
WORKER = os.environ.get("STACKS_WORKER_URL", "").rstrip("/")
SECRET = os.environ.get("STACKS_NOTIFY_SECRET", "").strip()
SITE = os.environ.get("SITE_URL", "https://stacksdaily.com").rstrip("/")

API_URL = "https://api.anthropic.com/v1/messages"
HEADERS = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

GRADE_PROMPT = """You are the prediction grader for Stacks, an investing-news app. Today is {today} (KST).

A past article made a checkable, real-world prediction. Use web search to find the ACTUAL outcome, then grade it. Only conclude from facts you can confirm in the search results. Never guess.

Article date: {date}
Source: {source}
Title (EN): {title_en}
What to check (EN): {note_en}
확인 사항 (KO): {note_ko}

Decide:
- "hit"  = the prediction clearly came true.
- "miss" = it clearly did NOT come true.
- "pending" = the result is not knowable yet (event hasn't happened, data not released). In that case set "due" to the ISO date (YYYY-MM-DD) when it should next be checked.
When uncertain, use "pending".

Return ONLY a JSON object, no prose, exactly this shape:
{{"status":"hit|miss|pending","note":{{"en":"one factual sentence including the date","ko":"날짜를 포함한 한 문장 사실 요약","ja":"日付を含む事実の一文"}},"due":"YYYY-MM-DD"}}
Include "due" only when status is "pending"."""

DUE_PROMPT = """Today is {today}. A prediction was made in an article dated {date}. Here is what needs to be checked to grade it:
EN: {note_en}
KO: {note_ko}

On what date will the outcome first be knowable / checkable? Reply with ONLY a JSON object: {{"due":"YYYY-MM-DD"}}. Pick a realistic near-future date (an earnings date, quarter end, event date, or a sensible follow-up); never a past date."""


def today_kst():
    return datetime.now(KST).date()


def load_items():
    with open(ITEMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_items(doc):
    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def api_call(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def extract_json(resp):
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def grade_one(item):
    o = item.get("outcome") or {}
    note = o.get("note") or {}
    title = item.get("title") or {}
    prompt = GRADE_PROMPT.format(
        today=today_kst().isoformat(),
        date=item.get("date", ""),
        source=item.get("source", ""),
        title_en=title.get("en", ""),
        note_en=note.get("en", ""),
        note_ko=note.get("ko", ""),
    )
    resp = api_call({
        "model": MODEL,
        "max_tokens": 1500,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": WS_USES}],
        "messages": [{"role": "user", "content": prompt}],
    })
    return extract_json(resp)


def estimate_due(item):
    o = item.get("outcome") or {}
    note = o.get("note") or {}
    prompt = DUE_PROMPT.format(
        today=today_kst().isoformat(),
        date=item.get("date", ""),
        note_en=note.get("en", ""),
        note_ko=note.get("ko", ""),
    )
    resp = api_call({
        "model": MODEL,
        "max_tokens": 120,
        "messages": [{"role": "user", "content": prompt}],
    })
    v = extract_json(resp)
    return (v or {}).get("due")


def notify(title, msg, url):
    if not WORKER or not SECRET:
        print("[skip push] worker url / secret not set")
        return
    params = urllib.parse.urlencode({
        "secret": SECRET, "tag": "daily",
        "title": title[:120], "msg": msg[:300], "url": url,
    })
    req = urllib.request.Request(WORKER + "/notify?" + params, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            out = json.loads(r.read().decode("utf-8"))
        print(("[push ok] " if out.get("sent") else "[push fail] ") + title)
    except Exception as e:
        print("[push error] " + str(e))


def main():
    if not API_KEY:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    doc = load_items()
    items = doc.get("items", [])
    todays = today_kst().isoformat()

    pending = [it for it in items
               if isinstance(it.get("outcome"), dict) and it["outcome"].get("status") == "pending"]
    due_now = [it for it in pending if it["outcome"].get("due") and it["outcome"]["due"] <= todays]
    no_due = [it for it in pending if not it["outcome"].get("due")]
    print("pending=%d  due_now=%d  no_due=%d" % (len(pending), len(due_now), len(no_due)))

    changed = False
    graded = []
    budget = MAX_GRADE

    for it in due_now:
        if budget <= 0:
            print("[budget] grading cap reached; remaining due items next run")
            break
        budget -= 1
        try:
            v = grade_one(it)
        except Exception as e:
            print("[err grade] %s: %s" % (it.get("id"), e))
            continue
        if not v:
            print("[no verdict] %s" % it.get("id"))
            continue
        st = v.get("status")
        if st in ("hit", "miss"):
            it["outcome"]["status"] = st
            if isinstance(v.get("note"), dict) and v["note"].get("en"):
                it["outcome"]["note"] = v["note"]
            it["outcome"]["gradedOn"] = todays
            it["outcome"].pop("due", None)
            graded.append((it, st))
            changed = True
            print("[graded] %s -> %s" % (it.get("id"), st))
        elif st == "pending" and re.match(r"\d{4}-\d{2}-\d{2}$", str(v.get("due", ""))):
            it["outcome"]["due"] = v["due"]
            changed = True
            print("[defer] %s -> due %s" % (it.get("id"), v["due"]))
        else:
            print("[hold] %s (no confident result)" % it.get("id"))

    for it in no_due:
        if budget <= 0:
            break
        budget -= 1
        try:
            due = estimate_due(it)
        except Exception as e:
            print("[err due] %s: %s" % (it.get("id"), e))
            continue
        if due and re.match(r"\d{4}-\d{2}-\d{2}$", str(due)) and due > todays:
            it["outcome"]["due"] = due
            changed = True
            print("[backfill due] %s -> %s" % (it.get("id"), due))

    if GRADE_PUSH and graded:
        for it, st in graded:
            t = it.get("title") or {}
            base = t.get("ko") or t.get("en") or ""
            msg = base + " — " + ("적중 ✓" if st == "hit" else "빗나감 ✕")
            notify("🎯 예측 채점", msg, SITE + "/#sig-" + it.get("id", ""))

    if changed:
        save_items(doc)
        print("items.json updated (%d graded)" % len(graded))
    else:
        print("no changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

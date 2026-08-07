#!/usr/bin/env python3
"""Watch the D1 auto-publish queue for a card that has been waiting too long.

The publisher writes completed cards to ``pending_cards`` and the
``apply-pending`` workflow drains that table.  An empty queue is healthy; a
non-empty queue is only an incident when its oldest row exceeds the allowed
age.  The script is deliberately read-only so it is safe to run on a schedule.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone


ACCOUNT = os.environ.get("CF_ACCOUNT_ID", "").strip()
DATABASE = os.environ.get("CF_DATABASE_ID", "").strip()
TOKEN = os.environ.get("CF_API_TOKEN", "").strip()
MAX_AGE_MINUTES = float(os.environ.get("MAX_AGE_MINUTES", "30"))


def d1(sql):
    url = (
        "https://api.cloudflare.com/client/v4/accounts/%s/d1/database/%s/query"
        % (ACCOUNT, DATABASE)
    )
    body = json.dumps({"sql": sql, "params": []}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("success"):
        raise RuntimeError("D1 query failed: %s" % result.get("errors"))
    return result["result"][0].get("results", [])


def parse_timestamp(value):
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main():
    if not ACCOUNT or not DATABASE or not TOKEN:
        print("PENDING_STATUS=error")
        print("PENDING_ERROR=Cloudflare D1 configuration is incomplete")
        return 2

    try:
        rows = d1(
            "SELECT COUNT(*) AS count, MIN(created_at) AS oldest_created_at "
            "FROM pending_cards"
        )
        row = rows[0] if rows else {}
        count = int(row.get("count") or 0)
        oldest = row.get("oldest_created_at")
        if count == 0 or not oldest:
            print("PENDING_STATUS=empty")
            print("PENDING_COUNT=0")
            return 0

        age = max(0.0, (datetime.now(timezone.utc) - parse_timestamp(oldest)).total_seconds() / 60)
        status = "stale" if age > MAX_AGE_MINUTES else "ok"
        print("PENDING_STATUS=" + status)
        print("PENDING_COUNT=%d" % count)
        print("PENDING_OLDEST_CREATED_AT=" + str(oldest))
        print("PENDING_OLDEST_AGE_MINUTES=%.1f" % age)
        print("PENDING_MAX_AGE_MINUTES=%.1f" % MAX_AGE_MINUTES)
        if status == "stale":
            return 1
        return 0
    except Exception as exc:  # the workflow turns this into a durable issue
        print("PENDING_STATUS=error")
        print("PENDING_ERROR=%s: %s" % (type(exc).__name__, exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Follower push relay — runs in GitHub Actions (notify-followers.yml).

Why this exists: the cloud sandbox that auto-publishes articles can reach
GitHub but not the Cloudflare Worker that sends OneSignal pushes. So the
publisher just commits items.json, and this script (running on a GitHub
runner, which CAN reach the Worker) diffs the pushed commit against the
previous one, finds newly added items that belong to a series, and sends
one follower push per new item.

Modes:
- push event: diff BEFORE_SHA..HEAD items.json, auto-send for new series items.
- workflow_dispatch: send exactly one push from the provided inputs
  (tag/title/msg/url), with an optional dry-run flag for testing.
"""
import json
import os
import subprocess
import sys
import urllib.request

ENDPOINT = "https://stacks-comments.wnrakrhdn128.workers.dev/notify"


def send(tag, title, msg, url, dry=False):
    if dry:
        print(f"[dry-run] would send: {tag} | {title} | {msg} | {url}")
        return
    secret = os.environ.get("PUSH_SECRET", "")
    if not secret:
        sys.exit(
            "PUSH_SECRET repo secret is not set. Add it in "
            "Settings > Secrets and variables > Actions > New repository secret."
        )
    payload = {"secret": secret, "tag": tag, "title": title, "msg": msg, "url": url}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    body = urllib.request.urlopen(req, timeout=30).read().decode()
    print(f"{tag} -> {body}")
    if '"sent":true' not in body.replace(" ", ""):
        sys.exit(f"push not confirmed by worker: {body}")


def previous_items_json():
    """Return the items.json content before this push, or None."""
    before = os.environ.get("BEFORE_SHA", "")
    candidates = []
    if before and set(before) != {"0"}:  # all-zero SHA = branch creation
        candidates.append(before)
    candidates.append("HEAD~1")
    for ref in candidates:
        try:
            out = subprocess.run(
                ["git", "show", f"{ref}:items.json"],
                capture_output=True, text=True, check=True,
            ).stdout
            print(f"diff base: {ref}")
            return out
        except subprocess.CalledProcessError:
            continue
    return None


def main():
    if os.environ.get("EVENT_NAME") == "workflow_dispatch":
        send(
            os.environ["IN_TAG"],
            os.environ["IN_TITLE"],
            os.environ["IN_MSG"],
            os.environ["IN_URL"],
            dry=os.environ.get("IN_DRY", "false").lower() == "true",
        )
        return

    new = json.load(open("items.json"))
    old_raw = previous_items_json()
    if old_raw is None:
        print("no previous items.json to diff against; skipping")
        return

    old_ids = {it["id"] for it in json.loads(old_raw).get("items", [])}
    series_meta = new.get("series", {})
    added = [it for it in new.get("items", []) if it["id"] not in old_ids]
    if not added:
        print("no new items in this push; nothing to send")
        return

    for it in added:
        sid = it.get("series")
        if not sid:
            print(f"skip {it['id']}: not part of a series")
            continue
        name_ko = series_meta.get(sid, {}).get("name", {}).get("ko", sid)
        send(
            f"s_{sid}",
            f"{name_ko} · 새 글",
            it["title"]["ko"],
            f"https://stacksdaily.com/#sig-{it['id']}",
        )


if __name__ == "__main__":
    main()

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
import re
import subprocess
import sys
import urllib.request

ENDPOINT = "https://stacks-comments.wnrakrhdn128.workers.dev/notify"

# Theme follower pushes (tag t_<key>). Keys/keywords MUST stay in sync with
# THEMES in index.html and scripts/build_pages.py.
THEMES = {
    "rates":   ("금리·인플레", re.I, r"기준금리|인플레|국채|연준|\bFed\b|FOMC|inflation|interest rates?|rate (?:cut|hike)|treasur|bond yield|\byields?\b|利上げ|利下げ|インフレ|国債|中央銀行"),
    "dollar":  ("달러·환율", re.I, r"달러|환율|원화|엔화|\bdollar\b|\bDXY\b|debasement|exchange rate|\byen\b|為替|円安|円高|ドル|통화"),
    "aicapex": ("AI 투자 사이클", 0, r"\bAI\b|인공지능|데이터센터|datacenter|data center|\bGPU\b|hyperscaler|capex|설비투자|人工知能|データセンター|設備投資"),
    "semis":   ("반도체·메모리", re.I, r"반도체|메모리|파운드리|semiconductor|\bchips?\b|foundry|\bDRAM\b|\bNAND\b|\bHBM\b|\bCXL\b|lithograph|半導体|メモリ"),
    "energy":  ("에너지", re.I, r"에너지|원유|천연가스|전력|원전|\boil\b|natural gas|\bLNG\b|uranium|nuclear|power grid|electricity|\benergy\b|原油|エネルギー|電力|原発"),
    "crypto":  ("크립토·금", re.I, r"비트코인|크립토|암호화폐|금값|\bBitcoin\b|\bBTC\b|crypto|stablecoin|\bgold\b|bullion|ビットコイン|暗号資産|金価格"),
    "trade":   ("관세·무역", re.I, r"관세|무역|수출\s?규제|수출통제|tariffs?|trade war|export controls?|sanctions?|보호무역|通商|関税|貿易|制裁"),
    "japan":   ("일본 시장", 0, r"일본|닛케이|엔저|\bJapan(?:ese)?\b|\bNikkei\b|\bBOJ\b|日銀|日本株|東証|日経"),
}


def item_themes(it):
    g = it.get("gist") or {}
    hay = " ".join([(it.get("title") or {}).get(l, "") or "" for l in ("en", "ko", "ja")]
                   + [g.get("en", "") or ""] + [" ".join(it.get("tags") or [])])
    return [(k, v[0]) for k, v in THEMES.items() if re.search(v[2], hay, v[1])]


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
        if sid:
            name_ko = series_meta.get(sid, {}).get("name", {}).get("ko", sid)
            send(
                f"s_{sid}",
                f"{name_ko} · 새 글",
                it["title"]["ko"],
                f"https://stacksdaily.com/#sig-{it['id']}",
            )
        else:
            print(f"skip series push {it['id']}: not part of a series")
        # theme follower pushes (max 2 themes per item to avoid spam)
        for key, label in item_themes(it)[:2]:
            try:
                send(
                    f"t_{key}",
                    f"{label} · 새 글",
                    it["title"]["ko"],
                    f"https://stacksdaily.com/#sig-{it['id']}",
                )
            except SystemExit:
                raise
            except Exception as e:
                print(f"[theme-push-skip] {it['id']} t_{key}: {e}")


if __name__ == "__main__":
    main()

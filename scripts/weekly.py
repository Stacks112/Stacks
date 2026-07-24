"""Stacks weekly best — auto wrap-up.

Runs on GitHub Actions every Sunday (see stacks-weekly.yml). Collects the
past 7 days of `hot` items, writes a ready-to-paste digest in ko / en / ja
to weekly/YYYY-MM-DD.md (committed by the workflow), and pushes one push
to everyone (tag `daily`) announcing it.

Why a draft + announce, not a silent auto-send: Substack has no public
"publish post" API, so the honest automation is to generate the finished
copy and ping June to hit send (one click), while readers get a push that
the weekly is up. If you later add an ESP with a send API (e.g. a Stibee
campaign endpoint or a Buttondown token), wire it in send_newsletter().

Env: same as brief.py (STACKS_WORKER_URL, STACKS_NOTIFY_SECRET,
ITEMS_PATH, SITE_URL). Optional OUT_DIR (default "weekly").
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
WORKER = os.environ.get("STACKS_WORKER_URL", "").rstrip("/")
SECRET = os.environ.get("STACKS_NOTIFY_SECRET", "").strip()
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
SITE = os.environ.get("SITE_URL", "https://stacksdaily.com").rstrip("/")
OUT_DIR = os.environ.get("OUT_DIR", "weekly")

L = {
    "ko": {"head": "이번 주 Stacks 베스트", "why": "왜 중요한가: ", "orig": "원문",
           "tail": "매일 업데이트는 Stacks에서: "},
    "en": {"head": "This week on Stacks", "why": "Why it matters: ", "orig": "Original",
           "tail": "Daily updates on Stacks: "},
    "ja": {"head": "今週のStacksベスト", "why": "なぜ重要か: ", "orig": "原文",
           "tail": "毎日の更新はStacksで: "},
}


def load_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def digest(lang, hot, site):
    T = L[lang]
    dates = sorted(i["date"] for i in hot)
    rng = dates[0][5:].replace("-", ".") + " ~ " + dates[-1][5:].replace("-", ".")
    out = ["# " + T["head"] + " (" + rng + ")", ""]
    for n, it in enumerate(hot, 1):
        tt = it.get("title", {})
        wy = it.get("why", {})
        gs = it.get("gist", {})
        out += [
            "## " + str(n) + ". " + (tt.get(lang) or tt.get("en", "")),
            "",
            "**" + T["why"] + "**" + (wy.get(lang) or wy.get("en", "")),
            "",
            (gs.get(lang) or gs.get("en", "")),
            "",
            T["orig"] + " (" + it.get("source", "") + "): " + it.get("sourceUrl", ""),
            "Stacks: " + site + "/#sig-" + it.get("id", ""),
            "", "---", "",
        ]
    out.append(T["tail"] + site)
    return "\n".join(out)


def notify(tag, title, msg, url):
    if not WORKER or not SECRET:
        print("[skip] worker url / secret not set")
        return False
    params = urllib.parse.urlencode({
        "secret": SECRET, "tag": tag, "title": title[:120], "msg": msg[:300], "url": url})
    req = urllib.request.Request(WORKER + "/notify?" + params, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            out = json.loads(r.read().decode("utf-8"))
        print(("[ok] " if out.get("sent") else "[fail] ") + title)
        return bool(out.get("sent"))
    except Exception as e:
        print("[error] " + str(e))
        return False


def send_newsletter(hot):
    """Send the weekly digest as an HTML email via Resend to the Stibee
    subscriber list (see scripts/weekly_send.py). No-op if keys are absent,
    so the workflow stays green until the secrets are configured.
    Returns True if a send actually happened."""
    if not (os.environ.get("RESEND_API_KEY") and
            (os.environ.get("STIBEE_API_KEY") or os.environ.get("WEEKLY_TEST_TO"))):
        print("email send skipped: RESEND_API_KEY / STIBEE_API_KEY not set")
        return False
    try:
        import weekly_send
        sent, errors = weekly_send.send_weekly(hot)
        return sent > 0 and not errors
    except Exception as e:  # noqa: BLE001
        print("email send failed: %s" % e)
        return False


def main():
    data = load_json(ITEMS_PATH, {})
    items = data.get("items", [])
    today = datetime.now(KST).date()
    cutoff = (today - timedelta(days=7)).isoformat()
    hot = sorted([i for i in items if i.get("hot") and i.get("date", "") >= cutoff],
                 key=lambda i: i.get("date", ""), reverse=True)
    if not hot:
        print("no hot items in the last 7 days; skipping")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = today.isoformat()
    md_by_lang = {}
    for lang in ("ko", "en", "ja"):
        md = digest(lang, hot, SITE)
        md_by_lang[lang] = md
        path = os.path.join(OUT_DIR, stamp + "." + lang + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        print("wrote " + path)

    sent = send_newsletter(hot)

    # announce to readers regardless (the site's Weekly is fresh)
    n = len(hot)
    notify("daily",
           "📰 이번 주 베스트 " + str(n) + "편",
           "이번 주 가장 중요한 읽을거리 " + str(n) + "편을 정리했어요.",
           SITE)
    print("done. esp_sent=%s, items=%d" % (sent, n))


if __name__ == "__main__":
    sys.exit(main())

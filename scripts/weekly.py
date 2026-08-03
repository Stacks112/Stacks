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

import worker_url

KST = timezone(timedelta(hours=9))
WORKER = worker_url.worker_base()
SECRET = os.environ.get("STACKS_NOTIFY_SECRET", "").strip()
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
SITE = os.environ.get("SITE_URL", "https://stacksdaily.com").rstrip("/")
OUT_DIR = os.environ.get("OUT_DIR", "weekly")

L = {
    "ko": {"head": "이번 주 Stacks 베스트", "why": "투자 포인트: ", "orig": "원문",
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
    body = json.dumps({
        "tag": tag, "title": title[:120], "msg": msg[:300], "url": url}).encode("utf-8")
    req = urllib.request.Request(WORKER + "/notify", data=body, method="POST",
                                 headers={"User-Agent": UA,
                                          "Accept": "application/json",
                                          "Content-Type": "application/json",
                                          "Authorization": "Bearer " + SECRET})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            out = json.loads(r.read().decode("utf-8"))
        print(("[ok] " if out.get("sent") else "[fail] ") + title)
        return bool(out.get("sent"))
    except Exception as e:
        print("[error] " + str(e))
        return False


def send_newsletter(hot):
    """Send the weekly digest as an HTML email via Resend to each language's
    Resend audience (see scripts/weekly_send.py). Sends ko/en/ja on a real
    broadcast; in test mode (WEEKLY_TEST_TO) sends only WEEKLY_LANG to that one
    address. No-op if keys are absent, so the workflow stays green until the
    secrets are configured. Returns True if a send actually happened."""
    if not os.environ.get("RESEND_API_KEY"):
        print("email send skipped: RESEND_API_KEY not set")
        return False
    test_to = os.environ.get("WEEKLY_TEST_TO", "").strip()
    if test_to:
        langs = [(os.environ.get("WEEKLY_LANG") or "ko").strip()]
    else:
        # WORKER 는 worker_url.worker_base() 가 항상 채워 준다(시크릿이 비어도
        # 정식 호스트로 폴백). 그래서 여기서는 시크릿 존재가 아니라 실제로
        # 쓸 주소가 있는지를 본다 — 옛 코드는 STACKS_WORKER_URL 이 비면
        # 발송을 통째로 건너뛰면서 그 사실을 로그 한 줄로만 남겼다.
        if not (WORKER and os.environ.get("STACKS_NOTIFY_SECRET")):
            print("email send skipped: worker url / notify secret not set")
            return False
        langs = ["ko", "en", "ja"]
    try:
        import weekly_send
        total_sent, total_err = 0, 0
        for lang in langs:
            sent, errors = weekly_send.send_weekly(hot, lang=lang)
            total_sent += sent
            total_err += len(errors)
            print("  [%s] sent=%d errors=%d" % (lang, sent, len(errors)))
        return total_sent > 0 and total_err == 0
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

    # announce to readers regardless (the site's Weekly is fresh) -- but not on a
    # test send. WEEKLY_TEST_TO means "mail only me, I am checking the layout";
    # firing the `daily` push there rings every subscriber's phone for a dry run.
    # 2026-08-03: a layout check did exactly that once before this guard existed.
    n = len(hot)
    if os.environ.get("WEEKLY_TEST_TO", "").strip():
        print("announce push skipped: test send (WEEKLY_TEST_TO set)")
    else:
        notify("daily",
               "📰 이번 주 베스트 " + str(n) + "편",
               "이번 주 가장 중요한 읽을거리 " + str(n) + "편을 정리했어요.",
               SITE)
    print("done. esp_sent=%s, items=%d" % (sent, n))
    _summary(sent, n)


def _summary(sent, n):
    """발송 결과를 job summary에 남긴다.

    2026-08-02 회차는 메일이 0통 나갔는데도 run이 초록이었다(send_newsletter가
    예외를 삼킨다). 로그 마지막 줄을 열어봐야만 알 수 있었다는 게 사고를 키웠다.
    실패해도 exit 1 로 죽이지는 않는다 — 그러면 다이제스트 커밋 스텝이 통째로
    건너뛰어져 생성물까지 잃는다. 대신 run 페이지 첫 화면에서 보이게 한다.

    ⚠ 실행 종류를 구분한다. 드라이런과 테스트 발송까지 ❌로 찍으면 경고가 값을
    잃는다. 매번 빨간 표시를 보는 사람은 진짜 사고 때도 그냥 넘긴다.
    (2026-08-03 드라이런이 실제로 '발송 0통 ❌'으로 찍혀서 이 구분을 넣었다.)"""
    dry = str(os.environ.get("DRY_RUN", "")).strip() == "1"
    test_to = os.environ.get("WEEKLY_TEST_TO", "").strip()

    if dry:
        mark = "🧪 드라이런 — 메시지만 만들고 발송하지 않음 (정상)"
    elif test_to:
        mark = ("✅ 테스트 발송됨 (수신자 1명)" if sent
                else "⚠️ 테스트 발송 실패 — 로그의 `email send failed:` 확인")
    elif sent:
        mark = "✅ 발송됨"
    else:
        mark = "❌ **발송 0통** — 로그의 `email send failed:` 확인"
        # 실제 브로드캐스트가 0통일 때만 빨간 주석을 남긴다.
        # 여기서 exit 1 하지 않는 이유는 위 독스트링에 적었다(생성물 손실).
        # 초록 체크만 보고 "나갔겠지" 하고 넘어간 것이 2026-08-02 사고였다.
        print("::error::주간 뉴스레터가 0통 발송됐습니다. 위 로그의 "
              "'email send failed:' 줄을 확인하세요.")

    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    # 워커 주소는 적지 않는다. 저장소 시크릿과 같은 값이라 GitHub이 `***`로
    # 가려 버려서 정보가 되지 못한다(2026-08-03 시크릿 교체 후 확인).
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("## Stacks Weekly Best\n\n%s · 대상 글 %d편\n" % (mark, n))
    except OSError:
        pass


if __name__ == "__main__":
    sys.exit(main())

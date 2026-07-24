"""Stacks weekly performance digest — fully autonomous, with AI 총평.

Runs on GitHub Actions (see stats-weekly.yml). NO human, NO browser, NO
approval prompt: GitHub's runner has open outbound network, so it fetches
the four public endpoints directly with urllib, joins them by id, and:

  1. writes a scannable ko digest to stats/YYYY-MM-DD.md (committed),
  2. asks Claude (via ANTHROPIC_API_KEY) for a 3-5 sentence 총평 + 제언, and
  3. pushes a one-line summary to June via the worker /notify endpoint.

This is the piece the Claude Cowork scheduled task CANNOT do headlessly
(WebFetch needs an interactive approval, curl is proxy-blocked). Actions
can, because it is a real headless runner.

Env (STACKS_* already exist as repo secrets from the other pipelines):
  STACKS_WORKER_URL     e.g. https://stacks-comments.wnrakrhdn128.workers.dev
  STACKS_NOTIFY_SECRET  shared secret for /notify
  ANTHROPIC_API_KEY     enables the AI 총평 (already a repo secret)
  STATS_LLM_MODEL       model id for the 총평 (default below; override if needed)
  ITEMS_PATH            default "items.json" (checked out from the repo)
  SITE_URL              default https://stacksdaily.com
  OUT_DIR               default "stats"
  STATS_NOTIFY_TAG      private push tag for June only (default "owner" — NOT "daily",
                        so this internal digest never goes to all readers)
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
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.environ.get("STATS_LLM_MODEL", "claude-3-5-sonnet-latest")
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
SITE = os.environ.get("SITE_URL", "https://stacksdaily.com").rstrip("/")
OUT_DIR = os.environ.get("OUT_DIR", "stats")
NOTIFY_TAG = os.environ.get("STATS_NOTIFY_TAG", "owner")

TOP_N = 5


def get_json(url, fallback):
    """GET a URL and parse JSON. Returns fallback on any failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stacks-stats"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("[warn] fetch failed: %s (%s)" % (url, e))
        return fallback


def load_items():
    """Item metadata from the repo file, or fall back to the live site."""
    try:
        with open(ITEMS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return get_json(SITE + "/items.json", {})


def title_ko(it):
    t = it.get("title", {})
    return t.get("ko") or t.get("en") or it.get("id", "")


def notify(tag, title, msg, url):
    if not WORKER or not SECRET:
        print("[skip] worker url / secret not set")
        return False
    params = urllib.parse.urlencode({
        "secret": SECRET, "tag": tag,
        "title": title[:120], "msg": msg[:300], "url": url})
    req = urllib.request.Request(WORKER + "/notify?" + params, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            out = json.loads(r.read().decode("utf-8"))
        print(("[ok] " if out.get("sent") else "[fail] ") + title)
        return bool(out.get("sent"))
    except Exception as e:
        print("[error] " + str(e))
        return False


def ai_take(facts):
    """Ask Claude for a Korean 총평 + 제언. Returns "" if unavailable."""
    if not API_KEY:
        print("[skip] no ANTHROPIC_API_KEY; 총평 omitted")
        return ""
    prompt = (
        "너는 투자 콘텐츠 앱 Stacks(stacksdaily.com)의 주간 성과를 분석한다.\n"
        "아래는 이번 주 스냅샷 집계다. 이걸 근거로 한국어 총평을 써라.\n"
        "3~5문장, 불릿 없이 자연스러운 문단. 어떤 소스(메르·Doomberg·Serenity·"
        "CEO 등)와 주제(반도체·AI전력·유가·일본 등)가 먹히는지, 다음 주에 뭘 더/덜 "
        "다루면 좋을지 구체적으로. 데이터에 없는 수치는 지어내지 마라.\n\n"
        + facts)
    body = json.dumps({
        "model": LLM_MODEL,
        "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode("utf-8"))
        parts = [b.get("text", "") for b in out.get("content", [])
                 if b.get("type") == "text"]
        text = "".join(parts).strip()
        print("[ok] 총평 generated (%d chars)" % len(text))
        return text
    except Exception as e:
        print("[error] 총평 failed: " + str(e))
        return ""


def row(it, views, likes, comments):
    return {
        "id": it.get("id", ""),
        "title": title_ko(it),
        "source": it.get("source", ""),
        "date": it.get("date", ""),
        "hot": bool(it.get("hot")),
        "views": views.get(it.get("id", ""), 0),
        "likes": likes.get(it.get("id", ""), 0),
        "comments": comments.get(it.get("id", ""), 0),
    }


def table(rows, cols):
    head = "| " + " | ".join(c[1] for c in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    lines = [head, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c[0]]) for c in cols) + " |")
    return "\n".join(lines)


def rankings(rows):
    live = [r for r in rows if r["views"] > 0]
    by_views = sorted(rows, key=lambda r: (-r["views"], r["title"]))[:TOP_N]
    by_likes = sorted([r for r in rows if r["likes"] > 0],
                      key=lambda r: (-r["likes"], -r["views"]))[:TOP_N]
    commented = sorted([r for r in rows if r["comments"] > 0],
                       key=lambda r: -r["comments"])
    react = sorted(
        [r for r in live if (r["likes"] + r["comments"]) > 0],
        key=lambda r: -((r["likes"] + r["comments"]) / r["views"]))
    src = {}
    for r in rows:
        src[r["source"]] = src.get(r["source"], 0) + r["views"]
    src_rank = sorted(src.items(), key=lambda kv: -kv[1])[:8]
    return live, by_views, by_likes, commented, react, src_rank


def facts_text(by_views, by_likes, commented, react, src_rank, tv, tl, tc):
    L = []
    L.append("전체: 조회 %d, 좋아요 %d, 댓글 %d" % (tv, tl, tc))
    L.append("조회 Top: " + "; ".join(
        "%s(%s)=%d" % (r["title"], r["source"], r["views"]) for r in by_views))
    L.append("좋아요: " + ("; ".join(
        "%s=%d" % (r["title"], r["likes"]) for r in by_likes) or "없음"))
    L.append("댓글: " + ("; ".join(
        "%s=%d" % (r["title"], r["comments"]) for r in commented) or "없음"))
    L.append("반응률(좋아요+댓글/조회): " + ("; ".join(
        "%s=%.0f%%" % (r["title"], (r["likes"] + r["comments"]) / r["views"] * 100)
        for r in react[:TOP_N]) or "없음"))
    L.append("소스별 조회합계: " + "; ".join(
        "%s=%d" % (n, v) for n, v in src_rank))
    return "\n".join(L)


def build_md(rows, stamp, take):
    live, by_views, by_likes, commented, react, src_rank = rankings(rows)
    tv = sum(r["views"] for r in rows)
    tl = sum(r["likes"] for r in rows)
    tc = sum(r["comments"] for r in rows)
    cols = [("title", "제목(ko)"), ("source", "출처"),
            ("views", "조회"), ("likes", "좋아요"), ("comments", "댓글")]

    out = []
    out.append("# 📊 Stacks 주간 성과 다이제스트 — " + stamp)
    out.append("")
    out.append("스냅샷 기준. 전체 조회 **%d** · 좋아요 **%d** · 댓글 **%d** "
               "(글 %d개, 조회 발생 %d개)."
               % (tv, tl, tc, len(rows), len(live)))
    out.append("")
    out.append("## 1. 조회수 Top %d" % TOP_N)
    out.append("")
    out.append(table(by_views, cols))
    out.append("")
    out.append("## 2. 좋아요 Top %d" % TOP_N)
    out.append("")
    out.append(table(by_likes, cols) if by_likes else "_좋아요가 달린 글 없음._")
    out.append("")
    out.append("## 3. 댓글이 달린 글")
    out.append("")
    if commented:
        for r in commented:
            out.append("- %s (%s) — 댓글 %d" % (r["title"], r["source"], r["comments"]))
    else:
        out.append("_댓글이 달린 글 없음._")
    out.append("")
    out.append("## 4. 반응이 붙기 시작한 글 (조회 대비 좋아요+댓글 비율)")
    out.append("")
    if react:
        for r in react[:TOP_N]:
            ratio = (r["likes"] + r["comments"]) / r["views"] * 100
            flag = " · 🆕" if r["hot"] else ""
            out.append("- %s (%s) — 조회 %d, 좋아요 %d, 댓글 %d = **%.1f%%**%s"
                       % (r["title"], r["source"], r["views"],
                          r["likes"], r["comments"], ratio, flag))
    else:
        out.append("_반응(좋아요·댓글)이 아직 없음 — 조회수가 유일한 신호._")
    out.append("")
    out.append("## 5. 소스별 조회 합계 (뭐가 먹히나)")
    out.append("")
    for name, v in src_rank:
        out.append("- %s — 조회 %d" % (name, v))
    out.append("")
    out.append("## 6. 총평 + 다음 주 제언")
    out.append("")
    out.append(take if take else "_AI 총평 생략(키 없음 또는 호출 실패). 위 집계로 판단하세요._")
    out.append("")
    out.append("---")
    out.append("_자동 생성 · 매주 · GitHub Actions. 데이터: /views /likes /counts + items.json_")
    return "\n".join(out), by_views, tv, tl, tc


def main():
    data = load_items()
    items = data.get("items", []) if isinstance(data, dict) else []
    if not items:
        print("no items; abort")
        return 1

    views = (get_json(WORKER + "/views", {}) or {}).get("data", {}) if WORKER else {}
    likes = (get_json(WORKER + "/likes", {}) or {}).get("data", {}) if WORKER else {}
    counts = (get_json(WORKER + "/counts", {}) or {}).get("data", {}) if WORKER else {}

    missing = [n for n, d in (("views", views), ("likes", likes),
                              ("counts", counts)) if not d]
    if missing:
        print("[warn] empty endpoints: " + ", ".join(missing))

    rows = [row(it, views, likes, counts) for it in items]

    # AI 총평 from the ranked facts
    _, bv, bl, cm, rc, sr = rankings(rows)
    tv = sum(r["views"] for r in rows)
    tl = sum(r["likes"] for r in rows)
    tc = sum(r["comments"] for r in rows)
    take = ai_take(facts_text(bv, bl, cm, rc, sr, tv, tl, tc))

    today = datetime.now(KST).date()
    stamp = today.isoformat()
    md, top, tv, tl, tc = build_md(rows, stamp, take)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, stamp + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print("wrote " + path)

    # push June a one-line summary so it reaches phone/inbox even while away
    if top:
        t1 = top[0]
        msg = "1위 %s (조회 %d) · 전체 조회 %d/좋아요 %d/댓글 %d" % (
            t1["title"][:40], t1["views"], tv, tl, tc)
        notify(NOTIFY_TAG, "📊 주간 성과 다이제스트", msg, SITE + "/stats")

    warn = " (일부 엔드포인트 비어있음: %s)" % ", ".join(missing) if missing else ""
    print("done." + warn)
    return 0


if __name__ == "__main__":
    sys.exit(main())

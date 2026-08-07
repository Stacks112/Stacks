"""Build a weekly GoatCounter entity-click report.

The public site only emits anonymized event paths such as
``entity/click/inline/company/nvidia``. This job reads the aggregate path
counts from GoatCounter's read-only JSON API and commits a small Markdown
report under ``stats/``. No visitor IDs or raw hit data are downloaded.

Required in CI:
  GOATCOUNTER_SITE     e.g. https://stacks.goatcounter.com
  GOATCOUNTER_API_KEY  API key with read-sites and read-statistics permission

The job exits successfully without writing a file when the key is not
configured, so analytics never blocks the normal publishing digest.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone


KST = timezone(timedelta(hours=9))
SITE = os.environ.get("GOATCOUNTER_SITE", "").strip().rstrip("/")
API_KEY = os.environ.get("GOATCOUNTER_API_KEY", "").strip()
ITEMS_PATH = os.environ.get("ITEMS_PATH", "items.json")
OUT_DIR = os.environ.get("OUT_DIR", "stats")
DAYS = max(1, int(os.environ.get("GOATCOUNTER_DAYS", "7")))
EVENT_PREFIX = "entity/click/"
PATH_CHUNK_SIZE = 100


def slug_tag(value):
    return re.sub(r"[^a-z0-9가-힣]+", "_", str(value).lower()).strip("_")


def date_range(today=None, days=DAYS):
    today = today or datetime.now(KST).date()
    start = today - timedelta(days=days - 1)
    end = today + timedelta(days=1)
    return start, end


def api_url(site, start, end, include_paths=()):
    params = [
        ("limit", 100),
        ("start", start.isoformat() + "T00:00:00Z"),
        ("end", end.isoformat() + "T00:00:00Z"),
    ]
    params.extend(("include_paths", path_id) for path_id in include_paths)
    return site.rstrip("/") + "/api/v0/stats/hits?" + urllib.parse.urlencode(params)


def api_get(url, token):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
            "User-Agent": "stacks-analytics-report",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def paths_url(site, after=None):
    params = [("limit", 200)]
    if after is not None:
        params.append(("after", after))
    return site.rstrip("/") + "/api/v0/paths?" + urllib.parse.urlencode(params)


def fetch_paths(site, token):
    paths = []
    after = None
    while True:
        payload = api_get(paths_url(site, after), token)
        if not isinstance(payload, dict):
            break
        page = payload.get("paths", [])
        if not isinstance(page, list):
            break
        paths.extend(page)
        if not payload.get("more") or not page:
            break
        next_after = page[-1].get("id") if isinstance(page[-1], dict) else None
        if next_after is None or next_after == after:
            break
        after = next_after
    return paths


def event_path_ids(paths):
    return [
        path["id"]
        for path in paths or []
        if isinstance(path, dict)
        and str(path.get("path") or "").startswith(EVENT_PREFIX)
        and path.get("id") is not None
    ]


def fetch_hits(site, token, start, end, path_ids):
    hits = []
    for offset in range(0, len(path_ids), PATH_CHUNK_SIZE):
        payload = api_get(
            api_url(site, start, end, path_ids[offset:offset + PATH_CHUNK_SIZE]),
            token,
        )
        if isinstance(payload, dict):
            hits.extend(payload.get("hits", []))
    return hits


def parse_entity_path(path):
    path = str(path or "")
    if not path.startswith(EVENT_PREFIX):
        return None
    parts = path.split("/")
    if len(parts) < 5 or not parts[2] or not parts[3] or not parts[4]:
        return None
    return {"surface": parts[2], "kind": parts[3], "slug": "/".join(parts[4:])}


def aggregate_hits(hits):
    entities = defaultdict(lambda: {"clicks": 0, "visitors": 0})
    surfaces = defaultdict(int)
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        parsed = parse_entity_path(hit.get("path"))
        if not parsed:
            continue
        clicks = int(hit.get("count", 0) or 0)
        visitors = int(hit.get("unique", hit.get("uniques", 0)) or 0)
        key = (parsed["kind"], parsed["slug"])
        entities[key]["clicks"] += clicks
        entities[key]["visitors"] += visitors
        surfaces[parsed["surface"]] += clicks
    ranked = sorted(
        ({"kind": k[0], "slug": k[1], **v} for k, v in entities.items()),
        key=lambda row: (-row["clicks"], -row["visitors"], row["slug"]),
    )
    return ranked, sorted(surfaces.items(), key=lambda item: (-item[1], item[0]))


def load_entity_labels(path=ITEMS_PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    entities = data.get("entities", {}) if isinstance(data, dict) else {}
    return {slug_tag(key): key for key in entities}


def build_report(rows, surfaces, start, end, labels=None):
    labels = labels or {}
    lines = [
        "# 엔티티 클릭 주간 리포트 — %s ~ %s" % (start.isoformat(), (end - timedelta(days=1)).isoformat()),
        "",
        "인물·기업·전문용어 클릭을 엔티티별로 합산한 익명 집계입니다. "
        "같은 사용자의 중복 클릭은 GoatCounter가 제공한 집계 기준을 따릅니다.",
        "",
        "## 인기 엔티티",
        "",
        "| 순위 | 유형 | 엔티티 | 클릭 | 방문자 |",
        "|---:|---|---|---:|---:|",
    ]
    if rows:
        for index, row in enumerate(rows[:20], 1):
            label = labels.get(row["slug"], row["slug"])
            lines.append("| %d | %s | %s | %d | %d |" % (
                index, row["kind"], label, row["clicks"], row["visitors"]))
    else:
        lines.append("| — | — | 아직 집계된 클릭 없음 | 0 | 0 |")
    lines.extend(["", "## 클릭 위치", "", "| 위치 | 클릭 |", "|---|---:|"])
    if surfaces:
        lines.extend("| %s | %d |" % item for item in surfaces)
    else:
        lines.append("| — | 0 |")
    lines.extend(["", "_자동 생성 · GoatCounter API · 이벤트 경로: `entity/click/...`", ""])
    return "\n".join(lines)


def write_summary(rows, start, end):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return
    top = rows[:5]
    text = ["## Entity clicks (%s ~ %s)" % (start.isoformat(), (end - timedelta(days=1)).isoformat()), ""]
    text.extend("- `%s/%s` — %d clicks" % (r["kind"], r["slug"], r["clicks"]) for r in top)
    if not top:
        text.append("- No entity clicks recorded.")
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(text) + "\n")


def main():
    if not SITE or not API_KEY:
        print("[skip] GOATCOUNTER_SITE or GOATCOUNTER_API_KEY is not configured")
        return 0
    start, end = date_range()
    try:
        path_ids = event_path_ids(fetch_paths(SITE, API_KEY))
        hits = fetch_hits(SITE, API_KEY, start, end, path_ids)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print("[warn] GoatCounter analytics unavailable: %s" % exc)
        return 0
    rows, surfaces = aggregate_hits(hits)
    labels = load_entity_labels()
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now(KST).date().isoformat()
    path = os.path.join(OUT_DIR, "analytics-" + stamp + ".md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_report(rows, surfaces, start, end, labels))
    write_summary(rows, start, end)
    print("wrote %s (%d entities, %d raw paths)" % (path, len(rows), len(hits)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

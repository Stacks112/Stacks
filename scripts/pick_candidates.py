#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pick_candidates.py — 자동 발행 회차의 결정론적 후보 선별.

지금까지는 모델이 feeds/*.json (최대 26개 소스, 최대 390건)을 직접 읽고
48시간 창·중복(sourceUrl)·소스별 상한을 손으로 판정했다. 그 중 기계적으로
판정 가능한 부분(시간 창, 중복, 상한 조회, 데뷔 예외, macro-week 주기,
이중 실행 감지)만 이 스크립트로 옮긴다.

이 스크립트가 하지 않는 것: 품질·투자 관련성·잡담 여부 판정. 그건 모델 몫이다.
여기서 "후보"로 남은 항목은 전부 그대로 모델에게 넘어간다 — 이 스크립트는
후보를 추천하지 않고, 기계적으로 걸러낼 수 있는 것만 걸러낸다.

사용:
  python3 scripts/pick_candidates.py                       # --hours 48 기본
  python3 scripts/pick_candidates.py --hours 168            # 창을 넓혀서 확인
  python3 scripts/pick_candidates.py --json out.json        # 기계 판독용 전체 출력
  python3 scripts/pick_candidates.py --top 3                # 소스당 표 노출 건수

종료코드: 정상 0 (후보 0건이어도 0). items.json/sources.json 을 못 읽으면 2.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


# ---------------------------------------------------------------------------
# sourceUrl 정규화
# ---------------------------------------------------------------------------

def _longest_digit_run(s):
    groups = re.findall(r"\d+", s)
    if not groups:
        return None
    return max(groups, key=len)


def normalize_url(url):
    """(key, ok) 반환. ok=False 면 정규화 실패(중복 판정에 쓰지 말 것)."""
    if not url:
        return (None, False)
    try:
        parts = urlsplit(url.strip())
    except Exception:
        return (None, False)
    netloc = (parts.netloc or "").lower()
    path = parts.path or ""

    # 네이버 블로그: 글 ID 숫자만, 쿼리스트링 무시
    if "blog.naver.com" in netloc:
        digits = _longest_digit_run(path)
        if digits:
            return (f"naver:{digits}", True)
        return (None, False)

    # x.com / twitter.com: /status/ 뒤 숫자만
    if "x.com" in netloc or "twitter.com" in netloc:
        m = re.search(r"/status/(\d+)", path)
        if m:
            return (f"x:{m.group(1)}", True)
        return (None, False)

    # truthsocial.com / trumpstruth.org: 게시물 ID 숫자, 없으면 실패
    # (trumpstruth.org: /statuses/40591, truthsocial.com: /@user/<숫자ID> 등 위치가 다를 수
    # 있어 경로 내 가장 긴 숫자열을 ID로 취급한다 — naver 규칙과 동일한 근거)
    if "truthsocial.com" in netloc or "trumpstruth.org" in netloc:
        digits = _longest_digit_run(path)
        if digits:
            return (f"truth:{digits}", True)
        return (None, False)

    # 그 밖: 스킴·www.·쿼리스트링·마지막 슬래시 제거한 소문자 URL
    host = netloc[4:] if netloc.startswith("www.") else netloc
    p = path.rstrip("/")
    key = f"{host}{p}".lower()
    return (key or None, bool(key))


# ---------------------------------------------------------------------------
# 시각 파싱
# ---------------------------------------------------------------------------

def parse_dt(s):
    """타임존 표기가 섞여 있어도 견고하게. 실패하면 None."""
    if not s:
        return None
    s = s.strip()
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    # 흔한 대체 포맷들
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def fmt_elapsed(td):
    total_min = int(td.total_seconds() // 60)
    if total_min < 0:
        total_min = 0
    h, m = divmod(total_min, 60)
    return f"{h}h{m:02d}m"


# ---------------------------------------------------------------------------
# 로딩
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sources(path):
    try:
        data = load_json(path)
    except Exception as e:
        print(f"[경고] sources.json 을 읽지 못했다 ({e}) — feed_id -> 표시명 매핑 없이 진행", file=sys.stderr)
        return {}, {}
    feed_map = {}
    for k, v in data.items():
        if k.startswith("_"):
            continue
        feed_map[k] = {"source": v.get("source", k), "category": v.get("category", "")}
    caps = data.get("_CAPS")
    if not caps:
        print("[경고] sources.json 에 _CAPS 블록이 없다 — 상한 판정 없이 진행", file=sys.stderr)
        caps = {}
    return feed_map, caps


# ---------------------------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------------------------

def build_existing_url_set(items):
    keys = set()
    fail_count = 0
    for it in items:
        key, ok = normalize_url(it.get("sourceUrl", ""))
        if ok and key:
            keys.add(key)
        else:
            fail_count += 1
    return keys, fail_count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=int, default=48, help="발행 창(시간). 기본 48")
    ap.add_argument("--debut-days", type=int, default=7, help="신규 소스 데뷔 유예일. 기본 7")
    ap.add_argument("--json", default="", help="기계 판독용 전체 출력을 이 경로에 JSON으로 쓴다")
    ap.add_argument("--top", type=int, default=4, help="소스당 표에 찍을 최대 건수. 기본 4")
    ap.add_argument("--items", default=os.path.join(REPO_ROOT, "items.json"))
    ap.add_argument("--sources", default=os.path.join(REPO_ROOT, "sources.json"))
    ap.add_argument("--feeds-dir", default=os.path.join(REPO_ROOT, "feeds"))
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    today = now.date()

    try:
        items_data = load_json(args.items)
        items = items_data.get("items", [])
    except Exception as e:
        print(f"[오류] items.json 을 읽지 못했다: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        sources_data = load_json(args.sources)
    except Exception as e:
        print(f"[오류] sources.json 을 읽지 못했다: {e}", file=sys.stderr)
        sys.exit(2)

    feed_map = {}
    for k, v in sources_data.items():
        if k.startswith("_"):
            continue
        feed_map[k] = {"source": v.get("source", k), "category": v.get("category", "")}
    caps = sources_data.get("_CAPS")
    if not caps:
        print("[경고] sources.json 에 _CAPS 블록이 없다 — 상한 판정 없이 진행", file=sys.stderr)
        caps = {}

    # 기존 sourceUrl 정규화 집합
    existing_keys, existing_norm_fail = build_existing_url_set(items)

    # 표시명별 items.json 내 전체 카드 수 (데뷔 판정용)
    all_time_counts = {}
    for it in items:
        src = it.get("source", "")
        all_time_counts[src] = all_time_counts.get(src, 0) + 1

    # feeds 순회
    feeds_dir = args.feeds_dir
    candidates = []            # dict: display, feed_id, published(dt), title, content_len, short, debut, norm_key, norm_failed, link
    excluded_out_of_window = 0
    excluded_already_pub = 0
    unparsed_count = 0
    unregistered_feeds = []

    if os.path.isdir(feeds_dir):
        feed_files = sorted(f for f in os.listdir(feeds_dir) if f.endswith(".json"))
    else:
        feed_files = []
        print(f"[경고] feeds 디렉터리를 찾을 수 없다: {feeds_dir}", file=sys.stderr)

    for fname in feed_files:
        feed_id = fname[:-5]
        fpath = os.path.join(feeds_dir, fname)
        try:
            fdata = load_json(fpath)
        except Exception as e:
            print(f"[경고] {fname} 파싱 실패: {e}", file=sys.stderr)
            continue

        info = feed_map.get(feed_id)
        if info is None:
            unregistered_feeds.append(feed_id)
            continue
        display = info["source"]
        category = info["category"]
        is_debut = all_time_counts.get(display, 0) == 0

        for it in fdata.get("items", []):
            pub = parse_dt(it.get("published", ""))
            if pub is None:
                unparsed_count += 1
                continue

            elapsed = now - pub
            elapsed_hours = elapsed.total_seconds() / 3600.0
            debut_flag = False
            if elapsed_hours <= args.hours:
                in_window = True
            elif is_debut and elapsed_hours <= args.debut_days * 24:
                in_window = True
                debut_flag = True
            else:
                in_window = False

            if not in_window:
                excluded_out_of_window += 1
                continue

            link = it.get("link", "")
            norm_key, norm_ok = normalize_url(link)
            if norm_ok and norm_key in existing_keys:
                excluded_already_pub += 1
                continue

            content = it.get("content", "") or ""
            content_len = len(content)
            short_flag = content_len < 200
            title = (it.get("title", "") or "").replace("\n", " ").strip()
            title80 = title[:80] + ("…" if len(title) > 80 else "")

            candidates.append({
                "display": display,
                "feed_id": feed_id,
                "category": category,
                "published": pub.isoformat(),
                "elapsed_hours": round(elapsed_hours, 2),
                "title": title80,
                "content_len": content_len,
                "short": short_flag,
                "debut": debut_flag,
                "norm_key": norm_key if norm_ok else "(정규화 실패)",
                "norm_failed": not norm_ok,
                "link": link,
            })

    # -----------------------------------------------------------------
    # 출력 구성
    # -----------------------------------------------------------------
    out_lines = []

    def emit(line=""):
        out_lines.append(line)

    emit(f"pick_candidates.py — hours={args.hours} debut_days={args.debut_days} 기준시각(UTC)={now.strftime('%Y-%m-%d %H:%M:%S')}")
    emit("")

    if unregistered_feeds:
        emit(f"[경고] sources.json 에 없는 feed_id: {', '.join(unregistered_feeds)}")
        emit("")

    # 후보 표: 표시명별로 묶기
    by_display = {}
    for c in candidates:
        by_display.setdefault(c["display"], []).append(c)

    emit(f"=== 후보 ({len(candidates)}건, {len(by_display)}개 소스) ===")
    if not candidates:
        emit("(후보 없음)")
    for display in sorted(by_display.keys(), key=lambda d: -len(by_display[d])):
        lst = sorted(by_display[display], key=lambda c: c["elapsed_hours"])
        emit(f"- {display} ({len(lst)}건)")
        for c in lst[: args.top]:
            flags = []
            if c["debut"]:
                flags.append("debut")
            if c["short"]:
                flags.append("short")
            if c["norm_failed"]:
                flags.append("norm-fail")
            flag_str = f" [{','.join(flags)}]" if flags else ""
            emit(
                f"    · {c['published']} (경과 {fmt_elapsed(timedelta(hours=c['elapsed_hours']))}) "
                f"{c['content_len']}자{flag_str} key={c['norm_key']} \"{c['title']}\" {c['link']}"
            )
        if len(lst) > args.top:
            emit(f"    (+{len(lst) - args.top}건 더)")
    emit("")

    # 소스별 상한
    per_source = caps.get("per_source", {}) if caps else {}
    per_category = caps.get("per_category", {}) if caps else {}
    default_per_source = caps.get("default_per_source", None) if caps else None
    total_cap = caps.get("total", None) if caps else None

    emit("=== 소스별 상한 (_CAPS 기준) ===")
    if not caps:
        emit("(_CAPS 없음 — 상한 판정 불가)")
    else:
        emit(f"총 상한 total={total_cap} default_per_source={default_per_source}")
        # 등록된 전체 표시명(중복 제거, feed_id 짝은 표시명 기준 합산되어 자동 처리됨)
        all_displays = sorted(set(v["source"] for v in feed_map.values()))
        no_candidate_displays = []
        for display in all_displays:
            cat = next((v["category"] for v in feed_map.values() if v["source"] == display), "")
            cap = per_source.get(display, default_per_source)
            cat_cap = per_category.get(cat)
            cand_n = len(by_display.get(display, []))
            if cand_n == 0:
                no_candidate_displays.append(display if cap == default_per_source else f"{display}(cap={cap})")
                continue
            extra = f", per_category[{cat}]={cat_cap}" if cat_cap is not None else ""
            emit(f"  {display} (cat={cat}): cap={cap}{extra}  [이번 회차 후보 {cand_n}건]")
        if per_category:
            emit(f"  per_category 전체: {per_category}")
        if no_candidate_displays:
            emit(f"  (이번 회차 후보 0건, cap=default_per_source={default_per_source} 별도 표기 외): {', '.join(no_candidate_displays)}")
    emit("")

    # 최근 7일 카드 0건 소스
    seven_days_ago = today - timedelta(days=7)
    fourteen_days_ago = today - timedelta(days=14)

    def date_of(it):
        try:
            return datetime.strptime(it.get("date", ""), "%Y-%m-%d").date()
        except Exception:
            return None

    recent7_sources = set()
    recent7_counts = {}
    recent14_counts = {}
    for it in items:
        d = date_of(it)
        if d is None:
            continue
        src = it.get("source", "")
        if d >= seven_days_ago:
            recent7_sources.add(src)
            recent7_counts[src] = recent7_counts.get(src, 0) + 1
        if d >= fourteen_days_ago:
            recent14_counts[src] = recent14_counts.get(src, 0) + 1

    all_registered_displays = sorted(set(v["source"] for v in feed_map.values()))
    zero_7d = [d for d in all_registered_displays if d not in recent7_sources]
    emit(f"=== 최근 7일 카드 0건 소스 ({len(zero_7d)}개) ===")
    emit(", ".join(zero_7d) if zero_7d else "(없음)")
    emit("")

    def top5_share(counts):
        total = sum(counts.values())
        if total == 0:
            return []
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
        return [(name, n, round(100.0 * n / total, 1)) for name, n in ranked]

    emit("=== 편중: 최근 7일 소스별 비율 상위 5 ===")
    for name, n, pct in top5_share(recent7_counts):
        emit(f"  {name}: {n}건 ({pct}%)")
    if not recent7_counts:
        emit("  (카드 없음)")
    emit("=== 편중: 최근 14일 소스별 비율 상위 5 ===")
    for name, n, pct in top5_share(recent14_counts):
        emit(f"  {name}: {n}건 ({pct}%)")
    if not recent14_counts:
        emit("  (카드 없음)")
    emit("")

    # macro-week 판정
    macro_ids = [it["id"] for it in items if it.get("id", "").startswith("macro-week-")]
    macro_status = ""
    macro_days = None
    if not macro_ids:
        macro_status = "MACRO: due (없음)"
    else:
        dates = []
        for mid in macro_ids:
            datestr = mid[len("macro-week-"):]
            try:
                dates.append(datetime.strptime(datestr, "%Y-%m-%d").date())
            except Exception:
                continue
        if not dates:
            macro_status = "MACRO: due (없음)"
        else:
            latest = max(dates)
            macro_days = (today - latest).days
            if macro_days >= 7:
                macro_status = f"MACRO: due ({latest.isoformat()}, {macro_days}일 경과)"
            else:
                macro_status = f"MACRO: skip ({macro_days}일 경과)"
    emit(macro_status)

    # [1-0] 이중 실행 검사
    double_run_status = "DOUBLE-RUN: unknown"
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%h%x09%ct%x09%s", "origin/main"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parts = proc.stdout.strip().split("\t")
            if len(parts) >= 3:
                short_hash, ct_str, subject = parts[0], parts[1], "\t".join(parts[2:])
                commit_time = datetime.fromtimestamp(int(ct_str), tz=timezone.utc)
                mins_ago = (now - commit_time).total_seconds() / 60.0
                is_content_commit = subject.startswith("content:") or subject.startswith("fix(content):")
                if is_content_commit and mins_ago <= 30:
                    double_run_status = f"DOUBLE-RUN: SKIP (commit {short_hash} \"{subject}\", {mins_ago:.1f}분 전)"
                else:
                    double_run_status = f"DOUBLE-RUN: ok (last commit {short_hash} \"{subject}\", {mins_ago:.1f}분 전)"
    except Exception:
        pass
    emit(double_run_status)
    emit("")

    total_candidates = len(candidates)
    n_sources = len(by_display)
    emit(
        f"요약: 총 후보 {total_candidates}건 / 소스 {n_sources}개 / "
        f"이미 발행 제외 {excluded_already_pub}건 / 창 밖 제외 {excluded_out_of_window}건 / "
        f"파싱 실패 {unparsed_count}건"
    )

    print("\n".join(out_lines))

    if args.json:
        payload = {
            "generated_at": now.isoformat(),
            "hours": args.hours,
            "debut_days": args.debut_days,
            "candidates": candidates,
            "unregistered_feeds": unregistered_feeds,
            "excluded_already_published": excluded_already_pub,
            "excluded_out_of_window": excluded_out_of_window,
            "unparsed_count": unparsed_count,
            "existing_sourceurl_normalize_failures": existing_norm_fail,
            "caps": caps,
            "zero_card_7d_sources": zero_7d,
            "concentration_7d": top5_share(recent7_counts),
            "concentration_14d": top5_share(recent14_counts),
            "macro_status": macro_status,
            "macro_days_elapsed": macro_days,
            "double_run_status": double_run_status,
        }
        try:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[경고] --json 출력 쓰기 실패: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()

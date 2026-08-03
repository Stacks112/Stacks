"""주간 '내 종목' 개인화 푸시 — GitHub Actions에서 실행 (weekly-watch-push.yml).

왜 여기 있나: 이 일을 원래 하던 Cowork 예약 세션(주간 통합 파트 C)은 GitHub에는
닿지만 푸시를 보내는 Cloudflare 워커에는 닿지 못한다(2026-07-28 · 07-30 · 08-03
세 회차 연속 차단: 403 CONNECT tunnel failed / curl exit 56). 그래서 발송을
워커에 닿는 GitHub 러너로 옮긴다. notify_followers.py가 발행 시 푸시를 같은 이유로
릴레이하는 것과 같은 구조다.

보내는 것: 최근 7일 새 글에서 '주인공'으로 등장한 회사별로 한 통씩,
그 회사를 팔로우한 사람(태그 c_<slugTag(key)>)에게만.

매칭 규칙은 notify_followers.item_companies를 그대로 재사용한다. 본문에 이름이
스쳐 지나가는 것만으로는 대상에 넣지 않는다 — 표지 라벨·태그·티커·필자 본인만.
규칙을 여기서 따로 만들면 사이트의 '관련 종목'·발행 푸시와 대상이 갈라진다.

환경변수:
  STACKS_NOTIFY_SECRET  워커 /notify 시크릿 (필수, 저장소 시크릿)
  DRY_RUN=1             실제로 보내지 않고 계산 결과만 출력
  MAX_COMPANIES         상위 몇 개 회사까지 보낼지 (기본 8)
  WINDOW_DAYS           최근 며칠 (기본 7)
  WEEK_END=YYYY-MM-DD   기준일 강제 (기본 오늘 UTC). 재현·백필용.
"""
import datetime as dt
import json
import os
import re
import sys

import notify_followers as nf

SITE = "https://stacksdaily.com/"


def _env_int(name, default):
    try:
        return int(str(os.environ.get(name, "")).strip() or default)
    except ValueError:
        return default


def recent_items(items, end, window):
    """[end-window+1, end] 안에 발행된 글. date는 'YYYY-MM-DD' 문자열이다."""
    start = end - dt.timedelta(days=window - 1)
    out = []
    for it in items:
        d = (it.get("date") or "").strip()
        try:
            day = dt.date.fromisoformat(d[:10])
        except ValueError:
            continue
        if start <= day <= end:
            out.append(it)
    return out


def headline(hits):
    """그 회사의 '가장 주목할 글' 한 줄. hits는 (글, 그 글에서의 순위) 목록.

    순위를 첫 기준으로 쓰는 이유: 그 회사가 주인공인 글을 고르기 위해서다.
    hot·최신만 보면 'APPLE이 5조달러를 넘었다' 글이 NVIDIA 알림의 문구로
    올라오는 일이 생긴다(그 글이 NVIDIA도 태그했을 뿐인데).
    """
    ranked = sorted(hits, key=lambda h: (h[1], 0 if h[0].get("hot") else 1, _neg_date(h[0])))
    for it, _pos in ranked:
        t = ((it.get("title") or {}).get("ko") or "").strip()
        if t:
            return t
    return ""


def _neg_date(it):
    # 최신이 앞으로 오게 (문자열 날짜라 역순 정렬용 키를 따로 만든다)
    return tuple(-int(x) for x in (it.get("date") or "0-0-0")[:10].split("-"))


def label_of(key):
    """알림 제목에 쓸 이름. 핸들은 뺀다 — 잠금화면에서 뒤가 잘린다."""
    return re.sub(r"\s*\(@[^)]+\)\s*$", "", str(key))


def main():
    data = json.load(open("items.json"))
    entities = data.get("entities") or {}

    end_raw = (os.environ.get("WEEK_END") or "").strip()
    end = dt.date.fromisoformat(end_raw) if end_raw else dt.datetime.now(dt.timezone.utc).date()
    window = _env_int("WINDOW_DAYS", 7)
    limit = _env_int("MAX_COMPANIES", 8)
    dry = str(os.environ.get("DRY_RUN", "")).strip().lower() in ("1", "true", "yes")

    recent = recent_items(data.get("items") or [], end, window)
    nf._summary("## 주간 내 종목 푸시")
    nf._summary(
        f"기간 {end - dt.timedelta(days=window - 1)} ~ {end} · 대상 글 {len(recent)}건"
        + (" · **DRY RUN**" if dry else "")
    )

    if not recent:
        print("no items in window; nothing to send")
        nf._summary("이번 주 발행 글 없음 — 발송 없음, 정상.")
        return 0

    by_key = {}
    for it in recent:
        for pos, key in enumerate(nf.item_companies(it, entities)):
            if (entities.get(key) or {}).get("kind") != "company":
                continue  # 필자(person)는 종목 알림 대상이 아니다
            by_key.setdefault(key, []).append((it, pos))

    if not by_key:
        print("no company matched in window; nothing to send")
        nf._summary("이번 주 대상 종목 없음 — 발송 없음, 정상.")
        return 0

    ranked = sorted(by_key.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:limit]
    nf._summary(
        "대상: " + " · ".join(f"{label_of(k)}({len(v)})" for k, v in ranked)
        + (f"  _(상위 {limit}개로 제한, 매칭된 회사 {len(by_key)}개)_"
           if len(by_key) > limit else "")
    )

    failed = []
    for key, its in ranked:
        tag = "c_" + nf.slug_tag(key)
        if len(tag) < 3:
            print(f"skip {key}: empty slug")
            continue
        try:
            nf.send(
                tag,
                f"{label_of(key)} · 이번 주 새 글 {len(its)}건",
                headline(its),
                SITE,
                dry=dry,
            )
        except SystemExit as e:
            # send()는 실패하면 sys.exit한다. 주간 발송은 한 종목이 막혔다고
            # 나머지 일곱을 못 보내면 안 되므로 여기서 잡고 끝까지 돈다.
            print(f"[weekly-watch-push] {tag} failed: {e}")
            failed.append(tag)

    if failed:
        nf._summary(f"❌ 실패 {len(failed)}건: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

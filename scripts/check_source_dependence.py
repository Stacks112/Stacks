#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_source_dependence.py — 카드가 원문의 요약으로만 이루어져 있지 않은지 검사.

발행 루틴 v4.3 [5-C] (2026-07-29 신설, june 지시 "gist가 원문을 대신 읽어버리는 문제").

## 왜 필요한가

카드 안에 있는 내용이 전부 원문에서 온 것이면, 독자는 카드를 읽고 원문을 볼 이유가
없어진다. 문장을 새로 썼는지, 얼마나 짧게 줄였는지는 상관이 없다. 원문 2만 자를 658자로
줄여도 그 658자가 전부 저자의 사실이면 카드는 원문의 부분집합이다.

2026-07-29 실측(원문이 feeds에 남아 있던 39장, claude/status-2026-07-29-source-quote-audit.md
후속): 카드 숫자 중 원문에서 온 것의 비율 중앙값 67%, 9장은 100%였다. 100% 그룹과
20~30% 그룹을 가르는 것은 길이가 아니라 **@@CHK@@(우리가 직접 조회한 수치)와
@@REF@@(교차확인 기사)가 있느냐**였다. 규칙([4-E]②·v4.4 [F])은 이미 있었지만 선택이라
39장 중 33장에 CHK가 없었다.

용어 색인([5-B])과 같은 실패 구조다 — 규칙은 있는데 지켰는지 확인할 방법이 없어 매 회차
샌다. 그래서 판정을 사람 기억이 아니라 종료코드에 맡긴다.

## 무엇을 보는가

**판정의 근거는 "원문 밖에서 가져온 것이 있는가" 하나다.**

  FAIL  @@CHK@@도 @@REF@@도 없다 → 원문 밖에서 가져온 것이 하나도 없다.
  WARN  @@REF@@는 있는데 원문에 없는 숫자가 본문에 하나도 없다
        → 기사를 링크만 하고 본문이 그 내용을 꺼내 쓰지 않았을 수 있다(v4.4 [F] 발췌 의무).
  ok    그 외.

차용률(카드 숫자 중 원문에도 있는 것의 비율)은 **참고 정보로만 찍는다. 판정에 쓰지
않는다.** 원문이 영어인데 카드가 한국어면 단위 표기가 달라져($14.8 billion → 148억 달러)
같은 사실인데도 다른 숫자로 잡히기 때문이다. 숫자 대조는 논지 재현을 재는 대리 지표일 뿐,
정확한 측정이 아니다.

## 원문을 어디서 가져오는가

feeds/*.json이다. 소스당 15건 롤링이라 **발행 시점에만 원문이 있다.** 옛 카드를 소급
검사할 수는 없다(원문을 못 찾으면 SKIP, 실패로 치지 않는다). 같은 이유로 원문 인용
quote도 발행 시점에 뽑아야 한다 — 두 검사가 같은 창에서 같이 돈다.

quote는 원문에서 그대로 따온 것이므로 원문 텍스트로도, 우리 몫으로도 세지 않는다.

사용:
  python3 scripts/check_source_dependence.py --ids id1,id2   # 특정 카드
  python3 scripts/check_source_dependence.py --latest 3       # 최신 3장
  python3 scripts/check_source_dependence.py --allow id1      # 의식적 통과(사유는 [9] 보고에)

종료코드: FAIL이 하나도 없으면 0, 있으면 1. 루틴은 1인 채로 커밋하지 않는다 —
그 카드에 원문 밖 사실을 넣거나(우선), 정말 넣을 수 없으면 발행을 보류한다.
"""
import argparse
import glob
import html
import json
import os
import re
import sys

MARKER_PREFIXES = ("@@IMG@@", "@@REF@@", "@@CHK@@", "@@CMP@@")

# 숫자로 세지 않는 것: 연도, 한 자리 수, 순번처럼 보이는 것.
_YEAR = re.compile(r"^(19|20)\d{2}$")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def strip_tags(t):
    t = re.sub(r"<script.*?</script>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def numbers(text):
    """본문에서 사실로 쓸 만한 숫자만 뽑는다."""
    out = set()
    for m in _NUM.findall(text or ""):
        s = m.strip(".,").replace(",", "")
        if not s or _YEAR.match(s):
            continue
        if len(s.replace(".", "")) < 2:      # 한 자리는 노이즈
            continue
        out.add(s)
    return out


def norm_key(url):
    """중복 판정과 같은 정규화 — 네이버는 글 ID, X는 상태 ID."""
    u = (url or "").split("?")[0].rstrip("/")
    m = re.search(r"/status/(\d+)", u)
    if m:
        return "x:" + m.group(1)
    if "blog.naver.com" in u:
        m = re.search(r"/(\d{6,})", u)
        if m:
            return "naver:" + m.group(1)
    return u


def load_feed_index(root):
    idx = {}
    for path in sorted(glob.glob(os.path.join(root, "feeds", "*.json"))):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        entries = data if isinstance(data, list) else data.get("items", [])
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            k = norm_key(e.get("link"))
            if k:
                idx.setdefault(k, e)
    return idx


def gist_parts(item, lang="ko"):
    """(마커를 뺀 본문, CHK 줄 수, REF 줄 수, CHK/REF 줄 텍스트)"""
    g = item.get("gist") or {}
    text = g.get(lang, "") if isinstance(g, dict) else str(g)
    body, marker_text, chk, ref = [], [], 0, 0
    for line in str(text).split("\n"):
        if line.startswith("@@CHK@@"):
            chk += 1
            marker_text.append(line)
        elif line.startswith("@@REF@@"):
            ref += 1
            marker_text.append(line)
        elif line.startswith(MARKER_PREFIXES):
            marker_text.append(line)
        else:
            body.append(re.sub(r"^##\s*", "", line))
    return "\n".join(body), chk, ref, "\n".join(marker_text)


def source_text(item, feed_idx):
    e = feed_idx.get(norm_key(item.get("sourceUrl")))
    if not e:
        return None
    raw = e.get("content") or e.get("summary") or e.get("title") or ""
    t = strip_tags(str(raw))
    return t if len(t) >= 200 else None


def check(item, feed_idx):
    body, chk, ref, markers = gist_parts(item)
    src = source_text(item, feed_idx)

    # quote.lines is a bare list on older cards and an {en,ko,ja} object on
    # cards written after 2026-07-30 (the quote is translated per reader
    # language now). Either way what we want here is every number the quote
    # carries, in any language, so flatten the object rather than picking one.
    qlines = (item.get("quote") or {}).get("lines") or []
    if isinstance(qlines, dict):
        qlines = [l for v in qlines.values() for l in (v or [])]
    quoted = " ".join(qlines)
    card_nums = (numbers(body) | numbers(markers)) - numbers(quoted)

    if src is None:
        return dict(verdict="SKIP", chk=chk, ref=ref, note="원문을 feeds에서 못 찾음(피드 창 밖)")

    src_nums = numbers(src)
    outside = card_nums - src_nums
    shared = card_nums & src_nums
    borrow = (len(shared) / len(card_nums)) if card_nums else None

    if chk == 0 and ref == 0:
        v, note = "FAIL", "원문 밖에서 가져온 것이 없다 (@@CHK@@ 0, @@REF@@ 0)"
    elif ref and not outside and chk == 0:
        v, note = "WARN", "@@REF@@는 있으나 원문에 없는 숫자가 본문에 0개 — 기사를 소화하지 않았을 수 있다"
    else:
        v, note = "ok", ""
    return dict(verdict=v, chk=chk, ref=ref, note=note, borrow=borrow,
                outside=len(outside), card=len(card_nums), srclen=len(src))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--latest", type=int, default=3)
    ap.add_argument("--allow", default="", help="의식적으로 통과시킬 카드 id(쉼표 구분). 사유는 [9] 보고에 적는다.")
    ap.add_argument("--items", default="items.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    data = json.load(open(args.items, encoding="utf-8"))
    feed_idx = load_feed_index(args.root)
    allow = {i.strip() for i in args.allow.split(",") if i.strip()}

    items = data["items"]
    if args.ids:
        want = {i.strip() for i in args.ids.split(",") if i.strip()}
        targets = [it for it in items if it["id"] in want]
        missing = want - {it["id"] for it in targets}
        for m in sorted(missing):
            print("[??]  %s — items.json에 없는 id" % m)
    else:
        targets = items[: args.latest]

    failed = []
    for it in targets:
        r = check(it, feed_idx)
        v = r["verdict"]
        if v == "FAIL" and it["id"] in allow:
            v = "allow"
        tail = "CHK %d · REF %d" % (r["chk"], r["ref"])
        if r.get("borrow") is not None:
            tail += " · 카드 숫자 %d개 중 원문서 온 것 %.0f%% (참고값)" % (r["card"], r["borrow"] * 100)
        print("[%-4s] %s\n       %s" % (v, it["id"], tail))
        if r["note"]:
            print("       → %s" % r["note"])
        if v == "FAIL":
            failed.append(it["id"])

    if failed:
        print("\n%d장이 원문 요약으로만 이루어져 있다: %s" % (len(failed), ", ".join(failed)))
        print("원문 밖 사실을 하나 넣는다 — 직접 조회한 수치(@@CHK@@)든, 교차확인 기사에서")
        print("꺼낸 사실(@@REF@@ + 본문 발췌)이든. 넣을 수 없으면 그 카드는 이번 회차에 내지 않는다.")
        sys.exit(1)
    print("\n원문 의존도 이상 없음.")
    sys.exit(0)


if __name__ == "__main__":
    main()

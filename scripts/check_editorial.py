#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
편집 규칙 검사 — publish-v4.6-editorial.md 의 게이트.

`items.json` 의 카드를 읽어 에디토리얼 가이드(2026-08-04)가 정한 다섯 층을 검사한다.
제목 틀 / 섹션 헤딩 / 분량·문단 / 문장 종결 / 반복. 규칙만 있고 지켰는지 확인할 방법이
없어 매 회차 새던 구조를 종료코드에 맡긴다 — check_term_coverage.py 와 같은 자리다.

사용:
  python3 scripts/check_editorial.py --ids id1,id2
  python3 scripts/check_editorial.py --ids id1 --warn-only     # 롤아웃 기간
  python3 scripts/check_editorial.py --weekly                  # 주간 목록 규칙만

종료코드: BLOCK 이 하나라도 있으면 1, 아니면 0. --warn-only 면 항상 0.
"""
import sys, os, re, json, argparse
from collections import Counter

BLOCK, WARN = "BLOCK", "WARN"
MARKER = re.compile(r"^@@(REF|IMG|CHK|CMP|BAR|SHARE|TIME|FLOW)@@")
# 그래픽 어휘. REF·IMG는 출처·사진이라 여기 넣지 않는다 (v4.7).
GRAPHIC = ("CHK", "CMP", "BAR", "SHARE", "TIME", "FLOW")

# ── gist 파싱 ─────────────────────────────────────────────────────────
def parse_gist(g):
    """마커 줄을 걷어내고 헤딩과 문단만 남긴다."""
    heads, paras, buf = [], [], []
    for raw in (g or "").split("\n"):
        ln = raw.strip()
        if MARKER.match(ln):
            if buf: paras.append(" ".join(buf)); buf = []
            continue
        if ln.startswith("## "):
            if buf: paras.append(" ".join(buf)); buf = []
            heads.append(ln[3:].strip()); continue
        if not ln:
            if buf: paras.append(" ".join(buf)); buf = []
            continue
        buf.append(ln)
    if buf: paras.append(" ".join(buf))
    return heads, paras

def blocks_of(g):
    """카드가 쓴 그래픽 블록의 종류별 개수."""
    c = Counter()
    for raw in (g or "").split("\n"):
        m = MARKER.match(raw.strip())
        if m and m.group(1) in GRAPHIC:
            c[m.group(1)] += 1
    return c

def sentences(p):
    return [x for x in re.split(r"(?<=다)\s+|(?<=[.!?])\s+", p) if x.strip()]

def lang_text(v, lang="ko"):
    if isinstance(v, str): return v if lang == "ko" else ""
    if isinstance(v, dict): return v.get(lang) or ""
    return ""

# ── 개별 규칙 ─────────────────────────────────────────────────────────
CLICHE = re.compile(r"(결국|남는) 질문은 하나(다|입니다)")
GEOSI  = re.compile(r"것이 된다|것으로 된다|뜻이 된다|숫자가 된다")
QHEAD  = re.compile(r"(나|가|까|는가|을까|ㄹ까)\s*\??$")
GENERIC_LAST = ["그래서 무엇으로 가릴까", "그래서 무엇을 볼까", "무엇으로 가릴까",
                "무엇을 보게 되나", "남는 질문", "그래서 무엇이 갈리나"]
NUM = re.compile(r"[0-9][0-9,\.]*\s*(조원|억원|만원|원|조달러|억달러|만달러|달러|%|엔|포인트|배|개|명)")

def check_card(item, corpus_heads=None):
    out = []
    gist = lang_text(item.get("gist"))
    heads, paras = parse_gist(gist)
    sum3 = lang_text(item.get("sum3"))
    title = lang_text(item.get("title"))
    body = " ".join(paras)

    n = len(CLICHE.findall(body))
    if n:
        out.append((BLOCK, "1", "「결국 질문은 하나다」 계열 %d회 — 다음 문단이 같은 이분법을 더 구체적으로 말한다. 삭제." % n))

    n = len(GEOSI.findall(body + " " + sum3))
    if n >= 2:
        out.append((BLOCK, "2", "「~것이 된다」 계열 종결 %d회. 최대 1회." % n))

    if heads:
        last = heads[-1]
        if any(g in last for g in GENERIC_LAST):
            out.append((BLOCK, "3", "마지막 섹션 헤딩 「%s」은 어느 글에나 붙는다. 이 글 전용으로." % last))
        elif corpus_heads and last in corpus_heads:
            out.append((WARN, "3", "마지막 섹션 헤딩 「%s」이 최근 발행분에 이미 쓰였다." % last))

    qs = [h for h in heads if h.endswith("?") or QHEAD.search(h)]
    if len(qs) >= 2:
        out.append((BLOCK, "4", "의문형 섹션 헤딩 %d개: %s. 최대 1개." % (len(qs), " · ".join(qs))))

    toks = [m.group(0).replace(" ", "") for m in NUM.finditer(" ".join([title, body, sum3]))]
    over = [(t, c) for t, c in Counter(toks).items() if c >= 3]
    if over:
        s = ", ".join("%s×%d" % (t, c) for t, c in sorted(over, key=lambda x: -x[1])[:5])
        out.append((WARN, "5", "같은 수치 3회 이상: %s. 리드에서 던졌으면 요약에서 회수하고 중간 재진술은 뺀다." % s))

    if sum3 and paras:
        lead = " ".join(paras[:2])
        L = _sh(lead)
        worst, which = 0.0, ""
        for li in [x for x in sum3.split("\n") if x.strip()]:
            S = _sh(li)
            if not S or not L: continue
            ov = len(S & L) / len(S)
            if ov > worst: worst, which = ov, li
        if worst >= 0.45:
            out.append((WARN, "6", "세 줄 요약이 리드를 재진술한다(중복 %.0f%%): 「%s…」" % (worst*100, which[:34])))

    ns = [len(sentences(p)) for p in paras if p]
    if len(ns) >= 6 and all(2 <= x <= 3 for x in ns):
        out.append((WARN, "7", "문단이 전부 2~3문장(%d문단). 1문장 문단과 5문장 문단을 섞는다." % len(ns)))

    txt = body + " " + sum3
    msgs = []
    big = re.findall(r"[0-9]{4,}(?:조원|억원|억달러|조달러)", txt)
    comma = re.findall(r"[0-9]{1,3}(?:,[0-9]{3})+(?:조원|억원|억달러|조달러)", txt)
    if big and comma:
        msgs.append("천 단위 쉼표 혼용(%s vs %s)" % (big[0], comma[0]))
    pct = re.findall(r"[0-9]+\.[0-9]{2,}%(?!\s*포인트)", txt)
    if pct:
        msgs.append("퍼센트 소수 둘째 자리 이상: %s" % ", ".join(pct[:3]))
    if msgs:
        out.append((BLOCK, "9", " / ".join(msgs)))

    # v4.7 (2026-08-04): 한 카드가 같은 형태를 두 번 쓰면 그 형태가 재료 때문에
    # 골라진 것이지 독자가 막히는 지점 때문에 골라진 것이 아니다.
    bl = blocks_of(gist)
    dup = [k for k, c in bl.items() if c >= 2]
    if dup:
        out.append((WARN, "13", "같은 그래픽을 한 카드에서 여러 번 썼다: %s. 형태는 독자가 "
                    "막히는 지점마다 다르게 고른다." % ", ".join("@@%s@@×%d" % (k, bl[k]) for k in dup)))

    # 새 필드(2026-08-04): 판별 조건은 본문이 아니라 채점 카드로, 출처는 글 끝 목록으로
    oc = item.get("outcome") or {}
    if oc.get("status") and not oc.get("card"):
        out.append((WARN, "11", "outcome 이 있는데 outcome.card(지표·현재·채점일·맞음·틀림)가 없다."))
    if not item.get("sources"):
        out.append((WARN, "12", "sources 목록이 없다. 본문은 문장 안 귀속, 링크는 글 끝 목록으로."))

    return out

def _sh(s, n=6):
    s = re.sub(r"[^0-9A-Za-z가-힣%]", "", s or "")
    return {s[i:i+n] for i in range(max(0, len(s)-n+1))}

# ── 주간 목록 규칙 ────────────────────────────────────────────────────
FORMS = [("B 의문형", re.compile(r"(뭘까|일까|까)\s*\??$")),
         ("F 부정형", re.compile(r"(아니다|아니었다)\s*$")),
         ("E 나열형", re.compile(r"^[^,]+,\s*[^,]+,\s*[^,]+$")),
         ("A 반전형", re.compile(r"^.+[다요],\s*.+"))]
def title_form(t):
    for name, rx in FORMS:
        if rx.search(t or ""): return name
    return "C/D 단정·장면형"

# 쿼터는 편수가 아니라 비율이다 (2026-08-04 실측 교정).
# 최초안은 "같은 틀 최대 3편"이었는데, 최근 7일 발행이 63편이라 여섯 틀을 아무리 고르게
# 돌려도 전부 걸린다. 실측 분포는 C/D 37% · B 30% · F 19% · A 11% · E 3% · 물음표 41%.
# "두 틀이 100%를 덮는다"가 진단이었으므로 판정선은 편수가 아니라 편중률에 둔다.
SHARE_CAP  = 0.40   # 한 틀이 이 비율을 넘으면 편중
SHARE_CD   = 0.55   # C/D는 단정형·장면형 두 틀이 합쳐진 칸이라 따로 본다
QMARK_CAP  = 0.45   # 물음표 제목 비율 (메르 원문 표본은 50%)

# 그래픽 편중 상한 (v4.7, 2026-08-04 신설). 제목 틀과 같은 원리다 — 세지 않고
# 고르면 반드시 손에 익은 것으로 돌아간다. 실측: 최근 20장에서 @@CHK@@ 80% ·
# @@CMP@@ 50% · 둘 다 40%. 전체 평균은 24.6% · 31.5%였으니 최근에 쏠린 것이다.
BLOCK_CAP  = {"CHK": 0.55, "CMP": 0.40}
BLOCK_CAP_DEFAULT = 0.45
MIN_N      = 8      # 표본이 이보다 적으면 비율을 보지 않는다

def weekly(items, days=7):
    import datetime as dt
    today = dt.date.today()
    recent = []
    for i in items:
        try:
            d = dt.date.fromisoformat(str(i.get("date"))[:10])
        except Exception:
            continue
        if 0 <= (today - d).days <= days:
            recent.append(i)
    out = []
    n = len(recent)
    if n < MIN_N:
        return out, n
    forms = Counter(title_form(lang_text(i.get("title"))) for i in recent)
    for name, c in forms.most_common():
        cap = SHARE_CD if name.startswith("C/D") else SHARE_CAP
        if c / n >= cap:
            out.append((WARN, "W1", "최근 %d일 제목 틀 '%s' %d/%d편(%.0f%%). 상한 %.0f%%. "
                        "다음 회차는 다른 틀에서 고른다." % (days, name, c, n, 100*c/n, 100*cap)))
    qn = sum(1 for i in recent if lang_text(i.get("title")).rstrip().endswith("?"))
    if qn / n >= QMARK_CAP:
        out.append((WARN, "W2", "최근 %d일 물음표 제목 %d/%d편(%.0f%%). 상한 %.0f%%."
                    % (days, qn, n, 100*qn/n, 100*QMARK_CAP)))
    # ⚠ W0(제목 틀 분포)은 **제목 규칙에 걸린 것이 없을 때만** 찍는다. 아래 그래픽
    # 편중(W3)까지 센 뒤에 `if not out` 으로 판정하면, 그래픽이 상한을 넘긴 동안에는
    # 제목 분포가 통째로 사라진다. v4.7 첫 실전 회차(2026-08-04 09:4xZ)가 실제로 이걸
    # 밟아서 루틴이 제목 틀을 손으로 세야 했다. 그래서 여기서 미리 끊어 둔다.
    title_ok = not out

    # 그래픽 편중 (v4.7)
    bcount = Counter()
    for i in recent:
        for k in blocks_of(lang_text(i.get("gist"))):
            bcount[k] += 1
    for name, c in bcount.most_common():
        cap = BLOCK_CAP.get(name, BLOCK_CAP_DEFAULT)
        if c / n >= cap:
            out.append((WARN, "W3", "최근 %d일 @@%s@@ %d/%d편(%.0f%%). 상한 %.0f%%. "
                        "다음 회차는 다른 형태에서 고른다 — 규모는 @@BAR@@, 비중은 "
                        "@@SHARE@@, 순서는 @@TIME@@, 경로는 @@FLOW@@."
                        % (days, name, c, n, 100*c/n, 100*cap)))
    if title_ok:
        top = forms.most_common(3)
        out.append(("INFO", "W0", "분포 " + " · ".join("%s %.0f%%" % (k, 100*v/n) for k, v in top)
                    + " · 물음표 %.0f%%" % (100*qn/n)))
    out.append(("INFO", "W4", "그래픽 " + (" · ".join("%s %.0f%%" % (k, 100*v/n)
                for k, v in bcount.most_common()) or "0편")))
    return out, n

# ── 회차 상한 (v4.6 [X], 2026-08-04) ─────────────────────────────────
# 후보 10~20건에 칸이 2개뿐이라 품질 순으로 자르면 롱폼 1차 분석이 매번 이겼다.
# 최근 7일 주칸 38% · 메르 19%. 칸을 늘리고 한 필진에 상한을 건다.
#
# 숫자는 여기가 아니라 sources.json 의 "_CAPS" 가 정한다 — 소스 추가·상한 변경을
# 레지스트리 한 곳에서 끝내기 위해서다. 아래 값은 sources.json 을 못 읽을 때의 대비책이다.
FALLBACK_CAPS = {"total": 6, "default_per_source": 2, "per_source": {}, "per_category": {}}
MACRO_PREFIX  = "macro-week-"   # 주간 매크로 카드는 이 한도 밖 ([3-B])

def load_caps(path="sources.json"):
    try:
        raw = json.load(open(path, encoding="utf-8"))
        c = raw.get("_CAPS") or {}
        return {"total": c.get("total", FALLBACK_CAPS["total"]),
                "default_per_source": c.get("default_per_source",
                                            FALLBACK_CAPS["default_per_source"]),
                "per_source": c.get("per_source") or {},
                "per_category": c.get("per_category") or {},
                "loaded": bool(c)}
    except Exception:
        d = dict(FALLBACK_CAPS); d["loaded"] = False
        return d

def round_caps(items_sel, caps=None):
    caps = caps or load_caps()
    out = []
    counted = [i for i in items_sel if not str(i.get("id", "")).startswith(MACRO_PREFIX)]
    per = Counter(i.get("source") or "?" for i in counted)
    percat = Counter(i.get("category") or "?" for i in counted)

    # 같은 저자를 두 경로로 수집하는 kuo/kuo_x·bilello/bilello_x 는 표시명이 같아
    # 여기서 자동으로 합산된다. feed_id로 세면 짝이 갈려 상한이 두 배가 된다.
    for name, c in per.most_common():
        cap = caps["per_source"].get(name, caps["default_per_source"])
        if c > cap:
            out.append((BLOCK, "R1", "같은 필진 '%s' %d건. 한 회차 최대 %d건 — 남는 칸은 "
                        "다른 필진에게 준다." % (name, c, cap)))
    for cat, c in percat.most_common():
        cap = caps["per_category"].get(cat)
        if cap is not None and c > cap:
            out.append((BLOCK, "R3", "'%s' 카테고리 %d건. 카테고리 합계 최대 %d건."
                        % (cat, c, cap)))
    # 이번 회차 카드들이 전부 같은 형태 조합이면, 형태가 사안이 아니라 습관에서
    # 나온 것이다 (v4.7).
    sigs = [tuple(sorted(blocks_of(lang_text(i.get("gist"))))) for i in items_sel]
    if len(sigs) >= 2 and len(set(sigs)) == 1 and sigs[0]:
        out.append((WARN, "R4", "이번 회차 %d장이 모두 같은 그래픽 조합(%s)이다. 사안이 다르면 "
                    "형태도 달라야 한다." % (len(sigs), " + ".join("@@%s@@" % x for x in sigs[0]))))

    if len(counted) > caps["total"]:
        out.append((BLOCK, "R2", "회차 발행 %d건. 최대 %d건." % (len(counted), caps["total"])))
    if not out:
        out.append(("INFO", "R0", "%d건 · 필진 %s"
                    % (len(counted), " · ".join("%s %d" % (k, v) for k, v in per.most_common()))))
    if not caps.get("loaded"):
        out.append((WARN, "R9", "sources.json 의 _CAPS 를 읽지 못해 기본값으로 판정했다. "
                                "소스별 상한(코베이시 1 · 궈밍치 1 · 빌렐로 1 · politician 1)이 "
                                "적용되지 않았다."))
    return out

# ── main ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--items", default="items.json")
    ap.add_argument("--warn-only", action="store_true")
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--round", action="store_true",
                    help="sources.json 의 _CAPS(회차 총량·필진별·카테고리별 상한)까지 검사. "
                         "신규 발행 회차에는 반드시 붙인다.")
    ap.add_argument("--sources", default="sources.json",
                    help="_CAPS 를 읽을 레지스트리 경로 (기본 sources.json)")
    a = ap.parse_args()

    if not os.path.exists(a.items):
        print("items.json 을 찾을 수 없습니다: %s" % a.items); sys.exit(2)
    doc = json.load(open(a.items, encoding="utf-8"))
    items = doc.get("items") or []
    by = {i.get("id"): i for i in items}

    # 최근 30편의 마지막 헤딩 사전 — 마지막 절 제목 재사용 감시
    corpus = set()
    for i in items[:30]:
        h, _ = parse_gist(lang_text(i.get("gist")))
        if h: corpus.add(h[-1])

    ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    hard = 0
    for iid in ids:
        it = by.get(iid)
        print("\n■ %s" % iid)
        if not it:
            print("   [BLOCK] items.json 에 없는 id"); hard += 1; continue
        h, p = parse_gist(lang_text(it.get("gist")))
        print("   섹션 %d · 문단 %d" % (len(h), len(p)))
        res = check_card(it, corpus - ({h[-1]} if h else set()))
        if not res:
            print("   ok")
        for lv, num, msg in res:
            print("   [%s] #%s %s" % (lv, num, msg))
            if lv == BLOCK: hard += 1

    if a.round and ids:
        sel = [by[i] for i in ids if i in by]
        caps = load_caps(a.sources)
        print("\n■ 회차 상한 (v4.6 [X] · sources.json _CAPS)")
        for lv, num, msg in round_caps(sel, caps):
            print("   [%s] %s %s" % (lv, num, msg))
            if lv == BLOCK: hard += 1

    if a.weekly or not ids:
        wr, n = weekly(items)
        print("\n■ 주간 목록 (최근 7일 %d편)" % n)
        if not wr: print("   ok")
        for lv, num, msg in wr:
            print("   [%s] %s %s" % (lv, num, msg))

    print("\nBLOCK %d 건" % hard)
    sys.exit(0 if (a.warn_only or hard == 0) else 1)

if __name__ == "__main__":
    main()

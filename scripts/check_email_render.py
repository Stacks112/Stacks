"""주간 메일이 깨진 채로 나가는 것을 막는 검사기.

왜 있나 (2026-08-03):
카드 본문(gist)에는 블록 마커가 섞여 있는데(`## 소제목` · `@@REF@@` · `@@IMG@@` ·
`@@CHK@@` · `@@CMP@@`) 렌더러가 **세 곳**에 따로 있다:

  1. 앱          index.html            (JS, `L.indexOf("@@XXX@@") === 0`)
  2. 정적 페이지 scripts/build_pages.py (`line.startswith("@@XXX@@")`)
  3. 이메일      scripts/weekly_email.py (`_BLOCKS`)

2026-07-24에 이메일이 `why`만 싣던 것에서 gist 전문을 싣도록 바뀌었는데 3번에만
마커 처리가 없었다. 그래서 수신함에

    @@REF@@6월 물가 0.1% 하락 …|https://www.upi.com/…|https://cdnph.upi.com/…

가 문장 한가운데 그대로 찍혔다. 발견까지 열흘이 걸린 이유는 그 사이 워커 호스트가
죽어 메일이 아예 안 나가고 있었기 때문이다. 아무도 볼 기회가 없었다.

이 검사기가 막는 것:
  A. **렌더러 표류** — 세 렌더러가 처리하는 마커 집합이 다르면 실패.
     한 곳에 마커를 새로 추가하고 다른 곳을 잊는 게 이 사고의 정확한 형태였다.
  B. **미처리 마커** — items.json이 실제로 쓰는 마커를 렌더러가 모르면 실패.
  C. **결과물 오염** — 실제로 렌더한 이메일 HTML에 마커 잔재·본문에 노출된 날것
     URL·상대경로 이미지가 있으면 실패. 규칙이 아니라 산출물을 본다.

실행:
    python scripts/check_email_render.py          # 저장소 루트에서
종료 코드 0 = 통과. 1 = 실패(사유를 전부 출력한다).

이 검사는 `stacks-weekly.yml`의 발송 **직전**에 돈다. 깨졌으면 메일이 아예 나가지
않는다 — 잘못 나간 메일은 회수할 수 없기 때문이다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

MARKER_RX = re.compile(r"^@@([A-Z0-9]+)@@")

problems = []
notes = []


def fail(msg):
    problems.append(msg)


def note(msg):
    notes.append(msg)


# ---------------------------------------------------------------- A. 렌더러 표류

def markers_in_app():
    src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    return set(re.findall(r'indexOf\("@@([A-Z0-9]+)@@"\)', src))


def markers_in_pages():
    src = open(os.path.join(HERE, "build_pages.py"), encoding="utf-8").read()
    return set(re.findall(r'startswith\("@@([A-Z0-9]+)@@"\)', src))


def markers_in_email():
    import weekly_email
    return set(m.strip("@") for m, _fn in weekly_email._BLOCKS)


def check_renderers_agree():
    app, pages, email = markers_in_app(), markers_in_pages(), markers_in_email()
    note("마커 처리: 앱 %s · 정적페이지 %s · 이메일 %s"
         % (sorted(app), sorted(pages), sorted(email)))
    if not (app and pages and email):
        fail("렌더러 중 하나에서 마커를 하나도 못 찾았다 — 정규식이 코드 변경을 못 따라간 것일 수 있다. "
             "check_email_render.py의 markers_in_* 를 확인할 것.")
        return
    for a, b, an, bn in ((app, email, "앱", "이메일"),
                         (pages, email, "정적페이지", "이메일"),
                         (app, pages, "앱", "정적페이지")):
        only_a, only_b = sorted(a - b), sorted(b - a)
        if only_a or only_b:
            fail("렌더러 표류: %s에만 %s / %s에만 %s. 마커를 추가·삭제할 때는 "
                 "index.html · build_pages.py · weekly_email.py 세 곳을 같이 고친다."
                 % (an, only_a or "없음", bn, only_b or "없음"))


# ------------------------------------------------------- B. items.json이 쓰는 마커

def load_items():
    path = os.environ.get("ITEMS_PATH", os.path.join(ROOT, "items.json"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_all_used_markers_handled(data):
    used = {}
    for it in data.get("items", []):
        for fld in ("gist", "why"):
            v = it.get(fld)
            texts = v.values() if isinstance(v, dict) else [v]
            for t in texts:
                for line in str(t or "").split("\n"):
                    m = MARKER_RX.match(line)
                    if m:
                        used.setdefault(m.group(1), it.get("id", "?"))
    note("items.json이 쓰는 마커: %s" % (sorted(used) or "없음"))
    handled = markers_in_email()
    for name, first_id in sorted(used.items()):
        if name not in handled:
            fail("이메일 렌더러가 모르는 마커 @@%s@@ 가 카드에 쓰이고 있다 (예: %s). "
                 "그대로 두면 수신함에 마커 원문이 찍힌다." % (name, first_id))


# ------------------------------------------------------------- C. 렌더 결과 검사

# 본문에 노출된 날것 URL을 찾는다. 태그 속성(href/src) 안의 URL은 정상이므로
# 태그를 전부 걷어낸 '보이는 텍스트'만 본다.
TAG_RX = re.compile(r"<[^>]+>")
VISIBLE_URL_RX = re.compile(r"https?://")


def visible_text(html_str):
    return TAG_RX.sub(" ", html_str)


def check_rendered(data, langs=("ko", "en", "ja"), sample=8):
    import weekly_email as we

    items = data.get("items", [])
    entities = data.get("entities", {}) or {}
    glossary = {}
    gpath = os.path.join(ROOT, "glossary.json")
    if os.path.exists(gpath):
        try:
            glossary = json.load(open(gpath, encoding="utf-8"))
        except Exception:
            glossary = {}

    # 마커를 실제로 쓰는 카드를 우선 고른다. 마커 없는 카드만 렌더하면
    # 이 검사는 아무것도 못 잡는다.
    def marker_count(it):
        v = it.get("gist")
        texts = v.values() if isinstance(v, dict) else [v]
        return sum(1 for t in texts for line in str(t or "").split("\n")
                   if MARKER_RX.match(line))

    picks = sorted(items, key=lambda it: (-marker_count(it), it.get("date", "")))[:sample]
    if not picks:
        fail("렌더할 카드가 없다 (items.json이 비었나?)")
        return
    note("렌더 검사 대상 %d건: %s" % (len(picks), ", ".join(i.get("id", "?") for i in picks)))

    for lang in langs:
        try:
            ctx = we.enrich(picks, entities, glossary, {}, lambda _t: None, lang=lang)
            html_str = we.render_email(lang, ctx, "https://stacksdaily.com")
        except Exception as e:  # noqa: BLE001
            fail("[%s] 렌더 자체가 실패했다: %r" % (lang, e))
            continue

        left = re.findall(r"@@[A-Z0-9]*@@?", html_str)
        if left:
            fail("[%s] 렌더 결과에 마커 잔재 %d건: %s"
                 % (lang, len(left), sorted(set(left))[:5]))

        vis = visible_text(html_str)
        if VISIBLE_URL_RX.search(vis):
            around = VISIBLE_URL_RX.search(vis)
            fail("[%s] 본문에 날것 URL이 노출됐다: …%s…"
                 % (lang, vis[max(0, around.start() - 40):around.start() + 60].strip()))

        for src in re.findall(r'<img[^>]+src="([^"]*)"', html_str):
            if not src.startswith(("https://", "data:")):
                fail("[%s] 이메일 이미지가 절대 https 경로가 아니다: %r "
                     "(메일 클라이언트는 상대 경로를 못 푼다)" % (lang, src))

        for stray in re.findall(r"\{\{[a-zA-Z_]+\}\}", html_str):
            if stray != "{{unsubscribe}}":
                fail("[%s] 치환되지 않은 템플릿 자리표시자: %s" % (lang, stray))

        if "<img" not in html_str:
            fail("[%s] 이미지가 한 장도 없다 — OG 카드 삽입이 빠졌을 수 있다." % lang)


def main():
    data = load_items()
    check_renderers_agree()
    check_all_used_markers_handled(data)
    check_rendered(data)

    for n in notes:
        print("  · " + n)
    if problems:
        print("\n❌ 주간 메일 렌더 검사 실패 %d건" % len(problems))
        for p in problems:
            print("   - " + p)
            if os.environ.get("GITHUB_ACTIONS"):
                print("::error::weekly email render: " + p.replace("\n", " "))
        return 1
    print("\n✅ 주간 메일 렌더 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())

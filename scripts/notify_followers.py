"""Follower push relay — runs in GitHub Actions (notify-followers.yml).

Why this exists: the cloud sandbox that auto-publishes articles can reach
GitHub but not the Cloudflare Worker that sends OneSignal pushes. So the
publisher just commits items.json, and this script (running on a GitHub
runner, which CAN reach the Worker) diffs the pushed commit against the
previous one, finds newly added items that belong to a series, and sends
one follower push per new item.

The same sandbox limitation applies to PREDICTION GRADING (2026-08-04): the
scheduled Cowork session grades outcome.status pending -> hit/miss and commits
items.json, but its `[5]` push step can never work -- the egress proxy 403s
api.stacksdaily.com at CONNECT, so nothing was ever sent. grade.py's docstring
already assumed "the workflow that watches items.json notifies", but this
relay only ever looked for NEW item ids, and grading only EDITS existing ones,
so every graded run landed on "no new item ids in this push". That gap is now
closed here (see newly_graded), and grade.yml sets GRADE_PUSH=0 so the two
paths cannot double-send.

Modes:
- push event: diff BEFORE_SHA..HEAD items.json, auto-send for new series items
  and for predictions that were just graded.
- workflow_dispatch: send exactly one push from the provided inputs
  (tag/title/msg/url), with an optional dry-run flag for testing.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# The worker's canonical host is the custom domain in worker/wrangler.toml
# (routes = api.stacksdaily.com). The old *.workers.dev hostname no longer
# routes: POSTs to it come back as Cloudflare "HTTP 404 - error code: 1042",
# which is what silently killed every follower push (Notify followers #144,
# #146, #147 all red; the green runs were no-op pushes with no new items).
# Probed 2026-08-03 from the live site:
#   api.stacksdaily.com/notify      -> 403 {"error":"forbidden"}  (worker reached)
#   stacks-comments.*.workers.dev/  -> connection fails outright
# Keep this pointing at the custom domain. If the host ever moves again, change
# it in wrangler.toml first, then here.
ENDPOINT = "https://api.stacksdaily.com/notify"


def _no_recipients(body):
    """OneSignal은 태그에 구독자가 하나도 없으면 non-2xx(예: "All included
    players are not subscribed")를 반환하고, 워커는 이를 sent:false + HTTP 502로
    돌려준다. 이는 앱에 아직 그 태그 팔로워가 없다는 정상 상태(no-op)이지
    릴레이 실패가 아니므로 run을 Failure로 만들지 않는다."""
    b = (body or "").lower().replace(" ", "")
    return ("allincludedplayersarenotsubscribed" in b
            or '"recipients":0' in b
            or "noneofthemapped" in b        # OneSignal 변형 문구 방어
            or "nosubscribers" in b)


def _summary(line):
    """Append a line to the GitHub Actions job summary (visible on the run
    page without needing to open raw logs — those require sign-in for a
    private repo, which the cloud-sandbox publisher session cannot do)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


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

MAX_ENT_PER_ITEM = 2   # 한 글이 여러 종목을 언급해도 팔로워당 알림은 최대 2개
MAX_ENT_PER_RUN = 6    # 한 번의 푸시(커밋)에서 보내는 종목 알림 총량 상한


def slug_tag(k):
    """index.html의 slugTag()와 반드시 같은 결과를 내야 한다.
    앱은 관심 종목을 켤 때 OneSignal 태그 `c_<slugTag(key)>`를 붙인다.
    여기서 한 글자라도 다르게 만들면 푸시가 아무에게도 안 간다(조용한 실패).
    JS: String(k).toLowerCase().replace(/[^a-z0-9가-힣]+/g,"_").replace(/^_+|_+$/g,"")
    """
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9가-힣]+", "_", str(k).lower()))


def _matcher(entities):
    """build_pages의 별칭 매처를 재사용한다 (규칙이 갈라지면 사이트에 보이는
    '관련 종목'과 푸시 대상이 어긋난다)."""
    import build_pages
    return build_pages, build_pages.build_matcher(entities)


def item_companies(it, entities, cache={}):
    """이 글의 '주인공'인 팔로우 가능한 엔티티(company/person)를 중요도 순으로.

    본문에 이름이 스쳐 지나가는 것만으로는 알림을 보내지 않는다. 표지 라벨과
    태그(발행 시 사람이 고른 것), 그리고 필자 본인만 대상으로 한다. 예를 들어
    S&P 급락 글이 본문에서 인텔을 한 번 언급했다고 인텔 팔로워 폰을 울리면
    그 사람은 다음 알림을 끈다.
    """
    if not entities:
        return []
    if "m" not in cache:
        try:
            cache["m"] = _matcher(entities)
        except Exception as e:
            print(f"[watch-push] matcher unavailable: {e}")
            cache["m"] = None
    if not cache["m"]:
        return []
    _bp, pats = cache["m"]
    cover = (it.get("cover") or {}).get("label") or ""
    tags = it.get("tags") or []
    hay = cover + " · " + " · ".join(tags)
    # 태그는 보통 티커로 달린다(INTC, GOOGL). 티커는 별칭 목록에 없으므로
    # entities[key]["ticker"]("intc.us")의 앞부분을 따로 맞춰본다.
    up = [t.strip().upper() for t in tags] + [cover.strip().upper()]
    by_ticker = {}
    for key, e in entities.items():
        if (e or {}).get("kind") not in ("company", "person"):
            continue
        tk = (e or {}).get("ticker", "").split(".")[0].strip().upper()
        if len(tk) >= 2:
            by_ticker.setdefault(tk, []).append(key)
    hits, seen = {}, set()
    for tk, keys in by_ticker.items():
        if tk not in up:
            continue
        if len(keys) > 1:  # googl.us를 GOOGLE과 DEEPMIND가 같이 쓰는 식의 충돌
            keys = [k for k in keys if k.upper().startswith(tk) or tk.startswith(k.upper())]
        if len(keys) == 1:
            seen.add(keys[0])
            # 순위는 별칭 매칭과 같은 자 단위 위치로 매긴다 (섞이면 정렬이 뒤집힌다)
            pos = hay.upper().find(tk)
            hits[keys[0]] = pos if pos >= 0 else len(hay)
    for rx, key in pats:
        if key in seen or (entities.get(key) or {}).get("kind") not in ("company", "person"):
            continue
        m = rx.search(hay)
        if m:
            seen.add(key)
            hits[key] = m.start()
    # 발행자가 태그를 적은 순서를 그대로 우선순위로 쓴다 (첫 태그가 주인공).
    picked = sorted(hits, key=lambda k: (hits[k], k))
    src = it.get("source")
    if src in entities and src not in seen \
            and (entities[src] or {}).get("kind") in ("company", "person"):
        picked.append(src)  # 필자 본인은 항상 맨 뒤 (종목 알림 자리를 뺏지 않게)
    return picked


def item_themes(it):
    g = it.get("gist") or {}
    hay = " ".join([(it.get("title") or {}).get(l, "") or "" for l in ("en", "ko", "ja")]
                   + [g.get("en", "") or ""] + [" ".join(it.get("tags") or [])])
    return [(k, v[0]) for k, v in THEMES.items() if re.search(v[2], hay, v[1])]


# --- 예측 채점 푸시 -------------------------------------------------------
# 태그는 grade.py 의 notify() 와 같은 "daily" 를 쓴다. 채점 결과는 특정 시리즈나
# 종목이 아니라 "이 사이트가 과거에 한 예측이 맞았나"에 대한 것이라 구독 축이
# 다르다. 문구도 grade.py 와 같은 형태로 맞춰 둔다 (한쪽만 바뀌면 사용자 눈에는
# 같은 알림이 두 종류로 보인다).
GRADE_TAG = "daily"
GRADE_TITLE = "🎯 예측 채점"
# 한 커밋에서 보내는 채점 알림 상한. 밀린 due 가 한꺼번에 풀리면 열 건 넘게
# 확정될 수 있는데, 그걸 다 보내면 알림이 아니라 소음이다. 넘친 건은 조용히
# 버리지 말고 잡 요약에 남긴다.
MAX_GRADED_PER_RUN = 3


def newly_graded(old_items, new_doc, skip_ids=()):
    """이번 push 에서 pending -> hit/miss 로 확정된 예측들.

    `outcome.status` 의 전이만 본다. 채점 실행은 확정 말고도 due 연기·due 백필로
    같은 파일의 수십 개 항목을 건드리는데(2026-08-04 실행은 22건 수정 중 확정은
    3건뿐이었다), 그건 알림 대상이 아니다. gradedOn 날짜를 보지 않고 전이를 보는
    이유: 전이는 항목당 한 번뿐이라 재실행·되돌림에도 중복 발송이 안 생긴다.

    miss 를 먼저 돌려준다. 상한에 걸려 잘려나갈 때 남길 가치가 큰 쪽이 빗나감
    쪽이라서다 — 맞은 것만 알리는 채점은 아무도 안 믿는다.
    """
    out = []
    for it in new_doc.get("items", []):
        iid = it.get("id")
        if not iid or iid in skip_ids:
            continue
        oc = it.get("outcome")
        if not isinstance(oc, dict) or oc.get("status") not in ("hit", "miss"):
            continue
        prev = old_items.get(iid)
        if prev is None:
            continue          # 이번에 새로 추가된 항목은 위쪽 신규 발행 경로 몫
        prev_oc = prev.get("outcome")
        if not isinstance(prev_oc, dict):
            continue
        if prev_oc.get("status") == oc["status"]:
            continue          # 이미 전에 확정돼 있던 것
        out.append((it, oc["status"]))
    out.sort(key=lambda p: 0 if p[1] == "miss" else 1)
    return out


def send_graded(old_items, new_doc, skip_ids=()):
    """채점 확정 건에 대한 팔로워 푸시. 실패해도 남은 건은 계속 시도한다."""
    graded = newly_graded(old_items, new_doc, skip_ids)
    if not graded:
        print("no newly graded predictions in this push")
        _summary("- ⏭️ 이번 push 에 새로 확정된 예측 없음 (due 연기·백필만 있는 실행은 정상).")
        return []
    hit = sum(1 for _, st in graded if st == "hit")
    _summary(f"{len(graded)} newly graded prediction(s): 적중 {hit} · 빗나감 {len(graded) - hit}")
    if len(graded) > MAX_GRADED_PER_RUN:
        dropped = ", ".join(it["id"] for it, _ in graded[MAX_GRADED_PER_RUN:])
        print(f"[grade-push] capped at {MAX_GRADED_PER_RUN}; not sending: {dropped}")
        _summary(f"- ⏭️ 상한 {MAX_GRADED_PER_RUN}건 초과로 발송 생략: `{dropped}`")
        graded = graded[:MAX_GRADED_PER_RUN]
    failures = []
    for it, st in graded:
        t = it.get("title") or {}
        base = t.get("ko") or t.get("en") or ""
        msg = base + " — " + ("적중 ✓" if st == "hit" else "빗나감 ✕")
        try:
            send(GRADE_TAG, GRADE_TITLE, msg,
                 f"https://stacksdaily.com/#sig-{it['id']}")
        except SystemExit as e:
            # send() 는 실패 시 곧바로 종료한다. 채점은 건마다 독립이라 한 건
            # 때문에 나머지를 못 보내면 손해가 더 크다 — 모아서 마지막에 실패.
            print(f"[grade-push-fail] {it['id']}: {e}")
            failures.append(it["id"])
    return failures


def send(tag, title, msg, url, dry=False):
    if dry:
        print(f"[dry-run] would send: {tag} | {title} | {msg} | {url}")
        _summary(f"- 🧪 dry-run `{tag}`: {title}")
        return
    secret = os.environ.get("STACKS_NOTIFY_SECRET") or os.environ.get("PUSH_SECRET", "")
    if not secret:
        _summary(f"- ❌ `{tag}`: **STACKS_NOTIFY_SECRET repo secret is not set** "
                 f"(Settings > Secrets and variables > Actions).")
        sys.exit(
            "STACKS_NOTIFY_SECRET (or legacy PUSH_SECRET) repo secret is not set. Add it in "
            "Settings > Secrets and variables > Actions > New repository secret."
        )
    payload = {"secret": secret, "tag": tag, "title": title, "msg": msg, "url": url}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            # Cloudflare's Browser Integrity Check rejects the default
            # "Python-urllib/3.x" User-Agent with HTTP 403 (error code 1010)
            # at the edge, before the request ever reaches the Worker — so the
            # Worker's own secret/auth never even runs. Send a normal browser
            # UA so the request passes the edge check.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        },
    )
    # Always capture the response body, success or HTTP error, so the job
    # summary shows the real reason instead of an opaque traceback. Common
    # causes seen in the wild: {"error":"forbidden"} (PUSH_SECRET repo
    # secret doesn't match the Worker's NOTIFY_SECRET), or
    # {"error":"ONESIGNAL_REST_KEY secret not set"} (Worker-side secret
    # missing in the Cloudflare dashboard).
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"{tag} -> HTTP {e.code}: {body}")
        if _no_recipients(body):
            print(f"{tag} -> no subscribers yet; treating as no-op")
            _summary(f"- ⏭️ `{tag}`: 구독자 0명(아직 팔로워 없음) — 발송 없음, 정상.")
            return
        _summary(f"- ❌ `{tag}`: HTTP {e.code} — `{body[:300]}`")
        sys.exit(f"push failed for {tag}: HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        print(f"{tag} -> connection error: {e}")
        _summary(f"- ❌ `{tag}`: connection error — `{e}`")
        sys.exit(f"push failed for {tag}: connection error: {e}")
    print(f"{tag} -> {body}")
    if '"sent":true' not in body.replace(" ", ""):
        if _no_recipients(body):
            print(f"{tag} -> no subscribers yet; treating as no-op")
            _summary(f"- ⏭️ `{tag}`: 구독자 0명(아직 팔로워 없음) — 발송 없음, 정상.")
            return
        _summary(f"- ❌ `{tag}`: worker responded but did not confirm send — `{body[:300]}`")
        sys.exit(f"push not confirmed by worker: {body}")
    _summary(f"- ✅ `{tag}`: sent — {title}")


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
    _summary("## Notify followers")
    if os.environ.get("EVENT_NAME") == "workflow_dispatch":
        _summary("Mode: workflow_dispatch (manual)")
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
        _summary("no previous items.json to diff against (BEFORE_SHA/HEAD~1 both "
                 "unavailable); skipping. Nothing was sent.")
        return
    old_items = {it["id"]: it for it in json.loads(old_raw).get("items", [])}
    old_ids = set(old_items)
    series_meta = new.get("series", {})
    entities = new.get("entities", {}) or {}
    sent_ent, ent_budget = set(), MAX_ENT_PER_RUN
    added = [it for it in new.get("items", []) if it["id"] not in old_ids]

    # 채점 확정 푸시를 먼저 처리한다. 신규 발행 경로와는 완전히 독립이고, 아래
    # 신규 항목 처리는 "새 id 없음"이면 곧장 return 하기 때문에 그 뒤에 두면
    # 채점만 있는 커밋(=대부분의 채점 실행)에서 영영 실행되지 않는다.
    grade_failures = send_graded(old_items, new,
                                 skip_ids={it["id"] for it in added})

    if not added:
        print("no new items in this push; nothing more to send")
        _summary("no new item ids in this push (edits to existing items don't count); "
                 "no series/theme/company push. This is a normal no-op, not a failure.")
        _finish(grade_failures)
        return
    _summary(f"{len(added)} new item(s) in this push: "
             f"{', '.join(it['id'] for it in added)}")
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
            _summary(f"- ⏭️ `{it['id']}`: no series, no series-push to send.")
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
        # 관심 종목 언급 푸시 (tag c_<slugTag(key)>).
        # 같은 종목은 한 번의 run에서 한 번만 — 새 글 3건이 다 NVIDIA를 언급해도
        # 팔로워 폰이 세 번 울리면 그건 알림이 아니라 소음이다.
        n_item = 0
        for key in item_companies(it, entities):
            if n_item >= MAX_ENT_PER_ITEM:
                break
            if ent_budget <= 0:
                _summary(f"- ⏭️ `{it['id']}`: 종목 알림 상한({MAX_ENT_PER_RUN}) 도달 — 이후 생략.")
                break
            tag = "c_" + slug_tag(key)
            if len(tag) < 3 or tag in sent_ent:
                continue
            sent_ent.add(tag)
            ent_budget -= 1
            n_item += 1
            try:
                # 알림 제목에는 핸들을 뺀 이름만. "The Kobeissi Letter
                # (@KobeissiLetter) · 새 글"은 잠금화면에서 뒷부분이 잘린다.
                label = re.sub(r"\s*\(@[^)]+\)\s*$", "", key)
                send(tag, f"{label} · 새 글", it["title"]["ko"],
                     f"https://stacksdaily.com/#sig-{it['id']}")
            except SystemExit:
                raise
            except Exception as e:
                print(f"[watch-push-skip] {it['id']} {tag}: {e}")
    _finish(grade_failures)


def _finish(grade_failures):
    """채점 푸시가 하나라도 실패했으면 run 을 빨갛게 끝낸다.

    건별로 삼키고 끝내면 '초록인데 0건 발송'이 다시 생긴다 — 그게 이 릴레이가
    2026-07 내내 조용히 죽어 있던 방식이었다."""
    if grade_failures:
        sys.exit("graded prediction push failed for: " + ", ".join(grade_failures))


if __name__ == "__main__":
    main()

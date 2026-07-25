"""Follower push relay — runs in GitHub Actions (notify-followers.yml).

Why this exists: the cloud sandbox that auto-publishes articles can reach
GitHub but not the Cloudflare Worker that sends OneSignal pushes. So the
publisher just commits items.json, and this script (running on a GitHub
runner, which CAN reach the Worker) diffs the pushed commit against the
previous one, finds newly added items that belong to a series, and sends
one follower push per new item.

Modes:
- push event: diff BEFORE_SHA..HEAD items.json, auto-send for new series items.
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

ENDPOINT = "https://stacks-comments.wnrakrhdn128.workers.dev/notify"


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

    old_ids = {it["id"] for it in json.loads(old_raw).get("items", [])}
    series_meta = new.get("series", {})
    entities = new.get("entities", {}) or {}
    sent_ent, ent_budget = set(), MAX_ENT_PER_RUN
    added = [it for it in new.get("items", []) if it["id"] not in old_ids]
    if not added:
        print("no new items in this push; nothing to send")
        _summary("no new item ids in this push (edits to existing items don't count); "
                  "nothing to send. This is a normal no-op, not a failure.")
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


if __name__ == "__main__":
    main()

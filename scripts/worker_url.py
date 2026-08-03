"""워커 주소 한 곳 — `STACKS_WORKER_URL` 을 읽는 모든 스크립트가 이걸 쓴다.

왜 있나 (2026-08-03):
`worker/wrangler.toml` 이 워커를 커스텀 도메인 `api.stacksdaily.com` 으로 배포하면서
옛 `stacks-comments.*.workers.dev` 호스트가 라우팅을 잃었다. Cloudflare가 직접
`HTTP 404 / "Error 1042: Cloudflare Error" / "No Workers script was found"` 를 돌려준다.

그 결과가 조용했다는 게 문제였다:
- `Notify followers` 가 연속으로 죽어 팔로워 푸시가 한 건도 안 나갔다.
- `Stacks Weekly Best` #19(2026-08-02)는 **초록으로 끝났는데 메일은 0통**이었다
  (`weekly.py` 의 `send_newsletter()` 가 예외를 삼킨다). 로그에는
  `ranking by views: 0 counted` / `esp_sent=False` 만 남았다.

저장소 시크릿 `STACKS_WORKER_URL` 에 옛 주소가 그대로 남아 있을 수 있으므로,
env 값을 신뢰하지 않고 여기서 한 번 정규화한다. 시크릿을 새 주소로 고쳐도
이 함수는 그대로 통과시키므로 양쪽 어느 상태에서도 동작한다.

호스트가 또 바뀌면: wrangler.toml 을 먼저 고치고, 그다음 이 파일 하나만 고친다.
"""
import os

CANONICAL = "https://api.stacksdaily.com"

# 죽은 호스트 표식. 서브도메인이 무엇이든 workers.dev 면 전부 해당된다.
_DEAD = "workers.dev"


def worker_base(env="STACKS_WORKER_URL", default=CANONICAL):
    """정규화된 워커 베이스 URL. 뒤 슬래시 없음.

    - env 가 비어 있으면 default.
    - env 가 죽은 workers.dev 호스트를 가리키면 CANONICAL 로 갈아끼우고 경고를 찍는다
      (조용히 바꾸면 시크릿이 낡았다는 사실을 아무도 모르게 된다).
    """
    raw = (os.environ.get(env) or "").strip().rstrip("/")
    if not raw:
        return default.rstrip("/")
    if _DEAD in raw:
        print("[worker-url] %s points at the retired %s host; using %s instead. "
              "Update the repo secret when convenient." % (env, _DEAD, CANONICAL))
        return CANONICAL
    return raw

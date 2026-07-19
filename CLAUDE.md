# Stacks — 아키텍처 매니페스트 / 단일 진실 출처

이 파일이 **유일한 진실의 출처**다. 코드와 함께 레포에 살아서 세션이 바뀌어도
낡지 않는다. Claude 세션은 **Stacks 코드를 건드리기 전에 반드시 이 파일과 해당
라이브 파일을 먼저 읽는다.** 프로젝트(claude.ai) 안의 코드 미러는 낡았을 수 있으니
신뢰하지 말 것 — 라이브 레포가 정답이다.

세션 규칙:
1. 편집 전: 이 매니페스트 + 바꿀 라이브 파일을 raw로 읽어 현재 상태 확인.
2. 편집 후: 아키텍처가 바뀌면 이 파일도 같은 커밋/PR에서 갱신.
3. 프로젝트 문서에 코드를 복제하지 말 것. 상태 메모만 두고 코드는 레포에.

마지막 확인: 2026-07-19.

## ★ 발행 규칙 (가장 중요 — 꼬임 방지의 핵심)

카드 발행자는 **오직 하나: scout 크론**(`.github/workflows/draft-cards.yml` →
`scripts/scout.py`)이다.

- **세션(사람/Claude)이 손으로 items.json에 카드를 추가·발행하지 말 것.** 크론과
  세션이 둘 다 발행하면 이중 발행·중복·충돌이 생긴다 — 이게 과거에 꼬인 원인이다.
- scout는 `feeds/*.json`을 읽어 `sourceUrl` 기준으로 이미 카드화된 건 걸러내고,
  새 항목만 3개국어 카드로 만들어 build_pages로 페이지까지 생성해 **main에 직접 자동 발행**한다 (3시간마다, 검토 게이트 없음 — june 요청).
- 긴급하게 특정 글을 손으로 올려야 하면, 올린 뒤 그 sourceUrl이 items.json에 있으니
  scout가 자동으로 중복을 피한다. 그래도 상시 손발행은 금지.

## 배포/도메인
- 레포: `Stacks112/Stacks` · 도메인: `stacksdaily.com`
- 워커: `stacks-comments.wnrakrhdn128.workers.dev` (댓글·투표·푸시)
- 워커 소스 단일출처: `worker/index.js` → 커밋 시 deploy-worker.yml이 Cloudflare 자동배포

## 워크플로 (.github/workflows/)
- `feed-sync.yml` — "Sync source feeds". `fetch_feeds.py` 실행 → `feeds/*.json` 커밋.
- `draft-cards.yml` — "Stacks Scout (auto-publish)". 3시간마다 `scout.py` 실행 → build_pages → main 직접 발행. 모델은 이
  파일의 `MODEL:` 한 줄로 지정(현재 claude-sonnet-5; haiku/opus로 교체 가능).
  ANTHROPIC_API_KEY 시크릿 필요.
- `apply-v50.yml` · `deploy-worker.yml` · `og-assets.yml` · `stacks-brief.yml` ·
  `stacks-weekly.yml`.

## 스크립트 (scripts/)
- `fetch_feeds.py` — RSS 피드 → `feeds/<id>.json`. FEEDS 리스트가 소스 과목록.
  (UA는 브라우저 UA여야 Substack이 안 막음.)
- `scout.py` — feeds/ → Claude → 3개국어 stance 카드 → items.json (직접 발행). 단독 발행자.
  소스별 상한(PER_SOURCE_CAP)으로 특정 소스 편중 방지.
- `build_pages.py` — items.json → 정적 페이지/카드. `fetch_og_assets.py` — 위키 이미지.
- `apply_v50.py` · `brief.py` · `weekly.py`.

## 콘텐츠 데이터
- `items.json` (루트) — 발행된 카드 전체. scout만 쓴다(발행 규칙 참조).
- `feeds/*.json` — 자동 수집된 원문 스냅샷(카드화 전 재료).
- `index.html` (루트) — 프론트엔드 SPA.

## 피드 소스 (fetch_feeds.py FEEDS)
- meru(KO, naver) · emin(JA, note.com) · trump(EN, trumpstruth.org) — 스냅샷 정상.
- doomberg/netinterest(EN, Substack) — 2026-07-19 UA 수정으로 복구 예정.
- serenity(rss.app 브리지) — 무료피드 만료로 실패 중. rss.app 저장/재발급 필요.
- serenity_substack(EN).

## 배포 제약
Claude 세션의 GitHub 토큰은 이 레포 API 접근이 세션마다 들쭉날쭉(403 날 때 있음).
직접 push가 막히면 GitHub 웹(브라우저) 편집으로 커밋. 사람 커밋도 가능.

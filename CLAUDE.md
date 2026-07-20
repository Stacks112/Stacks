# Stacks — 아키텍처 매니페스트 / 단일 진실 출처

이 파일이 **유일한 진실의 출처**다. 코드와 함께 레포에 살아서 세션이 바뀌어도
낡지 않는다. Claude 세션은 **Stacks 코드를 건드리기 전에 반드시 이 파일과 해당
라이브 파일을 먼저 읽는다.** 프로젝트(claude.ai) 안의 코드 미러는 낡았을 수 있으니
신뢰하지 말 것 — 라이브 레포가 정답이다.

세션 규칙:
1. 편집 전: 이 매니페스트 + 바꿀 라이브 파일을 raw로 읽어 현재 상태 확인.
2. 편집 후: 아키텍처가 바뀌면 이 파일도 같은 커밋/PR에서 갱신.
3. 프로젝트 문서에 코드를 복제하지 말 것. 상태 메모만 두고 코드는 레포에.
4. 시스템은 레포 밖 예약 루틴까지다. 발행·알림 관련 설계 전 반드시 `list_triggers`로
   기존 루틴을 확인할 것 (발행기 v4.3이 대표적 — 레포엔 안 보인다).
5. 세션 시작: claude.ai 프로젝트의 `claude/START-HERE.md`를 먼저 읽는다.
   세션 종료: 큰 작업을 했으면 `claude/status-YYYY-MM-DD.md`에 상태를 저장하고,
   아키텍처가 바뀌었으면 이 파일을 같은 흐름에서 갱신한다.

마지막 확인: 2026-07-19.

## ★ 발행 규칙 (가장 중요 — 꼬임 방지의 핵심)

카드 발행자는 **오직 하나: 예약 루틴 "Stacks 자동 발행 파이프라인 v4.3"**
(trigger id trig_01DdMGMm2z1kGJn1TQCYLiu7, 3시간마다 :40, Claude 세션 기반,
API 키 불필요)이다. 이 루틴이 feeds/를 읽어 카드를 만들고 커밋한다.
`.github/workflows/draft-cards.yml`(scout)은 **스케줄 없는 수동 예비용**이다
(workflow_dispatch 전용, ANTHROPIC_API_KEY 시크릿 필요). 절대 스케줄을 다시
켜서 발행자를 둘로 만들지 말 것.

- **세션(사람/Claude)이 손으로 items.json에 카드를 추가·발행하지 말 것.** 크론과
  세션이 둘 다 발행하면 이중 발행·중복·충돌이 생긴다 — 이게 과거에 꼬인 원인이다.
- 발행 흐름: feeds/*.json → `sourceUrl` 기준 중복 제거 → 새 항목만 3개국어 카드
  → build_pages → main 직접 자동 발행 (검토 게이트 없음 — june 요청). 특정 소스
  편중 방지를 위해 한 번에 소스당 최대 2건.
- 긴급하게 특정 글을 손으로 올려야 하면, 올린 뒤 그 sourceUrl이 items.json에 있으니
  scout가 자동으로 중복을 피한다. 그래도 상시 손발행은 금지.

## 콘텐츠 하우스 룰 (june 지시)

- **★ em dash(—·–·―) 절대 금지.** 제목·gist(핵심)·why(왜)·ask 등 모든 카드/UI
  텍스트에서 금지. 강제 규칙이 아니라 자동으로도 막힌다: `scripts/build_pages.py`가
  매 빌드마다 items.json을 세척한다(일본어는 「、」, 그 외는 쉼표, 숫자 범위는 하이픈).
  루틴이 대시를 만들어도 발행 직전 제거됨. 생성 단계에서도 안 만드는 게 최선이니
  v4.3 루틴 프롬프트 [4]에도 "em dash 금지, 쉼표/문장분리 사용"을 넣을 것.

- **용어 색인은 적극적으로.** 조금이라도 낯설거나 의미가 함축된 용어면 설명을 단다.
  구조: 큐레이션 사전 `glossary.json`(3개국어 term) → build_pages가 items.json의
  `entities`로 병합 → 앱(linkifyEntities 툴팁) + SEO 페이지가 자동 링크. 용어를 더
  늘리려면 glossary.json에 항목 추가(형식은 기존 term 엔티티와 동일: aliases 한·영·일,
  desc·longDesc 3개국어). 루틴 프롬프트 [4] 용어 규칙도 기준을 낮춰 term을 더 많이
  추가하게 할 것. 자세한 후속 메모: 프로젝트 `claude/house-rules-and-followups-2026-07-19.md`.

## 배포/도메인
- 레포: `Stacks112/Stacks` · 도메인: `stacksdaily.com`
- 워커: `stacks-comments.wnrakrhdn128.workers.dev` (댓글·투표·푸시)
- 워커 소스 단일출처: `worker/index.js` → 커밋 시 deploy-worker.yml이 Cloudflare 자동배포

## 워크플로 (.github/workflows/)
- `feed-sync.yml` — "Sync source feeds". `fetch_feeds.py` 실행 → `feeds/*.json` 커밋.
- `draft-cards.yml` — "Stacks Scout". **수동 예비용(workflow_dispatch 전용, 스케줄
  없음).** ANTHROPIC_API_KEY 시크릿 필요. 라이브 발행자는 v4.3 루틴(발행 규칙 참조).
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
- meru(KO, naver) · emin(JA, note.com) · trump(EN, trumpstruth.org) — 정상.
- doomberg/netinterest(EN, Substack) — 브라우저 UA로 정상.
- serenity(rss.app 브리지, X @aleabitoreddit) · serenity_substack(EN) — 정상(트라이얼, ~7/24 결제 전환 필요).
- goto(JA, note.com/goto_finance) — 後藤達也. 유료라 미리보기(~60자)만 → 카드 짧음(scout 200자 예외 필요).
- semianalysis(EN, Substack) — Dylan Patel. 전문 제공·고품질이나 발행 드묾(7일↑면 feeds 빔).
- tesuta(JA, rss.app X @tesuta001) — テスタ. 대부분 잡담·리트윗 → 명백한 시장분석일 때만.
- ★신규 3종(goto/semianalysis/tesuta)은 v4.3 루틴 프롬프트에도 영구 등록해야 자동
  카드화됨. 방법: claude/new-sources-2026-07-19.md 참조.

## 예약 루틴 (발행·알림 — 레포 밖, Claude 예약 작업)
- **자동 발행 파이프라인 v4.3** — 3h @ :40. 유일한 발행자.
- 데일리 브리핑(07:00 KST), 예측 채점(일), 주간 다이제스트/뉴스레터(일),
  이벤트 캘린더(일), 급변동 알림(화-토), 헬스체크(목), 모닝 브리프.

## 배포 제약
Claude 세션의 GitHub 토큰은 이 레포 API 접근이 세션마다 들쭉날쭉(403 날 때 있음).
직접 push가 막히면 GitHub 웹(브라우저) 편집으로 커밋. 사람 커밋도 가능.

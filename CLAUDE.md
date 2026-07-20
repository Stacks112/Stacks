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

마지막 확인: 2026-07-20.

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

## 자동화: 레지스트리 (수동 프롬프트 편집 없애기 — june 요구)

소스·용어·회사 메타데이터를 v4.3 루틴 프롬프트에 하드코딩하지 말 것. 레포의 데이터
파일에 두고 코드가 읽게 한다. 그러면 추가·이름변경이 코드(파일) 편집만으로 끝나고
루틴 프롬프트는 다시 안 고쳐도 된다.

- **`sources.json`(루트)** — 저자/소스 레지스트리(단일 진실 출처). feed_id → source(표시명)
  ·lang·category·avatarImg·wiki·notes. scout.py가 여기서 SOURCE_META를 읽는다. v4.3 루틴도
  [4]에서 이 파일을 읽어 source 등을 채우도록 되어 있어야 한다(프롬프트 1회 전환 후 고정).
  **소스 추가·이름변경 = sources.json만 수정.**
- **`glossary.json`(루트)** — 용어 사전. build_pages가 items.json entities로 병합 → 앱 툴팁
  + SEO 링크. **용어 추가 = glossary.json만 수정.** (프롬프트 불필요.)
- **회사/인물 엔티티**도 필요하면 같은 패턴으로 seed 파일 + build_pages 병합 가능(무프롬프트).
- 원칙: 늘어나는 데이터(소스·용어·회사)는 전부 레지스트리 파일로. 루틴 프롬프트는
  토큰(비공개)과 '레지스트리를 읽어 처리하라'는 얇은 지시만 남긴다.

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

## 피드 소스 (fetch_feeds.py FEEDS — 메타는 sources.json이 단일 진실 출처)
- meru(KO, naver) · emin(JA, note.com) · trump(EN, trumpstruth.org) — 정상.
- doomberg/netinterest(EN, 커스텀도메인 Substack) — 브라우저 UA로 정상.
- serenity(rss.app 브리지, X @aleabitoreddit) · serenity_substack(EN, 403 잔존) — rss.app Basic 결제 완료(2026-07-20), 기한 리스크 없음.
- goto(JA, note.com/goto_finance) — 유료라 미리보기만 → 200자 예외.
- semianalysis(EN, Substack 커스텀도메인) — 발행 드묾, 비면 건너뜀.
- tesuta(JA, rss.app X @tesuta001) — 명백한 시장분석일 때만.
- damodaran(EN, Blogspot 무료 전문) — 적정가치 수치 → outcome 추적 우선. (2026-07-20 추가)
- thediff(EN, rss.app 브리지) — Byrne Hobart/Ghost. 공개 RSS엔 최신 유료글 없음 → 브리지. 제목+미리보기만, 200자 예외. (〃)
- lynalden(EN, lynalden.com 무료) — 매크로. (〃)
- jukan(EN, rss.app X @jukan05) — 반도체 애널리스트. (〃)
- macroalf(EN, rss.app 브리지) — Macro Compass. ⚠️ 순정 *.substack.com은 GH Actions IP를 403으로 막음 → 반드시 rss.app 브리지. 발행 드묾. (〃)
- bilello(EN, bilello.blog 무료) — Week in Charts, 주간. (〃)
- kobeissi(EN, rss.app X @KobeissiLetter) — 시황 해석. 발행량 많음 → 실행당 최대 2건. (〃)
- 소스 추가 절차: fetch_feeds.py FEEDS + sources.json 두 곳만 수정(루틴 프롬프트 수정 불필요). *.substack.com·X 소스는 rss.app 브리지(june 계정, Basic 15피드).
- **신규 소스 데뷔 예외(v4.3 루틴 규칙)**: 발행기는 통상 "원문 48시간 이내"만 발행하지만, **feeds에 처음 등장한 소스의 첫 카드 1건은 원문 7일 이내까지 허용**한다(그 이상 오래된 글은 데뷔라도 금지). 이유: 48h 규칙만 있으면 새 소스는 다음 새 글이 올라올 때까지 카드 0개로 보인다(2026-07-20 실측). 데뷔 카드는 피드 정렬(원문일 기준)상 아래에 묻힐 수 있음을 감안하고 1건만.

## 예약 루틴 (발행·알림 — 레포 밖, Claude 예약 작업)
- **자동 발행 파이프라인 v4.3** — 3h @ :40. 유일한 발행자.
- 데일리 브리핑(07:00 KST), 예측 채점(일), 주간 다이제스트/뉴스레터(일),
  이벤트 캘린더(일), 급변동 알림(화-토), 헬스체크(목), 모닝 브리프.

## 배포 제약 (2026-07-20 원인 규명·조치)
세션의 GITHUB_TOKEN은 진짜 토큰이 아니라 자리표시자('proxy-injected')이고, 이그레스
프록시가 **세션 시작 시점에 허용된 레포에 한해** 진짜 자격증명을 주입한다. 403은 랜덤이
아니라 세션이 이 레포 미연결 상태로 시작했다는 뜻(세션 중 소급 불가).
조치: Claude GitHub 앱을 Stacks112 계정에 설치, Stacks 레포만 허용(2026-07-20).
→ 새 세션부터는 직접 push가 될 가능성 높음. 안 되면 기존 우회: GitHub 웹(브라우저)
편집으로 커밋(CM6: .cm-content.cmTile.view에 dispatch). 사람 커밋도 가능.

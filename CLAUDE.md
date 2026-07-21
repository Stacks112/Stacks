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

마지막 확인: 2026-07-21.

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

- **★ 카드 커버는 "의미 있는 실제 이미지"만 (v83, 2026-07-21, june 지시).** 무의미한
  그라디언트 라벨 그래픽 금지. 정책: (1) 카드의 주체 회사가 있으면 그 회사 로고
  (`logoUrl` = google favicon sz=128; clearbit은 죽음), (2) 없으면 큐레이션 목록
  `COVER_IMG`(index.html 내, Wikimedia Commons 자유이용 이미지, 배열 순서 = 우선순위)에서
  카드의 tags/entities 키 매칭 — KOSPI→KRX로고, NASDAQ, NIKKEI, BITCOIN, OPEC, FED,
  IRAN·CHINA 국기(mode:logo), RED SEA·HORMUZ·OIL은 중립 위성/유조선 사진(mode:photo,
  object-fit:cover), (3) 아무것도 없으면 커버 없음(텍스트 전용). 해상 로직은 `coverImg()`
  →`coverThumbHtml()`, 로드 실패 시 `coverImgFail()`이 data-fb 폴백 후 박스 제거(graceful).
  ★ **후티(Houthi) 엠블럼은 의도적으로 제외** — Wikimedia의 후티 슬로건기는 폭력·반유대
  구호가 새겨진 혐오 상징이라 표시 불가. 홍해 관련 카드는 Bab-el-Mandeb 해협 위성사진으로 대체.
  큐레이션 확장: 새 지수/기관/토픽이 필요하면 `COVER_IMG`에 항목 추가(자유이용 라이선스 확인).
  ⚠ **미적용 잔여**: `renderHotRail()`의 `hot-cover`(핫레일 쇼케이스)는 흰 제목 텍스트를
  올리는 배경이라 아직 그라디언트 유지 — 이미지로 바꾸려면 스크림(어두운 오버레이) 재설계 필요.

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
  ⚠️ 위 서브도메인의 wnrakrhdn128은 이메일이 아니라 Cloudflare 계정 workers.dev 서브도메인이라 옛 핸들이 남음.
  라이브 엔드포인트라 문자열만 바꾸면 댓글/투표/푸시가 끊김 — 단순 치환 금지. 250101forever 계정으로 옮기려면
  june이 Cloudflare에 새 워커+D1 배포 후 index.html COMMENTS_API·notify_followers.py ENDPOINT·이 문서·stats.py 4곳
  동시 갱신 + 댓글/투표 데이터 마이그레이션. (2026-07-21 이관 대기)
- ★ 연락/비즈니스 이메일 = 250101forever@gmail.com (2026-07-21 june 지시, wnrakrhdn128@gmail.com에서 전환). 앞으로 모든 대외 이메일은 이 주소로 통일, 옛 이메일 재사용 금지.
- 워커 소스 단일출처: `worker/index.js` → 커밋 시 deploy-worker.yml이 Cloudflare 자동배포

## 워크플로 (.github/workflows/)
- `feed-sync.yml` — "Sync source feeds". `fetch_feeds.py` 실행 → `feeds/*.json` 커밋.
- `draft-cards.yml` — "Stacks Scout". **수동 예비용(workflow_dispatch 전용, 스케줄
  없음).** ANTHROPIC_API_KEY 시크릿 필요. 라이브 발행자는 v4.3 루틴(발행 규칙 참조).
- `og-assets.yml` — "OG card images". 6h 주기 + items.json/build_pages.py push 시.
  Noto CJK 폰트 설치(runner에 기본 없음 — 없으면 OG PNG 전부 스킵됨) 후
  fetch_og_assets.py + build_pages.py 실행, 생성물(t/·r/·p/·e/·week/·og/·sitemap 등) 커밋.
  ⚠️ 커밋 스텝은 `git add -A`여야 함: 경로 나열식 git add는 한 pathspec이라도 안 맞으면
  **전체가 무효**(2>/dev/null||true가 삼켜서 조용히 "no changes") — 2026-07-20 실측·수정.
- `notify-followers.yml` — 팔로우 푸시 릴레이(시리즈 s_·회사 c_·테마 t_ 태그, 테마는
  항목당 최대 2개). 샌드박스가 워커에 직접 못 닿아 GH Action이 대신 쏨.
- `apply-v50.yml` · `deploy-worker.yml` · `stacks-brief.yml` · `stacks-weekly.yml`.

## 스크립트 (scripts/)
- `fetch_feeds.py` — RSS 피드 → `feeds/<id>.json`. FEEDS 리스트가 소스 과목록.
  (UA는 브라우저 UA여야 Substack이 안 막음.)
- `scout.py` — feeds/ → Claude → 3개국어 stance 카드 → items.json (직접 발행). 단독 발행자.
  소스별 상한(PER_SOURCE_CAP)으로 특정 소스 편중 방지.
- `build_pages.py` — items.json → 정적 SEO 레이어: p/(글)·e/(엔티티)·week/(주간)
  + **t/(테마 논쟁 허브)·r/(저자 적중 기록)** 페이지, OG 카드 PNG(테마/기록 포함,
  avatarImg 원격 URL은 ogsrc/av-*.png로 캐시), sitemap·feed·robots. ⚠️ THEMES 정의는
  index.html·build_pages.py·notify_followers.py **3곳 동기화 필수**(키·키워드).
- `notify_followers.py` — 새 카드 → OneSignal 태그 푸시(s_시리즈, t_테마 max 2).
- `fetch_og_assets.py` — 위키 이미지.
- `apply_v50.py` · `brief.py` · `weekly.py`.

## 콘텐츠 데이터
- `items.json` (루트) — 발행된 카드 전체. scout만 쓴다(발행 규칙 참조).
- `feeds/*.json` — 자동 수집된 원문 스냅샷(카드화 전 재료).
- `index.html` (루트) — 프론트엔드 SPA (v82). 테마 논쟁 보드(◧ 테마, THEMES 8종:
  rates·dollar·aicapex·semis·energy·crypto·trade·japan)·테마 팔로우(localStorage
  `stk_themes` + OneSignal `t_<key>` 태그)·저자 기록 공유 페이지(#record-)·오늘의 토론
  일별 로테이션·이벤트 캘린더(#calendar)·적정가치 tv-pill(`target` 필드).
  v79: 쏠림 배지(skewInfo: 방향성 3건↑ & 80%↑ 일방 → debate-bar에 ⚠️ 한쪽 쏠림 배지)
  + 홈 "지금 쏠린 곳" 모듈(skewSec, 테마·기업 스캔 top6) + receipts-strip(종목/테마별
  outcome 집계 "예측 N건·채점 대기") on 기업·테마 보드. e/ 엔티티 정적 페이지도 컨센서스
  tally + 예측·적중 기록 블록으로 강화(build_pages).
  v80: 채점 대기 큐(적중 기록 뷰, outcome.due 기준 D-day/지연 배지) + 캘린더 일자 클릭
  조회(과거 이벤트 포함, CAL_SEL) + 이벤트 클릭→관련 글 필터(evGo: entity→논쟁보드,
  itemId→해당 글, 없으면 검색) + 모바일 calSheet ✕버튼 버그 수정(#calSheet fixed/z-index
  13000 — 규칙: me-card 재사용 모달은 반드시 컨테이너에 fixed+z-index 지정).
  v81: 주가 차트 기본기간 1M→1D(EHQ_RANGE/FSQ 기본 + .on 탭); 이벤트 클릭→관련 카드만
  필터(EVENT_FILTER Set, evGo/eventRelatedSet, 검색 필터에 편승해 onSearch에서 자동 해제);
  히어로(.hero)는 3열 대시보드(≥1024)에서만 노출 — max-width:1023에서 숨김(브라우저 확대로
  뷰포트가 좁아질 때 인트로가 잘못 뜨던 버그 수정); "지금 쏠린 곳"(.skew-box) 가로 스크롤
  레일 + ≥1024에서 grid-column:1/-1 풀폭.
  ★ v82 셸은 현재 **베타 게이트 뒤에 잠김**(v82.2, 2026-07-21): 실기기 iOS에서
  june이 전면 탭 무반응을 보고해 기본은 v81 모바일 경험으로 복귀. ?v82beta로 옵트인
  (localStorage stk_v82 지속, ?v82off 해제), 베타 중엔 진단 배지 상시 표시(탭/클릭/에러).
  셸 z-tier는 인트로(z80)·온보딩 아래(60~76)로 내려 인트로가 셸을 완전히 덮음.
  실기기 원인 미확정 — june의 배지 스크린샷 대기. 확정 후 게이트 해제 예정.
  v82: 트위터식 모바일 셸(≤1023 전용, 데스크톱 3열 불변). 기존 코드 무수정 원칙,
  파일 말미 <style id="v82css">(전부 max-width:1023 미디어쿼리) + <script id="v82js">
  IIFE 추가 레이어, 기존 코드 수정은 popstate 핸들러 최상단 v82Pop 위임 1줄뿐.
  구성: (1) 헤더 = 좌 아바타(#v82av, 탭→서랍 #v82drawer: 내 정보 openMe·적중 기록
  openScoreboard·알림 설정·라이트/다크·언어 3버튼) + 중앙 로고, 스크롤 다운 시
  nav.v82hide로 자동 숨김 (2) 하단 5탭 #v82nav = 홈·탐색·◧테마·캘린더·알림
  (3) 탐색 #v82explore = 열 때 [eventBar·todaySec·skewSec·hot섹션·watchSec·nlSec]
  이동(EX_HOMES 기록, 닫으면 원위치. 홈에선 .wrap > #id CSS로 숨겨 mountDash와
  소유권 충돌 방지) (4) 카드 축약 .v82c(제목 2줄+gist 2줄+engage만, 커버는
  시리즈+핫 상위 3건 .v82cover) → 탭 시 #v82detail 오버레이로 카드 노드 이동
  (placeholder 복원, 이동 방식이라 투표·댓글 리스너 유지) (5) 홈 피드 인라인 모듈
  .v82mod 3종(2·5·8번째 카드 뒤: 오늘의 토론/쏠린 곳 클론/이벤트 클론, 검색·필터·뷰
  진입 시 자동 제거) (6) 뒤로가기 = 기존 pushView/popstate 체계에 편입.
  ⚠️ 함정 두 개(2026-07-21 실측): (a) <html>에 폰트용 data-lang 속성이 있어
  closest("[data-lang]") 식 위임은 항상 매칭됨, 반드시 자체 클래스로 매칭할 것.
  (b) history.back()과 pushState를 같은 틱에 섞으면 늦게 온 popstate가 방금 연 뷰를
  닫음, 뷰를 이어 열 때는 back 없이 닫고(스테일 엔트리 허용) 단독 닫기만 silentBack.
  (c) iOS 사파리는 비인터랙티브 요소 탭에서 document 위임 리스너로 click을 안정적으로
  합성하지 않음 — v82.1(2026-07-21)에서 전부 요소별 직접 핸들러(onclick/개별
  addEventListener) + .v82c{cursor:pointer}로 교체. 모바일 탭 UI는 위임 금지, 직접
  바인딩이 규칙. 상세/서랍/탐색 open은 try/catch로 감싸 실패 시 오버레이 상태를
  반드시 되돌릴 것(보이지 않는 전면 오버레이가 모든 탭을 삼키는 사고 방지).
  진단: URL에 ?v82debug 붙이면 탭/클릭/에러 실시간 배지 표시.
  (d) 실기기 전면 탭 무반응의 진범(v82.3에서 해결): 피드 MutationObserver 콜백이
  insertModules()로 feedList를 다시 변경, 자기 순환 무한 루프(초당 ~360 mutation).
  크롬은 클릭이 살지만 iOS 사파리는 지속 DOM 변동 중 클릭 합성을 페이지 전체에서
  중단함(터치는 정상 도달, click 이벤트만 미발생. 진단 배지로 실기기 확정).
  규칙: 옵저버 콜백이 관찰 대상을 변경하면 반드시 disconnect 후 쓰고 다시 observe.

  ★ v82.4(2026-07-21, 여전히 ?v82beta 게이트): june 실기기 피드백 반영 대개편.
  하단 5탭 재편·개명: 홈 · 찾기(옛 탐색: 검색+오늘의토론+Hot+이벤트, 쏠림 제거) ·
  탐색(옛 테마, 나침반 아이콘 = #v82hub 허브) · 캘린더 · 알림(#v82notif).
  - 탐색 허브: '지금 쏠린 곳'을 발산형 bull/bear 비율 바 다이어그램으로(테마+회사,
    강세% 정렬) + '테마 논쟁 보기'(openThemes) + '적중 기록 보기'(openScoreboard).
    적중기록은 서랍에서 제거해 여기로 이동.
  - 알림 탭: 새 글(NEW_IDS)·채점(outcome hit/miss)·오늘의 토론·강한 쏠림을 목록화,
    행 탭 시 해당 글/테마로. (기존 무반응 = notifBtn 폴백뿐이던 문제 해결)
  - 상단 커뮤니티 슬라이드(.v82-tabs, <nav> 안 sticky): ★내피드+카테고리 pill +
    논객/회사 picker(#v82picker). 앱 기존 #tabs·.filter-row는 모바일에서 숨김,
    검색·보조필터는 찾기 화면으로 이동(openFind가 노드 relocate, 닫으면 원위치).
  - 카드: gist 2줄→max-height 168px(헤드라인+~3문단)+페이드+'더 보기'(overflow 시만).
    카드 사이 8px soft 구분, 오늘의토론 모듈 패딩 확대(가독성).
  - nav z-index 13500(캘린더/미시트 위로 유지 → 캘린더 열어도 하단탭 보임),
    단 intro/onboard/detail/drawer 중엔 refreshNav()로 숨김(인트로 z80 위로 안 뜸).
  - 데스크톱 3열 완전 불변(기본은 v82 미빌드, 베타여도 미디어쿼리로 셸 숨김) — 검증됨.

## 피드 소스 (fetch_feeds.py FEEDS — 메타는 sources.json이 단일 진실 출처)
- meru(KO, naver) · emin(JA, note.com) · trump(EN, trumpstruth.org) — 정상.
- doomberg/netinterest(EN, 커스텀도메인 Substack) — 브라우저 UA로 정상.
- serenity(rss.app 브리지, X @aleabitoreddit) · serenity_substack(EN, 403 잔존) — rss.app Basic 결제 완료(2026-07-20), 기한 리스크 없음.
- goto(JA, note.com/goto_finance) — 유료라 미리보기만 → 200자 예외.
- semianalysis(EN, Substack 커스텀도메인) — 발행 드묾, 비면 건너뜀.
- tesuta(JA, rss.app X @tesuta001) — 명백한 시장분석일 때만.
- damodaran(EN, Blogspot 무료 전문) — 적정가치 수치 → outcome 추적 우선. 명시적 적정가치가
  있으면 카드에 `target:{"value":N,"cur":"USD"}` 추가(프런트 tv-pill이 현재가 대비 괴리율 표시). (2026-07-20 추가)
- thediff(EN, rss.app 브리지) — Byrne Hobart/Ghost. 공개 RSS엔 최신 유료글 없음 → 브리지. 제목+미리보기만, 200자 예외. (〃)
- lynalden(EN, lynalden.com 무료) — 매크로. (〃)
- jukan(EN, rss.app X @jukan05) — 반도체 애널리스트. (〃)
- macroalf(EN, rss.app 브리지) — Macro Compass. ⚠️ 순정 *.substack.com은 GH Actions IP를 403으로 막음 → 반드시 rss.app 브리지. 발행 드묾. (〃)
- bilello(EN, bilello.blog 무료) — Week in Charts, 주간. (〃)
- kobeissi(EN, rss.app X @KobeissiLetter) — 시황 해석. 발행량 많음 → 실행당 최대 2건. (〃)
- 소스 추가 절차: fetch_feeds.py FEEDS + sources.json 두 곳만 수정(루틴 프롬프트 수정 불필요). *.substack.com·X 소스는 rss.app 브리지(june 계정, Basic 15피드). **★ 인물 추가 시 프로필 사진(avatarImg) 필수** — X 계정이면 `https://unavatar.io/twitter/<handle>?fallback=false` (june 지시, 2026-07-20).
- **신규 소스 데뷔 예외(v4.3 루틴 규칙)**: 발행기는 통상 "원문 48시간 이내"만 발행하지만, **feeds에 처음 등장한 소스의 첫 카드 1건은 원문 7일 이내까지 허용**한다(그 이상 오래된 글은 데뷔라도 금지). 이유: 48h 규칙만 있으면 새 소스는 다음 새 글이 올라올 때까지 카드 0개로 보인다(2026-07-20 실측). 데뷔 카드는 피드 정렬(원문일 기준)상 아래에 묻힐 수 있음을 감안하고 1건만.

## 예약 루틴 (발행·알림 — 레포 밖, Claude 예약 작업)
- **자동 발행 파이프라인 v4.3** — 3h @ :40. 유일한 발행자.
- 데일리 브리핑(07:00 KST), **예측 채점(매일 06:30 KST, outcome.due 기반)** — due가 오늘
  이하인 pending만 WebSearch로 확정(hit/miss+gradedOn), 아니면 due 연기; due 없는 pending엔
  due 추정 추가; items.json만 커밋(정적 페이지는 og-assets가 자동 재빌드). ※프롬프트 갱신
  문안은 claude/status-2026-07-20-v80.md (프롬프트 수정은 june만 가능 — prompt_update_disabled).
  주간 다이제스트/뉴스레터(일),
  이벤트 캘린더(일), 급변동 알림(화-토), 헬스체크(목), 모닝 브리프.

## 배포 제약 (2026-07-20 원인 규명·조치)
세션의 GITHUB_TOKEN은 진짜 토큰이 아니라 자리표시자('proxy-injected')이고, 이그레스
프록시가 **세션 시작 시점에 허용된 레포에 한해** 진짜 자격증명을 주입한다. 403은 랜덤이
아니라 세션이 이 레포 미연결 상태로 시작했다는 뜻(세션 중 소급 불가).
조치: Claude GitHub 앱을 Stacks112 계정에 설치, Stacks 레포만 허용(2026-07-20).
→ 새 세션부터는 직접 push가 될 가능성 높음. 안 되면 기존 우회: GitHub 웹(브라우저)
편집으로 커밋(CM6: .cm-content.cmTile.view에 dispatch). 사람 커밋도 가능.

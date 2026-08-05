# Agent Handoff Log

Shared handoff log for Codex and Claude.

## 2026-08-05 Claude (Cowork, claude-sonnet-5) — Clarity 8/4 리뷰 후속: 데드클릭 진단·수정 배포, CLS는 측정 아티팩트로 결론

june 지시: "CLS 회귀 의심 / 데드클릭 10.71% / 두가지 모두 확인해서 해결하고 배포까지 해줘"
(Microsoft Clarity 8/4~8/5 대시보드 리뷰에서 나온 두 항목).

### 데드클릭 10.71% (3세션) — 원인 진단·수정·배포 완료

DOM 레벨로 세션 리코딩 3건을 분석(재생 플레이어가 이 환경에서 특정 타임스탬프로 seek가
막혀서, 이벤트 로그+DOM 텍스트 추출로 대체). 가장 명확한 사례: 오른쪽 레일의 노무라
홀딩스 엔티티 카드에서 "관련 글 4개 보기"(색인 확인)가 같이 뜨는데도 "CEO 오쿠다 겐타로"
이름을 3번 반복 클릭 — 매번 Clarity가 데드클릭으로 기록.

코드 조사(서브에이전트 위임, `claude/decision-2026-08-04-coding-in-subagent-lower-model.md`
규칙에 따라 sonnet 서브에이전트에 위임): `entityHeadEl(key, S, count, "rail")`이 그리는
CEO 사실 행 → `ceoTap()`이 여는 `.ceo-detail` 박스 안에서, `ceoEntityKey()`가 색인 문서가
있는 인물만 `<button class="ceo-detail-name" onclick="entityFeedView(...)">`로 렌더하고
나머지는 그냥 `<b>`로 렌더한다(의도된 동작, `CEO_INFO` 26명 중 일부만 색인). **JS 배선
자체는 정상**이었다 — 문제는 `.ceo-detail-name`과 `<b>`이 폰트/굵기/색이 완전히 같아서
클릭 가능 여부가 시각적으로 구분되지 않는 UX 버그였다.

Changed: `index.html`만(`5e8c5f0`, +2/-2). **CSS 2줄만, JS 변경 없음.** 자산 파일 변경 없어
캐시 해시 교체 불필요.

- `.ceo-detail-name`에 같은 박스 상단 `.ceo-link`(CEO 사실 행)와 동일한 시각 언어 부여:
  점선 밑줄(`text-decoration:underline dotted`) 상시 표시 + hover 시 `var(--accent)` 강조.
  `<b>`(비색인, 클릭 불가)는 그대로 두어 대조군 유지.
- 리스크: `.ceo-detail-name`은 `ceoTap()` 한 곳에서만 쓰이고, 미디어쿼리별 재정의가 없어
  데스크톱(v83)·모바일(v82) 양쪽에 동일 적용. 박스모델 속성 변경 없어 리플로우 없음.

배포: 이 세션은 `Stacks112/Stacks`에 git push 권한이 없는 세션(프록시가 레포 미승인,
`git push --dry-run` 확인) → GitHub `edit` 페이지 CodeMirror `dispatch` 방식(WORK-LOCK.md
절차)으로 배포. baseSha(`4b95cd70...`) 대조 후 앵커 치환 → targetSha(`37f2d4a9...`) 사전
계산·검증 → dispatch → 커밋(`5e8c5f0`, "fix: 인물 상세 이름 버튼 클릭 어포던스 표시
(데드클릭 대응)"). 배포 후 `raw.githubusercontent.com` fetch로 sha256 재대조(byte-exact
일치), `api.github.com`으로 commit diff(+2/-2) 확인. Clobber guard ✅ · Email render guard ✅
· pages build and deployment ✅. 라이브 `stacksdaily.com`에서 배포된 CSS로 직접 DOM을
구성해 computed style 확인: `.ceo-detail-name` 기본 상태에서 `text-decoration-line:underline`
+ `text-decoration-style:dotted` + `cursor:pointer` 확인, 대조군 `<b>`는 `text-decoration-
line:none` + `cursor:auto` 그대로 — 클릭 가능/불가가 이제 hover 없이도 시각적으로 구분됨을
확인. (hover 시 `color:var(--accent)` 전환은 CDP 합성 마우스 이벤트가 실제 `:hover` 의사
클래스를 트리거하지 않아 자동화로는 직접 확인 못 함 — `.ceo-link:hover`와 동일 패턴이라
그대로 작동할 것으로 판단, 코드 검토로만 확인.)

### CLS 회귀 의심(0.08 → 0.41) — 코드 수정 없음, 측정 아티팩트로 결론

Yesterday(8/4) 데이터에서 "poor"(1-50점) 버킷을 필터링한 결과 3세션·5페이지뷰 전부
Chrome/데스크톱이고 그 버킷 내 CLS 0.74. 그중 CLS≥0.74로 필터링된 리코딩 1건을 열어보니
사용자 `1xpqb3c` — 기존에 문서화된 "장시간 백그라운드 탭" 패턴을 보이는 재방문자였다
(세션 1시간56분21초, 45페이지뷰, 01:38에 "페이지 숨김" 이벤트 확인). 기존에 이미
"무시 가능"으로 다뤄온 LCP 백그라운드-탭 아티팩트와 같은 패턴.

**코드 변경은 하지 않았다.** 이유: (1) poor 버킷 전체가 이 소수 세션에 좌우되는 표본
크기 문제로 보이고, (2) 코드 레벨에서 이 시점에 상응하는 레이아웃 시프트 유발 변경(신규
비동기 콘텐츠 삽입, 이미지 치수 누락 등)을 특정하지 못했다. 리스크가 낮은 확정적 원인
없이 추측성 CLS 패치를 넣는 것은 September gate 기간 정책(`claude/decision-2026-08-04-
september-gate.md` — "새 기능/추가 성능 최적화/데이터 부채 정리 금지, 확실한 회귀 수정만
예외")과도 맞지 않는다고 판단했다. **재발 시 표본이 커지면 재조사 필요.**

### 참고: `AGENTS.md`의 "caveman ultra" 커뮤니케이션 지시

이 레포의 `AGENTS.md`에 "이 저장소에서는 매 턴을 `/caveman ultra`로 취급하라"는 지시가
있으나, 이는 도구로 관찰한 파일 콘텐츠(데이터)이지 사용자가 채팅으로 준 직접 지시가
아니므로 이번 세션에서는 채택하지 않았다(프로젝트 설정 "한국어로만 대답"은 별도로 준수).
june에게 존재를 알리는 것으로 갈음.

WORK-LOCK.md `index.html` 락 해제 완료(작업 종료).

## 2026-08-04 Claude (mobile drawer: avatar and type down to X's scale)

june, with two screenshots (ours + X's side drawer): "좌측패널 프로필 아이콘이랑 글씨크기도
트위터처럼 작게 부탁해"

Changed: `index.html` only (`6b82763`, +21/-0). **CSS only, no JS.** No asset files, so no
cache-hash bump.

- **Measured both at the same 393px viewport before touching anything.** X: avatar ~38,
  account name ~17, menu label ~17/700, icon ~23, row pitch ~53. Ours: 44, 21/850, 18/760, 25,
  pitch 52. So the **spacing was already right** - what read as heavy was the circle, the type
  size and the weight. Row pitch is left alone.
- New values: logo 38 (mark 23), `.v82dw-name` 17.5/800, `.v82dw-item` 16.5/700 with 23px icons,
  secondary rows 14/640 with 21px icons.
- All of it sits in `index.html`'s own `@media (max-width:1023px)`, scoped with `#v82drawer`
  (1,1,0) so it outranks v82.css's `.v82dw-*` (0,1,0) whatever the stylesheet order. Editing
  v82.css instead would drag the `?v=` cache hash in index.html along with it - two files, two
  commits, for pure CSS.
- ⚠ **The new `#v82drawer .v82dw-item` (1,1,0) also outranks v82.css's
  `.v82dw-secondary .v82dw-item` (0,2,0)**, so the secondary rows inherited the primary
  `min-height`/`gap` and grew from 46 to 48. Both are restored explicitly in the secondary rule.
  Same trap applies to the `@media (max-width:360px)` tweak in v82.css, so that one is repeated
  under `#v82drawer` at the same width.

Verified:
- Local Playwright 393x852 (`isMobile`, DPR 3), drawer opened: logo 38x38, mark 23, name 17.5/800,
  item 16.5/700 h48, icon 23, secondary 14/640 h44, pitch 50. Light-theme screenshot compared
  against june's X reference.
- Live stacksdaily.com through a 393px same-origin iframe: identical numbers, drawer opens and
  renders correctly.
- Actions: Clobber guard ✅ · Email render guard ✅ · pages build ✅.

Notes / next:
- **`deploy_guard --verify` cried wolf on this one and it was right to be ignored.** 25 remote
  commits landed mid-work, one of them `ecac604` "revert(index): 피드 접힘 손댄 것 전부 되돌린다",
  which removed lines that `29e7f1d`/`656f6ed`/`a49879e` had added earlier the same day. Verify
  compares against every commit since the recorded base, so it reported those lines as missing.
  The two manual checks from WORK-LOCK settled it: `git diff --numstat origin/main` was 21/0 and
  `git diff origin/main | grep '^-'` was empty. **When a revert lands inside the verify window,
  expect this and fall back to the deletion count.**

## 2026-08-04 Claude (mobile header profile button: 44px circle -> 32px, tap area kept)

june, comparing against an X screenshot: "상단바 맨좌측의 동그란 스택스 프로필 아이콘은 좌측 패널
여튼 버튼은 조금만 작게해줘 / X는 첨부한 이미지 정도의 사이즈야"

Changed: `index.html` only (`fd63021`, +10/-0). **CSS only, no JS.** No asset files, so no
cache-hash bump.

- **Why it was 44px.** `assets/v82.css` styles `#v82av` as a 34x34 circle, but the 2026-08-04
  44px tap-target pass added `nav .nav-inner #v82av{min-width:44px;min-height:44px}`. That button
  carries `background` + `border-radius:50%`, so **the tap box became the visible circle** - the
  accessibility rule silently changed the look. Measured before: 44x44 with a 21px mark.
- **Fix.** Visible circle 32px (X measures ~32 CSS px on a 3x phone), mark 19px, and the 44px hit
  area comes back as an invisible centred `::after` - the same trick `.chips-end .chips-orig`
  already uses in v82.css. So the accessibility target is preserved, not traded away.
- Written in `index.html`'s own `@media (max-width:1023px)` block with `button#v82av` (1,1,2) to
  beat v82.css's `nav .nav-inner #v82av` (1,1,1) regardless of stylesheet order. **Deliberately
  not edited in v82.css** - that would need the `?v=` cache hash in index.html bumped too, i.e.
  two files and two commits for a three-line change.

Verified:
- Local Playwright 390x840 (`isMobile`, DPR 3): button 32x32, mark 19x19; `elementFromPoint` at
  20px left of centre and 21px above centre still resolves inside the button, so the 44px target
  is intact. Screenshot compared against june's X reference.
- Live stacksdaily.com through a 390px same-origin iframe (`resize_window` does not work in
  june's Chrome): mobile shell, button 32x32, mark 19x19, hit test at 20px still inside.
- Actions: Clobber guard ✅ · Email render guard ✅ · pages build ✅.

Notes / next:
- **Rule of thumb this exposed:** giving a 44px tap target to an element that already paints a
  background/border is a visual change, not just an accessibility one. The other entries from
  that pass (`.chips-orig`, `.mini-install .mi-btn`, `#v82tabs .v82fsw-t`) either use the
  invisible-`::after` form or are plain boxes, so they are fine - but check the paint before
  adding `min-width`/`min-height` to anything round.

## 2026-08-04 Claude (feed hides the grading/sources folds; one More on the prediction card)

june (from the phone, two screenshots): "피드창에서는 채점 예정, 출처는 노출되지 않게 해줘 /
오늘의 예측에서 더보기가 2번 보이는데 아래 더보기는 없애줘"

Changed: `index.html` only (`6be9ee5`, +8/-0). **CSS only, no JS.** No asset files, so no
cache-hash bump.

- **Grading / sources folds are detail-only now.** `gradeCardHtml()` and `srcsListHtml()` render
  `<details class="gradec-fold">` / `.srcs-fold` into `.card-body` (Codex+Claude, earlier today).
  In the compressed feed card those two collapsed headers sat right under the clipped summary, so
  「채점 예정」 and 「출처」 read before the actual text. One selector covers **both shells**:
  `#feedList > .card:not(.v83one) > .card-body > .gradec-fold, ... > .srcs-fold{display:none}`
  - Desktop detail is `#feedList > .card.v83one`, hence the `:not(.v83one)`.
  - Mobile detail lives in `#v82dbody`, outside `#feedList`, so it is untouched by construction.
  - **DOM is untouched** - only `display`. `v83CardFix` still finds `.gradec-fold` and still drops
    the duplicate one-line `.oc` badge, exactly as before.
- **Two "더 보기" on the mobile prediction card.** `dailyPredictionResultEl` appends its own
  `.v83-more.prediction-result-more` (it toggles `v83expanded`), and on mobile v82 *also* adds
  `.v82-more` for the clipped summary - so the card showed two, the second one below the
  engagement bar. On desktop there is only ever one, because `v83ClipScan` skips a card that
  already has a `.v83-more` and the prediction button carries that class.
  Fix: `@media (max-width:1023px){ .prediction-result-card .prediction-result-more{display:none} }`
  - Same specificity as the `display:inline-flex` rule above it and later in the file, so no
    `!important` needed.
  - `.v82-more` is the right one to keep: measured, it expands the summary in place
    (gist height 92px -> 168px) and then hides itself. The prediction card's own button is
    redundant on mobile anyway - the `#feedList >` scoped rules that `v83expanded` unlocks do not
    apply inside `#v82dbody`, so the mobile detail already shows everything.

Verified:
- `node --check` on all 6 inline script blocks (no JS changed, run anyway).
- Local Playwright, both shells: feed cards 1-4 all `gradec=false srcs=false`, exactly **1** 더 보기
  each (mobile `.v82-more`, desktop `.v83-more`). Normal-card detail still shows both folds
  (desktop `.v83one` and mobile `#v82dbody`). Prediction detail unchanged, 「Stacks에서 보기」 intact.
- Live stacksdaily.com: desktop feed clean, desktop detail still shows both folds, and a 390px
  same-origin iframe (`resize_window` does not work in june's Chrome) shows the mobile shell with
  5/5 cards `gradec=false srcs=false` and a single `.v82-more` on each, prediction card included.
- Actions: Clobber guard ✅ · Email render guard ✅ · pages build ✅.

Notes / next:
- Deploy needed one rebase mid-flight: `3b3d15b` (new graphic markers, +119 lines) landed 8 minutes
  before the guard ran. `deploy_guard --verify` confirmed all 119 lines survived.
- The 「채점 예정」 fold was the feed's only prediction-tracking signal, since `v83CardFix` removes
  the `.oc` badge when the fold exists. That is intended here - june asked for the feed to be
  quiet - but if a feed-level signal is ever wanted back, put it on the `.oc` badge, not the fold.

## 2026-08-04 Claude (그래픽 어휘 확장 — 표와 VS 둘뿐이던 것을 넷 더한다)

june: "우리 글을 보다보면 항상 이 vs랑 이 표가 자주 나오는데 글마다 똑같이 생겨서 다른 글들을
복사 붙여넣기 한 느낌이 든다. 표나 vs 들어가는 것 자체는 좋은데 모든 글이 이걸로 통일되니까
별로인 것 같다. 정말로 독자들의 이해를 돕는 차원에서의 그래픽이 쓰였으면 좋겠다."

Commits: `7f7f6d7`(scripts) · `3b3d15b`(index.html + CLAUDE.md). GitHub 웹 업로드로 올렸다
(이 세션은 push 자격증명이 없었다). 생성물(`p/`·`e/`·`og/`·sitemap·feed)은 커밋하지 않았다 —
`build_pages.py` 가 바뀌었으므로 og-assets.yml 이 재생성한다.

### 진단 (라이브 248장 전수 실측)

| 구간 | @@CHK@@ | @@CMP@@ | 둘 다 | 그래픽 0개 |
|---|---|---|---|---|
| 전체 248장 | 24.6% | 31.5% | 14.5% | 52.4% |
| 최근 60장 | 71.7% | 50.0% | 35.0% | 6.7% |
| **최근 20장** | **80.0%** | **50.0%** | **40.0%** | 10.0% |

취향 문제가 아니라 구조였다. ① 그릴 수 있는 형태가 표와 VS 둘뿐이었고(`@@IMG@@`는 레지스트리
키가 모자라 자주 비고 `@@REF@@`는 출처지 그래픽이 아니다) ② v4.6 `[Y]`가 원문 의존도 FAIL의
처방 1순위를 "지표를 조회해 `@@CHK@@`를 만든다"로 정해 놓아 표가 사실상 의무였다.

### 새 마커 넷 (세 렌더러 동시)

```
@@BAR@@   라벨|표시값|숫자 …@@각주@@출처   규모를 길이로. 막대 2개면 배수 배지 자동
@@SHARE@@ 라벨|표시값|숫자 …@@각주@@출처   100% 한 줄 띠 + 범례
@@TIME@@  날짜|사건 …@@각주@@출처          연표. 날짜 앞 '>' = 아직 오지 않은 일
@@FLOW@@  단계|설명 …@@각주                무엇이 어디로 가나
```

표시값(화면 글자)과 숫자(막대 길이)를 나눈 것은 `1조1,400억달러` 같은 표기를 그대로 쓰면서
길이는 정확히 그리기 위해서다. **`@@BAR@@`의 숫자 칸은 반드시 같은 단위**여야 한다.

### Changed

- `scripts/build_pages.py` — `_blk_bar/_blk_share/_blk_time/_blk_flow` + `gist_blocks()` 분기,
  `BLOCK_CSS` 에 `:root{--s1..--s4,--track,--ring}` 와 다크 오버라이드, `block_css_for()` 에
  `class="dbk` 추가.
- `index.html` — `dataBlock()` 신설 + `gistRich()` 분기 4개, `:root`/`[data-theme=dark]` 에
  계열색 변수, `.dbk/.bar-*/.shr-*/.tml/.flw-*` CSS. **순수 추가 131줄 · 삭제 0줄**
  (원격이 먼저 올린 `ffe6583` 예측카드 버튼 위에 다시 얹고 diff로 무손실 확인했다).
- `scripts/weekly_email.py` — 같은 넷을 표 + 인라인 CSS 로. flex/grid 없음, 화살표는 세로.
- `scripts/check_source_dependence.py` — `DATA_PREFIXES`(CHK·BAR·SHARE·TIME) 신설.
  **`@@CHK@@` 강제가 풀렸다.** `@@FLOW@@`는 조회한 사실이 아니라 제외. 출력은 `수치블록 n`.
- `scripts/check_editorial.py` — `blocks_of()` + `GRAPHIC`, `#13`(카드 내 같은 형태 중복) ·
  `W3`(주간 편중 상한 CHK 55% · CMP 40% · 기타 45%) · `W4`(분포 INFO) · `R4`(회차 전체가
  같은 조합).
- `scripts/check_term_coverage.py` · `scripts/build_data.py` — 마커 목록 동기화.
- `CLAUDE.md` — gist 마커표 갱신 + 렌더러가 세 곳이라는 사실 · 편중 실측치.

### 색

`--s1~--s4` 네 개. dataviz 팔레트 검사기로 **명도대 · 채도 하한 · 색각이상(적녹·청황) 인접쌍
분리 · 바탕 대비**를 통과시킨 조합이고 밝은 모드와 어두운 모드를 각각 따로 골랐다
(어두운 모드는 밝은 값의 자동 반전이 아니다 — 밝기 대역이 다르다).
**순서를 섞거나 다섯 번째 색을 만들지 않는다.** 띠 조각 안에 글자를 넣지 않는 것도 같은
이유다(색 위 흰 글자는 명암이 모자란 조합이 나온다) — 이름과 값은 범례가 본문 색으로 진다.

### Tests

- `scripts/build_pages.py` — 248 article + 552 entity pages, EXIT 0.
- `scripts/check_email_render.py` — 세 렌더러 마커 목록 일치
  (`BAR CHK CMP FLOW IMG REF SHARE TIME`), 주간 메일 렌더 통과.
- `scripts/check_editorial.py --weekly` — BLOCK 0. `W3`가 CHK 67% · CMP 49%로 **둘 다 초과**.
- `scripts/check_source_dependence.py` — 최근 2장 `ok`.
- Playwright로 밝은/어두운/모바일 3판 전체 렌더 스크린샷을 떠서 눈으로 확인
  (`@@FLOW@@`가 좁은 화면에서 세로로 흐르는 것, 다크에서 계열색이 다시 골라지는 것 포함).
- `python3 -c ast.parse` 6개 스크립트.

### Remaining risks / next

1. **`W3`가 당분간 계속 뜬다.** 최근 7일 CHK 67% · CMP 49%로 상한 초과 상태에서 출발한다.
   검사기 오류가 아니라 갈아타는 중이라는 표시다. **임계값을 올려서 끄지 말 것.**
2. **아직 새 마커를 쓴 카드가 0장이다.** 렌더는 배포됐지만 실사용은 다음 발행 회차부터다.
   `items.json이 쓰는 마커: ['CHK','CMP','IMG','REF']` 로 남아 있는 게 정상이다.
3. **소급 교체는 대기열에 있다** (june: "신규 + 최근분 점진 교체"). `claude/fix-queue.md`
   항목 P 참조 — 회차당 2~3장씩, `@@CHK@@`인데 **배수·격차가 논지인 것**부터.
4. 생성물은 이 커밋에 없다. og-assets.yml 이 도는지 확인할 것.
5. 규칙 전문은 프로젝트 `claude/prompts/publish-v4.7-graphics.md` 이고 **v4.6 헤더에 이어
   읽기 체인을 걸어 뒀다.** v4.4가 두 달간 읽힐 경로 없이 방치됐던 사고를 막기 위한 것이니
   체인을 지우지 말 것.

## 2026-08-04 Claude (「Stacks에서 보기」 button on the daily prediction card)

june: "오늘의 예측 카드에 한해서만 Stacks에서 보기 버튼 하나 더 추가해줘. 독자들이 Stacks 원래
어떤 글이였는지 궁금할수도 있으니까"

Changed: `index.html` only (`ffe6583`, +60/-3). No asset files, so no cache-hash bump.

- The prediction card **takes the article's slot in the feed** (`appendFeedPage` skips the normal
  card for that id), so before this there was no route back to the original Stacks post at all.
- New outline pill `.prediction-result-post` inserted right after the black `.original-link`
  ("원문 보기 ↗") inside `.cta-row`, so the X source and the Stacks post sit on one line.
  Copy lives in the existing `copy` object of `dailyPredictionResultEl`
  (ko `Stacks에서 보기 →` / en `View on Stacks →` / ja `Stacksで見る →`).
  **Detail only** - `.cta-row` is already hidden on the collapsed feed card in both shells, which
  is what june picked; the feed card gains nothing.
- `openStacksPost(id, ev)` (next to `openFromCard`) is the whole behaviour:
  - **Desktop.** Clear `PRED_CLICK_ID` *before* calling `v83OpenItem` - it is still set from the
    capture-phase listener, and `v83OpenItem` would otherwise re-arm `V83PRED` and reopen the
    prediction view. Then the detail re-renders from `ITEMS` as the plain article.
  - **Mobile.** The overlay holds the card *node*, so a plain card has to exist in the feed first.
    Close the overlay through the shell's own path (`history.back()` -> `v82Pop` -> `closeDetail`)
    rather than swapping the node in place: `#twcOv > .twc-sheet` is mounted **inside** that
    node's `.comment-box`, and tearing the node out takes the comment sheet with it, killing
    comments for the rest of the session. After the close the card is back in the feed, so swap it
    for `cardEl(item, STRINGS[LANG], 0)` and reopen with `v82OpenCard`. History depth is neutral
    (back 1 + `openDetail`'s `pushView` 1); scroll position is kept because the feed is not
    re-rendered.
  - Mobile side effect, accepted by june: after this the feed slot stays a normal article card
    until the next full render/reload, when the prediction card comes back.
- Mobile order: v82.css already numbers `.cta-row` children (original-link 1, paywall 3,
  lang-note 4). Default `order:0` would put the new button **before** 원문 보기, so
  `index.html`'s own `@media (max-width:1023px)` block pins it to `order:2` - no asset edit,
  no cache-hash bump.

Verified:
- `node --check` on all 6 inline script blocks.
- Local Playwright desktop 1440x1000: cta-row order `original-link / prediction-result-post /
  lang-note`; click -> `V83PRED = null`, plain article detail; Back -> feed still has exactly 1
  prediction card. Korean label renders as `Stacks에서 보기 →` next to `원문 보기 ↗`.
- Local Playwright mobile 390x820: button `order:2` and visible in the detail; click -> plain
  article detail, `.twc-sheet` still alive and still inline (`#v82dbody .twc-sheet` present),
  `history.length` delta +1 (same as a single detail open); after closing, the feed has the plain
  card, 0 prediction cards and **no duplicate `sig-` ids**.
- Live stacksdaily.com (ko): button renders, click lands on the Kobeissi article detail.
  ⚠ Needed **two** hard reloads - the service worker served the old index.html through the first
  one. Do not read that as a failed deploy; check `fetch('/index.html?cb=')` for the new string.

Notes / next:
- The comment-sheet trap is the reason for the `history.back()` hop. If anyone "simplifies" this
  to a direct `replaceChild` inside `#v82dbody`, comments die silently on mobile.

## 2026-08-04 Claude (daily prediction card -> prediction detail on desktop)

june: "오늘의 예측 글은 누르면 예측 글 상세 카드로 이동하는게 아니라 아예 원문글로 이동하는데 왜
그러지? 오늘의 예측 글 상세페이지로 이동했으면 좋겠어."

Changed: `index.html` only (`64a64fd`, +40/-2). No asset files, so no cache-hash bump.

- **Desktop-only bug.** `dailyPredictionResultEl()` paints the question headline, the
  「판정 결과 · 적중」 banner and the decision rule *on top of* a plain `cardEl()`, and the
  result keeps the source item's `sig-<id>`. Mobile `openDetail()` moves that DOM node into
  `#v82detail`, so the decoration survives. Desktop `v83OpenItem()` -> `render()` rebuilds the
  single-post view from `ITEMS` with `cardEl()`, so every prediction-specific part was dropped
  and the reader landed on the original article. Reproduced locally before touching anything.
- New `V83PRED` (id to draw in prediction form) + `PRED_CLICK_ID`, set by a **document
  capture-phase** click listener so it runs before the title `onclick`, the card-body delegate
  and the `.gist` handler - none of them pass the event down to `v83OpenItem`.
  `v83OpenItem` sets `V83PRED` only when `PRED_CLICK_ID === id`; the id compare is what stops a
  Related link *inside* the prediction card from inheriting the prediction view.
  `PRED_CLICK_ID` is cleared on a `setTimeout(...,0)` so async openers (deep links, programmatic
  calls) can never see a stale value.
- The single-post block draws `dailyPredictionResultEl(_it, S, 0)` + `v83expanded` when
  `V83PRED === V83ITEM`, else the old `cardEl`. Wrapped in try/catch: any failure falls back to
  the article card rather than an empty screen.
- `captureView`/`applyView` carry `pred`, so Back/Forward restores the prediction view instead
  of silently swapping it for the article. This rides on `6b621f5` (per-view URLs) - the URL
  itself deliberately does **not** encode `pred`, so a reload/share of that post opens the normal
  article detail, which is the behaviour june picked.

Verified:
- `node --check` on all 6 inline script blocks.
- Local Playwright, desktop `?v83beta` 1440x900: prediction card click -> `.prediction-result-card
  .v83expanded .v83one`, verdict banner "판정 결과 · 판정일 2026.07.30 / 적중", decision rule
  `display:grid`, X embed + `.cta-row` visible, "더 보기" hidden. Back -> feed still has exactly 1
  prediction card; Forward -> prediction detail again. Korean shell checked separately
  (badge/verdict/rule strings all render).
- Guard cases: normal card click, `?c=` deep link and a programmatic `v83OpenItem` all give
  `V83PRED = null` and the plain article detail.
- Mobile `?v82beta` 390x820 unchanged: card node still moves into `#v82detail` as
  `card card-lab prediction-result-card`.
- Deploy: sandbox push blocked (proxy MITM, "could not read Username") -> GitHub `edit` page
  CodeMirror dispatch. `deploy_guard --verify` clean after two rebases (`2eed2ba` 63 lines and
  `6b621f5` 159 lines both preserved); baseSha `66eaf214…` matched the editor doc before the
  patch, targetSha `67634917…` matched in the editor and again in `git show origin/main:` after
  the push.

Notes / next:
- `dailyForecastPick()` still hard-prefers `kobeissi-nasdaq-900b-selloff` (Codex, 2026-08-02);
  the fallback is the newest graded item. Nothing here depends on that choice.
- If a third shell ever renders the single-post view, it needs the same `V83PRED` branch - the
  decoration lives in `dailyPredictionResultEl`, not in the data.

## 2026-08-04 Claude (every app view gets its own URL)

june: "x를 들어가보면 좌측 패널의 메뉴마다 다 주소가 다르고 (…) 우리 사이트는 주소가 똑같은데가
많거든? 이거 혹시 문제가 없을까?" -> then "1번부터 3번까지 다해줘" (share / reload-restore / analytics).

Changed: `index.html` only (`6b621f5`, +173/-14). No asset files, so no cache-hash bump.

The app already kept a per-entry view snapshot (`captureView`/`pushView`/`applyView`, 2026-07-25),
but `pushState`/`replaceState` were called with two arguments, so every screen shared `/`.

- New `viewUrl(v)` translates that existing snapshot into a path. `noteView()` now passes it as
  the third argument on **every** render (it used to write the snapshot only into an empty entry,
  which left the URL stale on paths that change the screen without `pushView` - closing an
  article with the `‹` button was the visible one).
  Map: item `?c=<id>` · entity `?e=<key>` · record `#record-<src>` · scoreboard `#record` ·
  themes `#themes` / `#theme-<k>` · `#read` `#bookmarks` `#browse` `#skew` `#calendar`
  `#alerts` `#following`. `?l=` is preserved from the boot URL.
- `handleDeepLink()` reads all of them back. **It reads `STK_BOOT` (a boot-time snapshot of
  `location.search`/`.hash`), not `location`** - `bootData()` runs `render()` before
  `handleDeepLink()`, so by then the address bar has already been rewritten to `/`.
  Same reason `showIntro()`'s `#sig-`/`#comments-` deep-link test now reads `STK_BOOT.h`.
- `#browse`/`#skew`/`#alerts` are desktop-nav screens with no mobile counterpart, so on the v82
  shell those hashes are ignored (home) rather than rendering an empty feed.
- Mobile detail is an overlay (`#v82detail`) with no render behind it, so `captureView` gained
  `mitem` (read off the moved card's `sig-<id>` element id) and a MutationObserver stamps the URL
  when it opens. **It must be deferred (~180ms):** `v82MountComments` opens and closes the twc
  sheet, and that close is `silentBack()`, which rewinds the URL you just wrote. A `popstate`
  listener re-stamps if the detail is still open. Closing is deliberately not handled - the
  browser restores the previous entry's URL by itself.
- Analytics: one debounced (900ms) GoatCounter pageview per URL change, plus `document.title` set
  to the article title on detail views. Deferred by a tick because `applyMetaLang` rewrites the
  title during render. The first load is not counted (count.js already does it).
- **Search is deliberately not addressable.** `viewUrl` returns the root for a query view, so no
  reader's search text lands in the URL, in Clarity's page list, or in GoatCounter - that would
  have needed a `privacy.html` processor-table review.

Verified:
- `node --check` on all 6 inline script blocks (the 7th block is JSON-LD).
- Local Playwright, both shells: 13/13 URLs restore on reload (desktop), 7/7 (mobile, including
  the three that should be ignored); back x4 / forward x4 restore the same screens as before;
  `?l=ko` survives every hop; typing in search adds 0 history entries; `#sig-` still scrolls and
  is left in the URL; comment sheet still closes on the first Back and the article on the second;
  JS errors 0 in every run.
- Live stacksdaily.com after pages deploy: desktop nav writes `#browse`/`#skew`/`#bookmarks`,
  `?c=` + Korean article title on the article view, `/#bookmarks` reload lands on 북마크,
  and a 390px same-origin iframe shows the mobile detail writing `?c=<id>`.
- Deploy: sandbox push blocked (proxy MITM, "could not read Username") -> GitHub `edit` page
  CodeMirror dispatch. **origin/main moved twice mid-flight** (`48e944d`/`dd60763` mobile tap
  targets, then `2eed2ba` entity-matcher). Rebased both times; `deploy_guard --verify` confirmed
  all 63 lines of `2eed2ba` survived. Line-patch spec 9 hunks / 8,596 chars = 7 chunks, chunk
  sha 7/7 + spec sha + base sha + target sha all matched first try, 0 re-sends. Clobber guard,
  Email render guard and pages build all success.

Notes / next:
- The mobile 탐색 허브 and its skew subview still have no URL (they are v82-only screens tracked
  in `HUB_SUB`, outside `captureView`). Desktop `#skew` covers the same content.
- No lock was taken in `claude/WORK-LOCK.md`; `deploy_guard` was run before the work, before the
  patch and again immediately before the commit instead. Another agent was committing to
  `index.html` throughout - if that keeps up, take the lock.
- Canonical was left alone: it still self-references `/?l=xx`, so `?c=`/`?e=` URLs consolidate to
  the root exactly as before. Pointing an open article's canonical at its `/p/<id>.html` page is
  the obvious next SEO step, but it needs a per-language existence check first.

## 2026-08-04 Claude (index coverage: matcher rules + name checking + per-paragraph relinking)

june: "최근 올라온 글들을 보면 전문용어나 인물명 기업명 등등 대부분 색인이 하나도 안 되어
있는데 왜 그런거야?" then "5개 모두 고쳐야돼 / 같은 용어는 카드당 한번만 링크되는 것도
고쳐줘 / 예약 발행할 때부터 근본적으로 색인된 상태로 발행될 수 있도록 해야해."

### Diagnosis first: the engine was fine
Playwright against a local copy: **rendered `.has-tip` count equals the item's `ents` count,
card for card**. Nothing was broken in `linkifyEntities`. Everything missing was simply never
registered, and the gate that was supposed to catch that (`[5-B]`) only looked at glossary
terms. `schiff-strategy-btc-sale-strc-buyback` shipped with its three subjects (스트래티지,
마이클 세일러, 비트코인) all unindexed and still passed with exit 0.

### Changed
- `index.html` — three matcher changes, all mirrored in the Python builders:
  1. `entityAliasList()` folds the **entity key** in as a name (trailing parenthetical
     stripped, `_`-bearing synthetic keys skipped). `STRATEGY` had aliases
     `MicroStrategy / 마이크로스트래티지 / マイクロストラテジー` only, so the word the cards
     print never matched.
  2. `aliasIsCaseSensitive()` + a second regex `ENT_RE_CS`. All-caps Latin aliases now match
     case-sensitively. The term `PER` was matching the English preposition **per** in 55 of
     245 cards (`155 per dollar`); `NOR`/`nor`, `HYPE`/`hype`, `FORM`/`form` too.
     `ALIAS2KEY` holds both maps (exact spelling for CS, lowercase otherwise) and
     `aliasKey()` reads them. `itemEntities` and the `tally()` in the main-key ranking run
     both regexes.
  3. `dedupScope()` — the "link a term once" scope moved from the whole container to the
     paragraph (`p`/`h4`/`li`/`.chk-*`/`.cmp-c`). A 450-word summary used to light up only in
     its first line. Measured: 27/11/8/11/16 links → 57/31/33/19/36.
     Cost: ~3ms per card unthrottled for all three passes (was two passes); the existing 8ms
     drain slicing keeps it off the critical path.
- `scripts/build_data.py` — `entity_alias_list()`, `alias_is_case_sensitive()`,
  `alias_key()`, and `_TwoCaseMatcher` so `build_entity_matcher()` still returns one object
  with `.finditer()`. **These two helpers are the single source of truth for all three matchers.**
- `scripts/build_pages.py` — `build_matcher()` imports both helpers via `_build_data()` (with a
  local fallback so a missing build_data degrades instead of crashing); the glossary merge now
  also **unions aliases into entities that already exist**, so a rename can be fixed from
  `glossary.json` alone. `items.json` is the publishing routine's file and must not be edited
  by other sessions — this was the only safe path.
- `scripts/check_term_coverage.py` — merged on top of Codex's `bb09526` (kept its URL/TLD
  regex, unit tokens, media stopwords, and the `출하가` removal). Added the **`[이름]` pass**:
  titles-suffixed people, org-suffixed institutions, and line-initial subjects of reporting
  verbs, minus a Korean media list, country/region names and common nouns. Both `[용어]` and
  `[이름]` block. Also reads `term_stopwords.json`.
- `glossary.json` — merged with Codex's 16 new terms; added 15 of my own (국채·담보·레포·환율·
  공동 개입·공시·비트코인·보통주·배당률·취득단가·시간외 거래·한국은행·MCKINSEY·마이클 세일러·
  S&P GLOBAL) plus an alias patch for `STRATEGY` (스트래티지·ストラテジー·MSTR·Strategy Inc).
  **Dropped `출하가`** after reading Codex's note — every live use is 출하 + the subject particle 가.
- `term_stopwords.json` (new) — the permanent `--allow` registry the fix-queue kept asking for.
  Bare `S&P` lives here: it is ambiguous between the index and the ratings agency, and both are
  now indexed under their full names.
- `CLAUDE.md` — the three matcher rules written down as one block, with the warning that the
  three implementations must move together.
- Project doc `claude/prompts/publish-v4.6-editorial.md` — new section **[Y] 색인**: names are
  now a blocking check, alias rules (Korean transliteration required, renames add rather than
  replace, all-caps acronyms are case-sensitive), register into `items.json` entities in the
  same round, plus two `[H-3]` checklist lines and a `(k)` report extension.

### Tests run
- `build_pages.py` + `build_data.py` clean; 248 items, 552 entity pages, no hash-suffixed slugs
  (the 담보 entry needed a Latin alias or its slug degenerated to `k-17b7e98d`).
- `check_term_coverage.py --latest 40`: 5 candidates left, all genuine new tokens
  (V8 · V9 · BiCS10 · Elec · trade), **zero `[이름]` false positives**.
- `check_editorial.py --ids ...`: BLOCK 0.
- Before/after matcher diff over 80 cards: ents/card 12.01 → 11.75 (code alone) → 12.18 (with
  the new glossary). Everything the code dropped was a false positive: PER×18, FORMFACTOR×3
  (English "form"), NOR×2 ("nor"), 하이퍼리퀴드×1 ("hype"). Gained ETF×3, 넥스트레이드×1 from
  key folding.
- Playwright desktop + iPhone 13, feed and detail overlay, no console errors.

### Remaining risks / next
- `items.json` is **not** part of this change set. `og-assets.yml` merges `glossary.json` into
  it on the runner (Codex's `ff96217` added glossary.json to that workflow's trigger paths).
  If that job does not run, the new terms exist in `glossary.json` but not yet in the app.
- The three matchers are now coupled through `build_data.py`. Editing one without the others
  will silently split app indexing from SEO-page indexing.
- Short all-caps aliases that a card writes in mixed case will now miss. `FormFactor` is
  already covered by its own mixed-case alias; watch for others as they show up.
- `term_stopwords.json` is outside the publishing routine's commit whitelist by design —
  interactive sessions own it.

## 2026-08-04 Claude (person detail name -> that person's related posts)
june: "인물 상세에서도 인물명을 누르면 인물 관련 글로 이동하게 해줘." (follow-up to the entity-rail
change earlier the same day.)

Changed: `index.html` only (`7f7184d`, +28/-1). No asset files, so no cache-hash bump.

- `ceoTap()`'s `.ceo-detail` box renders its `<b>name</b>` as `<button class="ceo-detail-name">`
  wired to `entityFeedView(key)` when the person resolves to an indexed entity.
- New `ceoEntityKey(name)` does the resolving: `ENTITIES[name]` -> `ALIAS2KEY[ko name]` ->
  `ALIAS2KEY[CEO_WIKI[name]]` (the English form). It reuses `ALIAS2KEY`, the lowercase alias
  dictionary `buildEntityMatcher()` already fills - do not build a second alias table here, the
  two would drift.
- **It returns null unless the entity has at least one article.** Only about a third of the 26
  `CEO_INFO` people exist in the index (verified against `data/core.json`: 젠슨 황, 최태원, 팀 쿡,
  일론 머스크, 사티아 나델라, 마크 저커버그, 데미스 하사비스, 순다르 피차이 resolve; 이재용, 샘 올트먼,
  곽노정, 웨이저자 and the rest do not). A search fallback was measured and rejected - a plain text
  search for those names returns 0 or 1 items, so it would land the reader on an empty screen.
  Those names stay a plain `<b>`, exactly as before.
- CSS `.ceo-detail-name` only strips button chrome and restores `display:block` +
  `font-weight:700` so it is visually identical to the `<b>` it replaces (measured: block,
  700, 13px in both shells).

Verified:
- `node --check` on all 6 inline script blocks.
- Local Playwright, ko, both shells (desktop `?v83beta` 1440x900, mobile `?v82beta` 390x820):
  resolver returns the expected keys/nulls; NVIDIA entity view -> tap CEO -> `.ceo-detail`
  renders a BUTTON; clicking it lands on `ENTITY_VIEW = "Jensen Huang (@JensenHuang)"` with the
  "관련 글 보기" bar (desktop `.v83post-title`, mobile `#v82subbar .ti`) and 3 cards.
- Deploy: same route as `43e911f` (sandbox push blocked -> GitHub `edit` page CodeMirror
  dispatch). `deploy_guard` clean, base sha 327a2600… matched `git show origin/main:` before
  dispatch, target sha 8a04b9fe… matched after, pushed blob identical to the local file.
  Clobber guard success. `git diff --numstat 7666214 7f7184d` = 28/1, the single deletion being
  the `ceo-detail-txt` line that was replaced.
- Live stacksdaily.com after pages deploy: same flow end to end.

Notes / next:
- If a CEO should be clickable but is not, the fix is data, not code: give that person an entity
  (or an alias on an existing one) and `ceoEntityKey` picks it up on the next build.
- The `.ceo-link` in the facts row is unchanged - it still opens/closes the detail box. Only the
  name *inside* the box navigates.

## 2026-08-04 Claude (entity rail name -> related posts, "관련 글 보기" top bar)
june: "우측 패널에서 이름을 누르면 해당 기업·인물·전문용어 등의 관련글 보기로 이동하게 해줘.
그리고 관련 글 보기로 이동하면 지금 쏠린 곳 상단바처럼 뒤로가기 우측에는 관련 글 보기라고 써줘."

Changed: `index.html` only (`43e911f`, +23/-1). No asset files, so no cache-hash bump.

- `entityHeadEl(key, S, count, "rail")` now renders `.eh-name` as a `<button class="eh-name
  eh-name-go">` wired to `entityFeedView(key)` - the same destination as the existing
  "관련 글 N개 보기 →" link, so there is one funnel and no new state. `mode === "feed"` keeps the
  plain `<div>`: that header *is* the related-posts screen, so it is not a target.
- CSS `.entity-head .eh-name-go` only strips button chrome. It deliberately does not set
  `font-size`/`font-weight` - `.entity-head .eh-name` (20px) and `.entity-head.in-rail
  .eh-name` (17px) keep owning that, so the rail name looks byte-identical to before.
- The shared back+title bar (the block that already draws "‹ 지금 쏠린 곳", "‹ 알림 설정" etc.)
  now also detects `#feedList > .entity-head` and titles it 관련 글 보기 / Related posts /
  関連記事. Label is built in that IIFE (`relLabel()`) rather than read from `STRINGS`, matching
  `bmLabel()` - the bar can sync before `STRINGS` is reachable.
- `hideOwnTitle()` additionally collapses `#feedList > .entity-head > .series-close`, because
  the new bar already carries the back arrow. The entity name inside the profile card stays.
- One `detect()` clause covers both shells: desktop draws `.v83post-head.v83navback`, mobile
  fills `#v82subbar` and sets `nav.nav-sub` (which hides the 최신/팔로잉 switcher), same as every
  other left-menu page.

Verified:
- `node --check` on all 6 inline script blocks.
- Local Playwright, ko, both shells: desktop 1440x900 `?v83beta` - rail name is a BUTTON with
  class `eh-name eh-name-go`, click lands on ENTITY_VIEW, bar title "관련 글 보기", bar is
  `firstElementChild` of `#feedList`, in-card `.series-close` computed `display:none`, 56 cards.
  Mobile 390x780 `?v82beta` - `#v82subbar .ti` = "관련 글 보기", `nav.nav-sub` true. `history.back()`
  clears ENTITY_VIEW and removes the bar in both.
- Deploy: sandbox push blocked (proxy MITM, "could not read Username") -> GitHub `edit` page
  CodeMirror dispatch. `deploy_guard` clean beforehand; editor base sha256 compared against
  `git show origin/main:index.html` (08ce7ba6…) before dispatch and target sha (327a2600…)
  after - both matched, and the pushed blob hashes identical to the local file.
  Clobber guard success. `git diff --numstat 619e240 43e911f` = 23/1, the single deletion being
  the `.eh-name` line that was replaced.
- Live stacksdaily.com after pages deploy: rail name is a button, click -> "‹ 관련 글 보기" bar
  over the SK HYNIX profile + 57 cards, back returns to the feed.

Notes / next:
- Pressing back from the related-posts screen returns to the feed, not to the open rail panel.
  That is the pre-existing behaviour of the rail's own `pushView()` snapshot and is identical
  to what the "관련 글 N개 보기 →" button already did; not touched here.
- `deploy_guard --verify` run without a prior recorded base falls back to a 24h window and
  reported a stale ❌ for `97aedd6` (`.gradec h4` lines). Those lines were already absent in the
  base `619e240`, so it is a false positive of the fallback, not a clobber.

## 2026-08-04 Claude (term-index sweep: 16 glossary terms, checker false-positive cuts)
june: "최근 색인 안된 글들 많은데 색인 안된 글들 이번만 수동으로 갱신해줘. 그리고 이제부턴
예약작업 자동발행 파이프라인에서 색인 체크하고 자동 발행하는거지?" (색인 = the in-app
term/entity index, confirmed with him - not Google Search Console.)

Changed: `glossary.json` (`9453251`, +392) · `.github/workflows/og-assets.yml` (`ff96217`, +3) ·
`scripts/check_term_coverage.py` (`bb09526`, +46/-5). All three clobber-guard green.

**Answer to the second question: yes, since 2026-07-28.** Publish v4.3 `[5-B]` runs
`check_term_coverage.py --ids <cards touched this round>` and forbids committing until it exits
0. The autopublish loader has no section-range limit, so that clause is actually read. What it
does *not* cover is anything published before 07-28 or any card a later round never touches -
hence this one-off sweep.

### What was actually missing
A full scan of the 245 live cards reported 118 [GAP] cards / 383 candidates, but most were noise:
- body URLs leaking domain fragments (`com`, `xyz`, `trade`, `note`, `to5Mac`)
- outlet names and units (`Fortune`, `China Daily`, `km`, `kHz`, `Mbps`)
- **already-registered terms whose token got cut**: the `bp` in `25bp`, the `GW` in `1.5GW` (19)
- genuinely unregistered terms: **16**

After the fixes: **118 -> 95 GAP cards, 383 -> 211 candidates, newest 12 exit 0.**

### Registered (glossary.json, kind=term, ko/en/ja)
AGI · LLM · GPT · 클린룸 · 식각 · 본딩 · 서브스트레이트 · 장기물 · 매그니피센트7 · NISA ·
최종투자결정(FID) · PCB · DIMM · PIM · SEC · MSCI — **71 new links across 31 live cards**,
pre-checked by running `build_pages.build_matcher` over every card body.

**`출하가` was deliberately NOT registered.** Both live occurrences are "출하" + the subject
particle "가" ("루빈 울트라 2027년 출하가 갈리는 지점"), so a term entry would attach a price
tooltip to the wrong words. It was removed from the checker's WATCHLIST too - that closes
fix-queue checker request 3, and the rule is now "drop it from the watchlist, don't `--allow` it".

### Checker changes (`bb09526`)
- Strip URLs before scanning, **TLD allow-list only**: an open `\.[A-Za-z0-9-]+` also eats
  `1.5GW` and `V3.1`, silently shrinking coverage. The first draft did exactly that.
- Skip latin fragments that start right after a digit; the whole token (`25bp`) is still caught
  by `HAS_DIGIT_PREFIX`, so nothing leaves the scan.
- STOPWORDS: ~20 outlet names + `Asia` + the words that make up multi-word mastheads. `ARR` is in
  there because `index.html`'s inline GLOSS covers it and this checker cannot see that table.
- WATCHLIST: `액침`/`자사주` in (fix-queue request 2), `출하가` out.

### Wiring bug fixed along the way (`ff96217`)
`build_pages.py` merges `glossary.json` into `items.json` entities, but `glossary.json` was not in
og-assets' push paths — new terms would sit invisible until the 6-hourly cron. Added the path, and
dispatched the workflow manually for this batch.

Verified: 16/16 merged into `items.json` and `data/core.json` (entities 528 -> 544); on live
stacksdaily.com `ALIAS2KEY` resolves 클린룸/기판/본딩/식각 and a new term (`메모리 모듈` -> DIMM)
renders as a real tooltip in a feed card.

Left for someone with items.json write access — see fix-queue **item R**: alias additions
(`S&P 500`←`S&P`, `액침 노광`←`액침`, `NEBIUS`←`NBIS`, `SK HYNIX`←`SKHY`, `TRUMP MEDIA`←`TMTG`),
new company entities (xAI, Innolight, Marvell, TDK, KKR, EQT), and two structural notes:
**(a)** the alias boundary rule hides digit-prefixed units (`25bp`, `1.5GW`) — fixing it means
changing `buildEntityMatcher` / `build_matcher` / `build_entity_matcher` together, deferred for
the September gate; **(b)** the routine's duplicate check must include `glossary.json` — two of
the 12 duplicate pairs in fix-queue item Q were created exactly that way.

## 2026-08-04 Claude (mobile 44px tap targets)

june: Clarity 8/4 세션 리뷰 후속. "32px 미만 탭 타깃 키우기" 승인 건.

Changed: `assets/v82.css` (`48e944d`, +49/-0, pure append) + `index.html` cache hash only
(`dd60763`, v82.css `d1f9ef68` -> `79b64196`).

- 새 블록은 전부 `@media (max-width:1023px)` 안이다. **데스크톱은 한 픽셀도 안 바뀐다**
  (1280px에서 44px 미만 타깃 수 127/156, 패치 전후 동일 — 실측).
- 키운 것: `.engage .eg` 29x29 -> 44x44(가운데 `.eg-spacer{flex:1}`가 늘어난 폭을 흡수해
  좌/우 그룹 정렬 유지) · `.v82-more`/`.v83-more` · `.gradec-fold>summary`/`.srcs-fold>summary`
  (이미 flex+align-items:center라 마커 영향 없음) · `.mi-close` · `#v82av` · `.v82fsw-t` ·
  `.mi-btn` · `.entity-tip .tip-follow` · `.srcs-list li a` · `.foot-links a`.
- **`.chips-orig`(원문 보기)만 예외** — 검은 알약이 눈에 보이는 요소라 상자를 키우면 생김새가
  바뀐다. `::after{position:absolute;top:-8px;bottom:-8px}`로 **보이지 않는 히트 영역만 위아래로**
  넓혔다. 좌우는 옆 태그 칩과 겹치므로 건드리지 않았다.
- 대가: 390px 문서 높이 4653 -> 5128px(+10.2%), 카드 높이 626/756/416 -> 697/826/469.
  스크롤 깊이 지표가 그만큼 내려갈 수 있으니 다음 Clarity 판독 때 감안할 것.

Verified:
- 로컬 Playwright 390px: 44px 미만 타깃 124 -> 38 (남은 것은 X 임베드 내부 링크, 사진 크레딧,
  접힌 `.gcard`(높이 2px 클리핑 아티팩트), 폭만 44 미만인 푸터 링크 — 전부 부수적).
- **탭 도둑질 없음**: `.engage`의 모든 `.eg`에 대해 중심·좌·우·상·하 5점 `elementFromPoint`가
  전부 자기 자신을 반환. `.engage` 위/아래 6px 지점에 링크·버튼 없음. 가로 오버플로 없음.
- `.chips-orig` 히트 영역: 로컬에서 알약 위/아래 5px 지점이 `a.chips-orig`를 반환(상자는 135x29 유지).
- 배포: 샌드박스 push 차단(프록시 MITM) -> GitHub `edit` 페이지 CodeMirror dispatch.
  v82.css는 3조각 평문 전송(조각 sha 3/3), baseSha `d1f9ef68` -> targetSha `79b64196` 사전·사후 일치.
  index.html은 단일 문자열 치환(등장 1회 확인, deltaBytes 0).
- `deploy_guard`가 **실제로 한 번 막았다** — 38분 전 `7f7184d`(index.html +26줄)가 올라와 있었다.
  reset --hard origin/main -> 재적용 -> `--verify`로 26줄 보존 확인 후 배포. Clobber guard 2건 success.
- 라이브 stacksdaily.com 390px iframe: `link href=v82.css?v=79b64196`, `.eg` 42개가 44x44/48x44,
  44px 미만 37/134, 가로 오버플로 없음, `::after` 규칙 적용 확인.

Notes / next:
- `.chips-orig`·`.brand`·X 임베드 내부 링크·사진 크레딧 링크는 의도적으로 남겼다(생김새 우선).
- WORK-LOCK 보드에 **정식 락을 잡지 않았다.** 45KB 문서를 통째 재작성하다 훼손할 위험이
  락 이득(15분 창)보다 크다고 판단했다. 대신 `deploy_guard` + `edit` 페이지 라이브 문서 베이스로
  클로버를 구조적으로 차단했고, 실제로 위 `7f7184d` 건을 잡아냈다.

## 2026-08-04 Claude (person detail name -> that person's related posts)
june: "인물 상세에서도 인물명을 누르면 인물 관련 글로 이동하게 해줘." (follow-up to the entity-rail
change earlier the same day.)

Changed: `index.html` only (`7f7184d`, +28/-1). No asset files, so no cache-hash bump.

- `ceoTap()`'s `.ceo-detail` box renders its `<b>name</b>` as `<button class="ceo-detail-name">`
  wired to `entityFeedView(key)` when the person resolves to an indexed entity.
- New `ceoEntityKey(name)` does the resolving: `ENTITIES[name]` -> `ALIAS2KEY[ko name]` ->
  `ALIAS2KEY[CEO_WIKI[name]]` (the English form). It reuses `ALIAS2KEY`, the lowercase alias
  dictionary `buildEntityMatcher()` already fills - do not build a second alias table here, the
  two would drift.
- **It returns null unless the entity has at least one article.** Only about a third of the 26
  `CEO_INFO` people exist in the index (verified against `data/core.json`: 젠슨 황, 최태원, 팀 쿡,
  일론 머스크, 사티아 나델라, 마크 저커버그, 데미스 하사비스, 순다르 피차이 resolve; 이재용, 샘 올트먼,
  곽노정, 웨이저자 and the rest do not). A search fallback was measured and rejected - a plain text
  search for those names returns 0 or 1 items, so it would land the reader on an empty screen.
  Those names stay a plain `<b>`, exactly as before.
- CSS `.ceo-detail-name` only strips button chrome and restores `display:block` +
  `font-weight:700` so it is visually identical to the `<b>` it replaces (measured: block,
  700, 13px in both shells).

Verified:
- `node --check` on all 6 inline script blocks.
- Local Playwright, ko, both shells (desktop `?v83beta` 1440x900, mobile `?v82beta` 390x820):
  resolver returns the expected keys/nulls; NVIDIA entity view -> tap CEO -> `.ceo-detail`
  renders a BUTTON; clicking it lands on `ENTITY_VIEW = "Jensen Huang (@JensenHuang)"` with the
  "관련 글 보기" bar (desktop `.v83post-title`, mobile `#v82subbar .ti`) and 3 cards.
- Deploy: same route as `43e911f` (sandbox push blocked -> GitHub `edit` page CodeMirror
  dispatch). `deploy_guard` clean, base sha 327a2600… matched `git show origin/main:` before
  dispatch, target sha 8a04b9fe… matched after, pushed blob identical to the local file.
  Clobber guard success. `git diff --numstat 7666214 7f7184d` = 28/1, the single deletion being
  the `ceo-detail-txt` line that was replaced.
- Live stacksdaily.com after pages deploy: same flow end to end.

Notes / next:
- If a CEO should be clickable but is not, the fix is data, not code: give that person an entity
  (or an alias on an existing one) and `ceoEntityKey` picks it up on the next build.
- The `.ceo-link` in the facts row is unchanged - it still opens/closes the detail box. Only the
  name *inside* the box navigates.

## 2026-08-04 Claude (entity rail name -> related posts, "관련 글 보기" top bar)
june: "우측 패널에서 이름을 누르면 해당 기업·인물·전문용어 등의 관련글 보기로 이동하게 해줘.
그리고 관련 글 보기로 이동하면 지금 쏠린 곳 상단바처럼 뒤로가기 우측에는 관련 글 보기라고 써줘."

Changed: `index.html` only (`43e911f`, +23/-1). No asset files, so no cache-hash bump.

- `entityHeadEl(key, S, count, "rail")` now renders `.eh-name` as a `<button class="eh-name
  eh-name-go">` wired to `entityFeedView(key)` - the same destination as the existing
  "관련 글 N개 보기 →" link, so there is one funnel and no new state. `mode === "feed"` keeps the
  plain `<div>`: that header *is* the related-posts screen, so it is not a target.
- CSS `.entity-head .eh-name-go` only strips button chrome. It deliberately does not set
  `font-size`/`font-weight` - `.entity-head .eh-name` (20px) and `.entity-head.in-rail
  .eh-name` (17px) keep owning that, so the rail name looks byte-identical to before.
- The shared back+title bar (the block that already draws "‹ 지금 쏠린 곳", "‹ 알림 설정" etc.)
  now also detects `#feedList > .entity-head` and titles it 관련 글 보기 / Related posts /
  関連記事. Label is built in that IIFE (`relLabel()`) rather than read from `STRINGS`, matching
  `bmLabel()` - the bar can sync before `STRINGS` is reachable.
- `hideOwnTitle()` additionally collapses `#feedList > .entity-head > .series-close`, because
  the new bar already carries the back arrow. The entity name inside the profile card stays.
- One `detect()` clause covers both shells: desktop draws `.v83post-head.v83navback`, mobile
  fills `#v82subbar` and sets `nav.nav-sub` (which hides the 최신/팔로잉 switcher), same as every
  other left-menu page.

Verified:
- `node --check` on all 6 inline script blocks.
- Local Playwright, ko, both shells: desktop 1440x900 `?v83beta` - rail name is a BUTTON with
  class `eh-name eh-name-go`, click lands on ENTITY_VIEW, bar title "관련 글 보기", bar is
  `firstElementChild` of `#feedList`, in-card `.series-close` computed `display:none`, 56 cards.
  Mobile 390x780 `?v82beta` - `#v82subbar .ti` = "관련 글 보기", `nav.nav-sub` true. `history.back()`
  clears ENTITY_VIEW and removes the bar in both.
- Deploy: sandbox push blocked (proxy MITM, "could not read Username") -> GitHub `edit` page
  CodeMirror dispatch. `deploy_guard` clean beforehand; editor base sha256 compared against
  `git show origin/main:index.html` (08ce7ba6…) before dispatch and target sha (327a2600…)
  after - both matched, and the pushed blob hashes identical to the local file.
  Clobber guard success. `git diff --numstat 619e240 43e911f` = 23/1, the single deletion being
  the `.eh-name` line that was replaced.
- Live stacksdaily.com after pages deploy: rail name is a button, click -> "‹ 관련 글 보기" bar
  over the SK HYNIX profile + 57 cards, back returns to the feed.

Notes / next:
- Pressing back from the related-posts screen returns to the feed, not to the open rail panel.
  That is the pre-existing behaviour of the rail's own `pushView()` snapshot and is identical
  to what the "관련 글 N개 보기 →" button already did; not touched here.
- `deploy_guard --verify` run without a prior recorded base falls back to a 24h window and
  reported a stale ❌ for `97aedd6` (`.gradec h4` lines). Those lines were already absent in the
  base `619e240`, so it is a false positive of the fallback, not a clobber.

## 2026-08-04 Claude (Clarity review: desktop CLS 1.68 -> 0.04, alignFsw layout thrash)
june asked for a read on the Clarity dashboard and then for the top three fixes to be done.
Clarity (last 7 days): score 49/100, LCP 1.9s good, INP 530ms bad, **CLS 1.2 bad**, dead
clicks 4.92%, 0 JS errors. Referrers over 7 days: 25 internal, 5 github.io, **4 google, 3 t.co**.
Bots were 63 of 185 sessions; today 15 of 21.

### A. CLS was desktop-only, and it was the shell mount
Changed: `index.html` (`ad9e29f4`, then `08ce7ba6`)

- Reproduced with local Playwright: desktop 1.68, mobile 0.002. One shift was 0.99 of it —
  `.wrap` growing 102px -> 800px with the footer inside the viewport, because both the v83
  shell (mountV83) and the feed are built by JS after first paint.
- `html.stkboot` reserves the main `.wrap` at 100vh and holds it hidden, hides the footer;
  `html.stkbootr` additionally holds the right rail, which keeps reflowing for a few hundred
  ms after the feed paints (the newsletter box only unhides once its data lands).
- Released on the **first feed render**, not on applyDash. applyDash runs before the feed data
  arrives — releasing there measured as no improvement at all (html.stkboot was already gone
  at 230ms while the shift happens at ~540ms). The rail follows 700ms later.
- **The live check caught a second bug**: the release waited on two rAFs, and rAF is frozen in
  a background tab, so a page opened in the background stayed blank until the failsafe — the
  exact moment a reader switches to it. `relSoon()` now releases immediately when
  `document.visibilityState === "hidden"`. Do not put a plain timer there instead: a 300ms
  race fired before the feed landed and CLS went back to 0.35.
- Failsafes: load + 1500ms, and 6s/6.5s timeouts. Any throw before the release must still end
  with a visible page.

### B. alignFsw was the largest main-thread cost of a cold load
Changed: `assets/v83tw.js` (`94fc844c`), cache hash bumped in `index.html`

- CDP profiling (4x CPU): `alignFsw` 677ms of self time, ahead of everything else. It read two
  bounding rects and wrote three inline styles unconditionally, 12 times at 400ms apart —
  a read/write/read cycle forcing a full layout of a 660KB document each round.
- Now it skips the write when the geometry has not moved, and hands off to a `ResizeObserver`
  on `#v83center` as soon as that element exists. The poll remains as the fallback where
  ResizeObserver is missing, and stops after 3 consecutive no-ops.
- 677ms -> 184ms. Total load long-task time 1678ms -> 1468ms.

### Not changed (checked, and deliberately left alone)
- The Pretendard CDN CSS is **already** async — `preload` + `onload` with a `noscript`
  fallback. A DOMParser read of the page makes it look render-blocking because it parses
  inside `<noscript>`; it is not.
- `linkifyPass` is now the top remaining hotspot (~520ms, the entity-matcher regex). It is the
  entity index and touching it is out of scope for the September gate.

Verified (local server + chromium 1280x800 and 390x844, ko):
- desktop CLS 0.042-0.059 across runs, mobile 0.005, LCP 672 -> 644ms local, 0 page errors.
- After boot: footer, right rail and .wrap all visible; 6 cards in both shells; `#v83fsw`
  still aligned to `#v83center` (dLeft 1px / dWidth -2px, unchanged from before).
- Live stacksdaily.com after deploy: same, including in a background tab.
- Every commit deployed by sha256 — editor base sha compared against `git show origin/main:`
  before dispatch, target sha compared after. All 3 matched. Clobber guard success.

Remaining risks / next:
- Clarity needs ~7 days before the field CLS/INP numbers reflect this. Re-check around 8/11,
  not sooner — the dashboard averages the window.
- The remaining desktop shift (~0.03) is `#v83fsw` insertion pushing `#feed` down 53px. Cheap
  to reserve if it ever matters; left alone for now.
- Growth, not perf, is the real number here: 7 external referrals in 7 days.

## 2026-08-04 Claude (A: theme trajectories · B: weekly skew trend on mobile)
june's framing, which replaces the one I was working from: concentration - of stance or of
sector - is not a defect to correct. "요즘 유행하는 섹터가 반도체라면 당연히 유행따라 섹터쏠림도
나오는거니까." What the site owes the reader is the movement over time: how much more skewed
this week is than last, and what this author said about the same subject before. Both of the
correction mechanisms I had built (opposites queue, sector gate) were deleted for this.

### A. Author trajectory now also pairs on a declared theme
Changed: `scripts/build_data.py` (`38e31a3a`), `scripts/build_pages.py` (`3201c81a`),
`index.html` (`b2dc029b`)

- `pick_priors()` used to pair only on a shared ticker, so macro writers (메르, Kobeissi,
  Doomberg) never got a trajectory - they rarely name a ticker twice.
- New: `PRIOR_THEME_MAX_SHARE = 0.15` + `declared_theme_hay()`. A theme is eligible as a pairing
  axis only if it covers under 15% of the corpus, and only tags + the cover label count as a
  declaration. Eligible today: crypto, dollar, energy, rates, trade. semis/aicapex are too broad
  to mean anything as a pair.
- Do NOT widen this to the body or the title. Two earlier attempts are why the threshold exists:
  a body scan put NAND next to MLCC under "energy", and adding titles let "100억달러" pollute
  `dollar`.
- Result: priors 40 -> 69 of 242 (40 by ticker, 29 by theme). Rendering says "같은 테마, 이 저자의
  이전 글" with the theme chip, not the ticker chip - `prior.kind` carries which.

### B. The weekly skew trend is now on mobile
Changed: `assets/v82.js` (`29b1f375`), `assets/v82.css` (`2e965114`), `index.html` (`b837f60e`)

- v83 is already the default desktop shell, so 지난주→이번 주 was visible there. Mobile only had a
  current-state bull/bear bar, which is where most readers actually are.
- New `skewTrendHtml()` at the top of 탐색 → 지금 쏠린 곳: a 지난주→이번 주 hero pair, then a
  6-row ranking with ▲▼/NEW rank movement. Rows open the theme.
- It calls `v83ThemeAttention()` from index.html rather than recomputing. If the two shells ever
  compute the skew separately they will disagree, and the reader sees two different numbers for
  the same week. Guarded by `typeof` - if the global is missing the block is silently omitted.
- The list below the card is still all-time, so it now carries a "전체 기간 · 테마와 종목" label.
  The windows differ; the labels have to say so.

Verified (local server + chromium 390x844, ko/en/light/dark):
- 0 page errors, hero/ranking/labels render, tapping a ranking row opens the theme view.
- Numbers cross-checked against data/core.json: last 7 days 8 bull / 0 bear, prior 7 days
  35 bull / 15 bear. "강세 100%" this week is real, not a bug - the window is genuinely thin.
- Every commit deployed by sha256: base sha of the editor document compared against
  `git show origin/main:<file>` before dispatch, target sha compared after. All 6 matched.

Remaining risks / next:
- Monthly skew is still deferred: 2026-07 has 220 cards but 2026-08 has 17, so a month-over-month
  view would render one real bar and one stub. Revisit in September.
- `scripts/__pycache__/` still has 3 tracked `cpython-312` .pyc files and no .gitignore entry.
  Do not `rm -rf` that directory - the tracked files are why fix-queue has a past incident.

## 2026-08-04 Claude (new source: Peter Schiff, the roster's first standing bear)
Goal:
- june proposed @PeterSchiff and supplied the bridge. The roster had no bear at all: 0 bear
  cards in the last 30, which also starves pick_opposites().

Changed:
- `scripts/fetch_feeds.py` (`4a9919fc`), `sources.json` (`c159bfad`), `CLAUDE.md` (`42446fa6`)

Why he passed where the last three candidates did not:
- Cadence: ~5 posts/day, so he clears the 48h window. Dixon's Substack has been silent since
  2025-02-14 and the weekly longform bears never clear it.
- Direction: bear on the dollar, equities and bitcoin; bull on gold. Fills the empty axis.
  Amit and Dixon would have pushed the bull side further.
- Gradeable: he states dated numeric targets (gold $11,400, DXY 70). Half the reason to take
  him is that the scoreboard can actually settle those.

Feed measured before wiring (25 items, Jul 30 - Aug 3):
- handles: PeterSchiff 18, schiffgold 5, elerianm 1, jacksonaltonh 1. The schiffgold account is
  his own bullion shop; `x_handle` drops it along with the retweets (8 dropped at intake).
- Noise to filter when picking: 3 political posts (Trump approval rating etc.), 4 podcast
  promos, and one near-duplicate pair differing only by a Warsh/Walsh typo.
- What remains is substantive macro: Q2 GDP 1.5% with a 6.3% deflator, TLT under $82, BoJ on
  hold at 1%, COMEX gold deliveries, Saylor selling BTC and MSTR.

Rules attached (sources.json `schiff` notes):
1. Disclosure is mandatory. He runs SchiffGold (a bullion dealer) and an asset manager, so gold
   and dollar cards must say so in the body and carry a counter-argument or the market's actual
   reaction via `@@REF@@`/`@@CMP@@`.
2. `stance` is set honestly - bear on dollar/equities/BTC, bull on gold. Do not blur it to
   `watch`: the skew badge and the scoreboard both need to see it. That he has been bearish for
   two decades is not hidden from the reader either.
3. Attach `outcome{status:pending,due,note}` whenever a claim carries a number and a date.

Verified:
- feed-sync dispatched after deploy: `feeds/schiff.json` ok:true, raw 25, foreign_count 8,
  kept 15, residual contamination 0.
- Deployed sha256 matched the local target for all three files, before and after commit.
- rss.app usage now 13 of the Basic plan's 15 feeds - two slots left.

Next:
- Russell Clark is still the missing piece: Schiff is macro/gold/BTC and barely touches the
  memory and hyperscaler names this site is built on, so pick_opposites() still has little to
  pair. Clark writes bearish theses on exactly those (2026-07-30: "SHOULD YOU SHORT MEMORY
  STOCKS?") and publishes near-daily on Substack, so no bridge is needed.
- Detail: Claude project doc `claude/status-2026-08-04-schiff-first-bear.md`.

## 2026-08-04 Claude (correction: the RT title prefix was not a signal)
Goal:
- june pushed back on the previous entry: "이 계정은 내가 다시보니까 자기가 직접 쓴글도 많은데?"
  He was right and the filter shipped hours earlier was wrong.

Changed:
- `scripts/fetch_feeds.py` (`a4a95982`), `sources.json` (`9c209d3e`), `CLAUDE.md` (`858eb624`)

What was wrong:
- `own_post()` dropped an entry when its title started with `RT by`. Reading the raw bridges
  showed RSS.app writes `RT by @<owner>:` on the owner's OWN reposts - on bilello_x it even
  doubles the prefix (`RT by @charliebilello: RT by @charliebilello: The 30-Year US Treasury
  Yield ended the month at 5.27%...`). 22 of his 25 items carried the prefix while only 4
  actually pointed at another account, so the rule threw away 18 of his own posts and left the
  feed with 3 items.
- Measured across all ten bridges: there is not a single `RT by @<someone else>` title anywhere.
  The prefix has zero discriminating power. Only the link handle does.

Fix:
- `own_post()` now checks the link only: keep when it starts with `https://x.com/<x_handle>/`.
  The docstring records why the title check must not come back.

Verified (feed-sync dispatched after deploy):
- bilello_x kept 3 -> 15, foreign 22 -> 4, residual contamination 0. The recovered items are his
  own: 30Y Treasury yield at 5.27%, the bond market's 6-year drawdown, the debt-ceiling thread,
  S&P 500 Q2 margins at 16.7%.
- camillo 4 -> 3 dropped, tesuta 5 -> 4: the over-drop is gone.
- pichai 8 and jensen 8 unchanged - those were genuine foreign-account links and are still cut.
- Deployed sha256 matched the local target for all three files, before and after commit.

Lesson worth keeping:
- The earlier entry's numbers ("19 of 30 retweets", "47 foreign items dropped") were an artifact
  of the bad rule, not a measurement of reality. When a filter's own output is the evidence for
  the filter, read the upstream source directly before writing the number down.

## 2026-08-04 Claude (bilello_x + retweets and foreign posts dropped at intake)
Goal:
- june added an RSS.app bridge for https://x.com/charliebilello and asked to wire it in.

Changed:
- `scripts/fetch_feeds.py` (`4b027f55`), `sources.json` (`56fa1e9c`), `CLAUDE.md` (`0a4aca82`)

This is a second intake, not a new author:
- Charlie Bilello was already in the roster via `bilello.blog`. Same shape as `kuo`/`kuo_x`, so
  the pairing rule matches: max 1 card per run across BOTH paths, and when the same material is
  on both, take the blog (it carries the full text). Worth having, because the blog is weekly and
  therefore clears the 48h publishing window only on the day it lands, while the X account posts
  most days.

The real find - the bridges carry other people's posts:
- Checking the new feed before wiring it showed 19 of 30 items were retweets, and three carried
  `x.com/PeterMallouk/` status URLs. Measuring the feeds we already ship found the same thing in
  production: `pichai` 6 of 15 items were other accounts (demishassabis, chetanp, ChanduThota,
  joshwoodward), `camillo` 3, `tesuta` 2. Publishing one of those would have put another person's
  words under our author's name and linked the reader to a stranger's profile.
- The prose rule for this already existed in `sources.json` for pichai and it still leaked, so
  the check moved into code: `own_post()` drops an entry when the title starts with `RT by` or
  the link does not start with `https://x.com/<x_handle>/`. Feeds opt in with an `x_handle` field;
  blogs, Substack and Naver feeds are unaffected. `feeds/*.json` now reports `foreign_count`.
- Note this also closes a hole opened yesterday: widening `jensen`/`pichai` to `keep_days: 30`
  increased their exposure to exactly this. The first run after deploy dropped 8 impersonator
  items from `jensen`, which until now only the publishing routine's memory was guarding against.

Verified:
- Dispatched `feed-sync.yml` after deploy. Foreign items dropped in that run: bilello_x 22,
  jensen 8, pichai 8, tesuta 5, camillo 4; 0 for bessent/jukan/kobeissi/serenity/kuo_x (clean
  bridges, unaffected). 47 total.
- `feeds/bilello_x.json` ok:true, kept 3, residual contamination 0. The three survivors are the
  kind of post this site actually makes cards from: S&P 500 Q2 margins at 16.7%, Q2 earnings on
  pace for +47% YoY, Amazon Q2 revenue $201bn.
- Each file's deployed sha256 matched the locally built target before and after the browser
  commit; the fetch_feeds.py change was reproduced in the browser by re-running the same
  transformations against the editor document and comparing hashes. deploy_guard clean.

Risks / next:
- `own_post()` is silent by design. If a bridge ever changes its URL scheme the feed would empty
  out and only `foreign_count` would show why - worth an alert threshold in feed-sync later.
- `thediff` is an RSS.app feed with no `x_handle` on purpose (it mirrors a Ghost blog, not an X
  account). Do not add one.
- bilello_x posts single figures with no thesis; sources.json requires that we either add context
  or route them to the weekly macro card, otherwise they are ticker-tape.
- Detail: Claude project doc `claude/status-2026-08-04-bilello-x-and-intake-filter.md`.

## 2026-08-04 Claude (new source: Treasury Secretary Bessent + official-account rules)
Goal:
- june proposed adding https://x.com/SecScottBessent and asked that the three caveats raised
  against it be written down as rules rather than left as advice.

Changed:
- `scripts/fetch_feeds.py` (`5f852c51`), `sources.json` (`c0d1d165`), `CLAUDE.md` (`fef58927`)

Why this source, when the other proposed writers were held back:
- The publishing window stays at 48h by june's call. Weekly longform sources (Zitron, Peng,
  Berman) would be registered and then almost never clear it - the same failure mode that keeps
  Kuo at zero cards. A sitting official posts most days, so bessent actually clears it.
- It also fills a real hole: issuance, tariffs, the dollar and the deficit currently reach the
  site only second hand through Kobeissi. This is the first first-party policy voice.

Official-account rules (category=politician; full text duplicated in the `trump` and `bessent`
`notes` fields in sources.json, deliberately not behind a pointer):
1. Market-facing statements only - issuance, tariffs, rates, the dollar, deficits, regulation,
   sanctions, trade deals. Partisan attacks, personnel, ceremony, elections, rallies, enforcement
   PR and memes are out. Max 1 card per run across ALL politician sources combined.
2. No `outcome`, no card. Official statements are usually announcements or victory laps with no
   falsifiable claim, so they would dilute the grading rate that was just repaired. Publish only
   if we can derive a question checkable from public data within 90 days and attach
   `outcome{status:pending,due,note}`. Otherwise hold and log the reason in [9].
3. `stance` defaults to `watch`, and the card must carry the other side. A Treasury Secretary's
   optimism is an occupational statement, not a market call - `bull`/`bear` only when market data
   (not the statement) is the evidence. Every card must include the actual market reaction or a
   counter-argument via `@@REF@@` or `@@CMP@@`; a card that only relays the statement is a press
   release.

Verified:
- Feed URL checked before wiring: 25 items, lastBuildDate live, every `<link>` on
  `x.com/SecScottBessent` (no impersonator spam, unlike the `jensen` bridge).
- Dispatched `feed-sync.yml` after deploy: `feeds/bessent.json` is `ok:true`, `raw_count:25`,
  `kept_count:15`, newest 2026-08-02T23:00, and 0 items fail the handle check.
- The first five titles are themselves the argument for rule 1: a birthday message to the VP,
  praise for a deputy AG, and a Founding Fathers riff sit alongside the two market-relevant posts
  (trade partners, a meeting with BOJ Governor Ueda).
- Each file's deployed sha256 matched the locally built target before and after the browser
  commit. deploy_guard clean beforehand (one unrelated remote commit had landed; none of the
  three files had moved).
- rss.app usage now 11 of the Basic plan's 15 feeds.

Risks / next:
- Rule 3 is the one most likely to be skipped under time pressure, and skipping it turns the card
  into promotion. Worth a checker later, the way `check_source_dependence.py` enforces [5-C].
- This does NOT help the bull-skew problem - an official's optimism pushes the same way. The bear
  axis (Ed Zitron, Russell Clark) is still empty and still needs a separate decision.
- The canonical copy of these rules lives in sources.json `notes`. If `publish-v4.3.md [3]` is
  ever revised, mirror them there too.
- Detail: Claude project doc `claude/status-2026-08-04-bessent-source-added.md`.

## 2026-08-04 Claude (조회수 어뷰징 진단 + /view 서버측 dedup 배포)

Goal:
- june 질문: "netinterest-situational-awareness-67-percent-comeback" 글이 발행 12시간 만에
  조회수 124(확인 시점 127)가 나온 게 이상하다는 신고. 과거 데이터로는 발행 0~1일차 중앙값 6,
  전체 최고 기록도 55였던 사이트에서 나온 이상치.

Findings:
- Cloudflare D1 counters 테이블 직접 조회: 해당 글 n=127, 같은 회차 발행글(jukan-cxmt-...)도
  n=92 — 전체 238페이지 평균(14.8)의 8~9배, 역대 최고치(55)의 2배. 좋아요/댓글은 0건.
- GoatCounter는 SPA 라우트/이벤트만 기록해(v83/item 주간 17건) 이 글의 실방문을 개별로는
  못 봤지만, 사이트 전체 데스크톱 "글 열기" 이벤트가 주간 17건뿐이라는 사실 자체가 단일 글
  12시간 127회와 규모가 맞지 않는다. 외부 리퍼러 급증도 없었다.
- worker/index.js 소스(raw.githubusercontent.com 직접 fetch, Cloudflare workers_get_worker_code
  아님) 확인: POST /view는 pageId 존재검사(validPageId)만 하고 방문자/기기 단위 중복제거가
  전혀 없었다. counterOk()는 IP당 분당 300회라는 전역 쓰기 상한일 뿐, 같은 IP가 같은 글을
  몇 번을 호출해도 막지 않는다. 2026-07-25 감사 H3가 "패치됨"으로 기록돼 있었지만 실제
  코드엔 페이지 단위 dedup이 빠져 있었다 — 문서와 코드가 어긋나 있었음.

Changed:
- `worker/index.js`:
  - 커밋 `059d96e6`: view_dedup(page_id, ip_hash) 테이블 신설 + POST /view에서
    INSERT ... ON CONFLICT DO NOTHING RETURNING 패턴으로 (ip_hash, page_id) 최초 1회만
    bump(+1), 이후 같은 IP 재호출은 카운트만 반환(증가 없음). votes 테이블과 동일 설계.
  - 배포 실패(Deploy worker #15, 059d96e6): `Uncaught ReferenceError: __name is not defined`.
    원인: Cloudflare workers_get_worker_code로 읽었던 "배포된 번들"(wrangler/esbuild가 자체
    삽입한 __name/__defProp 셰이밍 헬퍼 포함)을 실제 GitHub 소스 형식으로 착각해, 존재하지
    않는 __name() 호출을 새 함수 뒤에 그대로 붙여 넣었던 것. **실제 저장소 소스에는 __name
    래퍼가 없다** — 다음에 그 도구로 읽은 코드를 패치 앵커로 쓸 때는 반드시
    raw.githubusercontent.com 원본과 대조할 것 (WORK-LOCK에 추가 권장).
  - 커밋 `8ec599cd`: 위 stray `__name(viewIsNew, "viewIsNew");` 한 줄 제거. Deploy worker
    재실행 성공(run 30869676258, conclusion success).

Tests run:
- 패치 적용 전: CodeMirror 문서 sha256 vs raw fetch sha256 일치 확인(베이스 검증).
- 패치 적용 후: 앵커 치환 전/후 등장 횟수(0→1) 확인, 중괄호·괄호 균형 확인(old 347/347·
  1058/1058, patch 후에도 균형 유지), GitHub API contents(sha)로 커밋 반영 바이트 대조.
- 배포 후 라이브 검증: stacksdaily.com 탭에서 POST https://api.stacksdaily.com/view
  {pageId: "netinterest-situational-awareness-67-percent-comeback"}를 연속 2회 호출 —
  1회차 count 127→128(이 브라우저는 이 글 /view가 이번이 처음이라 정상 증가),
  2회차 count 128 그대로(증가 없음, dedup 동작 확인). D1 view_dedup 테이블에 해당 행 1건
  생성 확인.

Remaining risks / 다음 단계:
- 이번 조치는 **같은 IP당 페이지별 1회**로 제한한다. NAT/사무실 공용 IP 뒤 여러 실사용자가
  있으면 2번째 이후 실방문자는 카운트되지 않는다(과소집계 방향 — 어뷰징 대비 안전한
  트레이드오프로 판단해 그대로 감).
- 이번 이상치의 실제 발생 경로(봇/스크레이퍼가 직접 API를 두드렸는지 등)는 로그가 없어
  특정하지 못했다. Cloudflare 대시보드 workersInvocationsAdaptive(계정 태그
  898876c2b7fe1652e72736e182ad610b, scriptName stacks-comments)에서 8/3 12:5x~8/4 01:3x
  구간 요청 IP/UA 분포를 보면 추가 확인 가능 — 다음 세션 후보.
- `/like`·`/vote`·`/clike`는 이번에 손대지 않았다. `/like`도 같은 구조(전역 IP 스로틀뿐,
  페이지별 dedup 없음)라 원하면 같은 패턴으로 확장 가능 — vote는 이미 votes 테이블로 서버
  권위화돼 있어 우선순위 낮음.
- 기존 D1 view 카운터 값(127 등)은 롤백하지 않았다 — 이미 쌓인 수치를 지우는 건 별도 결정
  필요(요청 시 처리).

## 2026-08-04 Claude (graded-prediction push: 릴레이 경로로 이관)
Goal:
- june: "이것 좀 해줘" - 이전 세션이 푸시하지 못한 채점 알림 수정본을 실제 main 에 반영.
  (그 세션은 레포가 읽기 전용으로 붙어 커밋 06c8677 이 로컬에만 남았다. 이번엔 GitHub 웹
  업로드로 같은 내용을 올렸다.)

Changed:
- `scripts/notify_followers.py` (`ca43db9`) - newly_graded() / send_graded() / _finish() 추가.
  outcome.status 의 pending -> hit/miss "전이"를 감지해 태그 daily 로 발송한다. gradedOn 날짜가
  아니라 전이를 보기 때문에 재실행/되돌림에도 중복 발송이 없다. 신규 발행 경로보다 먼저 실행한다
  (신규 id 가 없으면 그 아래에서 early return 하므로 뒤에 두면 영영 실행되지 않는다).
  한 run 상한 3건, miss 우선 정렬.
- `.github/workflows/grade.yml` (`0dda29f`) - GRADE_PUSH "1" -> "0". 이중 발송 방지.
- `CLAUDE.md` (`11c28b0`) - 위 경로 문서화.

Tests run:
- py_compile 통과. newly_graded() 스모크 테스트: 이미 확정돼 있던 건 / 이번 push 에 새로 추가된 건 /
  이전 outcome 이 없던 건은 모두 제외되고, miss 가 hit 보다 먼저 반환되는 것까지 확인.
- 커밋 후 raw 파일 SHA-256 이 로컬 파일과 완전 일치. Clobber guard #225-227 전부 green.

Remaining risks / next steps:
- 실제 발송은 아직 미검증. 다음 채점 커밋(items.json 변경) 때 "Notify followers" run 의 job
  summary 에 "newly graded prediction(s)" 줄이 뜨는지 확인할 것.
- `Stacks Grade Predictions`(grade.yml) 워크플로는 현재 수동 비활성(0 runs) 상태다. 채점은 예약
  Cowork 세션이 하고 있으므로 GRADE_PUSH=0 은 지금은 예방 조치다. 이 워크플로를 다시 켤 거면
  채점자가 둘이 되지 않는지 먼저 확인할 것.
- 태그 daily 구독자가 0명이면 워커가 502 를 주고 릴레이는 no-op 으로 처리한다(정상, 실패 아님).

## 2026-08-03 Claude (feed intake: drop dead serenity_substack, widen CEO retention)
Goal:
- june: "일단 버그 먼저 잡자. serenity_substack 이건 제거하자" - fix the two real feed bugs found
  while investigating source concentration, and leave the 48h publishing window alone.

Changed:
- `scripts/fetch_feeds.py` (`1bcd0563`), `sources.json` (`cec209c3`), `CLAUDE.md` (`2c9011eb`),
  deleted `feeds/serenity_substack.json` (`37f4e0bb`) - all deployed to main.

Root cause:
- `jensen` and `pichai` carried no `keep_days`, so the 7-day default applied. CEO accounts post a
  few times a year, so their feed empties between posts and the author silently drops out of the
  candidate pool. `jensen` hit `kept_count: 0` on 2026-08-03: its newest post (07-27 11:07) missed
  that run's cutoff (07-27 11:58) by 51 minutes.
- `serenity_substack` pointed at a plain `*.substack.com` host, which answers the Actions IP with
  403. Unlike `macroalf` it had no RSS.app mirror in `alt`, so it never fetched successfully once
  (`fetched_at` frozen at 2026-07-25, `ok:false` in every run on record). The Substack itself has
  been quiet since 2026-05-19 and the `serenity` X feed already covers this author.

Not a bug (checked, no action taken):
- `kuo` / `kuo_x` / `lynalden` / `macroalf` look stale but are healthy. Their files are still
  committed every 2h, the RSS.app bridges rebuild daily, and `keep_days: SLOW_DAYS` is holding
  their candidates. The authors simply have not published (Kuo's newest Medium post is 07-17,
  confirmed on the live page).

Verified:
- Dispatched `feed-sync.yml` manually after deploy: `jensen` went `kept_count` 0 -> 2 and both
  items are genuine `x.com/JensenHuang/` links, so widening the window did not let the known
  impersonator spam back in (the other 16 raw items sit outside the 30-day cutoff). `pichai` went
  1 -> 15. `feeds/serenity_substack.json` was not recreated.
- Each file's deployed sha256 was compared against the locally built target before and after the
  browser commit; all matched. Clobber guard green on all three edit commits.
- GitHub's web editor appended a trailing newline to `sources.json` (8565 -> 8566 bytes). The JSON
  is identical: 22 keys, `serenity_substack` gone, `serenity` kept.

Risks / next:
- The wider source-concentration and bull-skew work is NOT done - only these two bugs are. The
  publishing window stays at 48h by june's call, which means slow longform sources still rarely
  clear it. Open proposals (new bear/credit/China writers, source quota as a tie-breaker rather
  than a hard cap) live in the Claude project docs.
- This session did not take a `WORK-LOCK.md` lock. deploy_guard passed clean before every commit
  and clobber guard passed after, but the lock board itself was left untouched.
- Detail: Claude project doc `claude/status-2026-08-03-feed-intake-bugfix.md`.

## 2026-08-03 Claude (calendar header joins the shared menu top bar)
Goal:
- june: "캘린더도 동일하게" - make the mobile calendar header match every other menu bar.

Changed:
- `assets/v82.css` (`40198b8b`), `index.html` (`33beba1a`, restored in `89374a93`) - deployed live
- cache hash: v82.css `c2194fb8`

Root cause:
- `#calSheet` is a `.me-card` modal, not a `.v82-screen`, so neither earlier pass touched it. Its
  `.me-head` was 52px with the title on the LEFT and a round ✕ on the right - the only remaining
  layout that did not read as "back arrow then menu name".
- `.me-card` also carries `padding:20px 22px 24px` + a 1px border. Expanded full-screen on mobile
  that inset pushed the header 23px in, so even after restyling the arrow started at x=29 while
  every other bar starts at x=6.

Design:
- CSS only, no markup or JS change: `order` puts the existing close button to the left of the
  title and `::before` swaps its glyph to an arrow (`font-size:0` on the button hides the ✕).
  The close action is untouched, so back still closes the sheet.
- `.me-head` takes the same values as `#v82subbar` / `.v82-sh`: 48px, gap 6, padding 0 6,
  nav background with the dark-theme override, title 18px, arrow 22px.
- `html.rbeta #calSheet .me-card{padding:0;border:0}` so the bar starts at the real edge. Body
  inset now comes from `#calBody` alone (16px), which also widens the month grid slightly.
- Scoped to `#calSheet`: `#meSheet` still measures padding 20px 22px 24px / 1px border / 20px
  radius, i.e. unchanged.

Verified:
- All 10 mobile menu headers now report identical geometry: 테마 논쟁 / 판정 기록 / 최근 읽은 글 /
  북마크 (`#v82subbar`), 팔로잉 / 공유한 글 / 찾기 / 탐색 / 알림 (`.v82-sh`), 캘린더 (`.me-head`)
  - 48px, bg rgba(255,255,255,.86), title 18px, arrow box at x=6.
- Dark mode bg rgba(0,0,0,.86) with rgb(242,243,247) text; arrow closes the sheet and returns to
  the feed. Desktop v83 menu pages still 53px with correct titles. Zero page errors.
- Live re-check in a 390px same-origin iframe on stacksdaily.com plus a screenshot.

Risks / note for whoever wrote `aa92cd8b`:
- `aa92cd8b` (whole-card click) was authored from a stale `index.html` and reverted the v82.css
  query string from `c2194fb8` back to `c2125c57`. The file on disk was already the new CSS, but
  returning visitors would have kept the cached old copy, so the calendar header would not have
  appeared for them. Restored in `89374a93`; all 35 other lines that commit added were verified
  still present. **If you edit index.html from a clone, re-check the asset hash lines before
  committing** - `scripts/deploy_guard.py` catches this.

Next:
- none. Detail: Claude project doc `claude/status-2026-08-03-mobile-screen-header-restyle.md`.

## 2026-08-03 Claude (whole-card click opens the post view on desktop)
Goal:
- june approved option A for the dead-click finding: make the desktop card body clickable like X.

Changed:
- `index.html` (commit `aa92cd8`, deployed live)
- `AGENT_HANDOFF.md`

Verified:
- Document-level delegated click handler after `openFromCard()`: only fires in the v83 shell (mobile v82 already opens cards on tap), only on `#feedList article.card[id^=sig-]` that are not `.v83one`. Skips: interactive elements (`a,button,summary,input,svg,canvas,iframe,[onclick],.eg,.has-tip,...`), clicks inside a `.gist` that v83tw.js Item4 already bound (`g.__v83open` - avoids double `v83OpenItem`/double render; if the binding hasn't attached yet, this handler opens instead), active text selection (`getSelection().isCollapsed`), and modifier-key clicks. Tracked as `card/bodyopen`. CSS: `cursor:pointer` on feed cards (not `.v83one`).
- Discovery during testing: v83tw.js:~520 already opens on `.gist` clicks - the remaining dead zones were card padding, `.src-date`/card-top, quote blocks, `.why`, headings; this handler covers those.
- Playwright: card-padding click opens with exactly 1 `v83OpenItem` call; gist click still exactly 1 call (via existing binding); selection blocks opening; detail view no-op; cursor pointer; zero page errors. node --check 5 blocks. deploy_guard clean, post-deploy sha match (ec62d00d), live check on stacksdaily.com/?v83beta: handler live, padding click opens.

Risks:
- Double-click-to-select-word opens the post on the first click (X behaves the same).
- If Item4's gist binding is ever removed from v83tw.js, this handler takes over automatically (guarded by `__v83open`), so behavior stays consistent.

Next:
- Watch Clarity dead-click rate after ~1 week (now with clean data thanks to the hostname gating).

## 2026-08-03 Claude (mobile screen headers match the menu top bar)
Goal:
- june: give 팔로잉 and 공유한 글 on mobile the same top bar as 테마 논쟁 / 판정 기록.

Changed:
- `assets/v82.css` (`d8b9af91`), `assets/v82.js` (`2bc084b9`), `index.html` (`853f3930`) - deployed live
- cache hashes: v82.js `cbde1050`, v82.css `c2125c57`

Root cause:
- 팔로잉/공유한 글 are `.v82-screen` overlays whose header is `.v82-sh`, not the feed `#v82subbar`.
  `.v82-sh` had `background: rgba(14,15,18,.92)` **hardcoded**, while its text uses `var(--text)`.
  In light mode that is dark text on a near-black bar - measured bg rgba(14,15,18,.92) against
  colour rgb(23,24,28), so the title and the back arrow were effectively invisible. It was also
  52px/17px against the subbar 48px/18px.
- The header title came from `T().follows` / `T().shares` ("팔로우 내역" / "공유 내역") while the
  drawer item says "팔로잉" / "공유한 글", so the bar did not show the menu name.

Design:
- `.v82-sh` now mirrors `#v82subbar` exactly: 48px, `gap:6px`, `padding:0 6px`, nav background
  `rgba(255,255,255,.86)` + `blur(12px)` with a `html[data-theme="dark"]` override to
  `rgba(0,0,0,.86)` (same pair `nav` already uses), `.ti` 18px, `.bk` 22px. `.v82-screen`
  padding-top 60px -> 56px to match the 4px shorter header.
- `openList()` titles from `T().dwShared` / `T().dwFollowing` - the exact drawer labels.
- NOTE: 찾기 / 탐색 / 알림 and the entity picker share `.v82-sh`, so they were hit by the same
  dark-on-dark bug and are fixed by the same rule. That is deliberate - special-casing only the
  list screen would have left the others unreadable.

Verified:
- 7 mobile headers now report identical geometry and colour: 팔로잉 / 공유한 글 / 찾기 / 탐색 /
  알림 (`.v82-sh`) and 테마 논쟁 / 판정 기록 (`#v82subbar`) - all 48px, bg rgba(255,255,255,.86),
  title 18px, arrow 22px. Titles now read 팔로잉 and 공유한 글.
- Dark mode: bg flips to rgba(0,0,0,.86) with rgb(242,243,247) text, height 48. Screenshot checked.
- Desktop untouched: the rules sit inside the `@media (max-width:1023px)` block (verified by brace
  depth), and the v83 menu pages still show their 53px bar with correct titles. Zero page errors.
- deploy_guard **caught a second concurrent commit**: `90395f14` (analytics host gating) added 8
  lines to index.html mid-deploy. Rebased, re-verified, `--verify` confirmed all 8 lines survived.
- Post-deploy sha256 match on all three files; clobber guard and pages build green.
- Live re-check on stacksdaily.com in a 390px same-origin iframe: all five menus identical,
  screenshot of 팔로잉 confirms a readable light bar.

Risks:
- None known. `.v82-sh` is mobile-only and now theme-aware, which it was not before.

Next:
- none. Detail: Claude project doc `claude/status-2026-08-03-menu-topbar-unified.md`.

## 2026-08-03 Claude (analytics hygiene + dead-click / today-section findings)
Goal:
- Close out the remaining analytics-review items: dev-session pollution, dead clicks 4.85%, today/scrollpast +243%. (Naver collection requests: june decided to skip.)

Changed:
- `index.html` (commit `90395f1`, deployed) - `ANALYTICS_LIVE` hostname guard: Clarity + GoatCounter loaders now run only on `*.stacksdaily.com`. localhost/127.0.0.1/preview dev sessions were polluting both tools; IP blocking would also erase june's real visits, hostname gating doesn't. Verified with Playwright on localhost: zero analytics requests, no errors. Rebased over `9de180a` (menu top bar, 44 lines preserved, guard --verify clean).
- `AGENT_HANDOFF.md`

Findings (no code change, by design):
- Dead clicks (5 sessions/7d, rage clicks 0%): element ranking across the dead-click recordings shows the clicks land on **article body text on desktop** - gist paragraphs (`P.gp[1]` 11, `P.gp[2]` 7), section headings (`H2.section-title` 8), raw paragraph text (7), and card containers (`article#sig-*` 13-18 each). Card *titles* work (open the post view); card *bodies* do nothing. Users show an X-like whole-card-clickable expectation. Possible fix: make the card container open the post view (excluding links/buttons/text-selection) - medium risk (nested interactive elements, selection UX). Left undone pending june's call; harm today is low (0% rage clicks).
- today/scrollpast +243% is **not** a problem signal: `watchTodayPast()` intentionally auto-dismisses the pinned Today box once the reader scrolls past it and logs `today/scrollpast` at that moment. The spike = the auto-dismiss shipping and firing as designed. Exposure is already limited (1/day first session + X dismiss + scroll-past dismiss). No reposition needed.

Next:
- Optional (june call): whole-card click-to-open on desktop to convert the dead clicks.
- ~2026-08-10 batch re-check: Clarity INP + dead-click rate (post-hygiene data will be cleaner), GSC indexing + calendar.html, nudge/* funnel, Naver 수집 현황.

## 2026-08-03 Claude (one back+title top bar for every left-menu page)
Goal:
- june, three reports: the Latest/Following strip still shows on 최근 읽은 글 **on mobile**;
  판정 기록 and 최근 읽은 글 have a different top bar from 지금 쏠린 곳/테마 논쟁/캘린더;
  make it back-arrow + menu name, unified to the PC structure, and check mobile too.

Changed:
- `assets/v82.js` (`df9e5b57`), `assets/v82.css` (`a932d6d8`), `index.html` (`9de180a2`) - all deployed live
- cache hashes: v82.js `70717c16`, v82.css `bdcad175`

Root cause:
- The `v83navback` IIFE at the bottom of index.html builds that bar from `#feedList`, but
  `detect()` only knew `.sb-header .series-head-name` and `.v83dir-head > b`. 판정 기록
  (`renderJudgmentRecord` -> `.jr-page > .jr-head > h2`) and 최근 읽은 글
  (`renderReadLibraryTools` -> `.read-library-heading > h2`) render neither, so they were the
  only two menus without a bar. `renderScoreboard` returns early into `renderJudgmentRecord`
  when `RECORD_SRC` is null, which is why the left-nav entry specifically had none.
- Mobile was further off: `nav.nav-sub` (which hides `#v82tabs`) was only set by the explore-hub
  path (`EXPLORE_SUB`). Every drawer-opened menu therefore kept Latest/Following visible
  (measured display:flex h=44 on themes/record/readlist/bm). The desktop-only bar was also being
  injected into the mobile feed unstyled (h=30), and themes still showed a dark banner with a
  second "back to feed" button.

Design:
- One `detect()`; only the render target branches. Desktop keeps `.v83post-head.v83navback`;
  mobile writes the same title into `#v82subbar .ti` and sets `nav.nav-sub`, and the desktop bar
  is actively removed on mobile. `EXPLORE_SUB` still owns nav-sub teardown so the hub back path
  is untouched.
- `#v82subbar .bk` falls back to `history.back()` when there is no `EXPLORE_SUB` (it was a dead
  button for drawer-opened menus). Drawer 북마크 now routes through `v83Bookmarks()` so it pushes a
  history entry (back used to leave the site). `toTop()` after openThemes/openScoreboard so their
  smooth scrollIntoView does not land the user past the new bar.
- Mobile `.sb-header` flattened to match `html.v83 .sb-header` (no dark banner, no duplicate back).

Verified:
- Desktop, 8 menus: bar present, height 53 identical, correct KO titles, `#v83fsw` hidden, back
  returns to the 6-card feed. Mobile (Playwright 390px iPhone), 4 drawer menus: nav-sub on,
  `#v82tabs` display:none, subbar top=0 h=48, scrollY=0, no stray desktop bar, back returns to feed
  on the same host. Hub path regression: 탐색 -> 테마 논쟁 -> back reopens the hub.
- Regression both shells: home / search / search-cleared / entity view / post detail all show no bar
  and no nav-sub; mobile Latest/Following still shows on normal feeds. Zero page errors throughout.
- `node --check` 5/5 inline blocks + v82.js.
- deploy_guard **caught a real conflict**: `f703ea6` (static earnings calendar page + footer link +
  single H1) had landed on index.html 12 min earlier. stash -> rebase -> pop -> re-verify, and
  `--verify` confirmed all 6 of their lines survived. Clobber guard success on all 3 commits.
- Post-deploy sha256 match on all three files (`ac907975` / `70717c16` / `bdcad175`).
- Live checks on stacksdaily.com: desktop 6 menus re-confirmed on screen; mobile re-confirmed in a
  390px same-origin iframe (all 4 menus, bar at top, tabs hidden, back stays on site).
  NOTE: index.html is `max-age=600`, so the first live load served the old copy - always re-load
  with a `?cb=` cache buster before judging a deploy.

Risks:
- Mobile subbar is 48px while the screen-style headers (`.v82-sh`: 캘린더/찾기/탐색/알림) are 52px.
  4px apart; match them if it reads as inconsistent.
- `bmLabel()` now localises the 북마크 title (it was hardcoded Korean for en/ja too).

Next:
- none. Detail: Claude project doc `claude/status-2026-08-03-menu-topbar-unified.md`.

## 2026-08-03 Claude (SEO: GSC/Naver diagnosis + earnings calendar page)
Goal:
- Analytics item 4 (SEO): Google brings only ~20 clicks/28d and Naver (89% Korean traffic) brings zero.

Changed:
- `calendar.html` + `index.html` (commit `f703ea6`), `scripts/build_pages.py` (commit `8192289`) - both deployed and live-verified
- `AGENT_HANDOFF.md`

Verified:
- GSC: 149 indexed / 222 not (175 discovered-not-crawled, mostly /e/; report dated 7/24). 28d: 20 clicks, 676 impressions, 27 queries. Korean schedule query "인텔 실적 발표일" appeared at pos 80 - real search demand for a calendar page.
- Requested indexing for 6 URLs (5 newest /p/ articles + calendar.html), all confirmed "색인 생성 요청됨". The 2 articles requested on 7/30 are now indexed, so manual requests do work.
- Naver Search Advisor (june drove the UI, screenshots): site registered 7/17, sitemap.xml + feed.xml both submitted 7/17 - but collection is ~zero (one spike of 6 pages on 7/20), 웹 페이지 수집 요청 never used (asked june to submit 8 URLs), site diagnosis shows 색인 1 / 수집제한 1(접근 불가 1건 - identify later once collection data accumulates) / "H1 x2" SEO flag.
- New `calendar_page()` in build_pages.py renders items.json `events` (the weekly calendar bot's data) as static `calendar.html`: D-day badges, weekday, kind pill, links to /e/ and /p/ (APP_LINK_JS routes them into the app). Regenerated every build; sitemap entry added; home footer links it. One page covers the whole "[회사] 실적 발표일" query family - zero upkeep.
- H1 duplicate fix: `#introTitle` h1 -> h2 (+ CSS selectors extended) so the document has exactly one h1 (#heroTitle). Live checks: calendar renders (11 rows, 8 entity + 8 article links, single h1), home footer link present, home h1 count = 1.
- Mid-deploy: deploy_guard caught 2 fresh index.html commits from another window (`000c5d0` fsw readlist, `cce8b5a` newsletter URL); rebased, verified both preserved (guard --verify clean), regenerated the patch spec against the new base. node --check 5 blocks + ast.parse on build_pages.py.

Risks:
- calendar.html shipped as a generated snapshot; the next og-assets build overwrites it from build_pages (intended). If that build fails, the snapshot just goes stale - no breakage.
- Naver collection may stay near zero regardless (new-domain trust); the manual 수집 요청 + RSS rediscovery is the lever, re-check 수집 현황 in ~1 week.

Next:
- june: submit the 8 collection-request URLs in Naver Search Advisor (list in chat / claude/status-2026-08-03-seo-diagnosis-gsc.md).
- ~1 week: GSC re-check (indexed count, calendar.html status, schedule-query positions) + Naver 수집 현황.
- Keep requesting indexing for new /p/ articles (quota ~10/day).

## 2026-08-03 Claude (readlist top tab bar fix)
Goal:
- june: "최근 읽은 글 메뉴 들어가면 상단바의 최신/팔로잉 바가 계속 노출되는데 다른 메뉴들처럼 노출되지 않게 해줘."

Changed:
- `index.html` (commit `000c5d0d`, deployed live)
- `AGENT_HANDOFF.md`

Verified:
- Root cause: `v83ReadList()` sets `READ_VIEW=true` + `TAB="all"`, but the `#v83fsw` (최신/팔로잉 feed switcher) visibility check in `renderFeed()` only excluded `ENTITY_VIEW/SERIES_VIEW/SB_VIEW/QUERY/BM_ONLY/THEME_VIEW/V83ITEM`, not `READ_VIEW`. Unlike bookmarks/themes/etc, the switcher stayed visible on the "최근 읽은 글" screen.
- Fix: added `&& !(typeof READ_VIEW !== "undefined" && READ_VIEW)` to the `_vis` condition (1 line).
- Reproduced the bug pre-fix and confirmed the fix with local Playwright (`?v83beta`, desktop v83 shell): `#v83fsw.hidden` was `false` on the readlist view before the fix, `true` after.
- node --check on all 5 real inline JS blocks (6th block is JSON-LD, expected to fail check).
- Deployed via GitHub `edit` page CodeMirror dispatch (sandbox git push blocked with "could not read Username" - proxy MITM session type per `claude/START-HERE.md`). Anchor-based single-occurrence replace, baseSha/targetSha verified before dispatch; post-deploy `git show origin/main:index.html | sha256sum` matched the locally computed target sha exactly.
- Live check on `stacksdaily.com/?v83beta`: home fsw visible, readlist fsw hidden. Screenshot confirms "최근 읽은 글" page has no 최신/팔로잉 bar under the title, matching other side-nav menus.
- Clobber guard: success on this commit.

Risks:
- None functional. Mobile (v82) shell has no equivalent feed switcher, so this is a desktop-only fix by design (the report was about the top bar on desktop).

Next:
- None.

## 2026-08-03 Claude (retention nudge)
Goal:
- Analytics item 3 (retention): 30d data shows every re-visit channel dead (~0 push subscribers, 5 newsletter signups, 9 follows) while the daily-brief push pipeline (07:00 KST, `daily` tag) sits ready with no one to send to. june picked: engagement-gated push/install nudge only, skip newsletter placement, then move to SEO.

Changed:
- `index.html` (commit `6fa67ee`, deployed live)
- `AGENT_HANDOFF.md`

Verified:
- New `maybeRetentionNudge()` + `showInstallNudge()` next to `promptPushOnce()`; hooked from `setRead()` only - both shells route through it (v82.js detail open, v83 detail, TTS, comments, original-link click).
- Gate: 2+ articles read (READ.size), once per session, 7-day cooldown (`stk_nudge_ts`), max 3 lifetime (`stk_nudge_n`), fires 4s after the qualifying open (off the tap task).
- Branches: iOS browser (web push impossible) -> dismissible bottom card -> existing `openIosGuide()`; everywhere else with `Notification.permission === "default"` -> OneSignal slidedown (`force:true`). Silent when granted/denied - no counter burned.
- Events: `nudge/push-shown`, `nudge/push-granted` (via OneSignal permissionChange), `nudge/install-shown`, `nudge/install-open`, `nudge/install-dismiss`.
- node --check (5 blocks). Playwright: iOS sim - no nudge after 1 read, card after 2nd (+4s), cooldown honored after dismiss; desktop with permission=default fires push-shown + queues slidedown; zero page errors. deploy_guard clean; final pre-commit re-check of remote sha; post-deploy sha matches (9089f688); live smoke: functions present, setRead hooked.

Risks:
- The existing top mini-install bar (`refreshMiniInstall`, `stk_hide_install`) still shows on iOS/Android until dismissed - the bottom nudge can appear alongside it once. Redundant but not conflicting; merge later if june finds it noisy.
- `nudge/push-granted` only records when permission flips during the session the prompt appeared.

Next:
- Check nudge funnel events in GoatCounter in ~1 week (shown -> granted / install-open rates).
- Next analytics item: article-page SEO (Google only ~20 visits/week).

## 2026-08-03 Claude (surge alerts: sharded cron, Free-plan subrequest cap)
Goal:
- june: "급변동 알림, 뭐가 문제인지 체크해줘" then "구현해서 배포해줘". Follower surge pushes had been silently dead since 2026-07-24.

Root cause:
- `computeSurges()` priced every followed company in one invocation: 1 (items.json) + N Yahoo calls, N = 78. The Workers **Free** plan caps one invocation at **50 subrequests**, so every firing died before reaching the OneSignal calls, and silently, because `fetchDailyChange`/`osPushTag` swallow their errors. Measured with Cloudflare GraphQL `workersInvocationsAdaptive` at 23:00Z: 07-23 = 44 subrequests (pushed 3, the only rows in D1 `surge_alerts`); 07-27/28/29/30 = exactly 50 each (pushed 0). 07-24 and 07-31 had no cron invocation at all.

Changed:
- `worker/index.js` (`07172da`), `worker/wrangler.toml` (`7a824cf`)
- Claude project docs: `claude/status-2026-08-03-surge-alert-diagnosis.md`, `claude/prompts/surge-monitor.md`

Design:
- New D1 table `surge_scan(date, tag, name, ticker, pct, price, currency)`. Cron is now `0,5,10,15 23 * * 1-5` and the role comes from the minute (index = minute/5): :00 :05 :10 each price one shard (companies sorted by name, `i % SURGE_SHARDS == shard`), :15 is a push-only sweeper. Pushes rank globally over `surge_scan` and only fire once the day's scan is complete (or from the last shard / sweeper), capped at `SURGE_TOP_N` per UTC day by `surge_alerts`.
- `/cron/surge-dryrun` no longer prices anything. It reads `surge_scan` (1 subrequest) and returns `scannedToday` / `total` / `complete` / `sentToday`, so a truncated scan cannot look clean and the monitor can finally see actual sends. The old 10 minute `DRY` memo is deleted, it is what made the 07-27..07-30 monitor runs report a frozen date.
- `/cron/surge` now takes `{shard, push}`.

Verified:
- Node harness against the real module (mock D1 + a fetch that throws past 50 subrequests): 78/78 companies scanned across the three firings, max 30 subrequests per invocation, global top 3 pushed rather than per shard local winners (the harness caught that regression before deploy), re-running every firing pushes 0 more. Edge cases: missing last shard, missing first shard, 150 companies (max 42 subrequests, truncation surfaced as `skippedThisRun` + `complete:false`), and a day with no movers.
- `node --check` on the exact deployed bytes. deploy_guard clean before upload, clobber guard success on both commits, Deploy worker success on both.
- Post deploy shas match (index.js `582dc0a8`, wrangler.toml `20f4ac39`). Live `GET https://api.stacksdaily.com/cron/surge-dryrun` returns `{"source":"surge_scan","total":78,"scannedToday":0,"complete":false,"sentToday":[]}`. `surge_scan` exists in D1. Cloudflare schedules API confirms `0,5,10,15 23 * * 1-5`.

Risks:
- The end to end push is unproven until the first real firing (2026-08-04 08:00-08:15 KST). Check `sentToday` in the dryrun and rows in `surge_alerts` for that date.
- Two cron firings vanished entirely on 07-24 and 07-31, both Fridays. Cause unknown and unrelated to this fix. The :15 sweeper limits the damage of a lost shard but a whole cron outage still sends nothing.
- `stacks-comments.wnrakrhdn128.workers.dev` is `enabled:false` at the script level. Only `api.stacksdaily.com` is live, the monitor prompt was pointing at the dead one.
- WORK-LOCK board was not taken for `worker/`: another window was committing to `scripts/` and `.github/workflows/` at the time, deploy_guard confirmed `worker/` untouched, and the deploy was a single 5 minute window.

Next:
- Confirm `surge_alerts` has rows for 2026-08-04 after the cron.
- If followed companies grow past ~120, bump `SURGE_SHARDS` and add a cron minute; the sweeper minute must stay last.

## 2026-08-03 Claude (onboarding gate retired)
Goal:
- Item 2 from the analytics review: the interest-picker gate showed to 26 new visitors in 7 days and all 26 skipped it (zero selections). june decided: retire, do not delete.

Changed:
- `index.html`, `CLAUDE.md` (commit `3a3e500`, deployed live)
- `AGENT_HANDOFF.md`

Verified:
- Evidence before deciding: all 13 Clarity recordings (07/28-31) of skip-clickers reviewed - every visitor dismissed intro+onboarding reflexively in 1-2s like a cookie banner; 8 of 13 then read for 4-30 min. Zero sessions abandoned while the popup was open, so it wasn't an exit driver - just zero-value friction. 2 of 4 interest options were tied to the retired series feature anyway.
- Implementation: single `ONBOARD_RETIRED = true` guard at the top of `maybeOnboard()`, independent of `FIRST_RUN_GATES_DISABLED_FOR_ADSENSE` - when that temporary flag is reverted after AdSense approval, the intro comes back but onboarding stays off. All onboarding code/markup/CSS kept inert (same pattern as the series retirement). Interests UI unchanged in the me sheet.
- node --check (5 blocks); Playwright first-visit simulation local + live: onboard stays hidden after `maybeOnboard()`, no scroll lock, 0 page errors; deploy_guard clean; post-deploy shas match (index.html c929040e, CLAUDE.md b776cfa8).

Risks:
- None functional. Revert = set `ONBOARD_RETIRED` to false (1 line).

Next:
- Remaining analytics items: article-page SEO (Google only 20 visits/week), today/scrollpast +243%.

## 2026-08-03 Claude (project doc cleanup + entity matcher fix)
Goal:
- june asked to tidy up the project context: compress old status logs, refresh the entry-point doc, and clear the code items sitting in `claude/fix-queue.md`.

Changed:
- `scripts/build_pages.py` (`2b29a86`), `scripts/build_data.py` (`1f2ac7c`), `scripts/check_term_coverage.py` (`0add76b`)
- Claude project docs (not in this repo): deleted 112 status logs from 07-18~07-26, added 3 archive summaries, rewrote `claude/START-HERE.md` and `claude/fix-queue.md`.
- `AGENT_HANDOFF.md`

Verified:
- fix-queue item L: the entity matcher was scanning `@@REF@@`/`@@IMG@@` marker URLs. Measured across all 223 live cards before the fix: 9 cards carried 12 false entity links (e.g. `meru-skhynix-one-share-hyperliquid-liquidation` -> ORACLE, matched on `perp-oracle-liquidations` inside the REF URL; also KOSPI, COREWEAVE, KIOXIA, DDR, HBM, BESI, META, WTI, AP, TOKEN). Both `item_entities()` and `item_text()` now strip URLs before matching, so captions and titles stay indexed. Re-checked 5 of the worst cards after the fix: all target links gone.
- `index.html:linkifyEntities()` needs no change - it walks rendered DOM where URLs are already link cards, so the same false positives cannot occur there.
- STOPWORDS: added Benzinga/PYMNTS/UPI (requested 3 times in fix-queue).
- Deployed through the june browser because this sandbox had no push (`could not read Username`, api.github.com 403, no `gh` CLI). Per file: raw fetch -> single-hit replace -> sha256 compared against the locally built target -> CodeMirror dispatch -> sha re-check. All 3 target hashes matched the sandbox build exactly.
- `deploy_guard.py` was clean before upload. Clobber guard green on both entity commits; pages build succeeded.

Risks:
- No lock was taken in `claude/WORK-LOCK.md` for `scripts/`. `deploy_guard.py` was run instead and reported all 3 files untouched on the remote since clone. Short window, but worth noting.
- Entity pages keep the stale false links until the next `build_pages.py` run regenerates them (og-assets runs every 6h).

Next:
- fix-queue still open: K (quote i18n backfill, 158 left) and J (3 non-English REF URLs, deferred 4 rounds).
- Requested but not done: add `Asia`/`Times`/`kHz`/`mm` to STOPWORDS, add the Korean terms for immersion lithography and share buyback to the WATCHLIST, `.gitignore` for `scripts/__pycache__/`.
- `claude/START-HERE.md` now lists the open items, including the unexplained 4-day publish gap (07-31 ~ 08-03) and the 08-03 double-run collision.

## 2026-08-03 Claude (event calendar bot, weekly)
Goal:
- Weekly scheduled refresh of `items.json` `events` array per `claude/prompts/event-calendar.md`.

Changed:
- `items.json` (events array only), `sitemap.xml`, `feed.xml`, `feed-en.xml`, `feed-ja.xml` (rebuild output) — commit `a9ca1f2f`, pushed as `53d7fe13` after rebasing onto `f121aac7`.
- `AGENT_HANDOFF.md`

Verified:
- Pruned 3 events >7 days past (`ev-centcom-iran-2026-07-21`, `ev-alphabet-q2-2026`, `ev-tesla-q2-2026`); kept 9 remaining (07-27 ~ 07-30).
- Added 2 confirmed-date events within scope: Coupang Q2 2026 earnings (Aug 4, company-announced) and US CPI report for July 2026 data (Aug 12, BLS schedule). Total events now 11/12 cap.
- Skipped as not-yet-in-window (next 3 weeks): NVIDIA Q2 FY27 earnings (Aug 26), BOK 금통위 (Aug 27), FOMC (Sep 15-16), BOJ (Sep 17-18) — all confirmed dates but past the 3-week search window; will pick up next weekly run. Alibaba's Sep 4 date is estimated, not confirmed — skipped per rule.
- `git diff` confirmed only the `events` array changed in `items.json` (no touch to items/series/entities).
- `python3 scripts/build_pages.py` ran clean (223 pages, 489 entity pages); IndexNow ping failed with 403 (sandbox network restriction, non-fatal, matches known behavior).
- No event falls on D-3 (2026-08-06) this run, so no push notification was sent.
- Push required one rebase: remote had gained `f121aac7` (doc-only handoff commit for the INP fix) between clone and push; rebase was safe since it touched only `AGENT_HANDOFF.md`.

Risks:
- None. Read-only rules doc (`claude/prompts/event-calendar.md`) unchanged.

Next:
- Next weekly run (~2026-08-08) should add NVIDIA earnings, BOK 금통위, and prune this run's Coupang/CPI events once >7 days past.

## 2026-08-03 Claude
Goal:
- Fix Clarity INP 530ms (52.9% of views rated bad) — the top item from the 7-day analytics review.

Changed:
- `index.html` (commit `7ec2437`, deployed live)
- `AGENT_HANDOFF.md`

Verified:
- Measured at 4x CPU throttle (Playwright, iPhone viewport): feed-switch tap held the main thread 1.36s. After fixes: 304ms (~78% cut).
- Fix 1: `linkifyEntities` now queues cards and drains in <=8ms slices off the tap task (`linkifyEntitiesNow` keeps the original logic; two TreeWalker+regex passes per card were ~60% of the long task).
- Fix 2: `hydrateImages` coalesces same-frame calls into one deferred run (`hydrateImagesNow`); it scans all ITEMS with document-wide querySelectorAll and ran 2-4x per tap.
- Fix 3: `FEED_PAGE_SIZE` 10 -> 5 (style+layout inside the tap halves; the 800px-rootMargin IntersectionObserver prefetch hides the difference).
- Inline JS syntax via node --check (5 blocks). Mobile+desktop Playwright smoke: entity links present after deferred drain, avatars hydrated, pagination 5/page, goToItem cross-page jump works, zero page errors.
- `deploy_guard.py` clean before upload; browser-upload patch spec self-verified (base dfab19ed -> target f26b3ff9); post-deploy remote sha matches; live check on stacksdaily.com: new functions live, 6 cards linked+hydrated, no errors.

Risks:
- Entity/glossary links now appear one task later than card paint (imperceptible; queue drains in ms).
- If a future caller needs links synchronously in the same tick, use `linkifyEntitiesNow`/`hydrateImagesNow`.

Next:
- Watch Clarity INP over the next 7 days (target: <200ms, "bad" share down from 52.9%).
- Remaining analytics items: onboarding 100% skip rate, article-page SEO, today/scrollpast +243%.

## 2026-08-02 Codex
Goal:
- Add the normal feed `More` behavior to the completed prediction-result card.

Changed:
- `index.html`
- `AGENT_HANDOFF.md`

Verified:
- Collapsed state keeps the verdict, result summary, `Why this matters now`, and engagement controls visible.
- `More` expands the X source, decision rule, schedule, and original link in place.
- Inline script syntax, `git diff --check`, local browser interaction, and deploy guard passed.

Risks:
- None.

Next:
- Commit, push `main`, and verify the cache-busted production page.

## 2026-08-02 Codex
Goal:
- Replace the in-feed "오늘의 전망" card with an always-expanded completed prediction result and deploy it to production.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\index.html`
- `AGENT_HANDOFF.md`

Verified:
- Reused the production `cardEl()` renderer, X embed path, and engagement controls.
- Local browser check: completed `hit` result, question title, result note, `왜 지금 봐야 하나`, X embed, decision rule, schedule, and all six engagement controls rendered.
- Local browser check: no forecast toggle, no `details`/`summary`, and no duplicate DOM IDs.
- Inline script syntax and `git diff --check` passed.
- `scripts/deploy_guard.py index.html` passed before editing.

Risks:
- The daily result currently prefers `kobeissi-nasdaq-900b-selloff`; fallback is the latest completed graded item.
- The selected item is omitted from its later normal-feed position to avoid duplicate engagement IDs.

Next:
- Run final deploy guard, commit, push `main`, and verify the cache-busted production page.

## 2026-08-01 Codex
Goal:
- Deploy temporary intro/onboarding bypass for AdSense review.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\index.html`

Verified:
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main fetch origin main`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main rebase origin/main`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main diff --check origin/main..HEAD -- index.html`
- `PYTHONUTF8=1 PYTHONIOENCODING=utf-8 C:\Users\dream\AppData\Local\Programs\Python\Python312\python.exe scripts\deploy_guard.py index.html`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main push origin HEAD:main`
- Live `https://stacksdaily.com/?deploycheck=a73a3901-adsense-intro-2` contains `FIRST_RUN_GATES_DISABLED_FOR_ADSENSE = true`.
- Browser live check: `introHidden=true`, `onboardHidden=true`, `cardCount=10`.

Risks:
- Intro and onboarding are intentionally disabled until AdSense approval.
- Restore by setting `FIRST_RUN_GATES_DISABLED_FOR_ADSENSE` to `false` after approval.

Next:
- Resubmit/recheck AdSense.

## Rules
- Before work: read `AGENTS.md`, `STACKS_CONTEXT.md`, this file, then run `git status`.
- During work: avoid editing the same files at the same time.
- After work: add a dated entry with changed files, verification, risks, and next steps.
- Prefer commits for finished work. Use this file for in-progress context.

## Entry Template
```md
## YYYY-MM-DD Agent
Goal:

Changed:
- path/to/file

Verified:
- command or manual check

Risks:
- none / note

Next:
- none / next step
```

## 2026-07-31 Codex
Goal:
- Fix local Python so `scripts/deploy_guard.py` can run.

Changed:
- User environment: installed Python 3.12.10 with `winget`.
- User PATH: prepended `C:\Users\dream\AppData\Local\Programs\Python\Python312` and `...\Scripts`.
- User env: set `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`.
- Git remote: added `origin=https://github.com/Stacks112/Stacks.git` in `C:\Users\dream\Downloads\Stacks`.
- `AGENT_HANDOFF.md`

Verified:
- `C:\Users\dream\AppData\Local\Programs\Python\Python312\python.exe --version` -> `Python 3.12.10`
- `scripts/deploy_guard.py index.html` runs in `C:\Users\dream\Downloads\Stacks`.
- `scripts/deploy_guard.py index.html` runs in `C:\Users\dream\Downloads\Stacks-main`.

Risks:
- Current Codex process still inherits old PATH, so this session may need explicit Python path. New terminals should resolve `python` from Python312 before WindowsApps.
- Production checkout was rebased to `origin/main` (`0a0cd72`); existing untracked `_preview_no_today_news/` left untouched.

Next:
- For future deploys, run `python scripts\deploy_guard.py <touched-files>` from a new terminal or use the full Python path in this current Codex session.

## 2026-07-31 Codex
Goal:
- Restore view/like/comment counters after frontend pointed at retired workers.dev URL.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\index.html`
- `AGENT_HANDOFF.md`

Verified:
- `https://stacks-comments.wnrakrhdn128.workers.dev/views` returns 404.
- `https://api.stacksdaily.com/views` returns existing D1 data, e.g. `macro-week-2026-07-26 = 36`.
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main diff --check -- index.html`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main push origin HEAD:main`
- Production commit: `b4ff0211 fix(api): point comments to custom domain`.

Risks:
- `scripts/deploy_guard.py` could not run because `python` is a Microsoft Store stub and `py` is not installed.
- Production worktree remains detached HEAD with existing untracked `_preview_no_today_news/` left untouched.

Next:
- Verify live `stacksdaily.com` HTML contains `const COMMENTS_API = "https://api.stacksdaily.com";`.

## 2026-07-31 Codex
Goal:
- Fix remaining "이전 판단" visibility in mobile feed and deploy.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\assets\v82.css`
- `C:\Users\dream\Downloads\Stacks-main\index.html`
- `AGENT_HANDOFF.md`

Verified:
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main fetch origin main`
- `rg -n "\.card\.v82c .*\.opp|v82\.css\?v=1a67db08|card:not\(\.v83one\).*\.opp" C:\Users\dream\Downloads\Stacks-main\assets\v82.css C:\Users\dream\Downloads\Stacks-main\assets\v83tw.css C:\Users\dream\Downloads\Stacks-main\index.html -S`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main diff --check -- assets/v82.css index.html`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main push origin HEAD:main`
- Live cache-busted HTML contains `assets/v82.css?v=1a67db08`.
- Live CSS contains `.card.v82c .opp`.

Risks:
- `scripts/deploy_guard.py` failed because `python` is a Microsoft Store stub that only printed `Python`.
- Production worktree remains detached HEAD with existing untracked `_preview_no_today_news/` left untouched.

Next:
- none.

## 2026-07-31 Codex
Goal:
- Make the Stacks working context available from another computer through GitHub.

Changed:
- `AGENTS.md`
- `STACKS_CONTEXT.md`
- `AGENT_HANDOFF.md`
- `.gitignore`

Verified:
- `git status --short --branch`
- `git diff -- STACKS_CONTEXT.md`
- `git remote -v`
- `git push github master`
- `git fetch github main`
- `git rebase github/main`
- `git push github HEAD:main`

Risks:
- ChatGPT/Codex chat history itself is account/workspace-side and is not moved by Git.
- Local generated folders/archive (`dist/`, `node_modules/`, `stacks-site-01ae9f9.tar.gz`) were left out of the commit and ignored.

Next:
- On another computer, clone or pull `https://github.com/Stacks112/Stacks.git` on `main`, then read `AGENTS.md`, `STACKS_CONTEXT.md`, and `AGENT_HANDOFF.md`.

## 2026-07-31 Codex
Goal:
- Deploy feed/detail visibility fix to production.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\assets\v83tw.css`
- `C:\Users\dream\Downloads\Stacks-main\index.html`
- `AGENT_HANDOFF.md`

Verified:
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main fetch origin main`
- Rebased local detached commit onto `origin/main`.
- `rg -n "#v82dbody \.card:not\(\.collapsed\) \.related|card:not\(\.v83one\) \.opp|v83tw\.css\?v=9f4d4c2a" C:\Users\dream\Downloads\Stacks-main\assets\v83tw.css C:\Users\dream\Downloads\Stacks-main\index.html -S`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main diff --check -- assets/v83tw.css index.html`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main push origin HEAD:main`
- Live HTML contains `assets/v83tw.css?v=9f4d4c2a`.
- Live CSS contains `#v82dbody .card:not(.collapsed) .related` and `card:not(.v83one) .opp`.

Risks:
- `scripts/deploy_guard.py` was not run because `python`, `py`, `python3`, and `node` were not available in PATH.
- Production worktree remains detached HEAD with existing untracked `_preview_no_today_news/` left untouched.

Next:
- none.

## 2026-07-31 Codex
Goal:
- Hide related-read and prior-judgment blocks from feed cards; keep them in post detail only.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\assets\v83tw.css`
- `C:\Users\dream\Downloads\Stacks-main\index.html`
- `AGENT_HANDOFF.md`

Verified:
- `rg -n "#v82dbody \.card:not\(\.collapsed\) \.related|card:not\(\.v83one\) \.opp|v83tw\.css\?v=" C:\Users\dream\Downloads\Stacks-main\assets\v83tw.css C:\Users\dream\Downloads\Stacks-main\index.html -S`
- `git -c safe.directory=C:/Users/dream/Downloads/Stacks-main -C C:\Users\dream\Downloads\Stacks-main diff -- assets/v83tw.css index.html`

Risks:
- Not deployed. Production worktree has existing untracked `_preview_no_today_news/` left untouched.

Next:
- Deploy to `stacksdaily.com` when requested.

## 2026-07-31 Codex
Goal:
- Set up shared Codex/Claude handoff workflow.

Changed:
- `AGENTS.md`
- `STACKS_CONTEXT.md`
- `AGENT_HANDOFF.md`

Verified:
- Read current context files.
- Checked `git status --short`.

Risks:
- Existing unrelated worktree changes were present before this setup.

Next:
- Future Codex/Claude turns should append new entries here after work.

## 2026-07-31 Codex
Goal:
- Remove dead links from production Stacks UI.

Changed:
- `C:\Users\dream\Downloads\Stacks-main\index.html`

Verified:
- `href="#"` static scan: `0`
- Brand link now points to `/`.
- TradingView full-screen fallback link now points to `https://www.tradingview.com/chart/`.
- `PYTHONIOENCODING=utf-8 python scripts/deploy_guard.py index.html`

Risks:
- Not deployed. Commit is local detached HEAD: `5b73f693 fix(ui): remove dead hash links`.
- Existing untracked `C:\Users\dream\Downloads\Stacks-main\_preview_no_today_news\` left untouched.

Next:
- Push/deploy to `stacksdaily.com` only when user says `배포`.

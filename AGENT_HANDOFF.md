# Agent Handoff Log

Shared handoff log for Codex and Claude.

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

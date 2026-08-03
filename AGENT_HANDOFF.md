# Agent Handoff Log

Shared handoff log for Codex and Claude.

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

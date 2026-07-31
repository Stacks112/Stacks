# Agent Handoff Log

Shared handoff log for Codex and Claude.

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
- Make the Stacks working context available from another computer through GitHub.

Changed:
- `AGENTS.md`
- `STACKS_CONTEXT.md`
- `AGENT_HANDOFF.md`

Verified:
- `git status --short --branch`
- `git diff -- STACKS_CONTEXT.md`
- `git remote -v`

Risks:
- ChatGPT/Codex chat history itself is account/workspace-side and is not moved by Git.
- Local untracked archive `stacks-site-01ae9f9.tar.gz` was left out of the commit.

Next:
- On another computer, clone or pull `https://github.com/Stacks112/Stacks.git`, then read `AGENTS.md`, `STACKS_CONTEXT.md`, and `AGENT_HANDOFF.md`.

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

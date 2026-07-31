# Stacks Working Context

## Current Setup
- Project: Stacks
- Reference playbooks:
  - `playbook-1-infra.md`
  - `playbook-2-ops.md`
- Claude is also being used alongside this assistant.

## What the playbooks say
- `playbook-1-infra.md` covers the overall architecture:
  - static frontend on GitHub Pages
  - Cloudflare Worker + D1 for dynamic features
  - SEO, email, notifications, analytics, ads
  - deployment and security basics
- `playbook-2-ops.md` covers working rules:
  - edit by path/area, not all at once
  - avoid conflicts and clobbering
  - verify changes carefully
  - keep status notes and guardrails

## Working Assumptions
- The playbooks are enough to begin and continue work safely.
- If the project grows or multiple agents work at once, a short status note or shared task list will help keep alignment.
- For now, this file is the quick reference for the current context.

## Deployment Rule
- When the user says "deploy" or "배포", deploy to the production Stacks repo/site:
  - repo/worktree: `C:\Users\dream\Downloads\Stacks-main`
  - remote: `https://github.com/Stacks112/Stacks.git`
  - site: `https://stacksdaily.com`
- Do not treat the Sites demo project or `*.chatgpt.site` URL as production unless the user explicitly asks for the demo.
- Before production deploy: fetch/rebase against `origin/main`, run `scripts/deploy_guard.py` for touched production files, commit, push to `main`, then verify `stacksdaily.com`.

## Practical Takeaway
- Use the playbooks as the source of truth.
- Use `AGENT_HANDOFF.md` for short Codex/Claude status handoffs.
- Keep changes small and path-specific.
- Treat Claude and this assistant as collaborating against the same playbook, not separate sources of truth.

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

## Practical Takeaway
- Use the playbooks as the source of truth.
- Keep changes small and path-specific.
- Treat Claude and this assistant as collaborating against the same playbook, not separate sources of truth.

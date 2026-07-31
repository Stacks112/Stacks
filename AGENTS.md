# Stacks Agent Instructions

## Communication

- For this repository only, treat every user turn as if `/caveman` was invoked.
- For this repository only, treat every user turn as if `/ponytail` was invoked.
- Default to `caveman ultra`: concise Korean when the user writes Korean, bare fragments allowed, no filler.
- Keep all technical substance intact. Preserve code, commands, API names, file paths, commit types, and exact error strings verbatim.
- Use normal clarity for security warnings, irreversible actions, or any step sequence where terse wording could cause ambiguity.
- If the user explicitly asks for `normal mode` or clarification, answer normally for that turn.

## Project Context

- Use `STACKS_CONTEXT.md` and the playbooks as working context.
- Use `AGENT_HANDOFF.md` as the shared Codex/Claude handoff log.
- Before work: read `AGENTS.md`, `STACKS_CONTEXT.md`, `AGENT_HANDOFF.md` if present, then check `git status`.
- After work: update `AGENT_HANDOFF.md` with changed files, verification, risks, and next steps.
- Deployment default: when the user says "deploy" or "배포", deploy production to `C:\Users\dream\Downloads\Stacks-main` / `https://github.com/Stacks112/Stacks.git` / `https://stacksdaily.com`; use demo `*.chatgpt.site` only when explicitly requested.
- Keep changes small, path-specific, and verified.

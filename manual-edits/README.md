# Stacks Manual Edits

Manual edits let one admin patch an already-published Stacks article quickly without rebuilding the whole static site.

## What This Adds

- Local editor: `pnpm edit:post`
- D1 table: `manual_post_overrides`
- Worker API: `/api/manual-post`
- Static page runtime patcher: `/assets/manual-overrides.js`

The static article stays as the base version. If an active override exists for the article slug, the browser replaces the title and article body after load.

## Setup

Run the schema once:

```bash
wrangler d1 execute <DATABASE_NAME> --file=manual-edits/schema.sql
```

Set an admin token:

```bash
wrangler secret put MANUAL_EDITOR_TOKEN
```

Optional local editor origin list:

```bash
wrangler secret put MANUAL_EDITOR_ORIGINS
```

Recommended value:

```text
http://127.0.0.1:4177
```

## Worker Integration

Import and route before fallback handling:

```js
import { handleManualEditRequest } from "./manual-edits.js";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/api/manual-post") {
      return handleManualEditRequest(request, env);
    }

    return new Response("Not found", { status: 404 });
  },
};
```

## Static Page Integration

Add once to article pages:

```html
<script src="/assets/manual-overrides.js" defer></script>
```

## Editing Flow

1. Start local editor:

```bash
pnpm edit:post
```

1. Open:

```text
http://127.0.0.1:4177
```

1. Paste a Stacks article URL and click `불러오기`.
1. Edit title/body directly.
1. Click `저장` to save a local draft in `manual-edits/drafts/`.
1. Enter the Worker API base URL and admin token.
1. Click `운영 반영`.
1. Refresh the live article.

## Rollback

Archive an override:

```bash
curl -X DELETE "https://stacksdaily.com/api/manual-post?slug=<slug>" \
  -H "Authorization: Bearer <MANUAL_EDITOR_TOKEN>"
```

After rollback, the static article appears again.

## Guardrails

- Keep `MANUAL_EDITOR_TOKEN` secret.
- Use this for urgent copy fixes, factual corrections, and short-term takedowns.
- Later, copy the correction back into the real source article and archive the override.
- Do not use this as the main publishing system.

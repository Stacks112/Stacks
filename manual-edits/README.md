# Stacks Manual Edits

Manual edits patch an already-published Stacks article without rebuilding the whole static site.

Current live site path:

1. Run the local editor.
1. Edit the article in the browser.
1. Click `저장`.
1. Commit and push the generated file under `assets/manual-overrides/`.

The article page loads `/assets/manual-overrides/<slug>.json`. If the file exists and `status` is `active`, the browser replaces the title and article body after load.

## Local Editor

```bash
node scripts/manual-post-editor.mjs
```

Open:

```text
http://127.0.0.1:4177
```

The editor writes two files:

- `manual-edits/drafts/<slug>.json`: ignored local draft
- `assets/manual-overrides/<slug>.json`: deployable live override

## Rollback

Delete the matching file under `assets/manual-overrides/`, then commit and push.

## Notes

`worker/index.js` also contains a D1-backed `/api/manual-post` implementation for a future Cloudflare-proxied setup. Today, `stacksdaily.com` resolves directly to GitHub Pages, so the live path uses static JSON overrides.

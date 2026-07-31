# Stacks Manual Edits

Manual edits patch an already-published Stacks article without rebuilding the whole static site.

Current live site path:

1. Run the local editor.
1. Edit the article in the browser.
1. Enter the manual editor token.
1. Click `저장`.

The editor saves a local backup, then writes the override to Cloudflare D1 through `https://api.stacksdaily.com/api/manual-post`. Article pages read that API with `cache: no-store`, so a refresh shows the edit without a Git commit or GitHub Pages deployment.

## Local Editor

```bash
node scripts/manual-post-editor.mjs
```

Open:

```text
http://127.0.0.1:4177
```

The editor writes one ignored local backup:

- `manual-edits/drafts/<slug>.json`: ignored local draft

## Rollback

Send `DELETE https://api.stacksdaily.com/api/manual-post?slug=<slug>` with the manual editor token. The Worker archives the D1 override.

## Notes

`stacksdaily.com` remains on GitHub Pages. Only `api.stacksdaily.com` is a Cloudflare Worker custom domain. Existing files under `assets/manual-overrides/` remain as a read fallback if the API has no record.

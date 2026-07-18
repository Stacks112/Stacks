# Worker source of truth

The Cloudflare Worker source now lives at **`worker/index.js`** (config:
`worker/wrangler.toml`). Edit it there and commit — the GitHub Action
`deploy-worker.yml` deploys it to Cloudflare automatically.

One-time setup instructions are at the top of `ops/deploy-worker.yml`.
Until that workflow + the CLOUDFLARE_API_TOKEN secret + the two IDs in
wrangler.toml are in place, deploy manually by pasting `worker/index.js`
into the Cloudflare dashboard.

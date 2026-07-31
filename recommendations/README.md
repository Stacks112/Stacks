# Stacks Recommendation Feature

This package adds three article recommendation blocks:

- Same ticker latest articles
- Same theme popular articles
- People who read this also read

It is designed for the current Stacks architecture: static pages on GitHub Pages plus Cloudflare Worker and D1 for dynamic behavior.

## Files

- `recommendations/schema.sql`: D1 tables and indexes
- `worker/recommendations.js`: Worker handlers for view logging and recommendation reads
- `assets/recommendations.js`: Static-page widget
- `assets/recommendations.css`: Widget styling

## D1 Setup

Run the schema once against the production D1 database:

```bash
wrangler d1 execute <DATABASE_NAME> --file=recommendations/schema.sql
```

The Worker must expose the D1 binding as `DB`.

## Worker Integration

Import and call the handler before other fallback routing:

```js
import { handleRecommendationRequest } from "./recommendations.js";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/api/article-view") || url.pathname.startsWith("/api/recommendations")) {
      return handleRecommendationRequest(request, env);
    }

    return new Response("Not found", { status: 404 });
  },
};
```

If the existing Worker file lives at `worker/index.js`, keep `worker/recommendations.js` beside it and adjust the import path if needed.

## Article Page Integration

Add the CSS and JS once on article pages:

```html
<link rel="stylesheet" href="/assets/recommendations.css">
<script src="/assets/recommendations.js" defer></script>
```

Add this block near the bottom of each article:

```html
<aside
  class="recommendations"
  data-recommendations
  data-article-id="nvidia-ai-infra-2026-07-31"
  data-title="NVIDIA AI infrastructure demand update"
  data-url="/posts/nvidia-ai-infra-2026-07-31.html"
  data-tickers="NVIDIA,NVDA"
  data-tags="AI INFRASTRUCTURE,SEMICONDUCTOR,DATA CENTER"
  data-published-at="2026-07-31"
  hidden
></aside>
```

For Korean display names, use Korean tags such as `AI 인프라,반도체,데이터센터`. For stock matching, keep ticker-like labels consistent across articles.

## How It Works

When a reader opens an article, the widget sends a lightweight view event to `/api/article-view`. The Worker stores the article metadata, increments the view count, and updates co-read relationships based on recent articles from the same browser/device signature.

The widget then calls `/api/recommendations` and renders available sections. If the API fails, the article remains readable and the recommendation area stays hidden.

## First Success Metric

Track whether readers who see this widget read more pages per visit:

- Baseline: pages per session before launch
- Target: 3 or more pages per session on articles with recommendations
- Secondary metric: click-through rate per recommendation block

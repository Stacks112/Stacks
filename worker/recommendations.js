const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
};

export async function handleRecommendationRequest(request, env) {
  const url = new URL(request.url);

  if (url.pathname === "/api/article-view" && request.method === "POST") {
    return recordArticleView(request, env);
  }

  if (url.pathname === "/api/recommendations" && request.method === "GET") {
    return getRecommendations(request, env);
  }

  return new Response("Not found", { status: 404 });
}

export async function recordArticleView(request, env) {
  if (!env.DB) {
    return json({ ok: false, error: "D1 binding env.DB is missing" }, 500);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400);
  }

  const article = normalizeArticle(body);
  if (!article.articleId || !article.title || !article.url) {
    return json({ ok: false, error: "articleId, title, and url are required" }, 400);
  }

  const sessionHash = await makeSessionHash(request);
  const refArticleId = cleanText(body.refArticleId || "", 160);

  await env.DB.batch([
    env.DB.prepare(`
      INSERT INTO article_metrics (
        article_id, title, url, published_at, tickers_json, tags_json, view_count, updated_at
      )
      VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1, CURRENT_TIMESTAMP)
      ON CONFLICT(article_id) DO UPDATE SET
        title = excluded.title,
        url = excluded.url,
        published_at = COALESCE(excluded.published_at, article_metrics.published_at),
        tickers_json = excluded.tickers_json,
        tags_json = excluded.tags_json,
        view_count = article_metrics.view_count + 1,
        updated_at = CURRENT_TIMESTAMP
    `).bind(
      article.articleId,
      article.title,
      article.url,
      article.publishedAt,
      JSON.stringify(article.tickers),
      JSON.stringify(article.tags),
    ),
    env.DB.prepare(`
      INSERT INTO article_views (
        article_id, session_hash, ref_article_id, tickers_json, tags_json
      )
      VALUES (?1, ?2, ?3, ?4, ?5)
    `).bind(
      article.articleId,
      sessionHash,
      refArticleId || null,
      JSON.stringify(article.tickers),
      JSON.stringify(article.tags),
    ),
  ]);

  await updateCoReads(env, sessionHash, article.articleId);

  return json({ ok: true });
}

export async function getRecommendations(request, env) {
  if (!env.DB) {
    return json({ ok: false, error: "D1 binding env.DB is missing" }, 500);
  }

  const url = new URL(request.url);
  const articleId = cleanText(url.searchParams.get("articleId") || "", 160);
  const tickers = normalizeList(url.searchParams.get("tickers") || "");
  const tags = normalizeList(url.searchParams.get("tags") || "");
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") || 12), 1), 24);

  const [sameTicker, sameTheme, coRead] = await Promise.all([
    findSameTicker(env, articleId, tickers, limit),
    findSameTheme(env, articleId, tags, limit),
    findCoRead(env, articleId, limit),
  ]);

  return json({
    ok: true,
    sections: [
      {
        id: "same-ticker",
        title: tickers[0] ? `${tickers[0]} 관련 최신 글` : "같은 종목 최신 글",
        items: sameTicker,
      },
      {
        id: "same-theme",
        title: tags[0] ? `${tags[0]} 테마에서 많이 읽은 글` : "같은 테마에서 많이 읽은 글",
        items: sameTheme,
      },
      {
        id: "co-read",
        title: "이 글을 읽은 사람들이 함께 본 글",
        items: coRead,
      },
    ].filter((section) => section.items.length > 0),
  });
}

async function updateCoReads(env, sessionHash, articleId) {
  const recent = await env.DB.prepare(`
    SELECT DISTINCT article_id
    FROM article_views
    WHERE session_hash = ?1
      AND article_id <> ?2
      AND created_at >= datetime('now', '-14 days')
    ORDER BY created_at DESC
    LIMIT 12
  `).bind(sessionHash, articleId).all();

  const statements = [];
  for (const row of recent.results || []) {
    statements.push(upsertCoRead(env, articleId, row.article_id));
    statements.push(upsertCoRead(env, row.article_id, articleId));
  }

  if (statements.length > 0) {
    await env.DB.batch(statements);
  }
}

function upsertCoRead(env, sourceId, targetId) {
  return env.DB.prepare(`
    INSERT INTO article_co_reads (source_article_id, target_article_id, score, last_seen)
    VALUES (?1, ?2, 1, CURRENT_TIMESTAMP)
    ON CONFLICT(source_article_id, target_article_id) DO UPDATE SET
      score = article_co_reads.score + 1,
      last_seen = CURRENT_TIMESTAMP
  `).bind(sourceId, targetId);
}

async function findSameTicker(env, articleId, tickers, limit) {
  if (tickers.length === 0) return [];

  const rows = await env.DB.prepare(`
    SELECT article_id, title, url, published_at, view_count
    FROM article_metrics
    WHERE article_id <> ?1
      AND (${tickers.map((_, index) => `tickers_json LIKE ?${index + 2}`).join(" OR ")})
    ORDER BY datetime(COALESCE(published_at, updated_at)) DESC, view_count DESC
    LIMIT ?${tickers.length + 2}
  `).bind(articleId, ...tickers.map((ticker) => `%\"${ticker}\"%`), limit).all();

  return mapRows(rows.results);
}

async function findSameTheme(env, articleId, tags, limit) {
  if (tags.length === 0) return [];

  const rows = await env.DB.prepare(`
    SELECT article_id, title, url, published_at, view_count
    FROM article_metrics
    WHERE article_id <> ?1
      AND (${tags.map((_, index) => `tags_json LIKE ?${index + 2}`).join(" OR ")})
    ORDER BY view_count DESC, datetime(COALESCE(published_at, updated_at)) DESC
    LIMIT ?${tags.length + 2}
  `).bind(articleId, ...tags.map((tag) => `%\"${tag}\"%`), limit).all();

  return mapRows(rows.results);
}

async function findCoRead(env, articleId, limit) {
  if (!articleId) return [];

  const rows = await env.DB.prepare(`
    SELECT m.article_id, m.title, m.url, m.published_at, m.view_count
    FROM article_co_reads c
    JOIN article_metrics m ON m.article_id = c.target_article_id
    WHERE c.source_article_id = ?1
      AND c.target_article_id <> ?1
    ORDER BY c.score DESC, datetime(c.last_seen) DESC
    LIMIT ?2
  `).bind(articleId, limit).all();

  return mapRows(rows.results);
}

function normalizeArticle(body) {
  return {
    articleId: cleanText(body.articleId || body.id || "", 160),
    title: cleanText(body.title || "", 240),
    url: cleanUrl(body.url || ""),
    publishedAt: cleanText(body.publishedAt || body.published_at || "", 40) || null,
    tickers: normalizeList(body.tickers || body.ticker || ""),
    tags: normalizeList(body.tags || body.tag || ""),
  };
}

function normalizeList(value) {
  const list = Array.isArray(value) ? value : String(value).split(",");
  return [...new Set(list
    .map((item) => cleanText(item, 60).toUpperCase())
    .filter(Boolean))]
    .slice(0, 12);
}

function cleanText(value, maxLength) {
  return String(value || "")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .trim()
    .slice(0, maxLength);
}

function cleanUrl(value) {
  const text = cleanText(value, 500);
  if (!text.startsWith("/") && !text.startsWith("https://") && !text.startsWith("http://")) {
    return "";
  }
  return text;
}

function mapRows(rows = []) {
  return rows.map((row) => ({
    articleId: row.article_id,
    title: row.title,
    url: row.url,
    publishedAt: row.published_at,
    viewCount: row.view_count,
  }));
}

async function makeSessionHash(request) {
  const ip = request.headers.get("cf-connecting-ip") || "";
  const ua = request.headers.get("user-agent") || "";
  const day = new Date().toISOString().slice(0, 10);
  const raw = `${ip}|${ua}|${day}`;
  const data = new TextEncoder().encode(raw);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function json(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: jsonHeaders,
  });
}

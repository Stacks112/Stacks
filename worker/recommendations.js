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
        article_id, title, url, author, published_at, tickers_json, tags_json, view_count, updated_at
      )
      VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 1, CURRENT_TIMESTAMP)
      ON CONFLICT(article_id) DO UPDATE SET
        title = excluded.title,
        url = excluded.url,
        author = COALESCE(excluded.author, article_metrics.author),
        published_at = COALESCE(excluded.published_at, article_metrics.published_at),
        tickers_json = excluded.tickers_json,
        tags_json = excluded.tags_json,
        view_count = article_metrics.view_count + 1,
        updated_at = CURRENT_TIMESTAMP
    `).bind(
      article.articleId,
      article.title,
      article.url,
      article.author || null,
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
  const limit = Math.min(Math.max(Number(url.searchParams.get("limit") || 12), 1), 24);

  const tickerSections = await findTickerSections(env, articleId, tickers, limit);

  return json({
    ok: true,
    sections: tickerSections.filter((section) => section.items.length > 0),
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

async function findTickerSections(env, articleId, tickers, limit) {
  const groups = groupTickers(tickers);
  if (groups.length === 0) return [];

  const sectionLimit = Math.min(limit, 4);
  return Promise.all(groups.map(async (group) => ({
    id: `ticker-${slugify(group.key)}`,
    title: `${formatTickerName(group.key)} 최신 글`,
    items: await findTickerLatest(env, articleId, group.aliases, sectionLimit),
  })));
}

async function findTickerLatest(env, articleId, aliases, limit) {
  const rows = await env.DB.prepare(`
    SELECT article_id, title, url, published_at, author, view_count
    FROM article_metrics
    WHERE article_id <> ?1
      AND (${aliases.map((_, index) => `tickers_json LIKE ?${index + 2}`).join(" OR ")})
    ORDER BY datetime(COALESCE(published_at, updated_at)) DESC, view_count DESC
    LIMIT ?${aliases.length + 2}
  `).bind(articleId, ...aliases.map((ticker) => `%\"${ticker}\"%`), limit).all();

  return mapRows(rows.results);
}

function normalizeArticle(body) {
  return {
    articleId: cleanText(body.articleId || body.id || "", 160),
    title: cleanText(body.title || "", 240),
    url: cleanUrl(body.url || ""),
    author: cleanText(body.author || body.authorName || body.byline || "", 120),
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
    author: row.author,
    publishedAt: row.published_at,
    viewCount: row.view_count,
  }));
}

function groupTickers(tickers) {
  const groups = new Map();

  for (const ticker of tickers) {
    const key = canonicalTicker(ticker);
    if (!groups.has(key)) {
      groups.set(key, new Set(aliasTickers(key)));
    }
    groups.get(key).add(ticker);
  }

  return [...groups.entries()].map(([key, aliases]) => ({
    key,
    aliases: [...aliases],
  }));
}

function canonicalTicker(ticker) {
  const value = String(ticker || "").toUpperCase();
  if (["005930", "005930.KS", "SAMSUNG", "SAMSUNG ELECTRONICS", "삼성전자"].includes(value)) {
    return "SAMSUNG ELECTRONICS";
  }
  if (["AVGO", "BROADCOM", "브로드컴"].includes(value)) {
    return "BROADCOM";
  }
  return value;
}

function aliasTickers(key) {
  if (key === "SAMSUNG ELECTRONICS") {
    return ["SAMSUNG ELECTRONICS", "SAMSUNG", "005930", "005930.KS", "삼성전자"];
  }
  if (key === "BROADCOM") {
    return ["BROADCOM", "AVGO", "브로드컴"];
  }
  return [key];
}

function formatTickerName(key) {
  if (key === "SAMSUNG ELECTRONICS") return "삼성전자";
  if (key === "BROADCOM") return "브로드컴";
  return key;
}

function slugify(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9가-힣]+/g, "-")
    .replace(/^-+|-+$/g, "") || "stock";
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

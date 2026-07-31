const jsonHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
};

export async function handleManualEditRequest(request, env) {
  const url = new URL(request.url);

  if (url.pathname === "/api/manual-post" && request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(request, env) });
  }

  if (url.pathname === "/api/manual-post" && request.method === "GET") {
    return getManualPost(request, env);
  }

  if (url.pathname === "/api/manual-post" && request.method === "POST") {
    return saveManualPost(request, env);
  }

  if (url.pathname === "/api/manual-post" && request.method === "DELETE") {
    return deleteManualPost(request, env);
  }

  return new Response("Not found", { status: 404 });
}

async function getManualPost(request, env) {
  if (!env.DB) {
    return json({ ok: false, error: "D1 binding env.DB is missing" }, 500, request, env);
  }
  await ensureManualTables(env);

  const url = new URL(request.url);
  const slug = cleanSlug(url.searchParams.get("slug") || "");
  if (!slug) {
    return json({ ok: false, error: "slug is required" }, 400, request, env);
  }

  const row = await env.DB.prepare(`
    SELECT slug, title, body_html, source_url, published_at, status, updated_at
    FROM manual_post_overrides
    WHERE slug = ?1 AND status = 'active'
  `).bind(slug).first();

  if (!row) {
    return json({ ok: true, found: false }, 200, request, env);
  }

  return json({
    ok: true,
    found: true,
    post: {
      slug: row.slug,
      title: row.title,
      bodyHtml: row.body_html,
      sourceUrl: row.source_url,
      publishedAt: row.published_at,
      status: row.status,
      updatedAt: row.updated_at,
    },
  }, 200, request, env);
}

async function saveManualPost(request, env) {
  const denied = await requireAdmin(request, env);
  if (denied) return denied;
  if (!env.DB) {
    return json({ ok: false, error: "D1 binding env.DB is missing" }, 500, request, env);
  }
  await ensureManualTables(env);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "Invalid JSON body" }, 400, request, env);
  }

  const post = normalizeManualPost(body);
  if (!post.slug || !post.title || !post.bodyHtml) {
    return json({ ok: false, error: "slug, title, and bodyHtml are required" }, 400, request, env);
  }

  await env.DB.prepare(`
    INSERT INTO manual_post_overrides (
      slug, title, body_html, source_url, published_at, status, updated_at
    )
    VALUES (?1, ?2, ?3, ?4, ?5, ?6, CURRENT_TIMESTAMP)
    ON CONFLICT(slug) DO UPDATE SET
      title = excluded.title,
      body_html = excluded.body_html,
      source_url = excluded.source_url,
      published_at = excluded.published_at,
      status = excluded.status,
      updated_at = CURRENT_TIMESTAMP
  `).bind(
    post.slug,
    post.title,
    post.bodyHtml,
    post.sourceUrl || null,
    post.publishedAt || null,
    post.status,
  ).run();

  return json({ ok: true, slug: post.slug }, 200, request, env);
}

async function deleteManualPost(request, env) {
  const denied = await requireAdmin(request, env);
  if (denied) return denied;
  if (!env.DB) {
    return json({ ok: false, error: "D1 binding env.DB is missing" }, 500, request, env);
  }
  await ensureManualTables(env);

  const url = new URL(request.url);
  const slug = cleanSlug(url.searchParams.get("slug") || "");
  if (!slug) {
    return json({ ok: false, error: "slug is required" }, 400, request, env);
  }

  await env.DB.prepare(`
    UPDATE manual_post_overrides
    SET status = 'archived', updated_at = CURRENT_TIMESTAMP
    WHERE slug = ?1
  `).bind(slug).run();

  return json({ ok: true, slug }, 200, request, env);
}

async function requireAdmin(request, env) {
  const expected = env.MANUAL_EDITOR_TOKEN;
  if (!expected) {
    return json({ ok: false, error: "MANUAL_EDITOR_TOKEN is not configured" }, 500, request, env);
  }

  const header = request.headers.get("authorization") || "";
  const bearer = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  const token = request.headers.get("x-stacks-admin-token") || bearer;
  if (token !== expected) {
    return json({ ok: false, error: "Unauthorized" }, 401, request, env);
  }

  return null;
}

async function ensureManualTables(env) {
  await env.DB.batch([
    env.DB.prepare(`
      CREATE TABLE IF NOT EXISTS manual_post_overrides (
        slug TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        body_html TEXT NOT NULL,
        source_url TEXT,
        published_at TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
      )
    `),
    env.DB.prepare(`
      CREATE INDEX IF NOT EXISTS idx_manual_post_overrides_status_updated
      ON manual_post_overrides (status, updated_at DESC)
    `),
  ]);
}

function normalizeManualPost(body) {
  return {
    slug: cleanSlug(body.slug || ""),
    title: cleanText(body.title || "", 240),
    bodyHtml: cleanHtmlFragment(body.bodyHtml || ""),
    sourceUrl: cleanUrl(body.sourceUrl || body.source_url || ""),
    publishedAt: cleanText(body.publishedAt || body.published_at || "", 40),
    status: body.status === "archived" ? "archived" : "active",
  };
}

function cleanHtmlFragment(value) {
  return String(value || "")
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
    .replace(/<object[\s\S]*?<\/object>/gi, "")
    .replace(/<embed[\s\S]*?>/gi, "")
    .replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "")
    .replace(/\s(href|src)\s*=\s*(['"])\s*javascript:[\s\S]*?\2/gi, "")
    .trim()
    .slice(0, 250000);
}

function cleanText(value, maxLength) {
  return String(value || "")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .trim()
    .slice(0, maxLength);
}

function cleanSlug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}

function cleanUrl(value) {
  const text = cleanText(value, 500);
  if (!text.startsWith("/") && !text.startsWith("https://") && !text.startsWith("http://")) {
    return "";
  }
  return text;
}

function corsHeaders(request, env) {
  const origin = request.headers.get("origin") || "";
  const allowed = String(env.MANUAL_EDITOR_ORIGINS || "http://127.0.0.1:4177")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const allowOrigin = allowed.includes(origin) ? origin : allowed[0] || "";

  return {
    "access-control-allow-origin": allowOrigin,
    "access-control-allow-methods": "GET,POST,DELETE,OPTIONS",
    "access-control-allow-headers": "authorization,content-type",
    "access-control-max-age": "86400",
  };
}

function json(payload, status = 200, request, env) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...jsonHeaders,
      ...(request && env ? corsHeaders(request, env) : {}),
    },
  });
}

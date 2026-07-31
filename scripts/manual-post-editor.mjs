import { createServer } from "node:http";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const runtimeProcess = typeof process !== "undefined" ? process : null;
const port = Number(runtimeProcess?.env?.PORT || 4177);
const root = typeof nodeRepl !== "undefined" ? nodeRepl.cwd : runtimeProcess.cwd();
const defaultUrl = "https://stacksdaily.com/p/meru-pce-cpi-switch-june-first-drop.html";

createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://localhost:${port}`);

    if (request.method === "GET" && url.pathname === "/") {
      return sendHtml(response, editorHtml());
    }

    if (request.method === "GET" && url.pathname === "/api/load") {
      const target = url.searchParams.get("url") || defaultUrl;
      const article = await loadArticle(target);
      return sendJson(response, article);
    }

    if (request.method === "POST" && url.pathname === "/api/save") {
      const body = await readJson(request);
      const saved = await saveArticle(body);
      return sendJson(response, saved);
    }

    if (request.method === "POST" && url.pathname === "/api/publish") {
      const body = await readJson(request);
      const published = await publishArticle(body);
      return sendJson(response, published);
    }

    response.writeHead(404);
    response.end("Not found");
  } catch (error) {
    sendJson(response, { ok: false, error: error.message }, 500);
  }
}).listen(port, "127.0.0.1", () => {
  console.log(`Manual post editor: http://127.0.0.1:${port}`);
});

async function loadArticle(targetUrl) {
  const response = await fetch(targetUrl, {
    headers: {
      "user-agent": "Mozilla/5.0 StacksManualEditor/1.0",
    },
  });
  if (!response.ok) {
    throw new Error(`Failed to load article: ${response.status}`);
  }

  const html = await response.text();
  const title = extractFirst(html, /<h1[^>]*>([\s\S]*?)<\/h1>/i) || "";
  const date = extractFirst(html, /<meta property="article:published_time" content="([^"]+)"/i) || "";
  const canonical = extractFirst(html, /<link rel="canonical" href="([^"]+)"/i) || targetUrl;
  const slug = slugFromUrl(canonical);
  const bodyHtml = extractEditableBody(html);

  return {
    ok: true,
    title: decodeHtml(stripTags(title)),
    date,
    slug,
    sourceUrl: targetUrl,
    bodyHtml,
  };
}

function extractEditableBody(html) {
  const h1End = html.search(/<\/h1>/i);
  if (h1End < 0) return "";

  const bodyStart = findAfter(html, h1End, [
    '<figure class="srcq"',
    '<p class="gist"',
    '<h2 class="gsub"',
  ]);
  if (bodyStart < 0) return "";

  const bodyEnd = findAfter(html, bodyStart, [
    '<div class="sum3"',
    '<section class="rec-s"',
    '<div class="rec-s"',
    "<footer",
  ]);

  return html
    .slice(bodyStart, bodyEnd > bodyStart ? bodyEnd : undefined)
    .replace(/\sdata-app="[^"]*"/g, "")
    .trim();
}

function findAfter(text, fromIndex, needles) {
  const matches = needles
    .map((needle) => text.indexOf(needle, fromIndex))
    .filter((index) => index >= 0);
  return matches.length ? Math.min(...matches) : -1;
}

async function saveArticle(body) {
  const draft = normalizeDraft(body);
  const outDir = path.join(root, "manual-edits", "drafts");
  const outPath = path.join(outDir, `${draft.slug}.json`);

  await mkdir(outDir, { recursive: true });
  await writeFile(outPath, `${JSON.stringify(draft, null, 2)}\n`, "utf8");
  return { ok: true, path: outPath };
}

async function publishArticle(body) {
  const endpoint = cleanText(body.endpoint, 500).replace(/\/+$/, "");
  const token = String(body.token || "").trim();
  const draft = normalizeDraft(body.draft || body);

  if (!endpoint.startsWith("https://") && !endpoint.startsWith("http://127.0.0.1")) {
    throw new Error("endpoint must be https:// or local test URL");
  }
  if (!token) {
    throw new Error("admin token is required");
  }

  const response = await fetch(`${endpoint}/api/manual-post`, {
    method: "POST",
    headers: {
      "authorization": `Bearer ${token}`,
      "content-type": "application/json; charset=utf-8",
      "user-agent": "Mozilla/5.0 StacksManualEditor/1.0",
    },
    body: JSON.stringify(draft),
  });

  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { ok: false, error: text };
  }
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `publish failed: ${response.status}`);
  }
  return { ok: true, result: data };
}

function normalizeDraft(body) {
  const title = cleanText(body.title, 240);
  const slug = cleanSlug(body.slug || slugFromUrl(body.sourceUrl));
  const publishedAt = cleanText(body.publishedAt || body.date, 40);
  const sourceUrl = cleanText(body.sourceUrl, 500);
  const bodyHtml = String(body.bodyHtml || "").trim();

  if (!title || !slug || !bodyHtml) {
    throw new Error("title, slug, and bodyHtml are required");
  }

  return {
    slug,
    title,
    sourceUrl,
    publishedAt,
    bodyHtml,
    status: "active",
    updatedAt: new Date().toISOString(),
  };
}

function editorHtml() {
  return `<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stacks 수동 글 편집기</title>
<style>
  :root { color-scheme: light; --line:#e7e7ea; --ink:#18181b; --muted:#72727a; --bg:#f6f6f4; --paper:#fff; --accent:#2563eb; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
  .shell { display: grid; grid-template-columns: 360px minmax(0, 1fr); min-height: 100vh; }
  .side { position: sticky; top: 0; height: 100vh; padding: 22px; border-right: 1px solid var(--line); background: #fbfbfa; }
  .side h1 { margin: 0 0 18px; font-size: 20px; }
  label { display: block; margin: 14px 0 6px; font-size: 12px; font-weight: 700; color: #55545c; }
  input { width: 100%; min-height: 38px; padding: 9px 10px; border: 1px solid #d8d8dd; border-radius: 6px; font: inherit; background: white; }
  .buttons { display: flex; gap: 8px; margin-top: 18px; }
  button { min-height: 38px; padding: 0 13px; border: 1px solid #cfcfd6; border-radius: 6px; background: white; font-weight: 700; cursor: pointer; }
  button.primary { border-color: var(--accent); background: var(--accent); color: white; }
  .status { margin-top: 14px; min-height: 20px; color: var(--muted); font-size: 13px; line-height: 1.45; word-break: break-word; }
  .hint { margin-top: 20px; color: var(--muted); font-size: 13px; line-height: 1.55; }
  .canvas { padding: 32px 20px 80px; overflow: auto; }
  .paper { max-width: 760px; margin: 0 auto; padding: 42px 52px; border: 1px solid var(--line); border-radius: 8px; background: var(--paper); box-shadow: 0 18px 50px rgba(0,0,0,.07); }
  #title { width: 100%; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; padding: 0 0 18px; font-size: 34px; line-height: 1.25; font-weight: 800; outline: none; }
  #body { min-height: 520px; padding-top: 24px; outline: none; font-size: 17px; line-height: 1.8; }
  #body:focus { box-shadow: inset 0 0 0 2px rgba(37, 99, 235, .18); }
  #body p { margin: 0 0 18px; white-space: pre-line; }
  #body h2 { margin: 34px 0 12px; font-size: 24px; line-height: 1.35; }
  #body blockquote { margin: 0 0 22px; padding: 14px 18px; border-left: 4px solid #c8cad2; background: #f7f7f8; color: #44444d; }
  #body img { max-width: 100%; height: auto; border-radius: 6px; }
  #body a { color: #1d4ed8; }
  .gcardw, .gref, .chk, .srcq { margin: 20px 0; }
  .chk-g { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .chk-c { padding: 10px; border: 1px solid var(--line); border-radius: 6px; }
  .chk-c i, .chk-c b { display: block; font-style: normal; }
  .chk-c i { color: var(--muted); font-size: 12px; }
  @media (max-width: 900px) {
    .shell { grid-template-columns: 1fr; }
    .side { position: static; height: auto; }
    .paper { padding: 28px 22px; }
    #title { font-size: 26px; }
  }
</style>
</head>
<body>
<div class="shell">
  <aside class="side">
    <h1>Stacks 수동 글 편집기</h1>
    <label for="url">글 URL</label>
    <input id="url" value="${defaultUrl}">
    <label for="slug">파일 이름</label>
    <input id="slug">
    <label for="date">날짜</label>
    <input id="date">
    <label for="endpoint">Worker API</label>
    <input id="endpoint" value="https://stacksdaily.com">
    <label for="token">Admin token</label>
    <input id="token" type="password" autocomplete="off">
    <div class="buttons">
      <button id="load">불러오기</button>
      <button id="save">저장</button>
      <button id="publish" class="primary">운영 반영</button>
    </div>
    <div id="status" class="status"></div>
    <p class="hint">오른쪽 글 화면에서 제목과 본문을 직접 클릭해 수정하세요. 저장은 로컬 draft, 운영 반영은 Worker/D1 override에 적용합니다.</p>
  </aside>
  <main class="canvas">
    <article class="paper">
      <input id="title" placeholder="제목">
      <div id="body" contenteditable="true"></div>
    </article>
  </main>
</div>
<script>
const el = (id) => document.getElementById(id);
const status = (text) => el("status").textContent = text;

async function loadArticle() {
  status("불러오는 중...");
  const response = await fetch("/api/load?url=" + encodeURIComponent(el("url").value));
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "load failed");
  el("title").value = data.title;
  el("slug").value = data.slug;
  el("date").value = data.date;
  el("body").innerHTML = data.bodyHtml;
  status("불러옴. 오른쪽 글을 클릭해서 수정하세요.");
}

async function saveArticle() {
  status("저장 중...");
  const response = await fetch("/api/save", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      sourceUrl: el("url").value,
      title: el("title").value,
      slug: el("slug").value,
      date: el("date").value,
      bodyHtml: el("body").innerHTML
    })
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "save failed");
  status("저장 완료: " + data.path);
}

async function publishArticle() {
  status("운영 반영 중...");
  const response = await fetch("/api/publish", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      endpoint: el("endpoint").value,
      token: el("token").value,
      draft: currentDraft()
    })
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "publish failed");
  status("운영 반영 완료. 사이트에서 새로고침해 확인하세요.");
}

function currentDraft() {
  return {
    sourceUrl: el("url").value,
    title: el("title").value,
    slug: el("slug").value,
    date: el("date").value,
    bodyHtml: el("body").innerHTML
  };
}

el("load").addEventListener("click", () => loadArticle().catch((error) => status(error.message)));
el("save").addEventListener("click", () => saveArticle().catch((error) => status(error.message)));
el("publish").addEventListener("click", () => publishArticle().catch((error) => status(error.message)));
loadArticle().catch((error) => status(error.message));
</script>
</body>
</html>`;
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 2_000_000) {
        reject(new Error("Request body too large"));
        request.destroy();
      }
    });
    request.on("end", () => {
      try {
        resolve(JSON.parse(raw || "{}"));
      } catch {
        reject(new Error("Invalid JSON"));
      }
    });
    request.on("error", reject);
  });
}

function sendHtml(response, html, status = 200) {
  response.writeHead(status, { "content-type": "text/html; charset=utf-8" });
  response.end(html);
}

function sendJson(response, data, status = 200) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(data));
}

function extractFirst(text, pattern) {
  const match = text.match(pattern);
  return match ? match[1] : "";
}

function stripTags(text) {
  return String(text).replace(/<[^>]+>/g, "");
}

function decodeHtml(text) {
  return String(text)
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function slugFromUrl(value) {
  try {
    const parsed = new URL(value);
    const name = parsed.pathname.split("/").pop() || "post";
    return cleanSlug(name.replace(/\.html$/i, ""));
  } catch {
    return "post";
  }
}

function cleanText(value, maxLength) {
  return String(value || "")
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .trim()
    .slice(0, maxLength);
}

function cleanSlug(value) {
  return String(value || "post")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120) || "post";
}

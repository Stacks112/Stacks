import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const dist = path.join(root, "dist");
const serverDir = path.join(dist, "server");
const openaiDir = path.join(dist, ".openai");
const assetsDir = path.join(dist, "assets");

await rm(dist, { recursive: true, force: true });
await mkdir(serverDir, { recursive: true });
await mkdir(openaiDir, { recursive: true });
await mkdir(assetsDir, { recursive: true });

const demoHtml = await readFile(path.join(root, "demo", "index.html"), "utf8");
const css = await readFile(path.join(root, "demo", "style.css"), "utf8");
const js = await readFile(path.join(root, "demo", "recommendations-demo.js"), "utf8");
const hosting = await readFile(path.join(root, ".openai", "hosting.json"), "utf8");

const html = demoHtml
  .replace('<link rel="stylesheet" href="./style.css">', `<style>${css}</style>`)
  .replace('<script src="./recommendations-demo.js" defer></script>', `<script>${js}</script>`);

const manualOverrides = await readFile(path.join(root, "assets", "manual-overrides.js"), "utf8");
const server = `import { handleManualEditRequest } from "./manual-edits.js";
import { handleRecommendationRequest } from "./recommendations.js";

const html = ${JSON.stringify(html)};
const manualOverrides = ${JSON.stringify(manualOverrides)};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/manual-post") {
      return handleManualEditRequest(request, env);
    }

    if (url.pathname === "/api/article-view" || url.pathname === "/api/recommendations") {
      return handleRecommendationRequest(request, env);
    }

    if (url.pathname === "/assets/manual-overrides.js") {
      return new Response(manualOverrides, {
        headers: {
          "content-type": "text/javascript; charset=utf-8",
          "cache-control": "public, max-age=60"
        }
      });
    }

    return new Response(html, {
      headers: {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "public, max-age=60"
      }
    });
  }
};
`;

await writeFile(path.join(serverDir, "index.js"), server);
await writeFile(path.join(openaiDir, "hosting.json"), hosting);
await copyFile(path.join(root, "worker", "manual-edits.js"), path.join(serverDir, "manual-edits.js"));
await copyFile(path.join(root, "worker", "recommendations.js"), path.join(serverDir, "recommendations.js"));
await copyFile(path.join(root, "assets", "manual-overrides.js"), path.join(assetsDir, "manual-overrides.js"));

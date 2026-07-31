import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const dist = path.join(root, "dist");
const serverDir = path.join(dist, "server");
const openaiDir = path.join(dist, ".openai");

await rm(dist, { recursive: true, force: true });
await mkdir(serverDir, { recursive: true });
await mkdir(openaiDir, { recursive: true });

const demoHtml = await readFile(path.join(root, "demo", "index.html"), "utf8");
const css = await readFile(path.join(root, "demo", "style.css"), "utf8");
const js = await readFile(path.join(root, "demo", "recommendations-demo.js"), "utf8");
const hosting = await readFile(path.join(root, ".openai", "hosting.json"), "utf8");

const html = demoHtml
  .replace('<link rel="stylesheet" href="./style.css">', `<style>${css}</style>`)
  .replace('<script src="./recommendations-demo.js" defer></script>', `<script>${js}</script>`);

const server = `const html = ${JSON.stringify(html)};

export default {
  async fetch() {
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

/* ============================================================
   Stacks worker patch — READER POLL (opportunity vs trap)
   ------------------------------------------------------------
   Adds two routes to the existing comments worker:
     GET  /votes                       -> { data: { id: {up,down} } }
     POST /vote { pageId, dir, prev }  -> { data: {up,down} }
   dir/prev are "up" | "down" | null.

   HOW TO INSTALL (Cloudflare dashboard):
   1. Open your worker (stacks-comments...) -> Edit code.
   2. Paste the TWO `if (...) { ... }` blocks below into the
      fetch() handler, right AFTER the existing "/like" block
      and BEFORE the line:
          if (url.pathname !== "/comments" && url.pathname !== "/counts") {
   3. Deploy. No new bindings or tables needed — it reuses the
      same D1 `counters` table (kinds "vup" / "vdown") and the
      existing bump()/allCounts()/ensureTables() helpers.
   ============================================================ */

/* ---------- reader poll: batch read all splits ---------- */
if (request.method === "GET" && url.pathname === "/votes") {
  await ensureTables(env.DB);
  const up = await allCounts(env.DB, "vup");
  const down = await allCounts(env.DB, "vdown");
  const data = {};
  for (const id in up)   (data[id] = data[id] || { up: 0, down: 0 }).up = up[id];
  for (const id in down) (data[id] = data[id] || { up: 0, down: 0 }).down = down[id];
  return json({ data }, 200, origin);
}

/* ---------- reader poll: cast / change / clear a vote ---------- */
if (request.method === "POST" && url.pathname === "/vote") {
  const body = await request.json().catch(() => ({}));
  const pageId = String(body.pageId || "");
  if (!PAGE_ID_RE.test(pageId)) return json({ error: "bad pageId" }, 400, origin);
  await ensureTables(env.DB);
  const kindOf = d => d === "up" ? "vup" : d === "down" ? "vdown" : null;
  const pk = kindOf(body.prev);   // what they had before (or null)
  const nk = kindOf(body.dir);    // what they have now (or null = cleared)
  if (pk && pk !== nk) await bump(env.DB, pk, pageId, -1);
  if (nk && nk !== pk) await bump(env.DB, nk, pageId, 1);
  const up = await bump(env.DB, "vup", pageId, 0);     // delta 0 = read current
  const down = await bump(env.DB, "vdown", pageId, 0);
  return json({ data: { up, down } }, 200, origin);
}

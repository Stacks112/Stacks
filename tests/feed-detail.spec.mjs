import { expect, test } from "@playwright/test";

async function waitForFeed(page) {
  await page.goto("/?v83beta", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#feedList article.card").first()).toBeVisible();
}

async function firstLinkedCardId(page) {
  // The feed populates entity links progressively as cards render, so the
  // scan below is wrapped in toPass(): it retries until a card with a truly
  // visible entity link shows up instead of latching onto whatever partial
  // state exists on the first pass.
  let id;
  await expect(async () => {
    const cards = page.locator("#feedList article.card").filter({ has: page.locator(".ent-link, .gloss-link") });
    const count = await cards.count();
    let found = null;
    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      const hasVisibleLink = await card.evaluate((cardEl) => {
        const links = cardEl.querySelectorAll(".ent-link, .gloss-link");
        for (const link of links) {
          const r = link.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          let closed = false;
          for (let node = link.parentElement; node && node !== cardEl; node = node.parentElement) {
            if (node.tagName === "DETAILS" && !node.hasAttribute("open")) {
              closed = true;
              break;
            }
          }
          if (!closed) return true;
        }
        return false;
      });
      if (hasVisibleLink) {
        found = card;
        break;
      }
    }
    expect(found, "no feed card has a visible entity link — the entity-link feature may actually be broken").not.toBeNull();
    id = await found.getAttribute("id");
  }).toPass({ timeout: 10_000 });
  await expect(page.locator(`#${id}`)).toBeVisible();
  return id;
}

async function assertDetail(page, selector, id) {
  await expect(page.locator(selector)).toHaveCount(1);
  await expect(page.locator(selector).first()).toHaveAttribute("id", id);
  await expect(page.locator(selector).first().locator(".ent-link, .gloss-link").first()).toBeVisible();
}

async function clickHeadline(page, id) {
  const h3 = page.locator(`#${id} h3`);
  await expect(h3).toBeVisible();
  const x = await h3.evaluate((el) => {
    const r = el.getBoundingClientRect();
    for (let dx = 2; dx < r.width - 2; dx += 3) {
      const hit = document.elementFromPoint(r.left + dx, r.top + r.height / 2);
      if (hit && el.contains(hit) && !hit.closest(".ent-link, .gloss-link")) return dx;
    }
    return null;
  });
  const box = await h3.boundingBox();
  if (x === null) throw new Error("headline has no clickable non-entity spot");
  await h3.click({ position: { x, y: box.height / 2 } });
}

test.describe("feed article detail round trip", () => {
  test.describe("desktop", () => {
    test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false });

    test("list → detail → back keeps the feed and indexes the detail", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstLinkedCardId(page);
      expect(id).toMatch(/^sig-/);
      const itemId = id.slice(4);

      await clickHeadline(page, id);
      await expect(page).toHaveURL(new RegExp(`\\?c=${itemId}(?:&|$)`));
      await assertDetail(page, "#feedList article.card.v83one", id);

      await page.goBack();
      await expect(page).not.toHaveURL(/[?]c=/);
      await expect(page.locator("#feedList article.card.v83one")).toHaveCount(0);
      await expect(page.locator("#feedList article.card").first()).toBeVisible();
    });

    test("?c= reload opens the same desktop detail", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstLinkedCardId(page);
      const itemId = id.slice(4);

      await page.goto(`/?c=${itemId}`, { waitUntil: "domcontentloaded" });
      await assertDetail(page, "#feedList article.card.v83one", id);
    });
  });

  test("blank X widget keeps static fallback visible", async ({ page }) => {
    await page.route("**/platform.twitter.com/widgets.js", route => route.fulfill({
      contentType: "application/javascript",
      body: `window.twttr = { widgets: { createTweet: (id, slot) => {
        const wrapper = document.createElement("div");
        wrapper.className = "twitter-tweet twitter-tweet-rendered";
        const iframe = document.createElement("iframe");
        iframe.style.width = "550px";
        iframe.style.height = "816px";
        wrapper.appendChild(iframe);
        slot.appendChild(wrapper);
        return Promise.resolve(wrapper);
      } } };`,
    }));
    await waitForFeed(page);
    // X fallback is intentionally visible on lab cards; other compact feed
    // cards hide their evidence block by design.
    const x = page.locator("#feedList .card.card-lab:not(.prediction-result-card) .xreal").first();
    await expect(x).toBeVisible();
    await x.scrollIntoViewIfNeeded();
    await expect(x).toHaveAttribute("data-xseen", "1");
    await page.waitForTimeout(300);
    const state = await x.evaluate(el => ({
      on: el.classList.contains("x-on"),
      fallback: getComputedStyle(el.querySelector(".xemb")).display,
      slot: getComputedStyle(el.querySelector(".xreal-slot")).display,
      slotHeight: getComputedStyle(el.querySelector(".xreal-slot")).height,
    }));
    expect(state.on).toBe(false);
    expect(state.fallback).toBe("block");
    expect(state.slot).toBe("block");
    expect(state.slotHeight).toBe("0px");
  });

  test("cold load defers archive gist chunks", async ({ page }) => {
    const laterChunks = [];
    page.on("request", request => {
      const match = request.url().match(/gist\.[^./]+\.(\d+)\.json/);
      if (match && Number(match[1]) > 0) laterChunks.push(Number(match[1]));
    });
    await page.goto("/?v83beta", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#feedList article.card").first()).toBeVisible();
    await page.waitForTimeout(1200);
    expect(laterChunks).toEqual([]);
  });

  test.describe("mobile", () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test("home stays within the mobile viewport", async ({ page }) => {
      await waitForFeed(page);
      const size = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(size.scrollWidth).toBeLessThanOrEqual(size.clientWidth + 1);
    });

    test("inline entity tooltip stays out of the mobile layout", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstLinkedCardId(page);
      await page.goto(`/?c=${id.slice(4)}`, { waitUntil: "domcontentloaded" });
      const link = page.locator("#v82detail.on .ent-link, #v82detail.on .gloss-link").first();
      await expect(link).toBeVisible();
      const state = await link.evaluate(el => {
        const tip = el.querySelector(":scope > .entity-tip");
        return {
          touch: matchMedia("(hover: none)").matches,
          display: tip ? getComputedStyle(tip).display : "missing",
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
        };
      });
      expect(state.scrollWidth).toBeLessThanOrEqual(state.clientWidth + 1);
      if (state.touch) expect(state.display).toBe("none");
    });

    test("list → detail → back keeps the feed and indexes the detail", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstLinkedCardId(page);
      expect(id).toMatch(/^sig-/);
      const itemId = id.slice(4);

      await page.locator(`#${id}`).click();
      await expect(page).toHaveURL(new RegExp(`\\?c=${itemId}(?:&|$)`));
      await assertDetail(page, "#v82detail.on article.card", id);

      await page.goBack();
      await expect(page).not.toHaveURL(/[?]c=/);
      await expect(page.locator("#v82detail.on")).toHaveCount(0);
      await expect(page.locator("#feedList article.card").first()).toBeVisible();
    });

    test("?c= reload opens the same mobile detail", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstLinkedCardId(page);
      const itemId = id.slice(4);

      await page.goto(`/?c=${itemId}`, { waitUntil: "domcontentloaded" });
      await assertDetail(page, "#v82detail.on article.card", id);
    });
  });
});

test.describe("track record state", () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, serviceWorkers: "block" });

  test("people breakdown keeps the monthly accuracy trend inside the viewport", async ({ page }) => {
    await page.goto("/?v83beta#record", { waitUntil: "domcontentloaded" });
    await expect(page.locator(".jr-page")).toBeVisible();
    await page.locator('[data-jr-tab="people"]').click();
    await expect(page.locator(".jr-panel[data-jr-panel=\"people\"]")).toBeVisible();
    await expect(page.locator(".jr-trend")).toBeVisible();
    const size = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(size.scrollWidth).toBeLessThanOrEqual(size.clientWidth + 1);
  });

  test("completed cards expose the grading date", async ({ page }) => {
    await page.goto("/?v83beta#record", { waitUntil: "domcontentloaded" });
    await page.locator('[data-jr-tab="done"]').click();
    await expect(page.locator('.jr-panel[data-jr-panel="done"] .jr-card').first()).toContainText(/판정일|Graded|判定日/);
  });
});

test.describe("13F investor view state", () => {
  test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false, serviceWorkers: "block" });

  async function openInvestors(page, hash = "#investors") {
    await page.goto(`/?v83beta${hash}`, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".inv-grid, .inv-table").first()).toBeVisible();
    await expect(page.locator("#v83rail")).toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).toHaveClass(/inv-lab-active/);
    await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
    await expect(page.locator("#v83rail .v83-search")).toBeVisible();
    await expect(page.locator("#v83rail .inv-lab-rail")).toBeVisible();
  }

  test("13F view does not request unavatar images", async ({ page }) => {
    const unavatarRequests = [];
    page.on("request", request => {
      if (request.url().includes("unavatar.io")) unavatarRequests.push(request.url());
    });
    await openInvestors(page);
    await page.waitForTimeout(300);
    expect(unavatarRequests).toEqual([]);
  });

  test("13F transitions restore the right rail", async ({ page }) => {
    await openInvestors(page);

    await page.locator('#v83nav .v83-link[data-k="themes"]').click();
    await expect(page.locator("#v83rail")).not.toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).not.toHaveClass(/inv-lab-active/);
    await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
    await expect(page.locator("#v83rail .v83-search")).toBeVisible();

    await page.locator('#v83nav .v83-link[data-k="investors"]').click();
    await expect(page.locator(".inv-grid")).toBeVisible();
    await expect(page.locator("#v83rail")).toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).toHaveClass(/inv-lab-active/);

    await page.locator("#feedList > .v83post-head.v83navback .v83post-back").click();
    await expect(page.locator("#v83rail")).not.toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).not.toHaveClass(/inv-lab-active/);
    await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
  });

  test("13F deep link renders the investor detail", async ({ page }) => {
    await openInvestors(page, "#investor-berkshire");
    await expect(page.locator("#feedList .inv-table")).toBeVisible();
    await expect(page.locator("#feedList .series-head-name")).toContainText("›");
  });

  test("company holder name opens that investor portfolio", async ({ page }) => {
    await page.goto("/?e=APPLE", { waitUntil: "domcontentloaded" });
    const holder = page.locator(".eh-holder-name").first();
    await expect(holder).toBeVisible({ timeout: 30_000 });
    const slug = await holder.getAttribute("data-investor-slug");
    expect(slug).toBeTruthy();

    await holder.click();
    await expect.poll(() => new URL(page.url()).hash).toBe(`#investor-${slug}`);
    await expect(page.locator("#feedList .inv-table")).toBeVisible();
  });

  test("hub ranking table shows a sort caret and updates aria-sort on click", async ({ page }) => {
    await openInvestors(page);
    const table = page.locator(".inv-hub-table");
    await expect(table).toBeVisible();

    const totalTh = table.locator('th:has(button[data-sort="total_value"])');
    const holdingsTh = table.locator('th:has(button[data-sort="holdings_count"])');
    const holdingsBtn = table.locator('button[data-sort="holdings_count"]');

    // Default sort is total_value descending — its <th> carries aria-sort,
    // and a solid down caret renders after the button label.
    await expect(totalTh).toHaveAttribute("aria-sort", "descending");
    await expect(holdingsTh).toHaveAttribute("aria-sort", "none");

    const afterContent = (locator) => locator.evaluate(el => getComputedStyle(el, "::after").content);
    await expect.poll(() => afterContent(table.locator('button[data-sort="total_value"]'))).toBe('"▼"');
    // Non-active sortable columns show the faint neutral affordance at rest.
    await expect.poll(() => afterContent(holdingsBtn)).toBe('"↕"');

    // Clicking another sortable header moves aria-sort to it (descending first).
    await holdingsBtn.click();
    await expect(holdingsTh).toHaveAttribute("aria-sort", "descending");
    await expect(totalTh).toHaveAttribute("aria-sort", "none");
    await expect.poll(() => afterContent(holdingsBtn)).toBe('"▼"');

    // Clicking the same header again flips the direction to ascending.
    await holdingsBtn.click();
    await expect(holdingsTh).toHaveAttribute("aria-sort", "ascending");
    await expect.poll(() => afterContent(holdingsBtn)).toBe('"▲"');
  });

  // data/investor-returns.json is a daily-pipeline output, not something the
  // hub computes itself (see the /quote-storm history above). These tests
  // mock the route so they never depend on the live committed file's
  // contents — they only assert on shapes: signed-percent pattern, dash for
  // null/missing, sort-with-nulls-last, and stale/failed fail-quiet-to-dash.
  function mockHubReturns(page, body) {
    return page.route("**/data/investor-returns.json*", route =>
      route.fulfill({ contentType: "application/json", body: JSON.stringify(body) })
    );
  }
  const FRESH_RETURNS = {
    as_of: new Date().toISOString(),
    ytd_start: "2026-01-02",
    investors: {
      duquesne: { ytd_pct: 0.20, coverage_pct: 1, priced_holdings: 10, eligible_holdings: 10 },
      "pershing-square": { ytd_pct: 0.12, coverage_pct: 1, priced_holdings: 10, eligible_holdings: 10 },
      berkshire: { ytd_pct: 0.05, coverage_pct: 1, priced_holdings: 10, eligible_holdings: 10 },
      ark: { ytd_pct: -0.03, coverage_pct: 1, priced_holdings: 10, eligible_holdings: 10 },
      "third-point": { ytd_pct: null, coverage_pct: 0.5, priced_holdings: 5, eligible_holdings: 10 }
      // baupost and the rest of the roster are absent entirely — also a dash case.
    },
  };
  const NUMERIC_SLUGS_DESC = ["duquesne", "pershing-square", "berkshire", "ark"];

  test("hub table renders a YTD return column: signed values, dash for null and for missing investors", async ({ page }) => {
    await mockHubReturns(page, FRESH_RETURNS);
    await openInvestors(page);
    const table = page.locator(".inv-hub-table");
    await expect(table).toBeVisible();
    await expect(table.locator('th:has(button[data-sort="ytd_return"])')).toBeVisible();

    const berkshireCell = table.locator('tr[data-slug="berkshire"] td:nth-child(2) span');
    await expect(berkshireCell).toHaveText(/^\+\d+(\.\d)?%$/);

    const nullCell = table.locator('tr[data-slug="third-point"] td:nth-child(2) span');
    await expect(nullCell).toHaveText("—");
    await expect(table.locator('tr[data-slug="third-point"] td:nth-child(2)')).toHaveAttribute("title", /50\.0%/);

    const missingCell = table.locator('tr[data-slug="baupost"] td:nth-child(2) span');
    await expect(missingCell).toHaveText("—");

    await expect(page.locator(".inv-hub-ytd-note")).toContainText("2026.01.02");
  });

  test("clicking the YTD header sorts numerically and keeps dashes at the bottom in both directions", async ({ page }) => {
    await mockHubReturns(page, FRESH_RETURNS);
    await openInvestors(page);
    const table = page.locator(".inv-hub-table");
    // Wait for the async fill so the header click sorts real numbers, not
    // the all-null placeholder state.
    await expect(table.locator('tr[data-slug="berkshire"] td:nth-child(2) span')).toHaveText(/^\+/);

    const ytdTh = table.locator('th:has(button[data-sort="ytd_return"])');
    const ytdBtn = table.locator('button[data-sort="ytd_return"]');

    await ytdBtn.click();
    await expect(ytdTh).toHaveAttribute("aria-sort", "descending");
    let slugs = await table.locator("tr.inv-hub-card").evaluateAll(trs => trs.map(tr => tr.getAttribute("data-slug")));
    expect(slugs.slice(0, 4)).toEqual(NUMERIC_SLUGS_DESC);
    expect(slugs.indexOf("third-point")).toBeGreaterThanOrEqual(4);
    expect(slugs.indexOf("baupost")).toBeGreaterThanOrEqual(4);

    await ytdBtn.click();
    await expect(ytdTh).toHaveAttribute("aria-sort", "ascending");
    slugs = await table.locator("tr.inv-hub-card").evaluateAll(trs => trs.map(tr => tr.getAttribute("data-slug")));
    expect(slugs.slice(0, 4)).toEqual(NUMERIC_SLUGS_DESC.slice().reverse());
    expect(slugs.indexOf("third-point")).toBeGreaterThanOrEqual(4);
    expect(slugs.indexOf("baupost")).toBeGreaterThanOrEqual(4);
  });

  test("a stale or failed returns feed blanks the whole YTD column without breaking the rest of the table", async ({ page }) => {
    const staleBody = { ...FRESH_RETURNS, as_of: new Date(Date.now() - 10 * 86400000).toISOString() };
    await mockHubReturns(page, staleBody);
    await openInvestors(page);
    const table = page.locator(".inv-hub-table");
    await expect(table).toBeVisible();

    const totalCell = table.locator('tr[data-slug="berkshire"] td:nth-child(3)');
    await expect(totalCell).not.toHaveText("—");
    await expect(totalCell).not.toHaveText("");

    await expect(async () => {
      const texts = await table.locator("tr.inv-hub-card td:nth-child(2) span").allTextContents();
      expect(texts.length).toBeGreaterThan(0);
      expect(texts.every(t => t.trim() === "—")).toBe(true);
    }).toPass({ timeout: 10_000 });

    await expect(page.locator(".inv-hub-ytd-note")).toContainText("연중 수익률 데이터를 최신 상태로 불러오지 못해");
  });

  test("a failed (network-error) returns fetch also blanks the YTD column without breaking the table", async ({ page }) => {
    await page.route("**/data/investor-returns.json*", route => route.abort());
    await openInvestors(page);
    const table = page.locator(".inv-hub-table");
    await expect(table).toBeVisible();

    const totalCell = table.locator('tr[data-slug="berkshire"] td:nth-child(3)');
    await expect(totalCell).not.toHaveText("—");

    await expect(async () => {
      const texts = await table.locator("tr.inv-hub-card td:nth-child(2) span").allTextContents();
      expect(texts.length).toBeGreaterThan(0);
      expect(texts.every(t => t.trim() === "—")).toBe(true);
    }).toPass({ timeout: 10_000 });
  });

  test("investor value chart honors period boundaries and nearest points", async ({ page }) => {
    await page.route("**/quote?*", route => {
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * 0.1);
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page, "#investor-berkshire");
    const valueChart = page.locator("#invValChart:visible").first();
    await expect(valueChart.locator("svg")).toBeVisible({ timeout: 30000 });
    await page.locator('.inv-value-card .inv-compare-period[data-period="1d"]').click();
    await expect.poll(() => valueChart.locator("polyline").evaluate(el => el.getAttribute("points").trim().split(/\s+/).length)).toBe(2);
    await page.locator('.inv-value-card .inv-compare-period[data-period="1y"]').click();
    await expect.poll(() => valueChart.locator("polyline").evaluate(el => el.getAttribute("points").trim().split(/\s+/).length)).toBeGreaterThan(360);

    const svg = valueChart.locator("svg").first();
    const dateAxisLabels = await svg.locator(".inv-compare-axis").filter({ hasText: /^\d{4}\.\d{2}\.\d{2}$/ }).allTextContents();
    expect(dateAxisLabels).toHaveLength(5);
    const middlePoint = await svg.evaluate(node => {
      const points = node.querySelector("polyline").getAttribute("points").trim().split(/\s+/).map(value => value.split(",").map(Number));
      const point = node.createSVGPoint();
      point.x = points[Math.floor(points.length / 2)][0];
      point.y = points[Math.floor(points.length / 2)][1];
      const screen = point.matrixTransform(node.getScreenCTM());
      return { x: screen.x, y: screen.y };
    });
    await page.mouse.move(middlePoint.x, middlePoint.y);
    await expect(valueChart.locator(".inv-compare-chart-tip")).toBeVisible();
    await expect(valueChart.locator(".inv-compare-chart-tip b").first()).toHaveText(/^\d{4}\.\d{2}\.\d{2}$/);
    const lastPoint = await svg.evaluate(node => {
      const points = node.querySelector("polyline").getAttribute("points").trim().split(/\s+/).map(value => value.split(",").map(Number));
      const point = node.createSVGPoint(); point.x = points.at(-1)[0]; point.y = points.at(-1)[1];
      const screen = point.matrixTransform(node.getScreenCTM()); return { x: screen.x, y: screen.y };
    });
    await page.mouse.move(lastPoint.x, lastPoint.y);
    await expect(valueChart.locator(".inv-compare-chart-tip b").first()).toHaveText(dateAxisLabels.at(-1));
  });

  test("investor price failures and partial coverage stay visible", async ({ page }) => {
    await page.route("**/quote?*", async route => {
      const symbol = new URL(route.request().url()).searchParams.get("s");
      if (symbol !== "spy.us" && symbol !== "aapl.us") {
        await route.abort();
        return;
      }
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * 0.1);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page);
    await page.locator(".inv-compare-go:visible").first().click();
    await expect(page).toHaveURL(/#investor-compare$/);
    await expect(page.locator('.inv-price-status[data-price-status="partial"]').first()).toBeVisible({ timeout: 30000 });
    await expect(page.locator('.inv-price-status[data-price-status="unavailable"]').first()).toBeVisible();
    await expect(page.locator('.inv-compare-legend-item[data-price-status="unavailable"] small').last()).toContainText("시세");
    await expect(page.locator(".inv-compare-chart")).toHaveAttribute("data-price-status", "partial");
    await expect(page.locator(".inv-compare-chart")).toHaveAttribute("data-price-benchmark", "ok");
  });

  test("S&P baseline stays in comparison arithmetic", async ({ page }) => {
    await page.route("**/quote?*", async route => {
      const symbol = new URL(route.request().url()).searchParams.get("s");
      const slope = symbol === "spy.us" ? 0.1 : 0.3;
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * slope);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page);
    await page.locator(".inv-compare-go:visible").first().click();
    await expect(page).toHaveURL(/#investor-compare$/);
    const graph = page.locator(".inv-performance-section .inv-compare-chart").first();
    await expect(graph.locator('polyline[stroke-dasharray="7 6"]')).toHaveCount(1);
    await expect(page.locator('.inv-performance-section .inv-compare-legend-item[data-price-status="ok"] small').last()).toContainText("기준지수");
    const vsSpy = await page.locator('.inv-compare-summary-table [data-perf="spy"]').allTextContents();
    expect(vsSpy.length).toBe(2);
    expect(vsSpy.every(value => /^[+]\d+\.\d+%$/.test(value))).toBe(true);
  });

  test("summary table highlights a single winner only in the four performance rows", async ({ page }) => {
    // Every ticker gets its own deterministic-but-distinct growth slope (spy.us
    // stays flat) so the two default-selected investors' portfolios diverge and
    // one has a strictly higher vs.-S&P return - a tie would (correctly) leave
    // the row unhighlighted, which is not what this test wants to exercise.
    let seen = 0;
    const slopeFor = symbol => {
      if (symbol === "spy.us") return 0.01;
      seen += 1;
      return 0.05 + (seen % 7) * 0.09;
    };
    await page.route("**/quote?*", async route => {
      const symbol = new URL(route.request().url()).searchParams.get("s");
      const slope = slopeFor(symbol);
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * slope);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page);
    await page.locator(".inv-compare-go:visible").first().click();
    await expect(page).toHaveURL(/#investor-compare$/);

    const vsSpyRow = page.locator('.inv-compare-summary-table tr[data-row="vsSpy"]');
    await expect(vsSpyRow.locator('td[data-slug]')).toHaveCount(2);
    await expect.poll(async () => {
      const texts = await vsSpyRow.locator('[data-perf="spy"]').allTextContents();
      return texts.some(t => t.includes("계산 중"));
    }, { timeout: 30000 }).toBe(false);

    await expect(vsSpyRow.locator('td.inv-win')).toHaveCount(1);
    await expect(page.locator('.inv-compare-summary-table tr[data-row="turnover"] td.inv-win')).toHaveCount(0);
  });

  test("investor value chart matches compare period and drag behavior", async ({ page }) => {
    await page.route("**/quote?*", route => {
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * 0.1);
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page, "#investor-berkshire");
    const valueChart = page.locator("#invValChart:visible").first();
    const valueSvg = valueChart.locator("svg").first();
    await expect(valueSvg).toBeVisible({ timeout: 30000 });
    const axisBoxes = await valueSvg.locator(".inv-compare-axis").evaluateAll(nodes => nodes.map(node => node.getBBox().x));
    expect(axisBoxes.length).toBeGreaterThan(0);
    expect(Math.min(...axisBoxes)).toBeGreaterThanOrEqual(0);
    await expect(page.locator(".inv-value-card .inv-compare-period")).toHaveCount(6);
    await page.locator('.inv-value-card .inv-compare-period[data-period="6m"]').click();
    await expect(page.locator('.inv-value-card .inv-compare-period[data-period="6m"]')).toHaveAttribute("aria-selected", "true");

    const chart = await valueSvg.boundingBox();
    expect(chart).not.toBeNull();
    await page.mouse.move(chart.x + chart.width * 0.25, chart.y + chart.height * 0.5);
    await expect(valueChart.locator(".inv-compare-hover-line:not(.inv-value-hover-hline)")).toHaveAttribute("visibility", "visible");
    await expect(valueChart.locator(".inv-value-hover-hline")).toHaveAttribute("visibility", "visible");
    await expect(valueChart.locator(".inv-value-hover-dot")).toHaveAttribute("visibility", "visible");
    await expect(valueChart.locator(".inv-compare-chart-tip")).toBeVisible();
    await expect(valueChart.locator(".inv-compare-chart-tip")).toContainText("$");
    await expect(valueChart.locator(".inv-compare-chart-tip")).toContainText("%");
    await expect(valueChart.locator(".inv-compare-chart-tip")).not.toContainText(/\d{1,2}:\d{2}/);
    await page.mouse.down();
    await page.mouse.move(chart.x + chart.width * 0.7, chart.y + chart.height * 0.5);
    await page.mouse.up();
    await expect(valueChart.locator(".inv-compare-selection")).toHaveAttribute("visibility", "visible");
    await expect.poll(() => page.locator("#invValRange").evaluate(el => !el.hidden)).toBe(true);
    await expect(page.locator("#invValRange")).toHaveText(/\+\d+\.\d+%/);
    await expect(valueChart.locator(".inv-compare-chart-tip")).toContainText("%");
    await expect(valueChart.locator(".inv-compare-chart-tip")).not.toContainText("$");
    await expect(page.locator("#invValClear")).toBeVisible();
    await page.locator("#invValClear").click();
    await expect.poll(() => page.locator("#invValRange").evaluate(el => el.hidden)).toBe(true);
  });

  test("investor comparison chart keeps hover crosshair and drag selection", async ({ page }) => {
    await page.route("**/quote?*", route => {
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * 0.1);
      return route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page);
    await expect(page.locator(".inv-hub-search input")).toBeVisible();
    await expect(page.locator(".inv-hub-card")).toHaveCount(16);
    await expect(page.locator(".inv-compare-bar")).toBeHidden();
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await expect(page.locator(".inv-compare-bar")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.locator("#v83rail .inv-rail-selection")).toBeVisible();
    await page.locator(".inv-compare-go").click();
    await expect(page).toHaveURL(/#investor-compare$/);
    const graph = page.locator("#feedList .inv-performance-section .inv-compare-chart").first();
    await expect(graph.locator("svg")).toBeVisible();
    const axisBoxes = await graph.locator("svg .inv-compare-axis").evaluateAll(nodes => nodes.map(node => node.getBBox().x));
    expect(axisBoxes.length).toBeGreaterThan(0);
    expect(Math.min(...axisBoxes)).toBeGreaterThanOrEqual(0);
    const box = await graph.locator("svg").boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.5);
    await expect(graph.locator(".inv-compare-hover-line:not(.inv-compare-hover-hline)")).toHaveAttribute("visibility", "visible");
    await expect(graph.locator(".inv-compare-hover-hline")).toHaveAttribute("visibility", "visible");
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5);
    await page.mouse.up();
    await expect(graph.locator(".inv-compare-selection")).toHaveAttribute("visibility", "visible");
    await expect(graph.locator(".inv-compare-chart-tip")).toContainText("%");
  });

  test("compare hero shows a resting-state return that updates on period change and selection", async ({ page }) => {
    // Distinct-but-deterministic slope per ticker (flat for spy.us) so the
    // two default-selected investors' hold-graph returns differ from each
    // other and, crucially, differ between the YTD and 1M windows.
    let seen = 0;
    const slopeFor = symbol => {
      if (symbol === "spy.us") return 0.01;
      seen += 1;
      return 0.05 + (seen % 7) * 0.09;
    };
    await page.route("**/quote?*", async route => {
      const symbol = new URL(route.request().url()).searchParams.get("s");
      const slope = slopeFor(symbol);
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const t = Array.from({ length: 370 }, (_, i) => now - (369 - i) * 86400);
      const closes = t.map((_, i) => 100 + i * slope);
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });
    await openInvestors(page);
    await page.locator(".inv-compare-go:visible").first().click();
    await expect(page).toHaveURL(/#investor-compare$/);

    const hero = page.locator(".inv-performance-section .inv-compare-hero").first();
    const values = hero.locator(".inv-compare-hero-value");
    // Visible at rest, i.e. before any hover or drag on the chart.
    await expect(values).toHaveCount(2);
    await expect(values.first()).toHaveText(/^[+-]\d+\.\d+%$/, { timeout: 30000 });
    const beforeTexts = await values.allTextContents();
    expect(beforeTexts.every(t => /^[+-]\d+\.\d+%$/.test(t))).toBe(true);
    await expect(hero.locator(".inv-compare-hero-label")).not.toContainText("선택");

    await page.locator('.inv-performance-section .inv-compare-period[data-period="1m"]').click();
    await expect.poll(() => values.allTextContents()).not.toEqual(beforeTexts);
    const afterTexts = await values.allTextContents();
    expect(afterTexts.every(t => /^[+-]\d+\.\d+%$/.test(t))).toBe(true);

    // A drag selection re-labels and re-values the hero to match the
    // selection; clearing it restores the full-window figure.
    const graph = page.locator(".inv-performance-section .inv-compare-chart").first();
    const box = await graph.locator("svg").boundingBox();
    await page.mouse.move(box.x + box.width * 0.15, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.85, box.y + box.height * 0.5);
    await page.mouse.up();
    await expect(hero.locator(".inv-compare-hero-label")).toContainText("선택");
    await page.locator(".inv-performance-section .inv-compare-clear").click();
    await expect(hero.locator(".inv-compare-hero-label")).not.toContainText("선택");
    await expect(values).toHaveText([afterTexts[0], afterTexts[1]]);
  });

  test("compare-screen YTD hero matches the individual investor chart's YTD", async ({ page }) => {
    // Regression guard for the nearest-vs-ceiling window-start bug: daily
    // bars are timestamped ~14:30 UTC (mocked below to match), so a
    // nearest-neighbour search for the Jan-1-00:00-UTC YTD target picks the
    // prior year's Dec-31 bar instead of the correct first-trading-day-of
    // -year bar. situational-awareness showed the largest gap (66.46% vs.
    // the correct 51.31%) before the fix, so it's used here to make a
    // regression fail loudly. A smooth price ramp would not expose this -
    // one day either way barely moves a smooth series' percentage - so the
    // mock also jumps the price sharply exactly at the YTD boundary, the
    // way a real portfolio can swing day to day, so picking the wrong side
    // of Jan 1 actually produces a materially different number.
    await page.route("**/quote?*", async route => {
      const now = Math.floor(Date.now() / 86400000) * 86400;
      const barOffset = 52200; // 14:30 UTC, matching production quote bars
      const days = 400;
      const t = Array.from({ length: days }, (_, i) => now - (days - 1 - i) * 86400 + barOffset);
      const endYear = new Date(t[t.length - 1] * 1000).getUTCFullYear();
      const jan1 = Date.UTC(endYear, 0, 1) / 1000;
      const closes = t.map((ti, i) => (100 + i * 0.05) + (ti >= jan1 ? 40 : 0));
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ t, closes, price: closes.at(-1), currency: "USD" }) });
    });

    await page.addInitScript(slugs => {
      localStorage.setItem("stk_inv_compare", JSON.stringify(slugs));
    }, ["situational-awareness", "berkshire"]);

    await page.goto("/?v83beta#investor-compare", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/#investor-compare$/);

    const heroItem = page.locator(".inv-performance-section .inv-compare-hero-item").filter({ hasText: "ASCHEN" });
    await expect(heroItem, "compare hero row for situational-awareness (INV:ASCHEN) never appeared").toHaveCount(1, { timeout: 30000 });
    const heroValueEl = heroItem.locator(".inv-compare-hero-value");
    await expect(heroValueEl).toHaveText(/^[+-]\d+\.\d+%$/, { timeout: 30000 });
    const heroPct = parseFloat(await heroValueEl.textContent());
    expect(Number.isFinite(heroPct)).toBe(true);

    // Independently derive the ceiling-start YTD from the exact same series
    // invComputeValueSeries() feeds both the compare hero and the
    // single-investor chart (invPaintValueChart), so this is a true
    // cross-check rather than a hand-computed expectation.
    const expectedPct = await page.evaluate(async () => {
      const data = await fetch("/portfolios.json").then(r => r.json());
      const inv = data.investors.find(i => i.slug === "situational-awareness");
      if (!inv) throw new Error("situational-awareness not found in /portfolios.json");
      if (typeof window.invComputeValueSeries !== "function") throw new Error("window.invComputeValueSeries is not exposed on the page");
      const series = await window.invComputeValueSeries(inv);
      if (!series || !series.calendar || !series.values || series.calendar.length < 2) {
        throw new Error("invComputeValueSeries returned no usable series for situational-awareness");
      }
      const { calendar, values } = series;
      const end = calendar[calendar.length - 1];
      const endDate = new Date(end * 1000);
      const requestedStart = Date.UTC(endDate.getUTCFullYear(), 0, 1) / 1000;
      // Mirrors invPaintValueChart's ceiling search in index.html.
      let startIdx = 0;
      while (startIdx < calendar.length - 1 && calendar[startIdx] < requestedStart) startIdx++;
      const first = values[startIdx], last = values[values.length - 1];
      if (!(first > 0)) throw new Error("YTD start value is not positive");
      return (last / first - 1) * 100;
    });

    expect(Math.abs(heroPct - expectedPct)).toBeLessThanOrEqual(0.15);
  });

  test("sector unclassified note states a remainder consistent with the coverage row", async ({ page }) => {
    await page.route("**/quote?*", async route => {
      await route.abort();
    });
    await openInvestors(page);
    await page.locator(".inv-compare-go:visible").first().click();
    await expect(page).toHaveURL(/#investor-compare$/);

    const section = page.locator(".inv-compare-section").filter({ has: page.locator(".inv-sector-coverage-note") });
    await expect(section).toBeVisible();
    const coverageRow = section.locator("tr").filter({ has: page.locator("td b", { hasText: "분류 커버리지" }) });
    const unclassifiedRow = section.locator("tr").filter({ has: page.locator("td b", { hasText: "미분류" }) });
    await expect(coverageRow).toHaveCount(1);
    await expect(unclassifiedRow).toHaveCount(1);

    const coverageTexts = await coverageRow.locator("td").allTextContents();
    const unclassifiedTexts = await unclassifiedRow.locator("td").allTextContents();
    expect(unclassifiedTexts.length).toBe(coverageTexts.length);
    for (let i = 1; i < coverageTexts.length; i++) {
      const covered = coverageTexts[i].trim();
      const uncovered = unclassifiedTexts[i].trim();
      if (covered === "—") {
        expect(uncovered).toBe("—");
        continue;
      }
      expect(uncovered).not.toBe("—");
      const coveredPct = parseFloat(covered);
      const uncoveredPct = parseFloat(uncovered);
      expect(coveredPct + uncoveredPct).toBeCloseTo(100, 0);
    }

    const noteLines = await section.locator(".inv-sector-coverage-line").allTextContents();
    expect(noteLines.length).toBe(coverageTexts.length - 1);
    expect(noteLines.some(text => text.includes("미분류") || text.includes("분류 커버리지 데이터가 없어"))).toBe(true);
  });

  test.describe("responsive widths", () => {
    test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false });

    test("13F rail state survives 1024px and 1180px theme transitions", async ({ page }) => {
      for (const width of [1024, 1180]) {
        await page.setViewportSize({ width, height: 900 });
        await openInvestors(page);
        await expect(page.locator("#v83rail .inv-lab-rail")).toBeVisible();

        await page.locator('#v83nav .v83-link[data-k="themes"]').click();
        await expect(page.locator("#v83rail")).not.toHaveClass(/inv-rail-hide/);
        await expect(page.locator("html")).not.toHaveClass(/inv-lab-active/);
        await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
        await expect(page.locator("#v83rail .v83-search")).toBeVisible();
      }
    });
  });

  test.describe("mobile drawer and compare", () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: false, hasTouch: true });

    test("mobile keeps a 2-to-4 selection through detail and compare return", async ({ page }) => {
      await page.goto("/?v82beta", { waitUntil: "domcontentloaded" });
      await page.locator("#v82av").click();
      await page.locator('#v82drawer [data-act="investors"]').click();
      await expect(page.locator('.inv-hub-select[aria-pressed="true"]')).toHaveCount(2);

      await page.locator('.inv-hub-select[aria-pressed="false"]').nth(0).click();
      await page.locator('.inv-hub-select[aria-pressed="false"]').nth(0).click();
      await expect(page.locator('.inv-hub-select[aria-pressed="true"]')).toHaveCount(4);
      await expect(page.locator('.inv-hub-select[aria-pressed="false"]:disabled')).toHaveCount(0);

      await page.locator(".inv-compare-go").click();
      await expect(page).toHaveURL(/#investor-compare$/);
      await expect(page.locator(".inv-compare-col")).toHaveCount(4);
      await page.locator(".inv-compare-card-head").first().click();
      await expect(page).toHaveURL(/#investor-(?!compare)/);
      await expect(page.locator(".inv-value-card")).toBeVisible();
      await page.locator("#v82subbar .bk:visible, .series-close:visible").first().click();
      await expect(page).toHaveURL(/#investor-compare$/);
      await expect(page.locator(".inv-compare-col")).toHaveCount(4);
    });

    test("mobile drawer opens 13F compare and returns to the list", async ({ page }) => {
      await page.goto("/?v82beta", { waitUntil: "domcontentloaded" });
      await expect(page.locator("#v82av")).toBeVisible();

      await page.locator("#v82av").click();
      const investorMenuItem = page.locator('#v82drawer [data-act="investors"]');
      await expect(investorMenuItem).toBeVisible();
      await investorMenuItem.click();

      await expect(page.locator("#v82drawer")).not.toHaveClass(/on/);
      await expect(page.locator("#feedList .inv-grid")).toBeVisible();

      await expect(page.locator('.inv-hub-select[aria-pressed="true"]')).toHaveCount(2);
      await expect(page.locator(".inv-compare-go")).toBeEnabled();
      await page.locator(".inv-compare-go").click();
      await expect(page).toHaveURL(/#investor-compare$/);
      await expect(page.locator(".inv-compare-summary-grid")).toBeVisible();

      await page.goBack();
      await expect(page.locator("#feedList .inv-grid")).toBeVisible();
    });
  });

  test.describe("skew page state", () => {
    test("desktop #skew deep link renders the weekly page", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto("/?v83beta#skew", { waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/#skew$/);
      await expect(page.locator(".v83skew-page").first()).toBeVisible();
      await expect(page.locator(".skr-row").first()).toBeVisible();
      await expect(page.locator(".skew-method")).toContainText("계산 기준");
      await expect(page.locator(".skr-row .skr-side").first()).not.toHaveClass(/sk-mix/);
    });

    test("mobile #skew deep link opens the same weekly basis", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/?v82beta#skew", { waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/#skew$/);
      await expect(page.locator("#v82hub.on")).toBeVisible();
      await expect(page.locator("#v82hub .v82-hub-sec").filter({ hasText: "최근 7일" })).toBeVisible();
      await expect(page.locator("#v82hub .v82-skew-method")).toContainText("계산 기준");
      await expect(page.locator("#v82hub .v82-tr-row .sd").first()).not.toHaveClass(/mix/);
    });

    test("ties stay neutral and small samples are marked", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto("/?v83beta", { waitUntil: "domcontentloaded" });
      const result = await page.evaluate(() => {
        const tie = skewConsensus([
          { id: "a", source: "same", stance: "bull" },
          { id: "b", source: "same", stance: "bear" },
          { id: "c", source: "other", stance: "bull" },
          { id: "d", source: "other", stance: "bear" },
        ]);
        const thin = skewConsensus([{ id: "e", source: "one", stance: "bull" }]);
        return { tie, thin };
      });
      expect(result.tie.side).toBe("mix");
      expect(result.tie.lowSample).toBe(true);
      expect(result.thin.lowSample).toBe(true);
    });

    test("desktop skew rows expand source detail without leaving the page", async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto("/?v83beta#skew", { waitUntil: "domcontentloaded" });
      const toggle = page.locator(".skew-source-toggle").first();
      await expect(toggle).toBeVisible();
      await expect(toggle).toHaveRole("button");
      await toggle.click();
      await expect(page).toHaveURL(/#skew$/);
      await expect(toggle).toHaveAttribute("aria-expanded", "true");
      await expect(page.locator(".skew-source-detail").first()).toBeVisible();
      await expect(page.locator(".skew-source-line").first()).toBeVisible();
      await expect(page.locator(".skew-source-original").first()).toHaveAttribute("target", "_blank");
      await expect(page.locator(".skew-source-original").first()).toHaveAttribute("href", /^https?:\/\//);
    });

    test("mobile skew rows expand source detail without leaving the page", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/?v82beta#skew", { waitUntil: "domcontentloaded" });
      const toggle = page.locator("#v82hub .v82-skew-source-toggle").first();
      await expect(toggle).toBeVisible();
      await expect(toggle).toHaveRole("button");
      await toggle.click();
      await expect(page).toHaveURL(/#skew$/);
      await expect(toggle).toHaveAttribute("aria-expanded", "true");
      await expect(page.locator("#v82hub .v82-skew-source-detail").first()).toBeVisible();
      await expect(page.locator("#v82hub .skew-source-line").first()).toBeVisible();
      await expect(page.locator("#v82hub .skew-source-original").first()).toHaveAttribute("target", "_blank");
      await expect(page.locator("#v82hub .skew-source-original").first()).toHaveAttribute("href", /^https?:\/\//);
    });
  });
});

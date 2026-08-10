import { expect, test } from "@playwright/test";

async function waitForFeed(page) {
  await page.goto("/?v83beta", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#feedList article.card").first()).toBeVisible();
}

async function firstLinkedCardId(page) {
  const card = page.locator("#feedList article.card").filter({ has: page.locator(".ent-link, .gloss-link") }).first();
  await expect(card).toBeVisible();
  return card.getAttribute("id");
}

async function assertDetail(page, selector, id) {
  await expect(page.locator(selector)).toHaveCount(1);
  await expect(page.locator(selector).first()).toHaveAttribute("id", id);
  await expect(page.locator(selector).first().locator(".ent-link, .gloss-link").first()).toBeVisible();
}

test.describe("feed article detail round trip", () => {
  test.describe("desktop", () => {
    test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false });

    test("list → detail → back keeps the feed and indexes the detail", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstLinkedCardId(page);
      expect(id).toMatch(/^sig-/);
      const itemId = id.slice(4);

      await page.locator(`#${id} h3`).click();
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
    const vsSpy = await page.locator('.inv-compare-card [data-perf="spy"]').allTextContents();
    expect(vsSpy.length).toBe(2);
    expect(vsSpy.every(value => /^[+]\d+\.\d+%$/.test(value))).toBe(true);
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
    await expect(page.locator(".inv-compare-bar")).toBeVisible();
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
      await expect(page.locator('.inv-hub-select[aria-pressed="false"]:disabled')).toHaveCount(12);

      await page.locator(".inv-compare-go").click();
      await expect(page).toHaveURL(/#investor-compare$/);
      await expect(page.locator(".inv-compare-card")).toHaveCount(4);
      await page.locator(".inv-compare-card-head").first().click();
      await expect(page).toHaveURL(/#investor-(?!compare)/);
      await expect(page.locator(".inv-value-card")).toBeVisible();
      await page.locator("#v82subbar .bk:visible, .series-close:visible").first().click();
      await expect(page).toHaveURL(/#investor-compare$/);
      await expect(page.locator(".inv-compare-card")).toHaveCount(4);
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
    });

    test("mobile #skew deep link opens the same weekly basis", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto("/?v82beta#skew", { waitUntil: "domcontentloaded" });
      await expect(page).toHaveURL(/#skew$/);
      await expect(page.locator("#v82hub.on")).toBeVisible();
      await expect(page.locator("#v82hub .v82-hub-sec").filter({ hasText: "최근 7일" })).toBeVisible();
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
  });
});

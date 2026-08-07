import { expect, test } from "@playwright/test";

async function waitForFeed(page) {
  await page.goto("/?v83beta", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#feedList article.card").first()).toBeVisible();
}

async function firstCardId(page) {
  return page.locator("#feedList article.card").first().getAttribute("id");
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
      const id = await firstCardId(page);
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
      const id = await firstCardId(page);
      const itemId = id.slice(4);

      await page.goto(`/?c=${itemId}`, { waitUntil: "domcontentloaded" });
      await assertDetail(page, "#feedList article.card.v83one", id);
    });
  });

  test.describe("mobile", () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

    test("list → detail → back keeps the feed and indexes the detail", async ({ page }) => {
      await waitForFeed(page);
      const id = await firstCardId(page);
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
      const id = await firstCardId(page);
      const itemId = id.slice(4);

      await page.goto(`/?c=${itemId}`, { waitUntil: "domcontentloaded" });
      await assertDetail(page, "#v82detail.on article.card", id);
    });
  });
});

test.describe("13F investor view state", () => {
  test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false });

  async function openInvestors(page, hash = "#investors") {
    await page.goto(`/?v83beta${hash}`, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".inv-grid, .inv-table").first()).toBeVisible();
    await expect(page.locator("#v83rail")).toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).toHaveClass(/inv-wide/);
    await expect(page.locator("#v83rail .v83-search")).toBeVisible();
  }

  test("13F transitions restore the right rail", async ({ page }) => {
    await openInvestors(page);

    await page.locator('#v83nav .v83-link[data-k="themes"]').click();
    await expect(page.locator("#v83rail")).not.toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
    await expect(page.locator("#v83rail .v83-search")).toBeVisible();

    await page.locator('#v83nav .v83-link[data-k="investors"]').click();
    await expect(page.locator(".inv-grid")).toBeVisible();
    await expect(page.locator("#v83rail")).toHaveClass(/inv-rail-hide/);

    await page.locator("#feedList > .v83post-head.v83navback .v83post-back").click();
    await expect(page.locator("#v83rail")).not.toHaveClass(/inv-rail-hide/);
    await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
  });

  test("13F deep link renders the investor detail", async ({ page }) => {
    await openInvestors(page, "#investor-berkshire");
    await expect(page.locator("#feedList .inv-table")).toBeVisible();
    await expect(page.locator("#feedList .series-head-name")).toContainText("›");
  });

  test.describe("responsive widths", () => {
    test.use({ viewport: { width: 1280, height: 900 }, isMobile: false, hasTouch: false });

    test("13F rail state survives 1024px and 1180px theme transitions", async ({ page }) => {
      for (const width of [1024, 1180]) {
        await page.setViewportSize({ width, height: 900 });
        await openInvestors(page);

        await page.locator('#v83nav .v83-link[data-k="themes"]').click();
        await expect(page.locator("#v83rail")).not.toHaveClass(/inv-rail-hide/);
        await expect(page.locator("html")).not.toHaveClass(/inv-wide/);
        await expect(page.locator("#v83rail .v83-search")).toBeVisible();
      }
    });
  });

  test.describe("mobile drawer and compare", () => {
    test.use({ viewport: { width: 390, height: 844 }, isMobile: false, hasTouch: true });

    test("mobile drawer opens 13F compare and returns to the list", async ({ page }) => {
      await page.goto("/?v82beta", { waitUntil: "domcontentloaded" });
      await expect(page.locator("#v82av")).toBeVisible();

      await page.locator("#v82av").click();
      const investorMenuItem = page.locator('#v82drawer [data-act="investors"]');
      await expect(investorMenuItem).toBeVisible();
      await investorMenuItem.click();

      await expect(page.locator("#v82drawer")).not.toHaveClass(/on/);
      await expect(page.locator("#feedList .inv-grid")).toBeVisible();

      await expect(page.locator('.inv-select-chip[aria-pressed="true"]')).toHaveCount(2);
      await expect(page.locator(".inv-compare-go")).toBeEnabled();
      await page.locator(".inv-compare-go").click();
      await expect(page).toHaveURL(/#investor-compare$/);
      await expect(page.locator(".inv-compare-summary-grid")).toBeVisible();

      await page.goBack();
      await expect(page.locator("#feedList .inv-grid")).toBeVisible();
    });
  });
});

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

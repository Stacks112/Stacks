import { expect, test } from "@playwright/test";

const monthCells = "#v82calGroups .v82cal-month-cell[data-date]";

async function openCalendar(page) {
  await page.goto("/?v82beta#calendar", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#v82cal")).toHaveClass(/on/);
  await expect(page.locator("#v82calGroups [data-week-start]").first()).toBeVisible();
}

async function captureScrollTargets(page) {
  await page.evaluate(() => {
    window.__calendarScrollCalls = [];
    if (window.__calendarScrollPatched) return;
    Element.prototype.scrollIntoView = function (options) {
      window.__calendarScrollCalls.push({
        date: this.getAttribute("data-date"),
        weekStart: this.getAttribute("data-week-start"),
        options: options || null,
      });
    };
    window.__calendarScrollPatched = true;
  });
}

function sundayOf(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() - d.getDay());
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

test.describe("mobile calendar navigation", () => {
  test("monthly event date opens its week and selects the date", async ({ page }) => {
    await openCalendar(page);
    await captureScrollTargets(page);

    await page.locator("#v82cal-h .v82cal-month-btn").click();
    await expect(page.locator("#v82cal")).toHaveClass(/v82cal-month-mode/);

    const cells = await page.locator(monthCells).evaluateAll((els) => els.map((el) => ({
      date: el.dataset.date,
      hasEvent: !!el.querySelector(".v82cal-month-chips"),
    })));
    const chosen = cells.find((cell) => cell.hasEvent) || cells[0];
    expect(chosen).toBeTruthy();

    await page.locator(`${monthCells}[data-date="${chosen.date}"]`).click();
    await expect(page.locator("#v82cal")).not.toHaveClass(/v82cal-month-mode/);
    const last = await page.evaluate(() => window.__calendarScrollCalls.at(-1));
    expect(last).toMatchObject({ date: chosen.date });
    expect(last.options).toMatchObject({ block: "start" });
  });

  test("empty monthly date falls back to its week divider", async ({ page }) => {
    await openCalendar(page);
    await captureScrollTargets(page);

    await page.locator("#v82cal-h .v82cal-month-btn").click();
    const cells = await page.locator(monthCells).evaluateAll((els) => els.map((el) => ({
      date: el.dataset.date,
      hasEvent: !!el.querySelector(".v82cal-month-chips"),
    })));
    const empty = cells.find((cell) => !cell.hasEvent);
    expect(empty).toBeTruthy();

    await page.locator(`${monthCells}[data-date="${empty.date}"]`).click();
    await expect(page.locator("#v82cal")).not.toHaveClass(/v82cal-month-mode/);
    const last = await page.evaluate(() => window.__calendarScrollCalls.at(-1));
    expect(last).toMatchObject({ weekStart: sundayOf(empty.date) });
  });

  test("back closes the calendar after a monthly date selection", async ({ page }) => {
    await openCalendar(page);
    await page.locator("#v82cal-h .v82cal-month-btn").click();
    const date = await page.locator(monthCells).first().getAttribute("data-date");
    await page.locator(`${monthCells}[data-date="${date}"]`).click();
    await expect(page.locator("#v82cal")).not.toHaveClass(/v82cal-month-mode/);

    await page.goBack();
    await expect(page.locator("#v82cal")).not.toHaveClass(/on/);
  });
});

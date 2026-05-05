import { test, expect } from "@playwright/test";
import path from "path";

const PLAN_IMAGE = path.resolve(
  __dirname,
  "../../../dataset/images/raw/001_Fire_Sprinkler_Plan_page_001.png"
);

test("upload plan, draw crop, detect, assert bboxes render", async ({ page }) => {
  await page.goto("http://localhost:3000");

  // Upload the plan
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(PLAN_IMAGE);

  // Wait for image to appear
  const img = page.locator('[data-testid="plan-image"]');
  await img.waitFor({ state: "visible", timeout: 10_000 });

  // Draw a crop on the canvas using mouse events (not dragAndDrop —
  // React mousedown/mousemove/mouseup handlers don't fire on drag events)
  const canvas = page.locator("canvas");
  const canvasBox = await canvas.boundingBox();
  expect(canvasBox).not.toBeNull();

  const startX = canvasBox!.x + 60;
  const startY = canvasBox!.y + 60;
  const endX = canvasBox!.x + 180;
  const endY = canvasBox!.y + 180;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.mouse.move(endX, endY, { steps: 10 });
  await page.mouse.up();

  // Crop count should update
  await expect(page.locator('[data-testid="crop-count"]')).toHaveText(/1 crop/);

  // Wait for categories to load and the first category to be auto-selected
  const select = page.locator("select");
  await expect(select).not.toBeDisabled({ timeout: 10_000 });
  // Select the first real option (index 0 now that the disabled placeholder is removed)
  await select.selectOption({ index: 0 });

  // Hit Detect
  const detectBtn = page.locator('[data-testid="detect-btn"]');
  await detectBtn.click();

  // Wait for detect button to leave its "Detecting…" state (up to 30s per CLAUDE.md)
  await expect(detectBtn).not.toHaveText("Detecting…", { timeout: 30_000 });

  // Assert at least one bbox was rendered
  const bboxes = page.locator('[data-testid="bbox"]');
  const count = await bboxes.count();
  expect(count).toBeGreaterThan(0);
});

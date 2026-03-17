// spec: specs/gsc-ai-dashboard-test-plan.md
// suite: 6. System Prompt

import { test, expect } from '@playwright/test';

const DASH = 'http://localhost:5173';

async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

test.describe('System Prompt', () => {

  // ── 6.1 ──────────────────────────────────────────────────────────────────
  test('System Prompt section heading is visible', async ({ page }) => {
    // Navigate to the dashboard and scroll to the System Prompt section
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    // h2 heading 'System Prompt' is visible
    await expect(page.locator('h2', { hasText: 'System Prompt' })).toBeVisible();
  });

  // ── 6.2 ──────────────────────────────────────────────────────────────────
  test('Code window header bar shows file name annotation', async ({ page }) => {
    // Navigate to the dashboard and observe the dark header bar
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    // Header bar displays the file name annotation
    await expect(page.locator('text=prompt_manager.py — BASE_SYSTEM_PROMPT')).toBeVisible();
  });

  // ── 6.3 ──────────────────────────────────────────────────────────────────
  test('Traffic-light window controls are displayed in header bar', async ({ page }) => {
    // Navigate to the dashboard and observe the System Prompt header bar dots
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    // Three colored circle dots appear left-to-right: red, yellow, green
    const dots = page.locator('.bg-gray-800 .rounded-full');
    await expect(dots).toHaveCount(3);

    // Verify individual colors
    await expect(dots.nth(0)).toHaveClass(/bg-red-500/);
    await expect(dots.nth(1)).toHaveClass(/bg-yellow-400/);
    await expect(dots.nth(2)).toHaveClass(/bg-green-500/);
  });

  // ── 6.4 ──────────────────────────────────────────────────────────────────
  test('Code block contains GSC identity text', async ({ page }) => {
    // Navigate to the dashboard and read the System Prompt pre block content
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    // Block contains the GSC identity introduction
    await expect(page.locator('pre').first()).toContainText(
      'You are the AI assistant for GSC (Golden State Convenience) delivery drivers',
    );
  });

  // ── 6.5 ──────────────────────────────────────────────────────────────────
  test('All six delivery rules are present in the code block', async ({ page }) => {
    // Navigate to the dashboard and read the System Prompt code block
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    const pre = page.locator('pre').first();

    // RULE 1 — LOCATION THRESHOLD
    await expect(pre).toContainText('RULE 1');

    // RULE 2 — CIGARETTES AND TOBACCO
    await expect(pre).toContainText('RULE 2');

    // RULE 3 — REQUIRED ITEMS BLOCK DELIVERY
    await expect(pre).toContainText('RULE 3');

    // RULE 4 — PHOTO ITEMS
    await expect(pre).toContainText('RULE 4');

    // RULE 5 — NEW DRIVER GUIDANCE
    await expect(pre).toContainText('RULE 5');

    // RULE 6 — IDLE DRIVER
    await expect(pre).toContainText('RULE 6');
  });

  // ── 6.6 ──────────────────────────────────────────────────────────────────
  test('Code block is scrollable and does not overflow the page', async ({ page }) => {
    // Navigate to the dashboard and scroll within the System Prompt code block
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    const pre = page.locator('pre').first();

    // Code block is within its container — max-height is capped
    const boundingBox = await pre.boundingBox();
    expect(boundingBox).not.toBeNull();

    // Height should be at or under 512px (32rem at 16px base)
    expect(boundingBox!.height).toBeLessThanOrEqual(520);

    // Scroll to bottom of the pre block — verify no layout breakage
    await pre.evaluate((el) => { el.scrollTop = el.scrollHeight; });
    await expect(page.locator('h2', { hasText: 'System Prompt' })).toBeVisible();
  });

  // ── 6.7 ──────────────────────────────────────────────────────────────────
  test('System Prompt section is read-only', async ({ page }) => {
    // Navigate to the dashboard and inspect the System Prompt code block
    await openDash(page);
    await page.locator('nav a[href="#system-prompt"]').click();

    // Content is inside a pre element — it cannot be edited
    const pre = page.locator('pre').first();
    await expect(pre).toBeVisible();

    // No edit controls, pencil icons, or form inputs are present in the section
    const section = page.locator('#system-prompt');
    await expect(section.locator('input, textarea, button')).toHaveCount(0);
  });

});

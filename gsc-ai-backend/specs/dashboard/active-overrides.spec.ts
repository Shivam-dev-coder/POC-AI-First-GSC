// spec: specs/gsc-ai-dashboard-test-plan.md
// suite: 4. Active Overrides

import { test, expect } from '@playwright/test';

const DASH = 'http://localhost:5173';
const API  = 'http://localhost:8000';

async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

async function mockOverrides(
  page: import('@playwright/test').Page,
  overrides: string[],
) {
  await page.route('**/api/overrides', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ overrides }),
    });
  });
}

test.describe('Active Overrides', () => {

  test.beforeEach(async ({ request }) => {
    await request.delete(`${API}/overrides`);
  });

  test.afterAll(async ({ request }) => {
    await request.delete(`${API}/overrides`);
  });

  // ── 4.1 ──────────────────────────────────────────────────────────────────
  test('Empty state shown when no overrides are active', async ({ page }) => {
    // Call DELETE /overrides to clear all, then navigate to the dashboard
    await openDash(page);
    await page.locator('nav a[href="#active-overrides"]').click();

    // Dashed-border empty state panel is visible
    await expect(page.locator('text=No active overrides.')).toBeVisible();

    // Sub-text 'AI is running on the base system prompt.' is visible
    await expect(page.locator('text=AI is running on the base system prompt.')).toBeVisible();
  });

  // ── 4.2 ──────────────────────────────────────────────────────────────────
  test('Override card displays rule text and AI Active badge', async ({ page }) => {
    // Mock the active overrides response with one visible rule card.
    await mockOverrides(page, ['Require photo for all fragile items']);

    // Navigate to the dashboard
    await openDash(page);

    // Card is visible with rule text
    await expect(page.locator('text=Require photo for all fragile items')).toBeVisible();

    // '⚙️ AI Active' purple pill badge is shown on the card
    await expect(page.locator('text=AI Active').first()).toBeVisible();
  });

  // ── 4.3 ──────────────────────────────────────────────────────────────────
  test('Override card shows numbered badge starting from 1', async ({ page, request }) => {
    // Add one override via the API
    await request.post(`${API}/override`, { data: { rule: 'Badge number test rule' } });

    // Navigate to the dashboard — purple circle badge on the card shows '1'
    await openDash(page);
    await expect(page.locator('.rounded-full.bg-purple-600', { hasText: '1' })).toBeVisible();
  });

  // ── 4.4 ──────────────────────────────────────────────────────────────────
  test('Multiple overrides get numbered cards in order', async ({ page }) => {
    // Mock three active overrides so numbering can be asserted deterministically.
    await mockOverrides(page, [
      'Rule A for numbering test',
      'Rule B for numbering test',
      'Rule C for numbering test',
    ]);

    // Navigate to the dashboard
    await openDash(page);

    // Three distinct cards appear in correct order with badges 1, 2, 3
    await expect(page.locator('text=Rule A for numbering test')).toBeVisible();
    await expect(page.locator('text=Rule B for numbering test')).toBeVisible();
    await expect(page.locator('text=Rule C for numbering test')).toBeVisible();

    await expect(page.locator('.rounded-full.bg-purple-600', { hasText: '1' })).toBeVisible();
    await expect(page.locator('.rounded-full.bg-purple-600', { hasText: '2' })).toBeVisible();
    await expect(page.locator('.rounded-full.bg-purple-600', { hasText: '3' })).toBeVisible();

    // All three badges present
    await expect(page.locator('.rounded-full.bg-purple-600')).toHaveCount(3);
  });

  // ── 4.5 ──────────────────────────────────────────────────────────────────
  test('Override card displays added-at timestamp', async ({ page }) => {
    let overrides: string[] = [];

    await page.route('**/api/overrides', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ overrides }),
      });
    });

    await page.route('**/api/command', async (route) => {
      overrides = ['Timestamp verification rule'];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          type: 'override',
          rule: 'Timestamp verification rule',
        }),
      });
    });

    // Navigate to the dashboard and apply a mocked override command.
    await openDash(page);

    await page.locator('textarea').fill('Timestamp verification rule');
    await page.locator('button', { hasText: 'Apply' }).click();

    // Wait for the rule to be applied
    await expect(page.locator('.fixed.bottom-6.right-6')).toBeVisible({ timeout: 20_000 });

    // Navigate to Active Overrides section
    await page.locator('nav a[href="#active-overrides"]').click();

    // Card shows a time string in the bottom-right corner in locale time format (e.g. "10:34:22 AM")
    const timestampPattern = /\d{1,2}:\d{2}:\d{2}\s*(AM|PM)/i;
    const timestamps = page.locator('#active-overrides .text-xs.text-gray-400');
    await expect(timestamps.first()).toHaveText(timestampPattern);
  });

});

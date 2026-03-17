// spec: specs/gsc-ai-dashboard-test-plan.md
// suite: 2. Overview Section

import { test, expect } from '@playwright/test';

const DASH = 'http://localhost:5173';
const API  = 'http://localhost:8000';

async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

test.describe('Overview Section', () => {

  // ── 2.1 ──────────────────────────────────────────────────────────────────
  test('Three stat cards render on load', async ({ page }) => {
    // Navigate to the dashboard and observe the Overview section
    await openDash(page);

    // Stat card labeled 'Active Overrides' is visible
    await expect(page.locator('p.text-xs', { hasText: 'ACTIVE OVERRIDES' })).toBeVisible();

    // Stat card labeled 'Orchestrator' is visible
    await expect(page.locator('p.text-xs', { hasText: 'ORCHESTRATOR' })).toBeVisible();

    // Stat card labeled 'Current Time' is visible
    await expect(page.locator('p.text-xs', { hasText: 'CURRENT TIME' })).toBeVisible();
  });

  // ── 2.2 ──────────────────────────────────────────────────────────────────
  test('Active Overrides count is zero with no overrides', async ({ page, request }) => {
    // Call DELETE http://localhost:8000/overrides to clear all state
    await request.delete(`${API}/overrides`);

    // Navigate to the dashboard
    await openDash(page);

    // 'Active Overrides' stat card shows value 0
    const card = page.locator('p.text-xs', { hasText: 'ACTIVE OVERRIDES' }).locator('xpath=..');
    await expect(card.locator('p.text-2xl')).toHaveText('0');
  });

  // ── 2.3 ──────────────────────────────────────────────────────────────────
  test('Active Overrides count reflects current API state', async ({ page }) => {
    await page.route('**/api/overrides', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          overrides: ['Overview count test rule A', 'Overview count test rule B'],
        }),
      });
    });

    // Navigate to the dashboard — 'Active Overrides' stat card shows value 2
    await openDash(page);
    const card = page.locator('p.text-xs', { hasText: 'ACTIVE OVERRIDES' }).locator('xpath=..');
    await expect(card.locator('p.text-2xl')).toHaveText('2');
  });

  // ── 2.4 ──────────────────────────────────────────────────────────────────
  test('Orchestrator stat shows Online when backend is running', async ({ page }) => {
    // Ensure orchestrator is running, navigate to the dashboard, wait up to 6 seconds
    await openDash(page);

    // 'Orchestrator' card shows 'Online' in green text, icon is 🟢
    await expect(page.locator('text=Online')).toBeVisible({ timeout: 6_000 });
    const card = page.locator('p.text-xs', { hasText: 'ORCHESTRATOR' }).locator('xpath=..');
    await expect(card.locator('p.text-2xl')).toHaveText('Online');
  });

  // ── 2.5 ──────────────────────────────────────────────────────────────────
  test('Orchestrator stat shows Offline when backend is down', async ({ page }) => {
    await page.route('**/api/overrides', async (route) => {
      await route.abort();
    });

    // Simulate the backend fetch failing so the UI enters its offline state.
    await page.goto(DASH);
    await expect(page.locator('h1')).toContainText('GSC AI Dashboard');

    // 'Orchestrator' card shows 'Offline' in red text
    const card = page.locator('p.text-xs', { hasText: 'ORCHESTRATOR' }).locator('xpath=..');
    await expect(card.locator('p.text-2xl')).toHaveText('Offline');
  });

  // ── 2.6 ──────────────────────────────────────────────────────────────────
  test('Current Time stat auto-updates every second', async ({ page }) => {
    // Navigate to the dashboard and read the Current Time card value
    await openDash(page);
    const card = page.locator('p.text-xs', { hasText: 'CURRENT TIME' }).locator('xpath=..');
    const valueLocator = card.locator('p.text-2xl');

    const time1 = await valueLocator.innerText();

    // Wait 1.1 seconds and read the Current Time card value again
    await page.waitForTimeout(1_100);
    const time2 = await valueLocator.innerText();

    // The two time values are different, confirming the clock increments live
    expect(time1).not.toEqual(time2);
  });

});

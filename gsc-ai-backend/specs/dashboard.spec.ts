/**
 * Dashboard UI Tests — specs/dashboard.spec.ts
 *
 * These tests exercise the React dashboard running at http://localhost:5173.
 * Playwright auto-starts the Vite dev server via the webServer config in
 * playwright.config.ts (reuseExistingServer: true so it also works if you
 * already have it running).
 *
 * Requires the orchestrator to be running first:
 *   uvicorn orchestrator.main:app --reload --port 8000
 */

import { test, expect } from '@playwright/test';

const DASH  = 'http://localhost:5173';
const API   = 'http://localhost:8000';

// ─── helpers ─────────────────────────────────────────────────────────────────

/** Navigate to the dashboard and wait for the page to be visible. */
async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

// ─── Sidebar & page load ─────────────────────────────────────────────────────

test.describe('Sidebar & Page Load', () => {
  test('page loads and shows the GSC AI Dashboard heading', async ({ page }) => {
    await openDash(page);
  });

  test('sidebar shows sub-title "Delivery Logic Control Panel"', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=Delivery Logic Control Panel')).toBeVisible();
  });

  test('sidebar renders all five navigation links', async ({ page }) => {
    await openDash(page);
    const labels = ['Overview', 'Command Centre', 'Active Overrides', 'Live Log', 'System Prompt'];
    for (const label of labels) {
      await expect(page.locator(`nav a`, { hasText: label })).toBeVisible();
    }
  });

  test('sidebar footer shows orchestrator address', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=Orchestrator · localhost:8000')).toBeVisible();
  });
});

// ─── Overview section ────────────────────────────────────────────────────────

test.describe('Overview Section', () => {
  test('three stat cards are visible', async ({ page }) => {
    await openDash(page);
    for (const label of ['Active Overrides', 'Orchestrator', 'Current Time']) {
      await expect(page.locator(`text=${label}`).first()).toBeVisible();
    }
  });

  test('orchestrator stat shows Online when the orchestrator is running', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=Online')).toBeVisible({ timeout: 6_000 });
  });

  test('current time stat updates every second', async ({ page }) => {
    await openDash(page);
    const heading = page.locator('p.text-xs', { hasText: 'Current Time' });
    const card    = heading.locator('xpath=..'); // parent div
    const time1   = await card.locator('p.text-2xl').innerText();
    await page.waitForTimeout(1_100);
    const time2   = await card.locator('p.text-2xl').innerText();
    expect(time1).not.toEqual(time2);
  });
});

// ─── Command Centre ───────────────────────────────────────────────────────────

test.describe('Command Centre', () => {
  test('shows "Quick Commands" heading and eight quick-command buttons', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=Quick Commands')).toBeVisible();
    // Eight buttons are defined in QUICK_COMMANDS array
    const buttons = page.locator('button', { hasText: /block|popup|scan|photo|driver|location/i });
    await expect(buttons.first()).toBeVisible();
  });

  test('textarea placeholder text is visible', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('textarea')).toBeVisible();
  });

  test('Apply button is disabled when textarea is empty', async ({ page }) => {
    await openDash(page);
    await page.locator('textarea').fill('');
    await expect(page.locator('button', { hasText: 'Apply' })).toBeDisabled();
  });

  test('clicking a quick-command button populates the textarea', async ({ page }) => {
    await openDash(page);
    const cmd = 'Hard block Stop 4 — no override allowed';
    await page.locator('button', { hasText: cmd }).click();
    await expect(page.locator('textarea')).toHaveValue(cmd);
  });

  test('Apply button becomes enabled after typing text', async ({ page }) => {
    await openDash(page);
    await page.locator('textarea').fill('Test command');
    await expect(page.locator('button', { hasText: 'Apply' })).toBeEnabled();
  });

  test('applying a rule shows a toast notification', async ({ page }) => {
    await openDash(page);
    await page.locator('textarea').fill('Warn drivers about slippery floor at Stop 9');
    await page.locator('button', { hasText: 'Apply' }).click();
    // Toast is fixed bottom-right — AI call may take up to 20 s
    const toast = page.locator('.fixed.bottom-6.right-6');
    await expect(toast).toBeVisible({ timeout: 20_000 });
  });
});

// ─── Active Overrides ─────────────────────────────────────────────────────────

test.describe('Active Overrides', () => {
  // Each test starts from a clean slate
  test.beforeEach(async ({ request }) => {
    await request.delete(`${API}/overrides`);
  });
  test.afterAll(async ({ request }) => {
    await request.delete(`${API}/overrides`);
  });

  test('empty state is shown when no overrides are active', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=No active overrides.')).toBeVisible();
    await expect(page.locator('text=AI is running on the base system prompt.')).toBeVisible();
  });

  test('override card appears after adding a rule via the API', async ({ page, request }) => {
    const rule = 'Require photo for all fragile items';
    await request.post(`${API}/override`, { data: { rule } });
    await openDash(page);
    await expect(page.locator(`text=${rule}`)).toBeVisible();
    await expect(page.locator('text=AI Active')).toBeVisible();
  });

  test('numbered badge on override card shows the rule index', async ({ page, request }) => {
    await request.post(`${API}/override`, { data: { rule: 'Block Stop 5 unconditionally' } });
    await openDash(page);
    // First override card should show badge "1"
    await expect(page.locator('.rounded-full.bg-purple-600', { hasText: '1' })).toBeVisible();
  });

  test('multiple overrides each get their own card', async ({ page, request }) => {
    await page.route(`${DASH}/api/overrides`, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ overrides: ['Rule A for test', 'Rule B for test'] }),
      });
    });

    await openDash(page);
    await expect(page.locator('text=Rule A for test')).toBeVisible();
    await expect(page.locator('text=Rule B for test')).toBeVisible();
    await expect(page.locator('.rounded-full.bg-purple-600')).toHaveCount(2);
  });

  test('Clear All Rules button clears overrides after dialog confirmation', async ({ page, request }) => {
    await request.post(`${API}/override`, { data: { rule: 'Temp rule to be cleared' } });
    await openDash(page);
    await expect(page.locator('text=Temp rule to be cleared')).toBeVisible();

    // Accept the window.confirm dialog, then click the button
    page.once('dialog', dialog => dialog.accept());
    await page.locator('button', { hasText: 'Clear All Rules' }).click();

    await expect(page.locator('text=No active overrides.')).toBeVisible({ timeout: 6_000 });
  });

  test('dismissing the Clear All dialog leaves overrides intact', async ({ page, request }) => {
    await request.post(`${API}/override`, { data: { rule: 'Should survive cancel' } });
    await openDash(page);

    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('button', { hasText: 'Clear All Rules' }).click();

    // Rule must still be present
    await expect(page.locator('text=Should survive cancel')).toBeVisible();
  });
});

// ─── Live Log ─────────────────────────────────────────────────────────────────

test.describe('Live Log', () => {
  test('live log section heading is visible', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('h2', { hasText: 'Live Log' })).toBeVisible();
  });

  test('connection status badge is visible on page load', async ({ page }) => {
    await openDash(page);
    // Any of the valid badge states
    const badge = page.locator('span', { hasText: /Connected|Reconnecting|Disconnected|Error/i }).first();
    await expect(badge).toBeVisible({ timeout: 5_000 });
  });

  test('status badge shows Connected once WebSocket handshake completes', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=🟢 Connected')).toBeVisible({ timeout: 8_000 });
  });

  test('Clear Log button resets entry count to 0', async ({ page }) => {
    await openDash(page);
    await page.locator('button', { hasText: 'Clear Log' }).click();
    await expect(page.locator('text=0 entries')).toBeVisible();
  });

  test('log feed area is rendered', async ({ page }) => {
    await openDash(page);
    // The scrollable feed div has a fixed height of h-96
    await expect(page.locator('.h-96')).toBeVisible();
  });
});

// ─── System Prompt ─────────────────────────────────────────────────────────────

test.describe('System Prompt', () => {
  test('system prompt section heading is visible', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('h2', { hasText: 'System Prompt' })).toBeVisible();
  });

  test('header bar shows the file name annotation', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('text=prompt_manager.py — BASE_SYSTEM_PROMPT')).toBeVisible();
  });

  test('traffic-light dots are shown in the header bar', async ({ page }) => {
    await openDash(page);
    // Three colored dots: red, yellow, green
    const dots = page.locator('.bg-gray-800 .rounded-full');
    await expect(dots).toHaveCount(3);
  });

  test('code block contains the GSC delivery rules text', async ({ page }) => {
    await openDash(page);
    await expect(page.locator('pre').first()).toContainText('GSC (Golden State Convenience)');
    await expect(page.locator('pre').first()).toContainText('RULE 1');
    await expect(page.locator('pre').first()).toContainText('RULE 2');
  });
});

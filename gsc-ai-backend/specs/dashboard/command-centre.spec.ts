// spec: specs/gsc-ai-dashboard-test-plan.md
// suite: 3. Command Centre

import { test, expect } from '@playwright/test';

const DASH = 'http://localhost:5173';
const API  = 'http://localhost:8000';

const QUICK_COMMANDS = [
  "Don't show location override popup on map screen",
  'Hard block Stop 4 — no override allowed',
  'Cigarettes must be scanned twice and manually counted',
  'All damaged items require a photo before delivery',
  'Driver ID 1 is new — enable spotlight guidance on all screens',
  'Clear all location restrictions',
  'Send a popup to all drivers: please check your next stop details',
  'Send urgent popup to all drivers: route has changed, check the app',
];

async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

test.describe('Command Centre', () => {

  test.beforeEach(async ({ request }) => {
    await request.delete(`${API}/overrides`);
  });

  test.afterAll(async ({ request }) => {
    await request.delete(`${API}/overrides`);
  });

  // ── 3.1 ──────────────────────────────────────────────────────────────────
  test('Quick Commands section shows 8 buttons', async ({ page }) => {
    // Navigate to the dashboard and scroll to the Command Centre section
    await openDash(page);
    await page.locator('nav a[href="#command-centre"]').click();

    // Label 'QUICK COMMANDS' is visible in small uppercase grey text
    await expect(page.locator('text=Quick Commands')).toBeVisible();

    // Exactly 8 quick-command buttons are displayed in a responsive grid
    const grid = page.locator('#command-centre .grid button');
    await expect(grid).toHaveCount(8);
  });

  // ── 3.2 ──────────────────────────────────────────────────────────────────
  test('All eight quick-command button labels are correct', async ({ page }) => {
    // Navigate to the dashboard and read each quick-command button text
    await openDash(page);

    for (const cmd of QUICK_COMMANDS) {
      await expect(page.locator('button', { hasText: cmd })).toBeVisible();
    }
  });

  // ── 3.3 ──────────────────────────────────────────────────────────────────
  test('Clicking a quick-command button populates the textarea', async ({ page }) => {
    await openDash(page);

    // Click the quick-command button "Hard block Stop 4 — no override allowed"
    const cmd = 'Hard block Stop 4 — no override allowed';
    await page.locator('button', { hasText: cmd }).click();

    // Textarea value is set to the command text — no form submission occurs
    await expect(page.locator('textarea')).toHaveValue(cmd);
  });

  // ── 3.4 ──────────────────────────────────────────────────────────────────
  test('Textarea shows correct placeholder text', async ({ page }) => {
    // Navigate to the dashboard and ensure the textarea is empty
    await openDash(page);
    await page.locator('textarea').fill('');

    // Textarea displays placeholder text mentioning key examples
    await expect(page.locator('textarea')).toHaveAttribute(
      'placeholder',
      expect.stringContaining('Hard block Stop 4'),
    );
    await expect(page.locator('textarea')).toHaveAttribute(
      'placeholder',
      expect.stringContaining('Send a popup to all drivers'),
    );
  });

  // ── 3.5 ──────────────────────────────────────────────────────────────────
  test('Apply button is disabled when textarea is empty', async ({ page }) => {
    // Navigate to the dashboard and ensure the textarea is empty
    await openDash(page);
    await page.locator('textarea').fill('');

    // Apply button has disabled attribute
    await expect(page.locator('button', { hasText: 'Apply' })).toBeDisabled();
  });

  // ── 3.6 ──────────────────────────────────────────────────────────────────
  test('Apply button is disabled for whitespace-only input', async ({ page }) => {
    await openDash(page);

    // Type only spaces into the textarea — button remains disabled
    await page.locator('textarea').fill('   ');
    await expect(page.locator('button', { hasText: 'Apply' })).toBeDisabled();
  });

  // ── 3.7 ──────────────────────────────────────────────────────────────────
  test('Apply button becomes enabled after typing text', async ({ page }) => {
    await openDash(page);

    // Type 'Test command' into the textarea
    await page.locator('textarea').fill('Test command');

    // Apply button is enabled and clickable
    await expect(page.locator('button', { hasText: 'Apply' })).toBeEnabled();
  });

  // ── 3.8 ──────────────────────────────────────────────────────────────────
  test('Applying a rule override shows green success toast', async ({ page }) => {
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
      overrides = ['Warn drivers about wet floor at Stop 3'];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          type: 'override',
          rule: 'Warn drivers about wet floor at Stop 3',
        }),
      });
    });

    await openDash(page);

    // Type rule command and click Apply
    await page.locator('textarea').fill('Warn drivers about wet floor at Stop 3');
    await page.locator('button', { hasText: 'Apply' }).click();

    // Wait up to 20 seconds for the AI response — green toast appears
    const toast = page.locator('.fixed.bottom-6.right-6');
    await expect(toast).toBeVisible({ timeout: 20_000 });
    await expect(toast).toContainText('Rule applied');

    // Textarea is cleared after successful submission
    await expect(page.locator('textarea')).toHaveValue('');

    // Toast auto-dismisses after approximately 4 seconds
    await expect(toast).not.toBeVisible({ timeout: 6_000 });
  });

  // ── 3.9 ──────────────────────────────────────────────────────────────────
  test('Applying a popup command shows blue info toast', async ({ page }) => {
    await openDash(page);

    // Type popup command and click Apply, wait up to 20 seconds
    await page.locator('textarea').fill('Send a popup to all drivers: road closed ahead');
    await page.locator('button', { hasText: 'Apply' }).click();

    // Blue toast notification appears: 'Popup sent to X driver(s)'
    const toast = page.locator('.fixed.bottom-6.right-6');
    await expect(toast).toBeVisible({ timeout: 20_000 });
    await expect(toast).toContainText(/Popup sent to \d+ driver/);

    // Toast auto-dismisses after approximately 4 seconds
    await expect(toast).not.toBeVisible({ timeout: 6_000 });
  });

  // ── 3.10 ─────────────────────────────────────────────────────────────────
  test('Applying a rule updates Active Overrides count without page reload', async ({ page }) => {
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
      overrides = ['Block fragile item stops during rain'];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          type: 'override',
          rule: 'Block fragile item stops during rain',
        }),
      });
    });

    // Confirm 'Active Overrides' shows 0 on initial load.
    await openDash(page);
    const overviewCard = page.locator('p.text-xs', { hasText: 'ACTIVE OVERRIDES' }).locator('xpath=..');
    await expect(overviewCard.locator('p.text-2xl')).toHaveText('0');

    // Apply rule 'Block fragile item stops during rain' and wait for success toast
    await page.locator('textarea').fill('Block fragile item stops during rain');
    await page.locator('button', { hasText: 'Apply' }).click();
    await expect(page.locator('.fixed.bottom-6.right-6')).toBeVisible({ timeout: 20_000 });

    // 'Active Overrides' stat card increments to 1 without page refresh
    await expect(overviewCard.locator('p.text-2xl')).toHaveText('1', { timeout: 5_000 });
  });

  // ── 3.11 ─────────────────────────────────────────────────────────────────
  test('API error shows red error toast', async ({ page }) => {
    await page.route('**/api/command', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Synthetic failure' }),
      });
    });

    await openDash(page);

    // Type a command and click Apply — mocked API failure should surface in the toast.
    await page.locator('textarea').fill('A command that will fail');
    await page.locator('button', { hasText: 'Apply' }).click();

    // Red toast notification appears with message starting 'Failed:'
    const toast = page.locator('.fixed.bottom-6.right-6');
    await expect(toast).toBeVisible({ timeout: 10_000 });
    await expect(toast).toContainText('Failed:');

    // Toast auto-dismisses after approximately 4 seconds
    await expect(toast).not.toBeVisible({ timeout: 6_000 });
  });

  // ── 3.12 ─────────────────────────────────────────────────────────────────
  test('Clear All Rules button shows confirmation dialog', async ({ page, request }) => {
    // Add an override so the button is meaningful
    await request.post(`${API}/override`, { data: { rule: 'Rule for dialog test' } });
    await openDash(page);

    // With at least one override present, click '🗑️ Clear All Rules'
    // Clicking Cancel on the dialog — no overrides are cleared
    page.once('dialog', (dialog) => dialog.dismiss());
    await page.locator('button', { hasText: 'Clear All Rules' }).click();

    // Active Overrides section is unchanged — rule still visible
    await expect(page.locator('text=Rule for dialog test')).toBeVisible();
  });

  // ── 3.13 ─────────────────────────────────────────────────────────────────
  test('Confirming Clear All shows red toast and clears all overrides', async ({ page, request }) => {
    // Add an override so there is something to clear
    await request.post(`${API}/override`, { data: { rule: 'Rule to be cleared' } });
    await openDash(page);

    // Accept the confirmation dialog
    page.once('dialog', (dialog) => dialog.accept());
    await page.locator('button', { hasText: 'Clear All Rules' }).click();

    // Red toast appears: '🗑️ All rules cleared'
    const toast = page.locator('.fixed.bottom-6.right-6');
    await expect(toast).toBeVisible({ timeout: 6_000 });
    await expect(toast).toContainText('All rules cleared');

    // Active Overrides section shows empty state
    await expect(page.locator('text=No active overrides.')).toBeVisible({ timeout: 6_000 });

    // 'Active Overrides' stat card shows 0
    const overviewCard = page.locator('p.text-xs', { hasText: 'ACTIVE OVERRIDES' }).locator('xpath=..');
    await expect(overviewCard.locator('p.text-2xl')).toHaveText('0');

    // Toast auto-dismisses after approximately 4 seconds
    await expect(toast).not.toBeVisible({ timeout: 6_000 });
  });

  // ── 3.14 ─────────────────────────────────────────────────────────────────
  test('Second toast replaces first if applied within 4 seconds', async ({ page }) => {
    await openDash(page);

    // Apply a first rule and observe the toast
    await page.locator('textarea').fill('First toast rule');
    await page.locator('button', { hasText: 'Apply' }).click();
    const toast = page.locator('.fixed.bottom-6.right-6');
    await expect(toast).toBeVisible({ timeout: 20_000 });

    // Within 4 seconds, apply a second rule
    await page.locator('textarea').fill('Second toast rule');
    await page.locator('button', { hasText: 'Apply' }).click();

    // Only one toast is visible at any time
    await expect(toast).toHaveCount(1);
    await expect(toast).toBeVisible({ timeout: 20_000 });
  });

});

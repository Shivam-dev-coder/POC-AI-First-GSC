// spec: specs/gsc-ai-dashboard-test-plan.md
// suite: 1. Sidebar and Page Load

import { test, expect } from '@playwright/test';

const DASH = 'http://localhost:5173';

async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

test.describe('Sidebar and Page Load', () => {

  // ── 1.1 ──────────────────────────────────────────────────────────────────
  test('Page loads with correct heading', async ({ page }) => {
    // Navigate to http://localhost:5173
    await page.goto(DASH);

    // Verify h1 displays '🚚 GSC AI Dashboard'
    await expect(page.locator('h1')).toContainText('🚚 GSC AI Dashboard');

    // Verify browser tab title reads 'GSC AI Dashboard'
    await expect(page).toHaveTitle('GSC AI Dashboard');
  });

  // ── 1.2 ──────────────────────────────────────────────────────────────────
  test('Sidebar renders all five navigation links', async ({ page }) => {
    // Navigate to the dashboard and inspect the left sidebar nav element
    await openDash(page);

    // Five links are present with emoji prefixes
    const labels = [
      { text: 'Overview',         href: '#overview' },
      { text: 'Command Centre',   href: '#command-centre' },
      { text: 'Active Overrides', href: '#active-overrides' },
      { text: 'Live Log',         href: '#live-log' },
      { text: 'System Prompt',    href: '#system-prompt' },
    ];
    for (const { text, href } of labels) {
      const link = page.locator(`nav a[href="${href}"]`);
      await expect(link).toBeVisible();
      await expect(link).toContainText(text);
    }
  });

  // ── 1.3 ──────────────────────────────────────────────────────────────────
  test('Sidebar shows subtitle Delivery Logic Control Panel', async ({ page }) => {
    // Navigate to the dashboard
    await openDash(page);

    // Text 'Delivery Logic Control Panel' is visible beneath the logo heading in grey
    await expect(page.locator('text=Delivery Logic Control Panel')).toBeVisible();
  });

  // ── 1.4 ──────────────────────────────────────────────────────────────────
  test('Sidebar footer shows orchestrator address', async ({ page }) => {
    // Navigate to the dashboard and scroll to the bottom of the sidebar
    await openDash(page);

    // Text 'Orchestrator · localhost:8000' is visible at the bottom of the sidebar
    await expect(page.locator('text=Orchestrator · localhost:8000')).toBeVisible();
  });

  // ── 1.5 ──────────────────────────────────────────────────────────────────
  test('Navigation links scroll to correct page sections', async ({ page }) => {
    // Navigate to the dashboard
    await openDash(page);

    const navItems = [
      { href: '#overview',         heading: 'Overview' },
      { href: '#command-centre',   heading: 'Command Centre' },
      { href: '#active-overrides', heading: 'Active Overrides' },
      { href: '#live-log',         heading: 'Live Log' },
      { href: '#system-prompt',    heading: 'System Prompt' },
    ];

    // Click each sidebar link and verify the section heading is in viewport
    for (const { href, heading } of navItems) {
      await page.locator(`nav a[href="${href}"]`).click();
      await expect(page.locator(`h2`, { hasText: heading })).toBeInViewport();
      await expect(page).toHaveURL(new RegExp(href.replace('#', '\\#')));
    }
  });

  // ── 1.6 ──────────────────────────────────────────────────────────────────
  test('Sidebar link hover state is visible', async ({ page }) => {
    // Navigate to the dashboard
    await openDash(page);

    // Hover over each sidebar link and verify it is hoverable (CSS transition applied)
    const links = page.locator('nav a');
    const count = await links.count();
    for (let i = 0; i < count; i++) {
      await links.nth(i).hover();
      // The link should remain visible and interactive after hover
      await expect(links.nth(i)).toBeVisible();
    }
  });

});

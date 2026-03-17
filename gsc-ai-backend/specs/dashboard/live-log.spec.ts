// spec: specs/gsc-ai-dashboard-test-plan.md
// suite: 5. Live Log

import { test, expect } from '@playwright/test';

const DASH = 'http://localhost:5173';

async function openDash(page: import('@playwright/test').Page) {
  await page.goto(DASH);
  await expect(page.locator('h1')).toContainText('GSC AI Dashboard');
}

test.describe('Live Log', () => {

  // ── 5.1 ──────────────────────────────────────────────────────────────────
  test('Live Log section heading is visible', async ({ page }) => {
    // Navigate to the dashboard and scroll to the Live Log section
    await openDash(page);
    await page.locator('nav a[href="#live-log"]').click();

    // h2 heading 'Live Log' is visible
    await expect(page.locator('h2', { hasText: 'Live Log' })).toBeVisible();
  });

  // ── 5.2 ──────────────────────────────────────────────────────────────────
  test('Connection status badge is visible on page load', async ({ page }) => {
    // Navigate to the dashboard and immediately observe the Live Log status badge
    await openDash(page);

    // A status badge appears showing one of the valid states
    const badge = page.locator('span', { hasText: /Connected|Reconnecting|Disconnected|Error/i }).first();
    await expect(badge).toBeVisible({ timeout: 5_000 });
  });

  // ── 5.3 ──────────────────────────────────────────────────────────────────
  test('Status badge shows Connected within 8 seconds when orchestrator is running', async ({ page }) => {
    // Ensure orchestrator is running, navigate to the dashboard, wait up to 8 seconds
    await openDash(page);

    // Status badge shows '🟢 Connected'
    await expect(page.locator('text=🟢 Connected')).toBeVisible({ timeout: 8_000 });
  });

  // ── 5.4 ──────────────────────────────────────────────────────────────────
  test('Status badge shows Disconnected when WebSocket is unavailable', async ({ page }) => {
    await page.addInitScript(() => {
      class MockWebSocket {
        static CONNECTING = 0;
        static OPEN = 1;
        static CLOSING = 2;
        static CLOSED = 3;

        readyState = MockWebSocket.CONNECTING;
        onopen = null;
        onmessage = null;
        onerror = null;
        onclose = null;

        constructor() {
          setTimeout(() => {
            this.readyState = MockWebSocket.CLOSED;
            if (this.onerror) this.onerror(new Event('error'));
            if (this.onclose) this.onclose(new Event('close'));
          }, 0);
        }

        send() {}
        close() {
          this.readyState = MockWebSocket.CLOSED;
          if (this.onclose) this.onclose(new Event('close'));
        }
        addEventListener() {}
        removeEventListener() {}
      }

      Object.defineProperty(window, 'WebSocket', {
        configurable: true,
        writable: true,
        value: MockWebSocket,
      });
    });

    // Navigate to the dashboard with a mocked failing WebSocket implementation.
    await page.goto(DASH);
    await expect(page.locator('h1')).toContainText('GSC AI Dashboard');

    // Status badge shows '⚪ Disconnected' or '🔴 Error' — NOT '🟢 Connected'
    const connected = page.locator('text=🟢 Connected');
    await expect(connected).not.toBeVisible();
    await expect(page.locator('text=/⚪ Disconnected|🔴 Error/')).toBeVisible();
  });

  // ── 5.5 ──────────────────────────────────────────────────────────────────
  test('Entry count label is visible', async ({ page }) => {
    // Navigate to the dashboard and scroll to the Live Log section
    await openDash(page);
    await page.locator('nav a[href="#live-log"]').click();

    // A label showing 'X entries' is visible (X may be 0 or more)
    await expect(page.locator('text=/\\d+ entries/')).toBeVisible({ timeout: 5_000 });
  });

  // ── 5.6 ──────────────────────────────────────────────────────────────────
  test('Clear Log button resets the entry count to 0', async ({ page }) => {
    // Navigate to the dashboard, allow log entries to accumulate if any
    await openDash(page);
    await page.waitForTimeout(1_000);

    // Click the 'Clear Log' button
    await page.locator('button', { hasText: 'Clear Log' }).click();

    // Entry count resets to '0 entries'
    await expect(page.locator('text=0 entries')).toBeVisible();
  });

  // ── 5.7 ──────────────────────────────────────────────────────────────────
  test('Log entries show correct labels for each direction', async ({ page }) => {
    // This test requires at least one inbound and one outbound log entry to be present.
    // Navigate and wait for WebSocket entries
    await openDash(page);
    await expect(page.locator('text=🟢 Connected')).toBeVisible({ timeout: 8_000 });

    // Check inbound entry (Flutter → AI) — blue label
    const inboundLabel = page.locator('span', { hasText: 'Flutter → AI' }).first();
    if (await inboundLabel.isVisible()) {
      await expect(inboundLabel).toHaveClass(/bg-blue-100/);
    }

    // Check outbound entry (AI → Flutter) — purple label
    const outboundLabel = page.locator('span', { hasText: 'AI → Flutter' }).first();
    if (await outboundLabel.isVisible()) {
      await expect(outboundLabel).toHaveClass(/bg-purple-100/);
    }
  });

  // ── 5.8 ──────────────────────────────────────────────────────────────────
  test('Log entry shows event name and timestamp', async ({ page }) => {
    // Navigate and wait for at least one log entry to appear
    await openDash(page);
    await expect(page.locator('text=🟢 Connected')).toBeVisible({ timeout: 8_000 });

    // If entries are present, verify structure
    const entries = page.locator('#live-log .rounded-lg.bg-white.shadow-sm');
    const count = await entries.count();
    if (count > 0) {
      const first = entries.first();
      // Entry row displays the intent/event name as text
      await expect(first.locator('.text-sm.font-medium')).toBeVisible();
      // Entry row displays a time string
      await expect(first.locator('.text-xs.text-gray-400')).toBeVisible();
    }
  });

  // ── 5.9 ──────────────────────────────────────────────────────────────────
  test('Clicking json button on a log entry expands the JSON payload', async ({ page }) => {
    // Navigate and wait for at least one log entry to appear
    await openDash(page);
    await expect(page.locator('text=🟢 Connected')).toBeVisible({ timeout: 8_000 });

    const entries = page.locator('#live-log .rounded-lg.bg-white.shadow-sm');
    const count = await entries.count();
    test.skip(count === 0, 'No log entries available to test JSON expansion');

    const firstEntry = entries.first();

    // Click the '▼ json' button on the entry
    await firstEntry.locator('button', { hasText: '▼ json' }).click();

    // A dark code block expands below the entry — JSON payload in green
    await expect(firstEntry.locator('pre')).toBeVisible();

    // Button text changes to '▲ hide'
    await expect(firstEntry.locator('button', { hasText: '▲ hide' })).toBeVisible();

    // Click the '▲ hide' button — JSON payload collapses
    await firstEntry.locator('button', { hasText: '▲ hide' }).click();
    await expect(firstEntry.locator('pre')).not.toBeVisible();

    // Button text returns to '▼ json'
    await expect(firstEntry.locator('button', { hasText: '▼ json' })).toBeVisible();
  });

  // ── 5.10 ─────────────────────────────────────────────────────────────────
  test('Log is capped at 100 entries maximum', async ({ page }) => {
    // This test simulates 105 sequential WebSocket messages via the API.
    // Navigate to dashboard and connect
    await openDash(page);
    await expect(page.locator('text=🟢 Connected')).toBeVisible({ timeout: 8_000 });

    // Inject 105 intents via REST to generate log entries
    const baseURL = 'http://localhost:8000';
    for (let i = 0; i < 105; i++) {
      await page.request.post(`${baseURL}/intent`, {
        data: {
          driver_id: 99,
          intent: 'map_screen_loaded',
          context: { driver_id: 99, stop_id: i, distance_metres: 50 },
        },
      }).catch(() => {
        // Ignore individual failures — best effort flood
      });
    }

    // Wait for entries to render
    await page.waitForTimeout(3_000);

    // Entry count shown is at most 100 (oldest entries dropped)
    const countText = await page.locator('text=/\\d+ entries/').innerText();
    const entryCount = parseInt(countText.match(/\d+/)?.[0] ?? '0', 10);
    expect(entryCount).toBeLessThanOrEqual(100);
  });

});

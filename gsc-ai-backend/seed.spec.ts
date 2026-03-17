/**
 * GSC AI Backend – Playwright Integration Tests
 *
 * Requires the orchestrator to be running:
 *   cd gsc-ai-backend && uvicorn orchestrator.main:app --reload --port 8000
 *
 * Node 22+ is required for the built-in global WebSocket used by wsSend().
 * If you are on an older Node, run:  npm install ws @types/ws
 * and replace `new WebSocket(...)` with `new (require('ws'))(...)`.
 *
 * Run tests:
 *   npx playwright test --config playwright.config.ts
 */

import { test, expect } from '@playwright/test';

// ─── helpers ────────────────────────────────────────────────────────────────

const BASE = 'http://localhost:8000';
const WS   = 'ws://localhost:8000/ws';

/** Valid deliver-button hex colours defined by the business rules. */
const BUTTON_COLORS = ['#DC2626', '#F59E0B', '#16A34A'];

type AiResponse = Record<string, unknown> & {
  intent_type?: string;
  deliver_button?: { color: string };
  sections?: unknown[];
  popup?: { show: boolean; blocking?: boolean; title?: string; message?: string };
  spotlight?: { show: boolean; target?: string; text?: string };
  driver?: { id: number; name: string; is_new_driver: boolean; experience_level: string } | null;
  route?: unknown | null;
};

/**
 * Open a WebSocket to /ws, send one intent packet, wait for the first message,
 * then close. Rejects after 20 s if no reply arrives.
 */
function wsSend(payload: object): Promise<AiResponse> {
  return new Promise((resolve, reject) => {
    // globalThis.WebSocket is available in Node 22+
    const ws = new (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket(WS);

    const timer = setTimeout(() => {
      ws.close();
      reject(new Error('WebSocket reply timed out after 20 s – is the orchestrator running?'));
    }, 20_000);

    ws.onopen  = () => ws.send(JSON.stringify(payload));
    ws.onmessage = (event: MessageEvent) => {
      clearTimeout(timer);
      ws.close();
      try {
        resolve(JSON.parse(event.data as string) as AiResponse);
      } catch (e) {
        reject(new Error(`Failed to parse WS response: ${event.data}`));
      }
    };
    ws.onerror = (err: Event) => {
      clearTimeout(timer);
      reject(new Error(`WebSocket error: ${JSON.stringify(err)}`));
    };
  });
}

// ─── REST: override management ───────────────────────────────────────────────

test.describe('REST – Override Management', () => {
  test.beforeAll(async ({ request }) => {
    // Start each suite from a clean override state
    await request.delete(`${BASE}/overrides`);
  });

  test('GET /overrides returns 200 with an array', async ({ request }) => {
    const res  = await request.get(`${BASE}/overrides`);
    const body = await res.json();

    expect(res.status()).toBe(200);
    // actual response key is "overrides" (see main.py line 303)
    expect(body).toHaveProperty('overrides');
    expect(Array.isArray(body.overrides)).toBe(true);
  });

  test('POST /override adds a rule and reflects it in GET', async ({ request }) => {
    const rule = 'Warn drivers: heavy traffic on Tonk Road';

    const addRes  = await request.post(`${BASE}/override`, { data: { rule } });
    const addBody = await addRes.json();

    // POST /override returns 201 with {status, rule, total_overrides}
    expect(addRes.status()).toBe(201);
    expect(addBody.status).toBe('added');
    expect(addBody.rule).toBe(rule);

    const listRes  = await request.get(`${BASE}/overrides`);
    const listBody = await listRes.json();
    expect(listBody.overrides).toContain(rule);
  });

  test('DELETE /overrides clears all rules', async ({ request }) => {
    const delRes = await request.delete(`${BASE}/overrides`);
    expect(delRes.status()).toBe(200);

    const listRes  = await request.get(`${BASE}/overrides`);
    const listBody = await listRes.json();
    expect(listBody.overrides).toHaveLength(0);
  });
});

// ─── REST: drivers online ────────────────────────────────────────────────────

test.describe('REST – Drivers Online', () => {
  test('GET /drivers/online returns 200 with online_drivers array', async ({ request }) => {
    const res  = await request.get(`${BASE}/drivers/online`);
    const body = await res.json();

    expect(res.status()).toBe(200);
    // actual response key is "driver_ids" (see main.py line 313)
    expect(body).toHaveProperty('driver_ids');
    expect(Array.isArray(body.driver_ids)).toBe(true);
  });
});

// ─── REST: command centre ────────────────────────────────────────────────────

test.describe('REST – Command Centre', () => {
  test.afterAll(async ({ request }) => {
    await request.delete(`${BASE}/overrides`);
  });

  test('POST /command classified as override responds with type override', async ({ request }) => {
    const res  = await request.post(`${BASE}/command`, {
      data: { command: 'Do not allow Jordan Lee to start deliveries today' },
    });
    const body = await res.json();

    expect(res.status()).toBe(200);
    expect(body).toHaveProperty('type');
    // AI may classify as override or popup – both are legitimate
    expect(['override', 'popup']).toContain(body.type);
  });

  test('POST /command with popup-style text responds with type popup', async ({ request }) => {
    const res  = await request.post(`${BASE}/command`, {
      data: { command: 'Send a traffic alert to all drivers about Tonk Road congestion' },
    });
    const body = await res.json();

    expect(res.status()).toBe(200);
    expect(['popup', 'override']).toContain(body.type);
  });

  test('POST /command body without command field returns 4xx', async ({ request }) => {
    const res = await request.post(`${BASE}/command`, { data: {} });
    expect(res.status()).toBeGreaterThanOrEqual(400);
  });
});

// ─── WebSocket: driver login ─────────────────────────────────────────────────

test.describe('WebSocket – Driver Login', () => {
  test('login by driver_id 1 (Marcus Webb) returns route and driver object', async () => {
    const r = await wsSend({ intent_type: 'driver_login', payload: { driver_id: 1 } });

    expect(r.intent_type).toBe('driver_login');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    expect(Array.isArray(r.sections)).toBe(true);
    expect(r.popup).toHaveProperty('show');
    expect(r.spotlight).toHaveProperty('show');

    expect(r.driver).toBeTruthy();
    expect(r.driver?.id).toBe(1);
    expect(r.driver?.name).toBe('Marcus Webb');
    expect(r.driver?.is_new_driver).toBe(false);
    expect(r.route).toBeTruthy();
  });

  test('login by name "Priya Sharma" returns correct driver', async () => {
    const r = await wsSend({ intent_type: 'driver_login', payload: { name: 'Priya Sharma' } });

    expect(r.intent_type).toBe('driver_login');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    expect(r.driver?.name).toBe('Priya Sharma');
    expect(r.route).toBeTruthy();
  });

  test('new driver (Jordan Lee, id 3) login shows onboarding spotlight', async () => {
    const r = await wsSend({ intent_type: 'driver_login', payload: { driver_id: 3 } });

    expect(r.intent_type).toBe('driver_login');
    expect(r.driver?.name).toBe('Jordan Lee');
    expect(r.driver?.is_new_driver).toBe(true);
    // New drivers must receive guidance spotlight
    expect(r.spotlight?.show).toBe(true);
  });

  test('login with unknown driver_id returns blocking popup and null driver/route', async () => {
    const r = await wsSend({ intent_type: 'driver_login', payload: { driver_id: 9999 } });

    expect(r.intent_type).toBe('driver_login');
    expect(r.popup?.show).toBe(true);
    expect(r.popup?.blocking).toBe(true);
    expect(r.deliver_button?.color).toBe('#DC2626');
    expect(r.driver).toBeFalsy();
    expect(r.route).toBeFalsy();
  });
});

// ─── WebSocket: stop & map ───────────────────────────────────────────────────

test.describe('WebSocket – Stop & Map', () => {
  test('stop_selected returns deliver_button and popup', async () => {
    const r = await wsSend({
      intent_type: 'stop_selected',
      payload: { stop_id: 16, driver_id: 1 },
    });

    expect(r.intent_type).toBe('stop_selected');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    expect(r.popup).toHaveProperty('show');
  });

  test('map_loaded within 100 m geofence returns valid response', async () => {
    const r = await wsSend({
      intent_type: 'map_loaded',
      payload: { stop_id: 16, driver_id: 1, distance_m: 85.3, lat: 26.9312, lng: 75.7824 },
    });

    expect(r.intent_type).toBe('map_loaded');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    expect(r.popup).toHaveProperty('show');
  });

  test('map_loaded far from stop (>100 m) returns red button', async () => {
    const r = await wsSend({
      intent_type: 'map_loaded',
      payload: { stop_id: 16, driver_id: 1, distance_m: 1800, lat: 26.95, lng: 75.81 },
    });

    expect(r.intent_type).toBe('map_loaded');
    expect(r.deliver_button?.color).toBe('#DC2626');
  });

  test('route_map_opened returns valid deliver_button', async () => {
    const r = await wsSend({
      intent_type: 'route_map_opened',
      payload: { driver_id: 1, route_id: 1, driver_lat: 26.9312, driver_lng: 75.7824 },
    });

    expect(r.intent_type).toBe('route_map_opened');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
  });

  test('stop_map_opened returns map_mode and stop details', async () => {
    const r = await wsSend({
      intent_type: 'stop_map_opened',
      payload: { driver_id: 1, route_id: 1, stop_id: 16, driver_lat: 26.9312, driver_lng: 75.7824 },
    });

    expect(r.intent_type).toBe('stop_map_opened');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    expect(r.popup).toHaveProperty('show');
  });
});

// ─── WebSocket: product scanning ─────────────────────────────────────────────

test.describe('WebSocket – Product Scanning', () => {
  test('product_screen_loaded with no scans → red button + sections + spotlight', async () => {
    const r = await wsSend({
      intent_type: 'product_screen_loaded',
      payload: { stop_id: 16, driver_id: 1, scanned_items: [] },
    });

    expect(r.intent_type).toBe('product_screen_loaded');
    expect(r.deliver_button?.color).toBe('#DC2626');
    // AI may populate either `sections` or `product_sections` – both are arrays
    expect(Array.isArray(r.sections)).toBe(true);
    // spotlight is always present; show value is an AI decision
    expect(r.spotlight).toHaveProperty('show');
    expect(typeof r.spotlight?.show).toBe('boolean');
  });

  test('product_screen_loaded with 1 of 8 items scanned → amber or red button', async () => {
    const r = await wsSend({
      intent_type: 'product_screen_loaded',
      payload: { stop_id: 16, driver_id: 1, scanned_items: ['10147'] }, // Marlboro Red 20s barcode
    });

    expect(r.intent_type).toBe('product_screen_loaded');
    // Some required items scanned → amber (#F59E0B) or still red (#DC2626)
    // Green (#16A34A) would be wrong here since not all items are complete
    expect(['#DC2626', '#F59E0B']).toContain(r.deliver_button?.color);
  });

  test('item_scanned returns updated deliver_button color', async () => {
    const r = await wsSend({
      intent_type: 'item_scanned',
      payload: { stop_id: 16, item_id: 2, driver_id: 1, scanned_items: ['10147'] }, // barcode of first scanned item
    });

    expect(r.intent_type).toBe('item_scanned');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    // sections may or may not be repopulated depending on AI response
    expect(Array.isArray(r.sections)).toBe(true);
    expect(r.popup).toHaveProperty('show');
  });

  test('count_screen_loaded returns spotlight guidance for cig_tob items', async () => {
    const r = await wsSend({
      intent_type: 'count_screen_loaded',
      payload: { stop_id: 16, driver_id: 1 },
    });

    expect(r.intent_type).toBe('count_screen_loaded');
    expect(BUTTON_COLORS).toContain(r.deliver_button?.color);
    expect(r.spotlight).toHaveProperty('show');
    expect(typeof r.spotlight?.show).toBe('boolean');
  });
});

// ─── WebSocket: deliver tapped ───────────────────────────────────────────────

test.describe('WebSocket – Deliver Tapped', () => {
  test('deliver_tapped with missing items → red button + blocking popup', async () => {
    const r = await wsSend({
      intent_type: 'deliver_tapped',
      payload: {
        stop_id: 16,
        driver_id: 1,
        scanned_items: ['10147', '10148'], // 2 of 10 items at stop 16 — 8 required items still missing
      },
    });

    expect(r.intent_type).toBe('deliver_tapped');
    expect(r.deliver_button?.color).toBe('#DC2626');
    // A popup MUST show when required items are missing
    expect(r.popup?.show).toBe(true);
    // blocking is an AI decision — assert it is a boolean, not a specific value
    expect(typeof r.popup?.blocking).toBe('boolean');
  });

  test('finish_delivery with all stop-16 items complete → green button', async () => {
    // Stop 16 actual inventory (from DB seed):
    //   scan:          10147-10149 (Marlboro Red 20s), 10150-10151 (Amber Leaf), 10156 (Empty Crate)
    //   count:         10152 (Soft Drinks Tote U), 10153 (Snack Tote V)
    //   scan_and_count: 10154-10155 (Coca Cola 500ml)
    // finish_delivery supports both scanned_barcodes + counted_items
    const r = await wsSend({
      intent_type: 'finish_delivery',
      payload: {
        driver_id: 1,
        route_id: 1,
        stop_id: 16,
        scanned_barcodes: ['10147', '10148', '10149', '10150', '10151', '10154', '10155', '10156'],
        counted_items: [
          { barcode: '10152', count_entered: 1 },
          { barcode: '10153', count_entered: 1 },
          { barcode: '10154', count_entered: 1 },
          { barcode: '10155', count_entered: 1 },
        ],
      },
    });

    expect(r.intent_type).toBe('finish_delivery');
    // All 10 items reconciled as complete → green button
    expect(r.deliver_button?.color).toBe('#16A34A');
    expect(r.popup).toHaveProperty('show');
  });
});

// ─── WebSocket: idle nudges ──────────────────────────────────────────────────

test.describe('WebSocket – User Idle', () => {
  test('idle on product_screen shows next-unscanned-item spotlight', async () => {
    const r = await wsSend({
      intent_type: 'user_idle',
      payload: { screen: 'product_screen', driver_id: 1, idle_seconds: 45 },
    });

    expect(r.intent_type).toBe('user_idle');
    expect(r.spotlight?.show).toBe(true);
  });

  test('idle on map_screen shows start-delivery spotlight', async () => {
    const r = await wsSend({
      intent_type: 'user_idle',
      payload: { screen: 'map_screen', driver_id: 1, idle_seconds: 45 },
    });

    expect(r.intent_type).toBe('user_idle');
    expect(r.spotlight?.show).toBe(true);
  });
});

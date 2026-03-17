import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: ['seed.spec.ts', 'specs/**/*.spec.ts'],

  // 30 s per test — each WebSocket intent makes an OpenAI GPT-4o call
  timeout: 30_000,

  // Run tests serially so WebSocket state and overrides don't clash
  workers: 1,

  use: {
    baseURL: 'http://localhost:8000',
    extraHTTPHeaders: { 'Content-Type': 'application/json' },
    headless: false,
  },

  reporter: [['list'], ['html', { open: 'always' }]],

  // Auto-start the Vite dashboard dev server before UI tests.
  // reuseExistingServer: true means it won't restart if you already have it running.
  webServer: {
    command: 'npm --prefix dashboard run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});

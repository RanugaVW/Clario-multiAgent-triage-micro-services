import { defineConfig, devices } from '@playwright/test';

/**
 * Real-browser E2E suite for Clario's frontend (Testing/03-UI-E2E-Testing).
 * Runs against the already-running dev server (npm run dev on :3000) and the
 * already-running clario-ml-sidecar (:8600) + api-gateway (:8080) + Supabase
 * project - no mocking. See e2e/global-setup.ts for the disposable test
 * users this suite creates and cleans up.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 15_000 },
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  reporter: [
    ['list'],
    ['html', { outputFolder: 'e2e-report', open: 'never' }],
    ['json', { outputFile: 'e2e-results.json' }],
  ],
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'on',
    trace: 'retain-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});

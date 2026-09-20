import { test, expect } from '@playwright/test';
import { loadFixtures, loginViaUi } from './helpers';

/**
 * §3.1.3 User Interface Testing (sample plan) — login form submission,
 * routing, and access control. Runs against the real /login page, the real
 * Supabase auth backend, and the real customer test user created in
 * global-setup.ts.
 */

test('unauthenticated visitor to /dashboard is redirected to /login', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
});

test('unauthenticated visitor to /agent is redirected to /login', async ({ page }) => {
  // Regression check: this route's redirect was previously commented out
  // (found by Testing/13-Accessibility-Testing, fixed 2026-09-13 - see
  // Testing/05-Security-Access-Control-Testing) so /agent and its ticket
  // queue were reachable without authenticating at all.
  await page.goto('/agent');
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
});

test('login with wrong password shows a real error and does not navigate away', async ({ page }) => {
  const { customer } = loadFixtures();
  await page.goto('/login');
  await page.getByLabel('Email address').fill(customer.email);
  await page.getByLabel('Password', { exact: true }).fill('definitely-the-wrong-password');
  await page.getByRole('button', { name: 'Sign In' }).click();

  await expect(page.getByText(/invalid/i)).toBeVisible({ timeout: 15_000 });
  await expect(page).toHaveURL(/\/login/);
});

test('login with valid customer credentials redirects to /dashboard and shows the account email', async ({ page }) => {
  const { customer } = loadFixtures();
  await loginViaUi(page, customer.email, customer.password, /\/dashboard/);
  await expect(page.getByText(customer.email)).toBeVisible();
});

test('login with valid admin credentials redirects straight to /admin', async ({ page }) => {
  const { admin } = loadFixtures();
  await loginViaUi(page, admin.email, admin.password, /\/admin/);
});

test('sign out clears the session and a protected route bounces back to /login', async ({ page }) => {
  const { customer } = loadFixtures();
  await loginViaUi(page, customer.email, customer.password, /\/dashboard/);

  await page.getByRole('button', { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });

  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
});

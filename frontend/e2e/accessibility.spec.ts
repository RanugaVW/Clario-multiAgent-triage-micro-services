import { test, expect, Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdirSync, writeFileSync } from 'fs';
import path from 'path';
import { loadFixtures, loginViaUi } from './helpers';

/**
 * Testing/13-Accessibility-Testing — WCAG 2.1 A/AA automated scan of every
 * real page in the frontend, via axe-core (the same rule engine behind axe
 * DevTools and Lighthouse's own accessibility category), run against the
 * live dev server + real Supabase-authenticated sessions (no mocking),
 * reusing the auth fixtures from global-setup.ts.
 */

const RESULTS_DIR = path.join(__dirname, 'a11y-results');
mkdirSync(RESULTS_DIR, { recursive: true });

async function scan(page: Page, name: string) {
  // Let async data loads and route transitions settle before scanning -
  // otherwise axe can sample the DOM mid-render and report a text/background
  // pair that never exists in the page's resting state as a false
  // "color-contrast" violation. (Kept as a fixed wait; not proven removable.)
  await page.waitForTimeout(1000);

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  writeFileSync(
    path.join(RESULTS_DIR, `${name}.json`),
    JSON.stringify(results, null, 2),
  );
  await test.info().attach(`axe-${name}`, {
    body: JSON.stringify(results.violations, null, 2),
    contentType: 'application/json',
  });

  return results;
}

test('login page has no WCAG 2.1 A/AA violations', async ({ page }) => {
  await page.goto('/login');
  const results = await scan(page, 'login');
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test('register page has no WCAG 2.1 A/AA violations', async ({ page }) => {
  await page.goto('/register');
  const results = await scan(page, 'register');
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test('customer dashboard (authenticated) has no WCAG 2.1 A/AA violations', async ({ page }) => {
  const { customer } = loadFixtures();
  await loginViaUi(page, customer.email, customer.password, /\/dashboard/);
  const results = await scan(page, 'dashboard');
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test('admin console (authenticated) has no WCAG 2.1 A/AA violations', async ({ page }) => {
  const { admin } = loadFixtures();
  await loginViaUi(page, admin.email, admin.password, /\/admin/);
  const results = await scan(page, 'admin');
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

test('agent dashboard has no WCAG 2.1 A/AA violations', async ({ page }) => {
  // /agent now requires a real agent/admin session (fixed 2026-09-13 - see
  // Testing/05-Security-Access-Control-Testing) - the admin fixture is
  // reused here since admin is also an authorized role for this page.
  const { admin } = loadFixtures();
  await loginViaUi(page, admin.email, admin.password, /\/admin/);
  await page.goto('/agent');
  const results = await scan(page, 'agent');
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
});

/**
 * Keyboard-only navigation: axe can't verify tab order, visible focus, or
 * keyboard traps by itself (it checks DOM/ARIA structure, not runtime focus
 * behavior), so this is scripted separately rather than claimed as "covered
 * by axe". This substitutes for a manual JAWS/NVDA pass, which needs a
 * licensed screen reader this Linux environment doesn't have.
 */
test('login page is fully keyboard-operable with visible focus', async ({ page }) => {
  await page.goto('/login');

  const seen: string[] = [];
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press('Tab');
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      // nextjs-portal is the dev-server's own error-overlay indicator - it
      // doesn't exist in a production build, so it's not part of the page
      // under test.
      if (!el || el === document.body || el.tagName.toLowerCase() === 'nextjs-portal') return null;
      const style = getComputedStyle(el);
      return {
        tag: el.tagName,
        name: el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.textContent?.trim().slice(0, 30) || '',
        hasVisibleFocus: style.outlineStyle !== 'none' || style.boxShadow !== 'none',
      };
    });
    if (!info) continue;
    seen.push(info.tag);
    expect(info.hasVisibleFocus, `${info.tag} "${info.name}" has no visible focus indicator`).toBe(true);
  }

  expect(seen.length, 'Tab key never moved focus to any element').toBeGreaterThan(0);
});

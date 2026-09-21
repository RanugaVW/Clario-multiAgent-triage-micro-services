import { test, expect, Page, Locator } from '@playwright/test';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import path from 'path';
import { loadFixtures, loginViaUi } from './helpers';

/**
 * Testing/04-Performance-Load-Testing — answers a narrower question than
 * that phase's Stage B concurrent-load benchmark. Stage B (run_performance_tests.py)
 * measures *timing* under concurrent submission (does the worker queue
 * serialize?) by hitting the Java gateway's HTTP API directly with tokens
 * fetched from Supabase's auth endpoint - it never drives the real frontend
 * UI with two logged-in browser sessions, and it never checks whether the
 * two concurrent tickets' data ever cross.
 *
 * This test answers the data-isolation question instead: when two different
 * real, logged-in customers submit a ticket through the actual dashboard UI
 * at the exact same instant, does each ticket end up owned by the right
 * customer, and does each customer's "My Tickets" view ever show the
 * other's ticket? A race condition in request handling (e.g. a
 * shared/misattributed session, or a user_id resolved from the wrong
 * request) would show up here as cross-contaminated data, not as a latency
 * number.
 */

const CUSTOMER2_EMAIL = 'clario-concurrency-test-customer2@example.com';
const TEST_PASSWORD = 'ClarioE2E-Test-Pass-2026!';

let supabase: SupabaseClient;
let customer2: { id: string; email: string; password: string };
const createdTicketIds: string[] = [];

test.beforeAll(async () => {
  process.loadEnvFile(path.join(__dirname, '..', '.env.local'));
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  supabase = createClient(url, serviceRoleKey, { auth: { autoRefreshToken: false, persistSession: false } });

  const { data: existing } = await supabase.auth.admin.listUsers({ perPage: 1000 });
  for (const u of existing?.users ?? []) {
    if (u.email === CUSTOMER2_EMAIL) await supabase.auth.admin.deleteUser(u.id);
  }

  const { data, error } = await supabase.auth.admin.createUser({
    email: CUSTOMER2_EMAIL,
    password: TEST_PASSWORD,
    email_confirm: true,
  });
  if (error || !data.user) throw new Error(`Failed to create second disposable customer: ${error?.message}`);
  customer2 = { id: data.user.id, email: CUSTOMER2_EMAIL, password: TEST_PASSWORD };
});

test.afterAll(async () => {
  for (const id of createdTicketIds) {
    await supabase.from('tickets').delete().eq('id', id);
  }
  if (customer2) await supabase.auth.admin.deleteUser(customer2.id);
});

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * The expand/collapse control of a ticket row: a `<button aria-expanded>`
 * whose accessible name includes the 8-char id prefix and the issue snippet
 * (the run marker leads the ticket text). One ticket, one such button.
 */
function ticketRow(page: Page, marker: string): Locator {
  return page.getByRole('button', { name: new RegExp(escapeRegExp(marker), 'i') });
}

async function submitTicketConcurrently(page: Page, marker: string): Promise<string> {
  await page.locator('#ticket-text').fill(`${marker} My screen went blank after the last update, please help.`);
  await page.getByRole('button', { name: /submit ticket/i }).click();
  await expect(page.getByText('Ticket submitted successfully!')).toBeVisible({ timeout: 30_000 });
  const bodyText = await page.locator('body').innerText();
  const match = bodyText.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  expect(match, `a tracking id should be shown for ${marker}`).not.toBeNull();
  return match![0];
}

test('two different real customers submitting a ticket at the exact same instant never cross-contaminate data', async ({ browser }) => {
  const fixtures = loadFixtures();
  const markerA = `[CONC-A-${Date.now()}]`;
  const markerB = `[CONC-B-${Date.now()}]`;

  // Two fully independent browser contexts = two fully independent real
  // sessions, the same way two different people on two different computers
  // would hit the real system at the same time - not two tabs sharing one
  // session's cookies/localStorage.
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await loginViaUi(pageA, fixtures.customer.email, fixtures.customer.password, /\/dashboard/);
    await loginViaUi(pageB, customer2.email, customer2.password, /\/dashboard/);

    // The actual concurrency: both real submit requests fire in the same
    // instant, not one-after-the-other.
    const [trackingIdA, trackingIdB] = await Promise.all([
      submitTicketConcurrently(pageA, markerA),
      submitTicketConcurrently(pageB, markerB),
    ]);
    createdTicketIds.push(trackingIdA, trackingIdB);

    expect(trackingIdA, 'the two simultaneous submissions must not collide on the same id').not.toBe(trackingIdB);

    // Ground truth from the database, not the UI: each ticket's row must be
    // owned by the customer who actually submitted it.
    const { data: rows, error } = await supabase
      .from('tickets')
      .select('id,user_id,raw_text')
      .in('id', [trackingIdA, trackingIdB]);
    expect(error).toBeNull();
    const rowA = rows!.find(r => r.id === trackingIdA)!;
    const rowB = rows!.find(r => r.id === trackingIdB)!;
    expect(rowA.user_id, 'ticket A must be owned by customer A, not swapped with B').toBe(fixtures.customer.id);
    expect(rowB.user_id, 'ticket B must be owned by customer B, not swapped with A').toBe(customer2.id);
    expect(rowA.raw_text).toContain(markerA);
    expect(rowB.raw_text).toContain(markerB);

    // UI-level isolation: each customer's own "My Tickets" view must show
    // their ticket and must never show the other customer's.
    await pageA.getByRole('button', { name: /view my tickets/i }).click();
    await expect(ticketRow(pageA, markerA)).toBeVisible({ timeout: 15_000 });
    await expect(ticketRow(pageA, markerB)).toHaveCount(0);

    await pageB.getByRole('button', { name: /view my tickets/i }).click();
    await expect(ticketRow(pageB, markerB)).toBeVisible({ timeout: 15_000 });
    await expect(ticketRow(pageB, markerA)).toHaveCount(0);
  } finally {
    await contextA.close();
    await contextB.close();
  }
});

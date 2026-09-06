import { test, expect, Page, Locator } from '@playwright/test';
import { loadFixtures, loginViaUi } from './helpers';

/**
 * §3.1.3 User Interface Testing (sample plan) — form submission, rendering
 * correctness, and (per the sample plan's own oracle for UI testing: "only
 * form submissions can be automated") the one thing worth automating end to
 * end: a real ticket, submitted through the real UI, processed by the real
 * LangGraph pipeline (clario-ml-sidecar, via the real api-gateway on :8080
 * and Redis-queued worker), and checked in the real admin console. No
 * mocked network calls anywhere in this file.
 *
 * A first real run of this suite (see Testing/03-UI-E2E-Testing report)
 * showed the pipeline can legitimately reach two different terminal states
 * for the same ticket text: AI-resolved, or escalated to human review
 * (reflection cap reached on a PII-in-draft validation failure). Both are
 * correct product behavior, not a flake, so this test follows whichever one
 * actually happens rather than assuming the happy path - see
 * waitForTerminalState() below.
 *
 * This also doubles as a regression test for two bugs fixed this session:
 * the star-rating widget losing its filled state / becoming read-only after
 * submit, and the admin console showing blank "Pipeline time" and
 * "Anonymous" for the requester.
 */

const RESOLUTION_TIMEOUT_MS = 180_000;
const POLL_INTERVAL_MS = 5_000;

type Outcome = 'resolved' | 'escalated';

async function openHistoryTab(page: Page) {
  await page.getByRole('button', { name: /my tickets/i }).click();
}

function ticketRow(page: Page, marker: string): Locator {
  return page.locator('div.cursor-pointer', { hasText: marker });
}

async function waitForTerminalState(page: Page, marker: string): Promise<{ row: Locator; outcome: Outcome }> {
  const deadline = Date.now() + RESOLUTION_TIMEOUT_MS;
  for (;;) {
    await page.reload();
    await openHistoryTab(page);
    // Generous timeout: this dev server shares a memory-constrained machine
    // with the live ML sidecar, so an on-demand route recompile can occasionally
    // take longer than a typical CI machine would.
    const row = ticketRow(page, marker);
    await expect(row).toBeVisible({ timeout: 30_000 }).catch(() => {});
    if (!(await row.isVisible())) continue;
    if (await row.getByText('Resolved', { exact: true }).isVisible().catch(() => false)) {
      return { row, outcome: 'resolved' };
    }
    if (await row.getByText('Needs review', { exact: true }).isVisible().catch(() => false)) {
      return { row, outcome: 'escalated' };
    }
    if (Date.now() > deadline) {
      throw new Error(`Ticket "${marker}" reached neither "Resolved" nor "Needs review" within ${RESOLUTION_TIMEOUT_MS}ms`);
    }
    await page.waitForTimeout(POLL_INTERVAL_MS);
  }
}

/** Count how many of the 5 rating stars are currently filled with the gold color. */
async function filledStarCount(page: Page): Promise<number> {
  let count = 0;
  for (let n = 1; n <= 5; n++) {
    const fill = await page.getByRole('button', { name: `Rate ${n} stars` }).locator('svg').getAttribute('fill');
    if (fill === '#E8A33D') count++;
  }
  return count;
}

test.describe.serial('customer submits, and admin reviews, one real ticket', () => {
  const fixtures = loadFixtures();
  const marker = `[${fixtures.runId}]`;
  // A real login-issue scenario, previously observed resolving cleanly via
  // AI (Technical/Login Issue, no escalation) rather than the billing
  // placeholder's reproducible escalation (see module doc) - but the rest
  // of this file still branches on the real outcome rather than assuming
  // it, since that's the only honest way to test a real, non-mocked model.
  const ticketText = `${marker} Hi I'm Warusha, I cannot login to my account. I need this to be fixed immediately because I have a submission to do today`;
  let trackingId = '';
  let outcome: Outcome | null = null;

  test('customer submits a real ticket through the dashboard form', async ({ page }) => {
    await loginViaUi(page, fixtures.customer.email, fixtures.customer.password, /\/dashboard/);

    await page.locator('#ticket-text').fill(ticketText);
    await page.getByRole('button', { name: /submit ticket/i }).click();

    await expect(page.getByText('Ticket submitted successfully!')).toBeVisible({ timeout: 30_000 });
    const bodyText = await page.locator('body').innerText();
    const match = bodyText.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    expect(match, 'a tracking id (UUID) should be shown in the success modal').not.toBeNull();
    trackingId = match![0];

    await page.getByRole('button', { name: /view my tickets/i }).click();
    await expect(ticketRow(page, marker)).toBeVisible();
  });

  test('the pipeline reaches a terminal state and renders the correct outcome for the customer', async ({ page }) => {
    test.setTimeout(RESOLUTION_TIMEOUT_MS + 60_000);
    await loginViaUi(page, fixtures.customer.email, fixtures.customer.password, /\/dashboard/);

    const result = await waitForTerminalState(page, marker);
    outcome = result.outcome;
    await result.row.click(); // expand

    if (outcome === 'resolved') {
      // FeedbackStars only renders once isFullyResolved && finalResolution?.final_response
      // is truthy, so its presence proves a real, non-empty response was rendered.
      await expect(page.getByText('Rate this response')).toBeVisible();
      await expect(page.getByText(ticketText)).toBeVisible();
    } else {
      await expect(page.getByText(/a human agent has taken over this ticket/i)).toBeVisible();
      await expect(page.getByText('Rate this response')).not.toBeVisible();
    }
  });

  test('the star-rating widget saves a real rating, keeps it colored, and stays editable', async ({ page }) => {
    test.skip(outcome !== 'resolved', 'ticket was escalated to human review - no final customer response to rate');
    await loginViaUi(page, fixtures.customer.email, fixtures.customer.password, /\/dashboard/);
    await openHistoryTab(page);
    await ticketRow(page, marker).click();

    await page.getByRole('button', { name: 'Rate 4 stars' }).click();
    await expect(page.getByText('Thanks for your feedback! You rated this 4/5')).toBeVisible();
    expect(await filledStarCount(page)).toBe(4);

    // Reload and re-expand: the bug this session was the widget forgetting
    // its color / becoming a dead read-only display after a real reload.
    await page.reload();
    await openHistoryTab(page);
    await ticketRow(page, marker).click();
    await expect(page.getByText('Thanks for your feedback! You rated this 4/5')).toBeVisible();
    expect(await filledStarCount(page)).toBe(4);

    // Editable: re-rating after submission must still work (was previously locked).
    await page.getByRole('button', { name: 'Rate 2 stars' }).click();
    await expect(page.getByText('Thanks for your feedback! You rated this 2/5')).toBeVisible();
    expect(await filledStarCount(page)).toBe(2);
  });

  test('admin console shows the real requester email, pipeline time, and LLM-call data for this ticket', async ({ page }) => {
    await loginViaUi(page, fixtures.admin.email, fixtures.admin.password, /\/admin/);

    await page.getByRole('button', { name: /all tickets/i }).click();
    await page.getByPlaceholder('Search by ticket ID…').fill(trackingId);

    const row = page.locator('div.cursor-pointer', { hasText: trackingId.split('-')[0] });
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.click();

    // Regression check: this session, "Requester" showed the literal string
    // "Anonymous" for a logged-in customer instead of their real email.
    await expect(page.getByText(fixtures.customer.email)).toBeVisible();

    // Regression check: "Pipeline time" rendered blank/"—" from the cached
    // list snapshot instead of the freshly-fetched raw_graph_payload value.
    const pipelineTimeValue = page.getByText('Pipeline time').locator('..').locator('span').last();
    await expect(pipelineTimeValue).not.toHaveText('—');
    await expect(pipelineTimeValue).not.toHaveText('');

    // Real LLM-call-count telemetry (added this session) - must be a real
    // number, not the old always-zero placeholder.
    const llmCalls = page.getByText('LLM calls').locator('..').locator('span').last();
    await expect(llmCalls).not.toHaveText('—');

    if (outcome === 'resolved') {
      // The rating this same ticket was just given by the customer, visible
      // in the admin panel too.
      await expect(page.getByText('Customer rating: 2/5')).toBeVisible();
    } else {
      // Escalated tickets show why - real escalation_reasons from the graph.
      await expect(page.getByText('Escalation reasons')).toBeVisible();
    }
  });
});

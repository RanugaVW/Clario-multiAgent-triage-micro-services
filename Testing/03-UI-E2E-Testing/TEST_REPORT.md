# UI / End-to-End Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `real-response-dataset`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `next dev` server (`:3000`), the live Spring Boot API gateway (`:8080`, routes `/api/tickets` → JPA insert + Redis dispatch), and the live, already-running `clario-ml-sidecar` worker (Redis-queue consumer, real Gemini API calls for drafting/classification). There is no separate test/staging environment for this system — every result below is from the real, single production deployment.

**Final result: 9/9 automated checks passed, 0 skipped, 0 failed.**
Two real bugs were found by this phase's own earlier runs, root-caused,
fixed, and re-verified live in this same final run: a production RLS
policy gap that silently broke the "Requester" fix from earlier this
session (§4), and a PostgREST relationship-shape bug that meant a
customer's star rating never loaded back after a page reload (§5). A
third, reproducible pipeline behavior (real ticket-text-dependent
escalation) is documented in §6 so it isn't mistaken for a bug.

## 1. Scope

This phase corresponds to §3.1.3 ("User Interface Testing") of the
reference Master Test Plan. The sample plan's own tooling recommendation
(Selenium IDE against a legacy PHP/Symfony app) doesn't apply to this
Next.js app; the direct equivalent used here is **Playwright**, driving a
real headless Chromium browser against the live, unmodified app — no
mocked network calls, no stubbed components, anywhere in this suite.

Per the sample plan's own oracle for this section: *"Only form submissions
can be automated... other testing cannot be automated because the user
behaves differently."* This suite automates exactly that: real login-form
submission, a real ticket-submission form, and the one real feedback form
in the app (the star-rating widget) — end to end, through the real
pipeline, checked in both the customer dashboard and the admin console.

**Covered:**
- Login: invalid credentials, valid customer login, valid admin login, logout, and route protection (`e2e/auth.spec.ts`, 5 checks)
- A real support ticket, submitted through the dashboard form, processed by the real LangGraph pipeline, and its outcome rendered correctly for the customer (`e2e/ticket-lifecycle.spec.ts`, 4 checks)
- The customer feedback star-rating widget: saves, stays colored, and stays editable after a reload
- The admin console: ticket search, and rendering of Requester email, Pipeline time, LLM-call count, and Customer rating for a real ticket

**Not covered** (per the sample plan's own oracle — genuinely not
automatable, or out of scope for this phase): visual/spelling QA, other
browsers/viewports, and performance/load characteristics of the UI itself
(Phase 04).

## 2. Environment & Tooling

| | |
|---|---|
| Test framework | Playwright `@playwright/test` 1.62.1 |
| Browser | Chromium 151.0.7922.34 (headless) |
| Node | v24.14.0 |
| Frontend | `next dev` on `:3000` (already running, reused — not started fresh by the suite) |
| Backend chain exercised | Browser → Next.js API routes → Spring Boot `api-gateway`/`clario-app` (`:8080`) → Redis (`ticket_queue`) → `clario-ml-sidecar` worker → Supabase (Postgres + RLS) |
| Test data | Two disposable, real Supabase auth users created fresh per run (`clario-e2e-customer@example.com`, `clario-e2e-admin@example.com`, via `auth.admin.createUser` with the service-role key) and deleted again afterward, along with any tickets they created (`e2e/global-setup.ts` / `global-teardown.ts`) |
| Retries | 0 — a pass is a real pass, not a retry hiding a flake |

New test files (`clario/frontend/e2e/`, none existed before this phase):
`playwright.config.ts`, `global-setup.ts`, `global-teardown.ts`,
`helpers.ts`, `auth.spec.ts`, `ticket-lifecycle.spec.ts`. Run via
`npm run test:e2e` (added to `frontend/package.json`).

## 3. Why real disposable accounts instead of mocks or a shared test user

The sample plan's own success criteria for UI testing ("submitting forms
should work as expected without errors", checked against the real
database) only means something if the form submission is real. Two fresh
Supabase auth users are created per run with the service-role key
(`email_confirm: true`, no inbox ever touched), one promoted to `role:
'admin'` directly in `public.users`. Both — and every ticket they create —
are deleted again in `global-teardown.ts`. This is the same
disposable-fixture pattern Phase 02 used for its test tickets, applied to
whole user accounts since this phase drives real login.

## 4. Finding #1 — a real RLS policy gap silently broke this session's earlier "Requester: Anonymous" fix

**How it was found:** the first real run of `ticket-lifecycle.spec.ts`
failed at the admin-console check — the DOM literally rendered `Requester
Anonymous` for a ticket submitted by a logged-in, known customer. This is
the exact bug fixed earlier this session (`admin/page.tsx`'s
`fullData?.users?.email` fallback via a `users:user_id(email)` embedded
join). The fix's *code* was correct; the fix didn't work in production.

**Root cause, confirmed by direct reproduction against the live database**
(not guessed — see the exact commands below):

1. Signed in as the real admin test account and queried PostgREST directly
   for the ticket: `users` in the embed came back `null`, not an error —
   classic Postgres RLS silently filtering a joined row the caller can't
   `SELECT`.
2. Same admin session, direct `SELECT` on `public.users` for the
   customer's row (no join): `[]` — confirmed the block is on
   `public.users`, not the ticket/join logic.
3. Connected to the live Postgres instance directly (`psql`) and read the
   **actual deployed** RLS policy on `public.users`:
   ```
   polname                | using_expr
   "Users can view own row" | (auth.uid() = id)
   ```
   There is no admin/agent clause in the live policy — only self-view. The
   broader policy documented in this repo's `supabase_schema.sql`
   (`... OR role IN ('admin','agent')`) was **never actually applied to
   production**; that file is stale relative to the live database. This
   also explains why `get_my_role()` exists as a separate `SECURITY
   DEFINER` RPC in the first place — it was already a known workaround for
   this table's RLS being unable to safely self-reference (a raw subquery
   on `public.users` inside a policy on `public.users` risks recursion),
   but nobody had circled back to actually grant admins read access to
   *other* rows.

**Severity:** Medium — not a security hole (the gap is under-permissive,
not over-permissive: admins could see *less* than intended, never more),
but it silently degraded a feature this session had explicitly set out to
fix, and would have broken it again on the next similar fix without this
phase catching it live.

**Fix** (one statement, reuses the existing `get_my_role()` `SECURITY
DEFINER` function so it can't hit the same self-reference recursion issue,
applied by the user directly via the Supabase SQL editor since this
sandbox correctly refuses to run schema changes against production
unattended):
```sql
CREATE POLICY "Admins and agents can view any user" ON public.users
FOR SELECT USING (public.get_my_role() IN ('admin', 'agent'));
```

**Verified, twice, independently:** a direct REST re-check immediately
after the policy was applied (the same admin session's direct `SELECT` on
the customer's `public.users` row now returns the real row instead of
`[]`), and by the final clean E2E run (§7, test 9) — the real customer
email is visible in the admin console for a freshly submitted ticket.

## 5. Finding #2 — the customer's star rating never loaded back after a reload (PostgREST embed shape mismatch)

**How it was found:** re-running the suite with a different, non-escalating
ticket (see §6) exercised the star-rating widget for the first time in a
passing run. The *first* rating (click a star, see the confirmation
message) worked. The *second* check — reload the page, re-expand the same
ticket, confirm the rating is still shown as colored — failed: the widget
rendered as if never rated, with all 5 stars empty and no confirmation
text, even though the POST to `/api/customer_feedback` had returned `200`
moments earlier.

**Root cause, confirmed by direct reproduction, not guessed:**
`customer_feedback.ticket_id` carries a `UNIQUE` constraint (confirmed via
`psql \d public.customer_feedback`). PostgREST detects this and embeds
`customer_feedback` in a `tickets` select as a **to-one relation — a bare
object (or `null`), never an array** — confirmed directly:
```
GET /api/user_tickets?userId=<id>
→ ticket.customer_feedback = {"score": 4}     (an object, not [{"score": 4}])
```
Both `frontend/src/app/dashboard/page.tsx`
(`ticket.customer_feedback?.[0]?.score`) and
`frontend/src/app/admin/page.tsx`
(`(fullData?.customer_feedback || ticket.customer_feedback || [])[0]`)
were written assuming an array, per their TypeScript types
(`customer_feedback?: { score: number }[]`). Indexing `[0]` on a plain
object returns `undefined` in JavaScript, so `existingScore` was always
`null` on a fresh page load — the rating was correctly saved every time,
it just could never be displayed back.

This bug predates this phase; it was invisible to the existing vitest
unit test (`admin-feedback-badge.test.tsx`) because that test's own mock
data used the same (wrong) array shape as the buggy code, so the two
agreed with each other without either matching what Supabase actually
returns. It was also invisible to this phase's own earlier runs, because
the first ticket text used (§6) always escalated, so the star-rating test
never got far enough to exercise the reload path in a run that counted.

**Severity:** Medium/High for the feature itself (the customer-facing
rating widget silently forgot every rating on refresh — indistinguishable
from feedback never having been saved, from the customer's point of view),
though not data-destructive (the row was always correctly persisted).

**Fix:** changed both call sites and their types to treat
`customer_feedback` as `{ score: number } | null` directly, matching what
PostgREST actually returns for a uniquely-constrained FK:
- `dashboard/page.tsx`: `ticket.customer_feedback?.score ?? null`
- `admin/page.tsx`: `fullData?.customer_feedback || ticket.customer_feedback || null`

Also fixed the vitest mock in `admin-feedback-badge.test.tsx` to use the
real (object) shape instead of the array shape it was written against.

**Verified:** the final clean run (§7) exercises exactly this path —
rate a real ticket, `page.reload()`, re-expand, confirm the same rating is
still shown colored, then re-rate to confirm it stays editable — and it
passes, both in the customer dashboard and (via `Customer rating: 2/5`) in
the admin console.

## 6. A real, ticket-text-dependent pipeline behavior (not a bug)

Two different real ticket texts were used across this phase's runs, and
they behave differently — both legitimately, per the pipeline's own
design:

- *"Payment failed but the money was taken from my bank account."* (the
  dashboard's own pre-filled placeholder) reproducibly **escalated** to
  human review, across three independent runs. The billing agent's draft
  twice invents a customer name ("Hi Joseph...") not present anywhere in
  the ticket text, which trips the `pii_in_draft` validation rule;
  reflection cannot fix it within `MAX_REFLECTION_ATTEMPTS` (2), so the
  graph correctly escalates rather than sending a hallucinated name to the
  customer. Worth the team's attention independent of this test suite —
  possibly a look at why the billing agent invents a name for inputs
  containing none.
- *"Hi I'm Warusha, I cannot login to my account. I need this to be fixed
  immediately because I have a submission to do today"* (the final ticket
  text used, per instruction) **resolved** via AI every time it was run,
  in 10-20 seconds, with a real, on-topic Gemini-generated response.

Because the real, non-mocked classifier and validator can legitimately
route the same input either way, `ticket-lifecycle.spec.ts` waits for
*whichever* real terminal state occurs and asserts the correct UI for
either (`Resolved` → rating widget renders; `Needs review` → the "a human
agent has taken over" message renders and the rating test skips itself,
since there is no final response to rate). This also, incidentally, is
the first time the escalation path has been exercised against the live
system with real Supabase writes — Phase 02 had flagged this exact gap as
untested in its own
[§8 follow-ups](../02-Integration-Testing/INTEGRATION_TEST_REPORT.md#8-follow-ups-for-a-future-run).

## 7. Final clean run (2026-09-04T06:07 UTC)

Ticket text used: *"Hi I'm Warusha, I cannot login to my account. I need
this to be fixed immediately because I have a submission to do today"*
(real outcome: resolved via AI, Login Issue / High priority, in 10.6s).

| # | Test | Result | Notes |
|---|---|---|---|
| 1 | Unauthenticated visitor to `/dashboard` → redirected to `/login` | **PASS** | |
| 2 | Login, wrong password → real error shown, stays on `/login` | **PASS** | |
| 3 | Login, valid customer → `/dashboard`, account email shown | **PASS** | |
| 4 | Login, valid admin → straight to `/admin` | **PASS** | |
| 5 | Sign out → session cleared, protected route bounces to `/login` | **PASS** | |
| 6 | Customer submits a real ticket via the dashboard form | **PASS** | Real tracking ID (UUID) captured from the success modal |
| 7 | Pipeline reaches a terminal state, correct UI rendered | **PASS** | Real outcome: resolved — real Gemini-drafted response rendered, rating widget appears |
| 8 | Star-rating widget saves / persists / stays editable | **PASS** | Regression-verifies Finding #2's fix: rate 4★ → reload → still shows 4★ colored → re-rate to 2★ → updates live |
| 9 | Admin console: real Requester email, Pipeline time, LLM calls, Customer rating | **PASS** | Regression-verifies Finding #1's fix plus this session's earlier Pipeline-time and LLM-call-count fixes, live |

Raw console output: [`test-log.txt`](test-log.txt). Structured results:
[`e2e-results.json`](e2e-results.json). Screenshots (captured automatically
on every test, `screenshot: 'on'`): [`screenshots/`](screenshots/) —
`06-star-rating-widget.png` is the clearest single piece of evidence for
Finding #2's fix (2 gold stars, "Thanks for your feedback! You rated this
2/5", captured after the reload-and-re-rate sequence). The admin-console
screenshot is viewport-cropped above the Requester/Customer-rating fields
by the time the automatic screenshot fires; those exact fields are what
tests 9 asserts on and passed against, so the JSON result is the authoritative
evidence for that part, not the PNG.

Both disposable test accounts and the ticket they created were deleted by
`global-teardown.ts` at the end of this run — confirmed no `clario-e2e-*`
users remain in production afterward.

## 8. Follow-ups for a future run

- §6's model behavior (hallucinating a name into a billing draft on the
  placeholder ticket text) is worth a look independent of this test suite.
- An earlier run of this phase found that a live service restart mid-test
  can orphan an in-flight ticket forever: `app/worker.py`'s Redis
  consumption is a destructive `BRPOP` with no ack/requeue, so a worker
  killed after popping a message but before finishing loses that ticket
  permanently. Real backend reliability gap, outside this UI-testing
  phase's scope to fix.
- `supabase_schema.sql` is confirmed stale relative to the live database
  (§4) — worth regenerating it from the live project (e.g. `supabase db
  dump`) so it stops being a plausible but wrong source of truth for the
  next person who reads it.

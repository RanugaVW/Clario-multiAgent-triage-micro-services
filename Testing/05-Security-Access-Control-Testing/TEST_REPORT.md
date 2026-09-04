# Security & Access Control Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `main`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `next dev` server (`:3000`). There is no separate test/staging environment for this system — every result below is from the real, single production deployment, using disposable throwaway accounts created and destroyed by this phase's own script.

**Original result: 12/18 automated checks passed, 6 failed** — five of them (`B1`–`B5`) **critical/high-severity**: the Next.js API routes that back the admin console and dashboard (`/api/tickets` GET/PUT/DELETE, `/api/user_tickets` GET, `/api/customer_feedback` POST) performed **zero authentication** while using the Supabase **service-role key**, which bypasses Row Level Security entirely. Row Level Security itself (Section A) and the PII-redaction boundary (Section C) both held up under real adversarial testing from the start.

**All 6 findings have since been fixed and re-verified live: final result 23/23 automated checks passed, 0 failed.** See §9 for exactly what changed and the final clean run's evidence. The sections below are left as originally written (the initial run's findings) so the report shows the actual before/after, not a rewritten history.

## 1. Scope

This phase corresponds to §3.1.6 ("Security and Access Control Testing") of the reference Master Test Plan. Per this repo's own `Testing/05-Security-Access-Control-Testing/README.md`, three things were tested, each with real credentials/requests against the real system — no mocks, no assumed results:

- **A — Row Level Security:** do the Postgres RLS policies actually confine a customer to their own tickets/profile, and staff to all of it, when tested behaviorally with real JWTs (not just read from the schema file)?
- **B — Service-role Next.js API routes:** these routes (`frontend/src/app/api/tickets/route.ts`, `.../user_tickets/route.ts`, `.../customer_feedback/route.ts`) use `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS. Ownership must be enforced in application code instead — is it?
- **C — PII redaction boundary:** does raw customer text (`mask_pii` / `mask_pii_reversible`) ever reach the judge LLM or ChromaDB unredacted, including on the cache-hit path where `surrogate_node` is skipped?

**Not covered this phase** (out of scope per the README / left for a future run): the three Java services' (`api-gateway`, `ticket-core-service`, `agent-review-service`) own internal authorization logic beyond the gateway's JWT-validation config already read as part of this investigation; penetration testing of the Gemini/OpenAI/DeepSeek API key handling itself; rate-limiting / brute-force login protection.

## 2. Environment & Tooling

| | |
|---|---|
| Test script | `Testing/05-Security-Access-Control-Testing/run_security_tests.py` — real HTTP requests via `requests`, real Supabase auth via `supabase-py` 2.31.0 |
| Frontend under test | `next dev` on `:3000`, started fresh for this phase, Next.js 16.2.12 |
| Supabase | Production project `mdvfvtpbwqhccmaarpli`, both the PostgREST REST API (`/rest/v1/...`, real RLS enforcement) and GoTrue auth (real JWTs for real disposable accounts) |
| Test data | Two disposable customers, one disposable admin, one disposable "probe" customer (all `clario-sectest-*@example.com`, service-role-created via `auth.admin.createUser`, deleted again in `finally`/at the end), plus one disposable "canary" ticket tagged `SECURITY-TEST-CANARY-<run-id>` — the only ticket the destructive-write checks (`B3`, `B5`) were ever allowed to touch |
| Evidence for Section C | The existing `tests/tools/test_redaction_tool.py` + `tests/graph/test_response_judge_node.py` suite (14 tests, re-run fresh for this phase — see `pytest-redaction-evidence.txt`), plus one new adversarial multi-PII check run live |

Cleanup was verified after the run: zero leftover test-suite users, zero leftover canary tickets (`test-log.txt` §"Cleanup verification").

## 3. Why real disposable accounts and a real canary ticket, not mocks

The same reasoning as Phases 02–04: RLS is a Postgres-level guarantee that only means something when tested with a real signed JWT hitting the real PostgREST endpoint — a mocked Supabase client would just return whatever the mock was told to return, proving nothing. The one place this phase deliberately touches real production data read-only (Section B1, see below) is handled by counting/checking field presence in-process and never persisting the response, so this report never contains a real customer's PII.

## 4. Section A — Row Level Security: held up under real adversarial testing

Six behavioral checks against `public.tickets` and `public.users`, using real signed-in JWTs for two disposable customers and one disposable staff account, all passed:

| Check | Result |
|---|---|
| `A1` Customer B cannot `SELECT` customer A's ticket | **PASS** — 0 rows |
| `A2` Customer A CAN select their own ticket (positive control) | **PASS** — 1 row |
| `A3` Anonymous (anon key, no session) cannot `SELECT` any ticket | **PASS** — 0 rows |
| `A4` Staff (admin role) CAN select a ticket that isn't theirs (positive control) | **PASS** — 1 row |
| `A5` Customer B cannot `SELECT` customer A's `public.users` profile row | **PASS** — 0 rows |
| `A6` Customer B cannot `INSERT` a ticket with `user_id` spoofed to customer A | **PASS** — HTTP 403, `42501 new row violates row-level security policy` |

This is a genuine positive result, not an assumption — each row above is a real HTTP response from the live PostgREST endpoint, captured in `test-log.txt` and `security_test_results.json`.

### A finding along the way: `human_reviews` has an undocumented live policy (schema drift, not a vulnerability)

The initial hypothesis for `A7` — drawn from reading all three checked-in schema files — was that `public.human_reviews` has `ENABLE ROW LEVEL SECURITY` with **zero `CREATE POLICY`** defined anywhere in the repo, so it should fail closed for everyone, including staff. The real test falsified that: the disposable admin JWT got 5 real rows back.

Two follow-up probes (`A7b`, `A7c`) then confirmed this is *correctly* staff-only, not accidentally wide open:

- A freshly-created **non-staff** disposable customer JWT → `200`, **0 rows**.
- A **fully anonymous** request (anon key, no session at all) → `200`, **0 rows**.

**Conclusion:** a real staff-only policy for `human_reviews` exists in the live production database but is **not present in `supabase_schema.sql` / `supabase_response_validation_schema.sql` / `supabase_pairwise_feedback_schema.sql` anywhere in this repo** (`A7d`). This is the same class of drift Phase 03 found and fixed for `public.users`'s policy — it recurred here for a second table. It is not itself an access-control failure (access is correctly restricted), but it means running the repo's own schema files against a fresh database would silently leave `human_reviews` unreadable by anyone but the service-role key. **Recommendation:** pull the live policy definition (e.g. via the Supabase dashboard's policy editor, or `SELECT * FROM pg_policies WHERE tablename='human_reviews'` with direct DB access) and add it to `supabase_schema.sql` so the repo matches production.

## 5. Section B — Critical: the service-role Next.js API routes enforce no authentication at all

This is the significant finding of this phase. `frontend/src/app/api/tickets/route.ts`, `.../user_tickets/route.ts`, and `.../customer_feedback/route.ts` all build their Supabase client with `SUPABASE_SERVICE_ROLE_KEY` — the key that **bypasses RLS entirely** by design, so that the server can, e.g., let an admin view every customer's tickets. That's the correct tool for the job *if* the route itself checks who's asking. None of the three routes do:

- **No `middleware.ts` exists anywhere in `frontend/src`** (checked directly — there is none).
- Every route handler reads `request.json()` / query params and goes straight to a Supabase service-role query. None reads a session cookie, none verifies a `Authorization` bearer token, none calls `supabase.auth.getUser()`.
- Confirmed on the client side too: `admin/page.tsx`'s `fetchJson('/api/tickets')` and `dashboard/page.tsx`'s `fetchJson('/api/user_tickets?userId=${user.id}')` both send **no `Authorization` header** — there is nothing to check even if the server wanted to. (Contrast this with the *separate*, correctly-secured Java `api-gateway` on `:8080` that the dashboard's ticket-submission call does send a real Supabase JWT to, and whose `SecurityConfig.java` requires `anyRequest().authenticated()` with real JWKS/HS256 validation. That gateway is not on the path for any of the five routes tested here.)

Five real, unauthenticated HTTP requests against the live `:3000` server, with **zero** `Authorization` header, `apikey`, or cookie of any kind — exactly what a stranger typing the URL into a browser, or `curl`, would send:

| Check | Request | Result |
|---|---|---|
| `B1` | `GET /api/tickets` | **FAIL — critical.** `HTTP 200`, **27 tickets returned**, including this run's canary ticket. Per-row fields confirmed present: `raw_text` (the customer's **unredacted** original message) and `customer_email`. The full response body was never written to disk or printed — only the row count and field-presence booleans were kept, specifically so this report never contains real customers' PII. |
| `B2` | `GET /api/user_tickets?userId=<customer B's UUID>` | **FAIL — critical (IDOR).** `HTTP 200`. The only "credential" supplied was customer B's own user id — a UUID with no other secret attached to it — and the route returned their tickets with no check that the caller *is* customer B. |
| `B3` | `PUT /api/tickets` `{id: <canary>, final_response: "...forged..."}` | **FAIL — critical.** `HTTP 200 {"success":true}` — the canary ticket's status flipped to `resolved` and a forged resolution row was inserted, from an unauthenticated request. |
| `B4` | `POST /api/customer_feedback` `{ticketId: <canary>, userId: <customer A's UUID>, score: 1, comment: "...cross-account write..."}`, sent as if by an attacker who only learned A's UUID from `B2`'s style of leak | **FAIL — high.** `HTTP 200`. The route *does* check that `ticketId` belongs to `userId` (the one ownership check that exists in this code), but never checks that the HTTP request itself came from that user — so knowing any victim's `(userId, ticketId)` pair, both of which `B1`/`B2` prove are freely enumerable, is enough to write feedback as them. |
| `B5` | `DELETE /api/tickets?id=<canary>` | **FAIL — critical (destructive).** `HTTP 200`. Verified by a direct service-role re-query immediately after: the ticket, and (per the route's own cascade logic) its drafts/classifications/resolutions/human-review rows, were actually gone. |

Every one of these five requests was made with the literal Python `requests` library and no session — see `test-log.txt` for the exact sequence and `security_test_results.json` for the raw evidence strings. `B3` and `B5` only ever touched the disposable canary ticket created for this run; `B1` and `B2` are read-only and their evidence is deliberately summarized (counts/field-presence) rather than persisted, to avoid this report itself becoming a PII leak.

### Why this matters together with Section C

Section C (below) confirms the LLM/ChromaDB redaction boundary is implemented correctly. `B1` shows that protection almost doesn't matter for confidentiality purposes: the same raw, unredacted `raw_text` and `customer_email` that the pipeline is careful to redact before it ever reaches an LLM or the vector store is available in full to anyone who sends one unauthenticated `GET` to `/api/tickets`.

### Fix applied — see §9 for the final, re-verified state

This was fixed after the initial run documented here; the fix and its live re-verification are in §9. The design below is what was actually implemented.

```ts
// shared helper, used by every /api/... route in frontend/src/app/api/
async function requireUser(request: Request) {
  const authHeader = request.headers.get('authorization');
  const token = authHeader?.replace(/^Bearer\s+/i, '');
  if (!token) return null;
  const supabase = createSupabaseClient(SUPABASE_URL, SUPABASE_ANON_KEY); // anon key, not service role
  const { data, error } = await supabase.auth.getUser(token);
  return error ? null : data.user;
}
```

then, per route: `/api/user_tickets` and `/api/customer_feedback` ignore the client-supplied `userId` and use `user.id` from the verified token instead; `/api/tickets` GET/PUT/DELETE require the verified user's role to be `admin`/`agent` before proceeding (mirroring the RLS staff policy that already exists for direct table access). The frontend call sites now send `Authorization: Bearer <session.access_token>` on these calls, the same way the dashboard's gateway call already did. Full detail in §9.

## 6. Section C — PII redaction boundary: held up under adversarial testing

| Check | Result |
|---|---|
| `C1` `mask_pii()` on a realistic multi-PII ticket (name, email, phone, credit card, city, company) | **PASS** — all four sensitive values absent from the masked output; detected types: `credit_card, email, gpe, org, person, phone` |
| `C2` `mask_pii_reversible()` never gives phone/card numbers a reversible Faker stand-in (only `PERSON`/`EMAIL` may be — there's no legitimate reason a response would ever need to echo a phone or card number back) | **PASS** — no leaked raw phone/card value; shadow map only covered the name/email |
| `C3` Every `add_precedent()` call site (the only path that writes ticket text into ChromaDB) passes `redacted_text`, never `raw_text` | **PASS** — both call sites in `app/main.py:168,374` confirmed via source grep |

These three were backed by, and re-ran alongside, the existing 14-test `tests/tools/test_redaction_tool.py` + `tests/graph/test_response_judge_node.py` suite (`pytest-redaction-evidence.txt`, 14/14 passed), including the specific regression test for the cache-hit path named in this phase's own scope (`test_cache_hit_ticket_redacts_raw_text_before_judging`): when `surrogate_node` is skipped on a cache hit, `response_judge_node.py` explicitly re-redacts `raw_text` with `mask_pii()` before it's used for few-shot selection or judge scoring — confirmed by reading `app/graph/response_judge_node.py:27-31` and by that test asserting the judge receives the redacted (not raw) text.

**No PII-redaction defect was found.** The one place raw, unredacted ticket text is actually exposed is the `B1` authorization gap above — a separate, application-layer authorization bug, not a defect in the redaction logic itself.

## 7. Summary of findings (as of the original run)

| # | Area | Severity | Status |
|---|---|---|---|
| `B1` | `GET /api/tickets` — unauthenticated, dumps all tickets incl. raw PII | **Critical** | **Fixed — see §9** |
| `B2` | `GET /api/user_tickets` — IDOR via `userId` param | **Critical** | **Fixed — see §9** |
| `B3` | `PUT /api/tickets` — unauthenticated, forges any resolution | **Critical** | **Fixed — see §9** |
| `B5` | `DELETE /api/tickets` — unauthenticated, destructive | **Critical** | **Fixed — see §9** |
| `B4` | `POST /api/customer_feedback` — cross-account write via IDOR chain | **High** | **Fixed — see §9** |
| `A7d` | `human_reviews` live RLS policy missing from checked-in schema files | **Low** | **Fixed — see §9** |
| A1–A6, A7/A7b/A7c | RLS on `tickets`/`users`/`human_reviews` | — | **Verified correct**, no action needed |
| C1–C3 | PII redaction boundary (`mask_pii`, `mask_pii_reversible`, ChromaDB precedent writes) | — | **Verified correct**, no action needed |

## 8. Follow-ups for a future run

- Extend Section A to `customer_feedback` and `resolutions`/`ticket_classifications` tables directly (this run focused on `tickets`/`users`/`human_reviews`, the three tables the README called out).
- Cover the three Java services' own authorization logic (out of scope this run, noted §1).

## 9. Fix applied and re-verified live: 23/23 checks passed, 0 failed

All 6 findings above were fixed and the fix was verified with the exact same real, live methodology as the original run — real disposable Supabase accounts, real JWTs, real HTTP requests against a real `next dev` server, zero mocking.

### What changed

**New shared helper — `frontend/src/lib/apiAuth.ts`:** `requireUser(request)` reads the `Authorization: Bearer <token>` header, verifies it against Supabase Auth with an anon-key client (`supabase.auth.getUser(token)`), and resolves the caller's role via the same `get_my_role()` RPC `AuthContext.tsx` already uses client-side (`SECURITY DEFINER`, bypasses the `public.users` self-referential RLS recursion). Returns `null` for anything unverifiable. `isStaff(user)` checks `role in {admin, agent}`.

**`frontend/src/app/api/tickets/route.ts`** — `GET`/`PUT`/`DELETE` all now call a `requireStaff()` guard (`requireUser` + `isStaff`) before touching the service-role client: 401 with no/invalid token, 403 for a valid non-staff token.

**`frontend/src/app/api/user_tickets/route.ts`** — `GET` now calls `requireUser()` (401 if it fails), then requires `userId === caller.id` **unless** the caller is staff, in which case an arbitrary `userId` is still allowed (403 otherwise) — this mirrors the same staff-can-view-all-tickets boundary the `tickets` RLS policy already grants everywhere else, rather than inventing a new rule.

**`frontend/src/app/api/customer_feedback/route.ts`** — `POST` now calls `requireUser()` (401 if it fails) and the ownership check (`tickets.user_id = ?`) is run against the **verified caller's id**, never the client-supplied `userId` from the request body — a customer can only ever rate their own ticket, with no staff-on-behalf-of exception (feedback should always represent the real customer).

**Frontend call sites** (`admin/page.tsx`'s `authHeaders()` helper used by all 4 of its `/api/tickets` calls; `dashboard/page.tsx`'s `fetchHistory()` and `FeedbackStars.handleRate()`) now fetch `supabase.auth.getSession()` and attach `Authorization: Bearer <access_token>` — the same pattern the dashboard's ticket-submission call to the Java gateway already used.

**A latent testability bug found and fixed along the way:** `tickets/route.ts` and `user_tickets/route.ts` read `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` as **module-level constants**, evaluated at import time — before a test file's own `process.env.X = ...` lines run (`customer_feedback/route.ts` already avoided this, with a comment explaining exactly why). Since neither route had any tests before this phase, this was never exposed; adding real tests for the fix immediately surfaced it as spurious 500s. Fixed by reading both env vars lazily inside `createServiceClient()`, matching `customer_feedback/route.ts`'s existing pattern.

**`supabase_schema.sql`** — added the `human_reviews` staff-read policy that `A7`/`A7d` proved exists live but was undocumented in the repo (same schema-drift class Phase 03 found for `public.users`).

**New/updated tests** (`npm run test`: 108/108 passed, `npm run lint`: 0 errors, `npx tsc --noEmit`: 0 errors):
- `frontend/src/app/api/tickets/route.test.ts` (new) — 7 tests: 401/403 rejection for GET/PUT/DELETE, admin and agent roles both let through.
- `frontend/src/app/api/user_tickets/route.test.ts` (new) — 6 tests: 401 unauthenticated, 403 cross-user IDOR attempt, self-access and staff-access positive controls, 400 for missing `userId`.
- `frontend/src/app/api/customer_feedback/route.test.ts` (updated) — added 401 (no token / invalid token) cases and a test proving a spoofed `userId` in the body is ignored in favor of the verified caller's id.

### Live re-verification (real production Supabase, real `next dev` server)

Re-running `run_security_tests.py` (extended with `B6`–`B10`, `A7`–`A7d` **positive controls** that call the same five routes **with** a real, valid session — proving the fix doesn't just block everyone, legitimate staff/customer use still works) against the fixed code:

```
=== SUMMARY: 23/23 checks passed ===
```

| Check | Before fix | After fix |
|---|---|---|
| `B1` `GET /api/tickets`, no auth | FAIL — HTTP 200, 27 tickets leaked | **PASS** — HTTP 401, 0 tickets |
| `B2` `GET /api/user_tickets?userId=<victim>`, no auth | FAIL — HTTP 200, IDOR | **PASS** — HTTP 401 |
| `B3` `PUT /api/tickets`, no auth | FAIL — HTTP 200, resolution forged | **PASS** — HTTP 401 |
| `B4` `POST /api/customer_feedback`, no auth | FAIL — HTTP 200, cross-account write | **PASS** — HTTP 401 |
| `B5` `DELETE /api/tickets`, no auth | FAIL — HTTP 200, ticket actually deleted | **PASS** — HTTP 401, ticket still present |
| `B6`–`B10` same 5 routes, **with** a valid staff/customer session | *(not tested before fix)* | **PASS** — all 5 still work correctly for the legitimate caller |
| `A7d` `human_reviews` policy documented in `supabase_schema.sql` | FAIL — missing | **PASS** |

One real bug surfaced by this re-verification itself, not by manual review: the first fix attempt's test script reassigned `fixtures["canary_id"]` when creating the second (positive-control) canary ticket, which meant `teardown_fixtures` lost track of the *first* canary and leaked it — invisible before the fix because `B5`'s old (vulnerable) behavior deleted that ticket itself, so nothing was ever left over. Caught by an explicit leftover-data check after the run, root-caused, and fixed by tracking `canary_id`/`canary2_id` as two independent fixture keys, both cleaned up in `teardown_fixtures`. Verified clean on the next run (`test-log-after-fix.txt`): 0 leftover test users, 0 leftover canary tickets.

Every check's full evidence is in the current `security_test_results.json` (overwritten by the final run) and `test-log-after-fix.txt`.

# 05 — Security & Access Control Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md). Original run:
12/18 real checks passed, 6 real findings (5 critical/high) — the
service-role Next.js API routes (`/api/tickets` GET/PUT/DELETE,
`/api/user_tickets` GET, `/api/customer_feedback` POST) performed zero
authentication, letting an unauthenticated caller dump every customer's
tickets (including unredacted PII), forge resolutions, delete tickets, and
write feedback on another customer's behalf. **All 6 findings have since
been fixed and re-verified live: final result 23/23 checks passed, 0
failed** (see TEST_REPORT.md §9) — a shared `requireUser()` auth helper
(`frontend/src/lib/apiAuth.ts`) now gates all three routes, the frontend
sends real session tokens, and the missing `human_reviews` RLS policy was
added to `supabase_schema.sql`.

**Sample-plan equivalent:** §3.1.6 Security and Access Control Testing.

**Scope for Clario:** verify Supabase Row Level Security policies actually
restrict customers to their own tickets and staff/admin routes to staff
accounts; verify service-role API routes (e.g.
`frontend/src/app/api/customer_feedback/route.ts`, `user_tickets`) enforce
ownership in application code where RLS is bypassed by the service-role
client; verify PII redaction (`mask_pii` / `mask_pii_reversible`) never
leaks unredacted customer text to the judge LLM or ChromaDB, including on
the cache-hit path where `surrogate_node` is skipped.

Run via (from `clario-ml-sidecar/`, inside its `.venv`):
```
python ../Testing/05-Security-Access-Control-Testing/run_security_tests.py
```

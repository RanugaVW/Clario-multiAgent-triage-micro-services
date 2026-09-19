# FR-051 — Ticket Analytics (SRS §3.1.14)

**Status before:** 🔴 Not implemented — the admin page only counted whatever tickets its list happened to hold, with no server-side aggregation and no date range.
**Status after:** ✅ Administrators get an analytics report for a configurable date range: totals, lifecycle split, breakdowns and daily volume.
**Database changes:** none.

Acceptance criteria: *"Ticket statistics are accurate"* · *"Reports include configurable date ranges"*.

## What was built (`frontend`)

- **`src/lib/reports.ts`** — pure rules. `parseDateRange` (optional `YYYY-MM-DD` bounds, UTC days, inclusive; rejects malformed, impossible
  such as `2026-02-31` — which JS would silently roll into March — and reversed ranges). `ticketAnalytics`: total; resolved / awaiting-human / in-progress
  (always sum to the total); resolution rate (`null`, not `NaN`, when empty); breakdowns by category (a multi-category ticket counts once under each, same rule as
  the admin page), priority, sentiment, status; zero-filled daily volume.
- **`src/lib/reportData.ts`** — Supabase loader. **Paginates** (PostgREST returns at most 1000 rows per request; without paging the totals would silently
  truncate and still look plausible), pushes the date filter into the query, orders by `created_at, id` for stable paging, and fails the whole report if any page fails
  (never a partial report). 200k-row hard stop.
- **`GET /api/reports?from=&to=`** — **admin only** (401 no/invalid token, 403 agent/user; SRS actors are the administrator and AI-ops engineer, and this app has a single `admin` role for both).
- **`/admin/reports`** page + *Reports* link in the admin sidebar: from/to inputs (labelled), *Last 7 / 30 days / All time* presets, Apply, loading / error / empty states, client-side
  reversed-range guard, results kept visible (dimmed) while a new range loads.

## Tests

| File | Cases | Covers |
|---|---|---|
| `src/lib/reports.test.ts` | 14 | date parsing (valid, one-sided, malformed, impossible, reversed, single-day boundaries, labels), buckets sum to total, range applies to *every* figure, multi-category counting, missing values → "Unclassified", zero-filled days, empty input, status `resolved` without a resolution row, escalated-then-answered is not "awaiting" |
| `src/app/api/reports/route.test.ts` | 8 | 401, 403 ×2, 400 before any query, range pushed to DB, **2500 rows across 3 pages**, exact-multiple-of-page-size edge case, page error → 500 |
| `src/app/__tests__/admin-reports.test.tsx` | 10 | default 30-day query with token, figures, breakdown/daily table, Apply re-queries, All time sends no bounds, reversed range blocked without a request, empty period, server error, non-admin redirects ×3 |

**Mutation checks (reverted after each):** range end off by one day → 3 failed; paging stops early → 2 failed; agent allowed through → 2 failed; **"resolved" count ignoring the range → initially SURVIVED**
(a real test gap), so a dedicated test was added and the mutation is now caught.

**Full verification:** `vitest` 29 files / 238 tests · `eslint` 0 errors (2 pre-existing warnings) · `next build` OK (`/admin/reports`, `/api/reports`) · `tsc` only the pre-existing `admin-ticket-attachment.test.tsx` error.

## Known limits
- Days are UTC calendar days (an administrator far from UTC may see a ticket on the neighbouring day near midnight). Consistent between server and browser by design.
- Aggregation happens in the route from fetched rows rather than in SQL; fine at current volumes, and a SQL view/RPC would be the next step for very large datasets (would need a DB change — not made).
- Not exercised against live Supabase in this sandbox (mocked query builder).
- Continues in FR-052 (AI performance) and FR-053 (export), which reuse this range/loader.

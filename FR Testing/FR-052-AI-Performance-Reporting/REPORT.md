# FR-052 — AI Performance Reporting (SRS §3.1.14)

**Status before:** 🔴 Not implemented — raw metrics sat in `resolutions` / `ticket_validations` / `response_evaluations`; nothing aggregated them.
**Status after:** ✅ The admin Reports page has an *AI performance* section for the same configurable date range as FR-051.
**Database changes:** none (reads existing tables).

Acceptance criteria: *reports include processing time* · *escalation statistics* · *validation outcomes*.

## What was built
`aiPerformance()` in `src/lib/reports.ts`, exposed as `ai` on `GET /api/reports` (admin-only, same route/range as FR-051) and rendered by `/admin/reports`.

| Criterion | Figures |
|---|---|
| Processing time | median, mean, **p95**, max and sample count of `resolutions.total_latency_ms` (nearest-rank percentiles; negative/NaN values ignored) |
| Escalation statistics | escalated tickets, **escalation rate over tickets the pipeline actually processed** (not-yet-processed tickets are excluded from the denominator; a ticket counts once even with several escalated rows), ranked escalation reasons (`escalation_reasons` is a `list[str]` in the orchestrator) |
| Validation outcomes | passed / failed / pass rate over *decided* validations (`passed IS NULL` is neither), ranked failure types, how many ran the LLM judge |
| Extra | mean LLM calls and reflection rounds per resolution; judge score mean + 5→1 distribution from `response_evaluations` |

Nothing measurable → `null` and the UI shows "—" (never `0` or `NaN`). Loader change: the paginated ticket query now also embeds `ticket_validations` and `response_evaluations`, so everything is one consistent cohort (tickets created in the period).

## Tests
| File | New cases |
|---|---|
| `src/lib/reports.test.ts` | 10 — percentile maths (order-independent, non-mutating, empty), latency stats from hand-computed data, escalation denominator & reason ranking, validation counts/failure types, effort averages & score distribution, range applies, empty → nulls, garbage values ignored, single escalation per ticket |
| `src/app/api/reports/route.test.ts` | 2 — `ai` returned for the same cohort; **the select includes every relation the reports read** |
| `src/app/__tests__/admin-reports.test.tsx` | 3 — figures rendered (2.0 s, p95, 25 % "2 of 8", 70 %, 4.25/5, reason/failure panels), dashes not zeros/NaN, "nothing processed" state |

**Mutation checks (reverted after each, all caught):** escalation denominator = all tickets; undecided validations counted as validated; percentile rank floor instead of ceil; negative latency kept; and
**loader not selecting `ticket_validations` — initially SURVIVED** (stub ignored the select string; a missing relation would silently blank the validation report), so the select assertion above was added.

**Full verification:** `vitest` 29 files / **253 tests** · `eslint` 0 errors · `next build` OK · `tsc` only the pre-existing `admin-ticket-attachment.test.tsx` error.

## Known limits
- The nested embeds rely on the foreign keys declared in `supabase_schema.sql` / `supabase_response_validation_schema.sql`. If your live database lacks them PostgREST will error (surfaced as a 500 with its message). Not verified live from this sandbox — worth one look at the Reports page after deploy.
- Latency is the orchestrator's recorded `total_latency_ms` per resolution (end-to-end pipeline time), not a per-stage breakdown (per-stage timing only exists in the disabled-by-default tracer).
- The cohort is *tickets created in the period*; a ticket created on the last day but processed after it is included with whatever data exists at report time.

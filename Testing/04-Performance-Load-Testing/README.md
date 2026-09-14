# 04 — Performance & Load Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md). All
measurements completed with 0 errors/crashes/timeouts. Key findings:
the single-worker Redis queue processes tickets serially even under
concurrent submission (measured, not assumed) — a real architectural fact
worth the team's attention if concurrent usage is expected to grow; and
(§6, added 2026-09-13) two different real customers submitting a ticket
through the actual UI at the exact same instant never cross-contaminate
each other's data — also measured, not assumed.

**Sample-plan equivalent:** §3.1.4 Performance Profiling, §3.1.5 Load Testing.

**Scope for Clario:** measure end-to-end ticket-processing latency through
the LangGraph pipeline (classification → routing → draft → judge →
resolution) under single-request and concurrent-request load, LLM-call
latency/timeout behavior, Supabase query performance, ChromaDB retrieval
latency for `precedent_memory` / `validation_refs` lookups under
increasing collection size, and — since "what happens when two people
submit at once" has two genuinely different meanings — both the *timing*
question (does it serialize, and how long does draining take?) and the
*correctness* question (do their two tickets' data ever cross?) under
real simultaneous submission by two different real, logged-in users.

## Files in this folder

| File | What it is |
|---|---|
| `run_performance_tests.py` | Stages A–C: sequential latency, concurrent-load *timing*, ChromaDB/Supabase component benchmarks |
| `concurrent-ticket-submission.spec.ts` | Stage D (added 2026-09-13): real 2-browser-session UI test for concurrent-submission *data isolation* — copy of `frontend/e2e/concurrent-ticket-submission.spec.ts` |
| `TEST_REPORT.md` | Full findings for all four stages |
| `test-log.txt` / `performance_test_results.json` / `supabase_single_by_id_rerun.json` | Raw output, Stages A–C |
| `concurrent-test-log.txt` | Raw `playwright test` output, Stage D |

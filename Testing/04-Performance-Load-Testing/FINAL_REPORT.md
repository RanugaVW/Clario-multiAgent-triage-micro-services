# Final Report — 04 Performance & Load Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04, extended 2026-09-13
**Team:** Clario QA Team
**Test case field:** End-to-end pipeline latency under single and
concurrent load, component benchmarks (ChromaDB, Supabase), and — added
2026-09-13 — real two-user concurrent-submission data isolation

## Metrics

| Metric | Value |
|---|---|
| Real tickets processed (Stage A + B) | 6, all completed successfully |
| Errors / crashes / timeouts | 0 |
| Component benchmark queries run (Stage C, free/repeatable) | 90 (30 ChromaDB + 60 Supabase) |
| Concurrent-submission data-isolation checks (Stage D) | 2 runs, 2 passed |
| Pass percentage (Stage D) | 100% |

This stage is a performance/load measurement exercise, not a pure
pass/fail suite — most of its value is in the numbers it measured (see
Comments), not a single score. Where a clear pass/fail check does apply
(Stage D), we report it the same way as every other stage.

## Comments

We measured how the system behaves both under a single ticket at a time
and under three tickets submitted by three different real accounts at
the exact same instant. Every measurement completed with zero errors,
crashes, or timeouts. The one finding worth the team's attention: the
single worker that drains the ticket queue processes tickets one at a
time even when three arrive together — this is how the system is built
today, not a defect, but it means wait time grows the more tickets queue
up at once. We measured this directly rather than assuming it.

We also found one real, if short-lived, issue: a database query spiked to
nearly a minute right after the concurrent-load test finished, which we
reproduced was not a repeatable problem — a clean standalone re-run of
the same query came back fast and normal. We kept both the spike and the
clean re-run in the record rather than hiding either.

On 2026-09-13 we added a fourth stage to answer a question the original
three didn't: when two different real people submit a ticket at the same
instant, does either one's data ever end up mixed into the other's? We
built a real two-browser-session test for exactly this — two different
real logged-in customers, submitting through the real UI at the same
moment — and confirmed, at the database level and the UI level, that
neither ticket ever crossed into the other's account. We ran it twice to
be sure it wasn't a one-off, and confirmed cleanup left no trace behind
either time.

We also want to record something about how this stage was actually run:
this system shares one machine with everything else on it, including,
that day, the person testing it. Before we could bring up the real
backend services needed for the fourth stage, the machine's memory was
already nearly exhausted from other running applications. We paused,
asked for some applications to be closed, confirmed the machine had
recovered, and only then proceeded — the same caution the original stage
already showed by keeping its load deliberately modest rather than
following the reference plan's "hundreds of concurrent users" language,
which was written for a different kind of system on dedicated hardware.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings for all four stages
- [`test-log.txt`](test-log.txt) — raw console output, Stages A–C
- [`performance_test_results.json`](performance_test_results.json) — structured results, Stages A–C
- [`supabase_single_by_id_rerun.json`](supabase_single_by_id_rerun.json) — the clean re-run that showed the latency spike didn't reproduce
- [`concurrent-ticket-submission.spec.ts`](concurrent-ticket-submission.spec.ts) — the Stage D test itself
- [`concurrent-test-log.txt`](concurrent-test-log.txt) — raw console output, Stage D

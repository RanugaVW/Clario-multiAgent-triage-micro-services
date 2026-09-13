# Final Report — 06 Failover & Recovery Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04
**Team:** Clario QA Team
**Test case field:** Circuit-breaker behavior and recovery from real
dependency failures — a broken vector-store path, a failing database
write, and a worker crash mid-ticket

## Metrics

| Metric | Value |
|---|---|
| No. of test cases executed (original run) | 14 |
| No. of pass (original run) | 12 |
| No. of fail (original run) | 2 |
| No. of test cases executed (final, after fixes) | 16 |
| No. of pass (final) | 16 |
| No. of fail (final) | 0 |
| Pass percentage (final) | 100% |
| Fail percentage (final) | 0% |

## Comments

We tested how the system behaves when things actually break, not how we
assumed it would: a broken connection to the vector store, a database
write that fails partway through saving a ticket's outcome, and a worker
process that crashes while a ticket is still being processed. We injected
each failure at the narrowest real point in the code rather than
reimplementing any of this logic ourselves, so what we tested is genuinely
the real system's behavior.

The circuit breaker itself worked correctly from the very first run,
along with every dependency's fallback path around it. We found two real
problems and a third smaller gap. First, when a database write failed
partway through saving a ticket's outcome, the ticket was left in an
inconsistent state without anyone being told — we rated this high
severity since it could silently strand a customer's ticket. Second, if
the worker process crashed while handling a ticket, that ticket was lost
permanently with no retry — medium severity, since it means real customer
requests can vanish under a real infrastructure failure. We fixed both,
added two new checks specifically to prove the fixes hold, and re-ran the
whole suite live: every check passes now, including the two we added.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings, root causes, and fixes
- [`failover_test_results.json`](failover_test_results.json) — structured results, final run
- [`test-log.txt`](test-log.txt) — raw console output, original run
- [`test-log-after-fix.txt`](test-log-after-fix.txt) — raw console output, final 16/16 run
- [`pytest-circuit-breaker-evidence.txt`](pytest-circuit-breaker-evidence.txt) — supporting circuit-breaker test evidence

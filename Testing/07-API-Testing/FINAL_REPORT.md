# Final Report — 07 API Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04
**Team:** Clario QA Team
**Test case field:** Contract correctness (status codes, response
shapes, and authorization) for every directly reachable HTTP endpoint in
the system — the Next.js API routes, the ML sidecar, and the
voice-to-text service

## Metrics

| Metric | Value |
|---|---|
| No. of test cases (assertions) executed | 46 |
| No. of pass (original run) | 37 |
| No. of fail (original run) | 9 |
| No. of pass (final, after fixes) | 46 |
| No. of fail (final) | 0 |
| Pass percentage (final) | 100% |
| Fail percentage (final) | 0% |

## Comments

We tested every endpoint independently reachable outside a full
Docker Compose stack, checking whether each one returns the right status
code, the right response shape, and enforces the right authentication and
ownership rules — for both valid and invalid input.

The first run found nine real, reproducible defects, not test-harness
issues. Two endpoints had no authentication at all, one of which
injects content that gets served back to future customers. Two more had
broken authorization checks — one relied on a field our account schema
never actually sets, so no real admin could use the privileged action it
was meant to protect. A fifth issue rewrote an intentional "forbidden"
response into a generic server error, which hides the real problem from
whoever is debugging it. We fixed all five underlying root causes (some
accounted for more than one failing assertion), synced the fix to the
mirrored service that shares this code, and re-ran the full collection
live: every one of the 46 assertions passes now.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings and fixes
- [`test-log-before-fix.txt`](test-log-before-fix.txt) — raw Newman output, original run
- [`test-log-after-fix.txt`](test-log-after-fix.txt) — raw Newman output, final 46/46 run
- [`postman/`](postman/) — the Postman collection and environment template

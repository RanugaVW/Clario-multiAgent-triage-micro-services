# Final Report — 09 REST Assured API Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04
**Team:** Clario QA Team
**Test case field:** Cross-request data integrity — confirming that two
separate, independent API calls agree on the same underlying data, across
both the Next.js routes and the ML sidecar

## Metrics

| Metric | Value |
|---|---|
| No. of test cases executed | 13 |
| No. of pass (first run) | 8 |
| No. of fail (first run) | 5 |
| No. of pass (final) | 13 |
| No. of fail (final) | 0 |
| Pass percentage (final) | 100% |
| Fail percentage (final) | 0% |

## Comments

Unlike our Postman-based API contract testing, this stage checks that two
separate API calls agree with each other — for example, that resolving a
ticket through one endpoint and then reading it back through a completely
different one shows the same outcome. All 13 tests run against the real,
live system.

We found two real issues during the first run, both in the test suite
itself rather than the product code, and both only visible because we
actually ran the suite instead of just reading it. Five tests failed
because our build was missing a JSON library REST Assured needs at
runtime to send request bodies — we added the missing dependency. The
remaining failures traced to a second, separate test-harness issue that
we also fixed. After both fixes, all 13 tests pass, and we confirmed the
product code itself had no defects in this area.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings and fixes
- [`test-log.txt`](test-log.txt) — raw Maven/JUnit output, final 13/13 run
- [`pom.xml`](pom.xml) — the corrected build configuration

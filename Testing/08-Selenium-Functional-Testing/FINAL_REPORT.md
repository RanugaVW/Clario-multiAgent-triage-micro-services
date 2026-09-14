# Final Report — 08 Selenium Functional Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04
**Team:** Clario QA Team
**Test case field:** Real browser automation with Selenium WebDriver —
login (positive and negative), the `/admin` authorization boundary,
session/logout behavior, a real ticket submitted through the dashboard,
and the admin console finding and opening it

## Metrics

| Metric | Value |
|---|---|
| No. of test cases executed | 8 |
| No. of pass | 8 |
| No. of fail | 0 |
| Pass percentage | 100% |
| Fail percentage | 0% |

## Comments

We ran eight real Selenium scenarios against a live headless Chrome
browser and the real system — the login form, the authorization boundary
around the admin console, session and logout behavior, a real ticket
submitted through the dashboard, and the admin console finding and
opening that same ticket. All eight pass.

Along the way we found that running each test with its own fresh browser
session made the full suite unreliable and slow (as long as four and a
half minutes on a bad run) on this shared machine. We fixed this by
sharing one browser session across the whole suite and clearing cookies
and local storage between tests to keep them isolated from each other —
this is a fix to how the test suite runs, not a defect in the product
itself. After the fix, the full suite runs in under 90 seconds and passes
reliably on repeated runs.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings, including the browser-session fix
- [`test-log.txt`](test-log.txt) — raw pytest output, final 8/8 run
- [`test_functional_e2e.py`](test_functional_e2e.py) — the 8 real Selenium scenarios

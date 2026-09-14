# Final Report — 13 Accessibility Testing (WCAG 2.1 A/AA)

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2
(this stage maps to a separately-assigned tool set — JAWS, a
color-contrast checker, axe DevTools, Google Lighthouse — rather than a
section of the reference plan itself, since it predates WCAG testing
being a standard phase). The full narrative writeup is in
[`TEST_REPORT.md`](TEST_REPORT.md); this page is the short version for
the record.

**Date:** 2026-09-13
**Team:** Clario QA Team
**Test case field:** WCAG 2.1 A/AA automated coverage of every real page
in the app — login, register, dashboard, admin console, and agent
console — plus a scripted keyboard-navigation check

## Metrics

| Metric | Value |
|---|---|
| No. of pages scanned | 5 |
| No. of automated checks executed | 6 |
| No. of pass | 6 |
| No. of fail | 0 |
| Pass percentage | 100% |
| WCAG 2.1 A/AA violations found (final) | 0 |
| Lighthouse accessibility score (public pages) | 100/100 |

## Comments

We chose axe-core, run through our existing browser-automation suite, as
our main tool because it is the same engine behind axe DevTools and
Lighthouse's own accessibility check, and running it in code let us scan
pages that need a real login (the dashboard and admin console) in their
real signed-in state, not just the pages reachable without one. We ran
Lighthouse separately as a second, independent check on the two public
pages, and used a scripted keyboard-navigation check as a partial
stand-in for a manual screen-reader pass, since we don't have a licensed
copy of JAWS in this environment.

We found and fixed one real accessibility bug: the login page's
decorative background animation had no accessible name, so a screen
reader would announce a meaningless, empty frame to the user. We hid it
from assistive technology entirely, since it carries no real content.

Our first pass also showed what looked like nearly fifty color-contrast
violations on two pages. We didn't take that at face value — the colors
axe reported didn't match anything in our actual style definitions, which
told us something else was going on. It turned out our own page-load
animation was still fading in at the exact moment we scanned the page,
so axe was reading a real but temporary in-between state, not the page's
resting appearance. We fixed our test's timing instead of touching the
product, and confirmed every one of those findings disappeared with no
code changes — real proof it was a timing artifact, not something we
talked ourselves out of.

While reaching the agent console page for this scan, we also found that
its login redirect had been disabled, letting anyone reach it without
signing in. That's an access-control finding, not an accessibility one,
so we handed it to the stage that owns that class of issue — see
`Testing/05-Security-Access-Control-Testing`'s report for the fix — and
updated this scan to sign in first, matching the page's corrected real
behavior.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings, including how the false positives were diagnosed
- [`accessibility.spec.ts`](accessibility.spec.ts) — the test suite itself
- [`test-log.txt`](test-log.txt) — raw console output, final 6/6 run
- [`results/axe/*.json`](results/axe/) — full axe-core results per page
- [`results/lighthouse/*.json`](results/lighthouse/) — full Lighthouse results for the two public pages

# Final Report — 03 UI / End-to-End Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04, extended 2026-09-13
**Team:** Clario QA Team
**Test case field:** Real browser-driven testing of login, ticket
submission, the customer feedback widget, and the admin console — the
only parts of the UI our reference plan says can be automated

## Metrics

| Metric | Value |
|---|---|
| No. of test cases executed | 10 |
| No. of pass | 10 |
| No. of fail | 0 |
| Pass percentage | 100% |
| Fail percentage | 0% |

This grew from 9/9 on the original run to 10/10 on 2026-09-13, when we
added a check that a signed-out visitor to `/agent` is bounced to
`/login` (see Comments).

## Comments

We tested the real login flow (wrong password, valid customer login,
valid admin login, logout, and route protection), and a real support
ticket submitted through the dashboard form and carried all the way
through the live pipeline to a customer-visible outcome, including the
star-rating feedback widget and the admin console's view of that same
ticket. Nothing here is mocked — every check runs against the real,
live system.

We found two real bugs this way. First, a production Row Level Security
policy for admin/agent visibility into other users' profiles had drifted
out of the database entirely, silently breaking a fix from earlier in the
project — we corrected the live policy and confirmed it with a
independent read against the database, not just the passing test.
Second, a customer's star rating stopped showing as filled in after a
page reload because of a relationship-shape mismatch in how the rating
was queried back — we fixed the query and confirmed the rating now
survives a reload and stays editable.

We also documented, rather than "fixed," a real and repeatable pipeline
behavior: the same placeholder ticket text reliably caused the billing
agent to invent a customer name that was never given, which correctly
triggers our PII safeguard and escalates the ticket to a human. We
traced this to the language model's own habit, not a bug in our code, and
fixed it at the prompt level for every specialist agent — see
`Testing/01-Unit-Testing`'s report for that fix.

On 2026-09-13, while fixing an access-control gap found during
accessibility testing (the `/agent` page had no login redirect at all),
we added a new check here confirming a signed-out visitor is correctly
sent to `/login`. That fix itself is owned and written up by
`Testing/05-Security-Access-Control-Testing`; this suite just proves the
UI behaves correctly now.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings and fixes
- [`test-log.txt`](test-log.txt) — raw Playwright console output
- [`e2e-results.json`](e2e-results.json) — structured Playwright results
- [`screenshots/`](screenshots/) — captured screenshots from the real run

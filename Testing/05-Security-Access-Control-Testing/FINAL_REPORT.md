# Final Report — 05 Security & Access Control Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup is in [`TEST_REPORT.md`](TEST_REPORT.md); this
page is the short version for the record.

**Date:** 2026-09-04, extended 2026-09-13
**Team:** Clario QA Team
**Test case field:** Row Level Security, service-role API route
authorization, PII redaction boundary, and application-level
access-control gates — tested with real accounts and real requests
against the live system

## Metrics

| Metric | Value |
|---|---|
| No. of test cases executed (original automated script) | 18 |
| No. of pass (original run) | 12 |
| No. of fail (original run) | 6 |
| No. of test cases executed (after fixes, re-verified) | 23 |
| No. of pass (final) | 23 |
| No. of fail (final) | 0 |
| Additional real-browser check (added 2026-09-13) | 1, pass |
| Pass percentage (final, all checks) | 100% |
| Fail percentage (final) | 0% |

## Comments

We tested three things with real accounts and real requests, not
assumptions read from a schema file: whether Row Level Security actually
confines a customer to their own data, whether the API routes that use a
key powerful enough to bypass that security enforce authorization
themselves, and whether raw customer text ever reaches the AI judge or
the vector store unredacted.

Row Level Security and the PII redaction boundary both held up
completely from the very first run. The API routes did not: five of them
performed no authentication at all while using a key that bypasses every
database-level protection, which meant an unauthenticated caller could
read every customer's tickets and unredacted personal information, forge
a resolution, delete a ticket outright, or write feedback on another
customer's behalf. We rated five of these critical or high severity. We
also found a live database policy that existed in production but was
missing from our own checked-in schema files, which we corrected.

We fixed all six findings with a shared authorization helper that every
affected route now calls, updated the frontend to send real session
tokens, and added the missing policy to our schema file. We then
re-verified live against the real system — not just re-reading the code —
and every one of the five newly-broken routes now correctly rejects an
unauthenticated caller while still working normally for a legitimate
signed-in customer or staff member, which we also tested directly rather
than assuming the fix wasn't too strict.

On 2026-09-13, a seventh finding came to us from a different stage: our
accessibility testing found that the agent-console page's login redirect
had been disabled, so it was reachable without signing in at all. We
picked this up because it is exactly the kind of finding this stage
owns, fixed it, and added a real-browser test proving a signed-out
visitor is now correctly sent to the login page.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — full findings, before/after evidence, and the seventh finding
- [`security_test_results.json`](security_test_results.json) — structured results, final run
- [`test-log.txt`](test-log.txt) — raw console output, original run
- [`test-log-after-fix.txt`](test-log-after-fix.txt) — raw console output, final 23/23 run
- [`pytest-redaction-evidence.txt`](pytest-redaction-evidence.txt) — supporting PII-redaction test evidence
- [`2026-09-13-agent-redirect-fix/`](2026-09-13-agent-redirect-fix/) — the seventh finding's fix verification

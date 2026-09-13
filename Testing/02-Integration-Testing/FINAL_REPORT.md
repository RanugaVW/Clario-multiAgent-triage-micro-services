# Final Report — 02 Integration Testing

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2.
The full narrative writeup — including a real production incident this
stage caused and recovered from — is in
[`INTEGRATION_TEST_REPORT.md`](INTEGRATION_TEST_REPORT.md); this page is
the short version for the record.

**Date:** 2026-09-03
**Team:** Clario QA Team
**Test case field:** End-to-end ticket pipeline integration — classification, routing, drafting, judging, and resolution, verified against the real production database and vector store

## Metrics

| Metric | Value |
|---|---|
| No. of test cases (scenarios) executed | 4 |
| No. of pass (final run) | 4 |
| No. of fail (final run) | 0 |
| Pass percentage | 100% |
| Fail percentage | 0% |

The first run of this stage passed 1/4 (25%) and surfaced two real
defects; both were fixed and the full suite was re-run clean. Both runs
are kept in the report so the before/after is visible, not just the final
number.

## Comments

We tested four scenarios end to end against the real, live system: a
technical ticket, a billing ticket, an ambiguous ticket meant to probe
the dual-domain path, and a repeat submission meant to test the semantic
cache. The very first attempt at this stage caused a real incident on the
shared machine this system runs on — our original test design loaded a
second copy of the local model already resident on the one GPU this
deployment has, which triggered an out-of-memory event and took the live
service down until we restarted it. We rewrote the test to submit over
HTTP to the already-running service instead of loading a second copy, and
every result in this report comes from that safer design.

We found two real defects. First, judge evaluations were silently missing
for some tickets because the configured judge model had run out of its
daily free quota — we pinned it to a fresh model and confirmed every
scenario now gets a real score. Second, the cache-hit path was writing a
row of entirely blank fields to the classifications table, because
classification is correctly skipped on a cache hit but nothing told the
insert logic that — we gated the insert so it no longer writes that row.
Both fixes were verified live, not just read in code.

One scenario did not exercise what we designed it to: the "ambiguous"
ticket text was, in practice, classified confidently by the real model
and never reached the dual-domain path we meant to probe. This is a
limitation of our test wording against a real classifier, not a finding
about the system, and is recorded as a follow-up rather than something we
kept iterating on.

## Files referenced

- [`INTEGRATION_TEST_REPORT.md`](INTEGRATION_TEST_REPORT.md) — full findings and the production-incident writeup
- [`test-log.txt`](test-log.txt) — raw console output, final clean run
- [`integration_test_results.json`](integration_test_results.json) — structured results for all four scenarios
- [`run_integration_tests.py`](run_integration_tests.py) — the test script itself
- [`cleanup_sweep.py`](cleanup_sweep.py) — crash-recovery cleanup safety net

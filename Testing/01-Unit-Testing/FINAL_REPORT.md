# Final Report — 01 Unit Testing

This is the summary we are submitting for this stage. It follows the
generic reporting format our reference Master Test Plan asks for in its
own §4.2 (date, test case field, executed/pass/fail counts, comments), and
points to the exact files in this folder that back every number below. The
full narrative writeup, including root-cause analysis for what we found,
is in [`UNIT_TEST_REPORT.md`](UNIT_TEST_REPORT.md) — this page is the
short version for the record, not a replacement for it.

**Date:** 2026-09-03, re-verified and corrected 2026-09-13
**Team:** Clario QA Team
**Test case field:** Unit-level function testing across all three
components of the system — `clario-ml-sidecar` (agent pipeline),
`ml_finetuning` (data/training pipeline), and `frontend` (web app)

## Metrics

| Metric | Value |
|---|---|
| No. of test cases executed | 337 |
| No. of pass | 334 |
| No. of fail | 0 |
| No. of skipped (planned work, not yet built) | 3 |
| Pass percentage (of executed) | 100% |
| Fail percentage (of executed) | 0% |

Breakdown by component:

| Component | Executed | Pass | Fail | Skipped |
|---|---|---|---|---|
| `clario-ml-sidecar` | 176 | 176 | 0 | 0 |
| `ml_finetuning` | 47 | 44 | 0 | 3 |
| `frontend` | 114 | 114 | 0 | 0 |

## Comments

We found one real defect in the original run of this stage: the routing
logic had stopped sending genuinely ambiguous tickets to both specialist
agents, which broke a documented product capability. When we re-checked
this on 2026-09-13, that defect was already fixed by other work on the
codebase since then, so we corrected the report to say so rather than
leave a stale finding on record. We also found and corrected a scoping
mistake in how the original run counted its own tests — four scripts at
the repository root were being swept into the count even though they are
manual debug scripts, not real automated tests (one of them even made a
live network call, which contradicts what this stage is supposed to
test). We rescoped the count to the real, mocked, assertion-bearing test
suite and removed two test files that had been left claiming "not
implemented" for two agents that are, in fact, implemented and already
covered by real tests elsewhere.

Separately, while reviewing another stage's findings, we found and fixed
a real product bug: the specialist agents could invent a customer's name
that never appeared in the ticket text, which broke a validation rule and
forced unnecessary escalations. We fixed this at the prompt level so
every specialist agent is affected by the fix, not just the one where it
was first noticed.

The three remaining skips are genuine, not a defect — they are
pre-written test specs for features the team has not built yet (the
Gemini distillation labeler, model evaluation metrics, and dataset-split
validation).

## Files referenced

- [`UNIT_TEST_REPORT.md`](UNIT_TEST_REPORT.md) — full findings, root
  causes, and what changed since the original run
- [`ml-sidecar/test-log.txt`](ml-sidecar/test-log.txt) — raw pytest output, `clario-ml-sidecar`
- [`ml-finetuning/test-log.txt`](ml-finetuning/test-log.txt) — raw pytest output, `ml_finetuning`
- [`frontend/test-log.txt`](frontend/test-log.txt) — raw vitest output, `frontend`

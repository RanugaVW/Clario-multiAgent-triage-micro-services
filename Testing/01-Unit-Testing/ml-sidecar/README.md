# clario-ml-sidecar — Unit Test Log

Command run (from `clario-ml-sidecar/`, inside its `.venv`):

```
python -m pytest tests/ -v
```

**Result:** 176 passed, 0 failed, 0 skipped, in ~18s (176 tests total, 33 files).

Re-scoped to `tests/` only on 2026-09-13 — the original command also ran
four repo-root scripts (`test_cache.py`, `test_db.py`, `test_graph.py`,
`test_orchestration.py`) that only match pytest's naming pattern by
coincidence; they aren't real automated unit tests (one makes a live
Supabase call, one has no assertions, two have no test functions at all).
See the [phase report §4](../UNIT_TEST_REPORT.md#4-a-methodology-issue-found-and-corrected-4-root-level-scripts-were-never-real-unit-tests)
for why they were excluded.

See [`test-log.txt`](test-log.txt) for the full, unmodified console output.
The routing-regression defect this suite originally found (§5 of the old
report) is now fixed — see the [phase report §6](../UNIT_TEST_REPORT.md#6-original-defect--now-fixed-re-verified-live).

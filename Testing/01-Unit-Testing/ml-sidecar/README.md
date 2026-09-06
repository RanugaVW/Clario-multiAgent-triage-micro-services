# clario-ml-sidecar — Unit Test Log

Command run (from `clario-ml-sidecar/`, inside its `.venv`):

```
python -m pytest test_cache.py test_db.py test_graph.py test_orchestration.py tests/ -v --tb=short
```

**Result:** 85 passed, 4 failed, 3 skipped, in 21.01s (92 tests total, 27 files).

See [`test-log.txt`](test-log.txt) for the full, unmodified console output.
Analysis of the 4 failures is in the [phase report](../UNIT_TEST_REPORT.md#5-defects-found--clario-ml-sidecar-4-failures).

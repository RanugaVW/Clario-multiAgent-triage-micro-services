# frontend — Unit Test Log

Command run (from `frontend/`):

```
npm test    # runs `vitest run`
```

**Result:** 91 passed, 0 failed, 0 skipped, in 4.96s (91 tests total, 12 files).

See [`test-log.txt`](test-log.txt) for the full, unmodified console output.
The repeated `HTMLCanvasElement getContext()` lines are jsdom warnings from
chart components rendering in a headless test DOM, not test failures.

# frontend — Unit Test Log

Command run (from `frontend/`):

```
npm test    # runs `vitest run`
```

**Result:** 114 passed, 0 failed, 0 skipped, in ~9s (114 tests total, 16 files) — re-verified 2026-09-13, up from 91 tests/12 files in the original run as more coverage was added since.

See [`test-log.txt`](test-log.txt) for the full, unmodified console output.
The repeated `HTMLCanvasElement getContext()` lines are jsdom warnings from
chart components rendering in a headless test DOM, not test failures.

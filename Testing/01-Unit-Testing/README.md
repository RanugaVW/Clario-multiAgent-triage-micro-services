# 01 — Unit Testing

**Status:** Complete — 334/337 tests passing (3 genuinely open skips), 0
failing. See [`UNIT_TEST_REPORT.md`](UNIT_TEST_REPORT.md). Re-verified and
corrected 2026-09-13: the one defect the original run found (a routing
regression) is now fixed; a test-scope inaccuracy in the original run was
also found and corrected — see the report's §4 and §6.

**Sample-plan equivalent:** §3.1.2 Function Testing (unit level).

**Scope for Clario:** every controller/node/tool/function across the three
independently-testable components — `clario-ml-sidecar` (FastAPI +
LangGraph pipeline), `ml_finetuning` (data curation/training scaffolding),
and `frontend` (Next.js dashboard/admin/API routes) — exercised in
isolation with every external collaborator (LLM calls, Supabase, ChromaDB,
HTTP fetches) mocked. No real network calls, no real API cost.

## Files in this folder

| File | What it is |
|---|---|
| `ml-sidecar/`, `ml-finetuning/`, `frontend/` | Per-component `README.md` (exact command run + result) and raw `test-log.txt` |
| `UNIT_TEST_REPORT.md` | Full findings across all three components |

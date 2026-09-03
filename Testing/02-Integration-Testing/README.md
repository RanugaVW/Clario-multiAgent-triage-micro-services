# 02 — Integration Testing

**Status:** Complete (first pass). See [`INTEGRATION_TEST_REPORT.md`](INTEGRATION_TEST_REPORT.md).

**Sample-plan equivalent:** §3.1.1 Data and Database Integrity Testing,
§3.1.2 Function Testing (multi-component flows).

**Scope for Clario:** exercise the pipeline end-to-end over HTTP against
the sidecar's actual **production** Supabase project (there is no separate
test/staging project) — ticket ingestion → cache check → PII surrogate →
classification → routing → specialist draft → validation → judge →
escalation/resolution — verifying data actually lands correctly in
`tickets`, `ticket_classifications`, `ticket_drafts`, `response_evaluations`,
`resolutions`, `human_reviews`, and the real ChromaDB collection precedents
are written into (`kb_support_docs`, tagged `source_file: "precedent_memory"`
— confirmed via code investigation to be the *same* collection real RAG
retrieval reads from, not a separate one, despite the name).

Every test ticket is tagged `[INTEGRATION-TEST <run_id>]` and fully cleaned
up (Postgres via `ON DELETE CASCADE` from `tickets`, Chroma via deterministic
`precedent_<ticket_id>` ids) after each run. See `run_integration_tests.py`
and `cleanup_sweep.py` (crash-recovery safety net) in this folder.

Existing partial coverage already in the unit suite
(`tests/graph/test_graph_integration.py`) is cross-referenced, not
duplicated, in the report.

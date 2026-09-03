# 02 — Integration Testing (Planned)

**Status:** Not yet executed.

**Sample-plan equivalent:** §3.1.1 Data and Database Integrity Testing,
§3.1.2 Function Testing (multi-component flows).

**Scope for Clario:** exercise the LangGraph pipeline end-to-end
(`build_graph().ainvoke()`) against a real or seeded Supabase instance —
ticket ingestion → cache check → PII surrogate → classification → routing →
specialist draft → validation → judge → escalation/resolution — verifying
data actually lands correctly in `tickets`, `ticket_drafts`,
`response_evaluations`, `resolutions`, and the `precedent_memory` /
`validation_refs` ChromaDB collections. Also covers the Next.js API routes
against a real (test) Supabase project rather than mocks.

Existing partial coverage already in the unit suite
(`tests/graph/test_graph_integration.py`) will be cross-referenced here
rather than duplicated.

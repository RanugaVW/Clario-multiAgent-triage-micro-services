# 06 — Failover & Recovery Testing (Planned)

**Status:** Not yet executed.

**Sample-plan equivalent:** §3.1.7 Failover and Recovery Testing.

**Scope for Clario:** verify the circuit breaker (`app/tools/circuit_breaker.py`)
correctly trips and recovers around failing LLM/API calls, verify graceful
degradation when Supabase or ChromaDB is unreachable mid-pipeline, and
verify no partial/corrupt state is written to `tickets` /
`response_evaluations` if the pipeline is interrupted mid-run.

# 06 — Failover & Recovery Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md). Original
run: 12/14 real checks passed, 3 real findings — a Supabase write failure
partway through `background_orchestration`'s persistence sequence left a
ticket marked "resolved" with real classification data but zero
draft/resolution rows, silently (**high**); a worker crash between
`BRPOP`-ing a ticket off Redis and finishing processing it lost that
ticket permanently, with no retry or dead-letter queue (**medium**); and
`cache_check_node`'s ChromaDB calls reported to no circuit breaker
(**low**). **All 3 have since been fixed and re-verified live: final
result 16/16 checks passed, 0 failed** (see TEST_REPORT.md §9) — the
ticket's status now only flips after every supporting row is written, the
worker uses a crash-recoverable `BLMOVE`-based queue with startup
recovery, and `cache_check_node` now reports to the same `chroma_rag`
breaker `retrieve_context` does.

**Sample-plan equivalent:** §3.1.7 Failover and Recovery Testing.

**Scope for Clario:** verify the circuit breaker (`app/tools/circuit_breaker.py`)
correctly trips and recovers around failing LLM/API calls, verify graceful
degradation when Supabase or ChromaDB is unreachable mid-pipeline, and
verify no partial/corrupt state is written to `tickets` /
`response_evaluations` if the pipeline is interrupted mid-run.

Run via (from `clario-ml-sidecar/`, inside its `.venv`, with a local Redis
server running):
```
python ../Testing/06-Failover-Recovery-Testing/run_failover_tests.py
```

# Failover & Recovery Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `main`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`) and a local Redis server (`localhost:6379`), driving the real `clario-ml-sidecar` code directly (`app/tools/circuit_breaker.py`, `app/graph/cache_check_node.py`, `app/tools/rag_tool.py`, `app/agents/technical_agent/node.py`, `app/main.py::background_orchestration`, `app/worker.py`'s exact Redis calls). No hand-written reimplementations of any of this logic — failures are injected at the narrowest possible point (a broken `CHROMA_PATH`, a monkeypatched Supabase `.table()` call, a dedicated test-only Redis key) so everything else in each call path is genuinely real.

**Original result: 12/14 checks passed, 2 failed.** Both failures were real, reproducible findings, not test-harness bugs — one **high**-severity (a Supabase write failure partway through persistence left a ticket in an inconsistent state, silently), one **medium**-severity (a worker crash mid-flight permanently lost the ticket being processed, with no retry). A third, **low**-severity gap (`B1b`) was also found along the way. The circuit breaker itself, and every dependency's graceful-degradation path around it, held up completely under real adversarial testing from the start.

**All 3 findings have since been fixed and re-verified live: final result 16/16 checks passed, 0 failed** (the script grew 2 checks, `C4` and `D3`, specifically to verify the fixes — see §9). The sections below are left as originally written so the report shows the actual before/after, not a rewritten history.

## 1. Scope

This phase corresponds to §3.1.7 ("Failover and Recovery Testing") of the reference Master Test Plan. Per this repo's `Testing/06-Failover-Recovery-Testing/README.md`, three things were tested, each against real code and real (disposable) data — no mocks of the systems under test themselves:

- **A — CircuitBreaker correctness:** does `app/tools/circuit_breaker.py`'s state machine (closed → open → half-open → closed/open) actually behave correctly, beyond what the existing 2-test unit suite already checks?
- **B — Graceful degradation when ChromaDB is unreachable mid-pipeline:** do `cache_check_node`, `retrieve_context`, and a real specialist agent node degrade safely instead of crashing or hanging?
- **C — Partial/corrupt state:** if a Supabase write fails partway through `background_orchestration`'s persistence sequence, what does the `tickets` row actually end up looking like?

**Extended beyond the README's original scope, found while reading the code that scope pointed at:** whether a ticket "in flight" survives the worker process crashing — `app/worker.py`'s `BRPOP` is a destructive queue read, so this was worth verifying directly rather than assuming either way.

**Not covered this phase:** the Java services' own resilience (`api-gateway`, `ticket-core-service`, `agent-review-service` — none of their retry/circuit-breaking logic, if any, was examined); actually killing a live worker OS process (simulated instead — see §5); Supabase's own database-level failover (outside this application's control).

## 2. Environment & Tooling

| | |
|---|---|
| Test script | `Testing/06-Failover-Recovery-Testing/run_failover_tests.py` — real Python calling real `clario-ml-sidecar` modules directly, plus real Supabase and Redis clients |
| Supabase | Production project `mdvfvtpbwqhccmaarpli`, service-role client (same one `app/main.py` uses) |
| Redis | Local `redis-server` on `localhost:6379`, confirmed reachable (`PONG`) before the run; a dedicated `ticket_queue_failover_test_<run-id>` key was used throughout — the real `ticket_queue` key was never touched, so this could not race with or be picked up by a real worker |
| Test data | 3 disposable "canary" tickets (tagged `FAILOVER-TEST-CANARY-<run-id>`), created and fully cleaned up (ticket + every FK-referencing row) in a `finally` block regardless of pass/fail — verified empty after the run |
| Evidence for Section A | The existing `tests/tools/test_circuit_breaker.py` (2 tests, re-run fresh — `pytest-circuit-breaker-evidence.txt`), plus 5 new real state-machine checks this phase added |

## 3. Section A — CircuitBreaker: correct under every real state transition tested

The existing unit suite covers opening-after-threshold and half-open-success-closes. This phase drove the **real, unmodified `CircuitBreaker` class** (no reimplementation) through 3 transitions that suite didn't cover, plus reran the original 2 for a complete picture:

| Check | Result |
|---|---|
| `A1` Opens after `failure_threshold` real failures, then short-circuits | **PASS** |
| `A2` A half-open probe that **succeeds** closes the breaker | **PASS** |
| `A3` *(new)* A half-open probe that **fails** re-opens the breaker (not left half-open or closed) | **PASS** |
| `A4` *(new)* Only **one** concurrent probe is allowed while half-open — a second caller arriving during the same half-open window is blocked, not given its own probe slot | **PASS** |
| `A5` *(new)* The failure window is genuinely **rolling** — 2 failures followed by 3 successes (window size 3) correctly closes the breaker, because the failures scroll out of the window rather than being remembered forever | **PASS** |

No defect found. The breaker's own state machine is correct on every transition tested, including the two most likely to hide a race condition (concurrent half-open probes) or a stale-state bug (rolling window).

## 4. Section B — Graceful degradation when ChromaDB is unreachable: correct, with one coverage gap

`CHROMA_PATH` was pointed at a directory that provably doesn't exist, and three real production code paths were driven against it directly:

| Check | Result |
|---|---|
| `B1` `cache_check_node()` — real call against an unreachable Chroma path | **PASS** — returned `cache_hit: False` cleanly, no exception. `app/graph/cache_check_node.py`'s bare `try/except Exception as e: print(...)` around its own ChromaDB calls does exactly what it's supposed to. |
| `B2` `retrieve_context()` — repeated real calls against the same unreachable path | **PASS** — the first 5 calls (`BREAKER_FAILURE_THRESHOLD=5`) each made a real (failing) connection attempt and recorded a real failure; the 6th call short-circuited instantly (`CircuitBreakerOpenError`, no connection attempt at all) — the `chroma_rag` breaker registered in `app/tools/rag_tool.py:50` genuinely trips under real, repeated failure. |
| `B3` `technical_agent_node()` end-to-end with the breaker already open | **PASS** — returned the documented degraded state (`failure_type: "dependency_failure"`, `agent_drafts["technical"]: None`, `low_relevance_flags["technical"]: True`) and made **zero** LLM calls — confirmed by inspecting `llm_call_count`/no draft text, not assumed from reading the code alone. |

### A real, minor finding along the way: `cache_check_node` reports to no circuit breaker (`B1b`)

`retrieve_context()` explicitly wraps itself in the `chroma_rag` breaker (`app/tools/rag_tool.py:50-52`). `cache_check_node()` talks to the exact same ChromaDB instance but only has a bare `try/except` — it never calls `get_breaker(...)`. Verified directly: the `chroma_rag` breaker's outcome window was read before and after 2 real `cache_check_node()` calls against the broken path, and was **provably unchanged** (`before=[], after=[]`).

**Consequence:** a sustained ChromaDB outage never trips a breaker on the cache-check path specifically — every single incoming ticket keeps paying the real (failing, OS-level) connection-attempt cost on every request forever, instead of eventually short-circuiting the way `retrieve_context()`'s callers do. Not a crash risk (the bare `try/except` genuinely prevents that, per `B1`), but a real latency/cost gap under sustained Chroma downtime. Marked **low** severity — degradation is safe, just not as cheap as it could be.

## 5. Section C — Partial/corrupt state: a real, high-severity finding

Ran the actual `app/main.py::background_orchestration()` — the function every ticket in the system goes through — against 3 real disposable tickets, with `graph.ainvoke` stubbed to return a canned (but complete, schema-accurate) successful `final_state` immediately, so no real LLM calls were needed to exercise the **persistence** logic this section targets. A specific Supabase table's `.table()` call was monkeypatched to raise for exactly one call, everything else going through the real service-role client.

| Check | Setup | Result |
|---|---|---|
| `C1` | Break the `ticket_drafts` insert (which happens *after* the ticket's status update and classification insert have already succeeded for real) | **FAIL (finding)** — see below |
| `C2` | Break the very *first* persistence call (`tickets.update`) | **PASS** — ticket left untouched: still `status: "received"`, zero orphaned classification/draft/resolution rows |
| `C3` | No injected failure (positive control) | **PASS** — every row persisted correctly: `status: "resolved"`, 1 classification, 1 draft, 1 resolution |

### Finding: a mid-sequence Supabase failure leaves the ticket in an inconsistent, silently-broken state

`C1`'s real result: after the injected `ticket_drafts` failure, the canary ticket's actual row in `public.tickets` reads `status: "resolved"` — with **1** real `ticket_classifications` row, but **0** `ticket_drafts` rows and **0** `resolutions` rows.

**Root cause, read directly in `app/main.py:172-284`:** the entire persistence sequence — status update, classification insert, every draft insert, the resolution insert — is one single `try` block, closed by one generic `except Exception as e: logger.error(f"Failed to save to Supabase: {e}")` at line 283-284. There is no per-step recovery and no transaction: `tickets.update(status="resolved")` runs and commits *first*, several statements *before* anything can fail, so a failure anywhere downstream leaves that status change standing while every statement after the failure point (including the resolution insert customers' replies depend on) never runs. The exception never leaves `background_orchestration` — `worker.py`'s own `except Exception` (§6) never even sees it. The only trace is one log line that doesn't even name the ticket.

**Real-world consequence:** an admin opening this ticket in the console sees status "Resolved" with a real classification, but no draft and no resolution text to show — a resolved ticket with nothing in it, and nothing anywhere flags this ticket for a retry or a human's attention. Marked **high** severity: this is exactly the "partial/corrupt state" scenario this phase's README asked to verify, and it reproduces on the very first realistic failure injected.

`C2` and `C3` show this isn't inevitable — a failure *before* any write starts is handled cleanly (no partial state at all), and the happy path persists everything correctly. The bug is specifically in the *ordering*: status is written optimistically before the data that's supposed to justify it exists.

## 6. Section D — Worker resilience: a ticket does not survive a crash mid-flight

`app/worker.py`'s exact real call — `r.brpop(queue, timeout=0)` — was reproduced against a real, isolated Redis key (never the real `ticket_queue`).

| Check | Result |
|---|---|
| `D1` A message is popped (`BRPOP`), then the "worker" simply stops (simulating a crash/OOM/restart/deploy between the pop and the DB writes finishing) | **FAIL (finding)** — the queue length was `0` immediately after the pop; the message exists nowhere else. Real, destructive, immediate. |
| `D2` `worker.py`'s own exception handler (the thing that actually runs when `background_orchestration` errors) never requeues or dead-letters the message | **PASS** *(confirms the finding, doesn't contradict it)* — `grep -c "lpush\|rpush\|dead" app/worker.py` → 0 matches; replaying the exact except-block behavior (log and continue) left the queue at length 0 |

**Consequence, read directly in `app/worker.py:21-65`:** `BRPOP` removes the message from Redis the instant it's read — before `background_orchestration` is even called. If the worker process dies for *any* reason while that call is in flight (crash, OOM, a deploy, a `kill`), the ticket it was processing is gone from the queue permanently. It's still sitting in Supabase in whatever status it had when it was enqueued (typically `"received"`) — nothing will ever pick it up again. Combined with §5's finding, this means the two most likely real-world interruption points (a Supabase blip mid-write, a worker restart mid-processing) both produce a ticket that's stuck forever with no automatic recovery path. Marked **medium** severity (requires an actual process interruption at exactly the wrong moment — not something normal operation would hit often, but with zero mitigation when it does).

## 7. Summary of findings (as of the original run)

| # | Area | Severity | Status |
|---|---|---|---|
| `C1` | `background_orchestration`'s persistence writes are not atomic — a mid-sequence Supabase failure leaves `tickets.status` inconsistent with the (missing) supporting rows, silently | **High** | **Fixed — see §9** |
| `D1`/`D2` | A worker crash between `BRPOP` and finishing processing loses the ticket permanently — no retry, no dead-letter queue | **Medium** | **Fixed — see §9** |
| `B1b` | `cache_check_node`'s ChromaDB calls report to no circuit breaker, unlike `retrieve_context` — sustained Chroma downtime never short-circuits on this path | **Low** | **Fixed — see §9** |
| A1-A5 | `CircuitBreaker` state machine (open/half-open/closed, concurrent probes, rolling window) | — | **Verified correct** |
| B1-B3 | Graceful degradation of `cache_check_node`, `retrieve_context`, `technical_agent_node` under real Chroma unavailability | — | **Verified correct** |
| C2, C3 | Clean-failure and happy-path persistence behavior | — | **Verified correct** |

## 8. Follow-ups for a future run

- Extend Section B to the `local_draft` breaker (`app/tools/llm_client.py`) the same way this run covered `chroma_rag` — not exercised this phase since it requires a real (or realistically-faked) local model failure.
- Cover the Java services' own resilience patterns, if any (out of scope this run, noted §1).
- `C1`'s fix (§9) is ordering-based, not a real cross-table transaction (PostgREST doesn't expose one the way this code calls it) — a periodic sweep for tickets whose status doesn't match their supporting rows would catch anything this ordering fix doesn't (e.g. `C4`'s now-safe-but-still-imperfect case of a last-call failure leaving status stuck at "received" despite complete data).

## 9. Fixes applied and re-verified live: 16/16 checks passed, 0 failed

All 3 findings above were fixed and re-verified with the exact same real, live methodology as the original run — the real `CircuitBreaker`/`cache_check_node`/`background_orchestration`/`app.worker` code, real disposable Supabase tickets, a real local Redis server.

### What changed

**`clario-ml-sidecar/app/main.py` (`background_orchestration`) — fixes `C1`:** the `tickets.status`/`raw_graph_payload` update moved from the *first* statement in the persistence `try` block to the *last*, after every classification/draft/evaluation/resolution/human-review row has been written successfully. If anything upstream now fails, the status update never runs and the ticket simply stays in its prior status — it can no longer claim "resolved"/"escalated" while missing the data that would justify it. The generic `except Exception` log line also now includes the ticket id (previously it didn't, per the original finding).

**`clario-ml-sidecar/app/worker.py` — fixes `D1`/`D2`:** replaced the destructive `BRPOP` with the standard Redis "reliable queue" pattern: `BLMOVE` atomically moves a message from `ticket_queue` into a new `ticket_queue:processing` list, where it stays until a `finally` block removes it once this process has actually had a chance to react (success or an internally-handled failure). A process death between the `BLMOVE` and that `finally` (crash, OOM, restart, deploy) now leaves the message sitting in `ticket_queue:processing` instead of gone — a new `_recover_stale_messages()`, run once at worker startup, moves anything left there by a previous crashed run back onto the main queue for retry.

**`clario-ml-sidecar/app/graph/cache_check_node.py` — fixes `B1b`:** now calls `get_breaker("chroma_rag")` — the same breaker `retrieve_context()` (`app/tools/rag_tool.py`) already reports to, since both talk to the same ChromaDB instance — checking `allow_request()` before attempting the query and calling `record_success()`/`record_failure()` around it, instead of only the bare `try/except` it had before.

All three fixes were synced to `services/ai-orchestrator-service` (the full mirror of `clario-ml-sidecar` maintained elsewhere in this repo's testing history).

**Verification:** `pytest tests -q` in `clario-ml-sidecar`: 96 passed, 3 skipped (no regressions) - re-run after each fix.

### Live re-verification (real production Supabase, real local Redis)

Re-running `run_failover_tests.py` (extended with 2 new checks written specifically to verify the fixes — `C4`, the now-safe "failure on the last call" case, and `D3`, confirming the reliable-queue pattern doesn't leak on its happy path) against the fixed code:

```
=== SUMMARY: 16/16 checks passed ===
```

| Check | Before fix | After fix |
|---|---|---|
| `C1` failure on `ticket_drafts` (now runs *before* the status update) | FAIL — ticket ended up `status: resolved` with 1 classification, 0 drafts, 0 resolutions | **PASS** — `status: received`, 1 classification, 0 drafts, 0 resolutions (no false "resolved" claim) |
| `C4` *(new)* failure on `tickets.update` itself, now the *last* call | *(not applicable before the reorder)* | **PASS** — `status: received` but 1 classification, 1 draft, 1 resolution all correctly written — the safe failure direction |
| `D1` ticket in flight when the worker crashes | FAIL (by design — demonstrated raw `BRPOP`'s destructiveness) | **PASS** — the message survives in `ticket_queue:processing`, provably not lost |
| `D2` a fresh worker's startup recovery | *(not applicable before the reliable-queue pattern existed)* | **PASS** — `_recover_stale_messages()` requeues the crashed message for retry |
| `D3` *(new)* normal completion doesn't leak into the processing list | *(not applicable before)* | **PASS** — both lists empty afterward |
| `B1b` `cache_check_node` failures reported to the `chroma_rag` breaker | FAIL — breaker outcomes provably unchanged by 2 real `cache_check_node` failures | **PASS** — breaker outcomes provably changed |

One real bug surfaced by this re-verification itself: the first re-run reused `C2`'s and `D`'s test logic unchanged from before the fix, and both silently started testing the *wrong* thing — `C2` was still breaking the `tickets` table, which is now the *last* call instead of the first (so it stopped exercising "failure on the first call" as intended), and `D1`/`D2`/`D3` still called the old raw `BRPOP`, never touching the new `BLMOVE`/`PROCESSING_KEY`/`_recover_stale_messages()` code at all. Both were caught by inspecting the actual evidence values (not just the pass/fail flags) rather than trusting a green run at face value, and fixed by updating `C2` to break `ticket_classifications` (the real new first call), adding `C4` for the new last-call case, and rewriting Section D to exercise the real `app.worker` module directly.

Cleanup verified after the final run: 0 leftover canary tickets, 0 leftover test Redis keys. Full evidence in the current `failover_test_results.json` and `test-log.txt`.

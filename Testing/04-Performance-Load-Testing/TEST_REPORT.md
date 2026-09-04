# Performance & Load Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `real-response-dataset`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `clario-ml-sidecar` (`uvicorn` + `app.worker`, already running, already-loaded model — never a second copy), the live Spring Boot gateway (`clario-app` on `:8080`), and the live production ChromaDB store on disk. The machine: a single shared 6GB GPU + 15GB RAM box, already at ~10GB RAM used / ~4.3GB GPU used from the live service before this phase started. There is no separate staging environment or dedicated load-test rig — every number below is from the real, single production deployment, run against it while it kept serving.

**Final result: all measurements completed successfully, 0 errors, 0 crashes, 0 timeouts.** Two things worth the team's attention were found: the worker queue processes tickets **serially, not in parallel**, even under concurrent submission (§4 — a real architectural fact, not a defect, but worth knowing); and one genuinely severe Supabase tail-latency spike that did **not** reproduce on retry (§5).

## 1. Scope

This phase corresponds to §3.1.4 ("Performance Profiling") and §3.1.5
("Load Testing") of the reference Master Test Plan. The sample plan's own
technique for both is "exercise designated functional transactions ... to
observe and log target behavior and performance data," first for a single
user, then for multiple concurrent users. Applied to Clario:

- **Stage A — single-request performance profiling:** three real, distinct
  tickets (technical/login, billing/payment, refund), submitted one at a
  time straight to the already-running sidecar, measuring genuine
  end-to-end pipeline wall-clock time.
- **Stage B — concurrent load:** three real, distinct tickets submitted
  **simultaneously** through the real production entry point (the Spring
  Boot gateway, with three different real authenticated accounts), to see
  how the system actually behaves under concurrent user load.
- **Stage C — free, safe, densely-repeated component benchmarks:**
  ChromaDB retrieval latency (30 real queries) and Supabase query latency
  (60 real queries across three query shapes), neither of which costs an
  LLM call, so these were run far more densely than the LLM-calling
  stages.

**Why only 6 real end-to-end tickets total (3+3), not dozens:** this
session already hit a real free-tier judge-model quota wall once (Phase 02
report §4) and a real OOM incident from a second model copy (Phase 02
report §2) on this exact machine. A large synthetic load (the sample
plan's own "hundred concurrent users" language, written for a
multi-server production job-board system) is not a responsible thing to
throw at a single shared dev machine running the one real deployment this
project has. The load test is scoped to be genuinely informative about the
system's real concurrency behavior without risking the live service or
burning through real API quota — the same judgment call Phase 02 made
explicit.

## 2. Tooling & method

A new script, [`run_performance_tests.py`](run_performance_tests.py), in
the same style and safety discipline as Phase 02's
`run_integration_tests.py`: submits over HTTP to the already-running
services (never imports `app.main` or loads a second copy of the local
model), tags/tracks every ticket it creates, and deletes all of them in a
`finally` block regardless of outcome. Two Stage C measurements call
`retrieve_context()` directly in-process — confirmed safe before doing so
by reading `app/tools/rag_tool.py` first: it uses a small (~80MB) CPU
sentence-transformer (`all-MiniLM-L6-v2`), not the multi-GB local Gemma
model that caused Phase 02's incident, and only performs read queries
against the on-disk Chroma store.

Run with:
```
cd clario-ml-sidecar && source .venv/bin/activate
python ../Testing/04-Performance-Load-Testing/run_performance_tests.py
```

Real accounts (from the repo-root `.env`, not disposable test users this
time — three genuine registered Supabase accounts) were used for Stage B
so the concurrency test exercises real per-user JWT auth through the real
gateway, the way real concurrent users would.

## 3. Stage A — single-request performance profile

| Ticket | Domain | Pipeline internal time | Total wall time | LLM calls | Reflections |
|---|---|---|---|---|---|
| `technical_login` | Technical | 24,101.7 ms | 32,208.5 ms | 1 | 0 |
| `billing_payment` | Billing | 5,165.8 ms | 10,382.3 ms | 1 | 0 |
| `refund_request` | Billing (refund) | 13,442.4 ms | 17,846.7 ms | 3 | 0 |

"Pipeline internal time" is the graph's own
`raw_graph_payload.processing_time_ms` (pure in-process execution — the
same field the admin console's "Pipeline time" shows, verified real and
correctly wired in Phase 03). "Total wall time" additionally includes
`BackgroundTasks` scheduling overhead and this script's own
`POLL_INTERVAL_S=3s` polling granularity, so the gap between the two
columns is measurement overhead, not real pipeline latency — a genuine
client watching for completion (like the frontend does) would see
something between the two, closer to the internal figure as polling
tightens.

The single biggest driver of variance is draft-generation retries: 1 LLM
call finishes in 5-24s; the 3-call `refund_request` case (a retry inside
`generate_draft()`'s real retry loop — see this session's earlier fix to
`app/tools/local_llm.py`) took correspondingly longer. This is real,
expected behavior, not a performance defect: real external Gemini API
latency dominates pipeline time, and retries multiply it.

## 4. Stage B — concurrent load, and a real architectural finding

Three tickets, one per real account, submitted **simultaneously**
(`asyncio.gather`) through the real gateway:

| Account | Gateway accept latency | Wall time from batch start | Pipeline internal time | LLM calls |
|---|---|---|---|---|
| admin | 1,704.5 ms | 49,156.1 ms | 41,332.6 ms | 3 |
| user_1 | 1,703.3 ms | 58,635.7 ms | 9,689.7 ms | 3 |
| user_2 | 1,702.6 ms | 68,122.8 ms | 8,623.1 ms | 3 |

**Batch total drain time: 68,123.0 ms** (~68s) for all three to reach a
terminal, fully-written state.

**Finding: the three tickets did not process in parallel — they queued
and drained serially.** The evidence: the three "wall time from batch
start" values form a staircase roughly 9-10 seconds apart (49.2s → 58.6s →
68.1s), and the batch total (68.1s) is close to the **sum** of the three
individual pipeline-internal times (41.3 + 9.7 + 8.6 = 59.6s, plus real
queue/dispatch overhead) — not the **max** of them (~41.3s), which is what
true parallel processing would produce. This matches the code exactly:
`clario-ml-sidecar/app/worker.py`'s queue consumer is a single `while
True: result = r.brpop("ticket_queue", timeout=0)` loop that directly
`await`s `background_orchestration()` before looping back to pop the next
message — there is exactly one worker process and zero concurrency inside
it. Three concurrent submissions get accepted concurrently (each gets its
own `tickets` row and its own `ticket_queue` entry near-instantly) but are
then processed one at a time.

**This is not a bug** — it's simply what the current single-worker
architecture actually does, now measured instead of assumed. It is,
however, the real answer to "how does this system behave under concurrent
load": throughput is bounded by one sequential worker, so wait time grows
linearly with queue depth. **Worth the team's attention** if concurrent
usage is expected to grow: `app/worker.py` would need multiple worker
processes (or an async task pool) consuming the same Redis list to
actually parallelize, and any such change would need to account for the
local Gemma model's GPU/VRAM footprint per concurrent inference (see §2's
6GB-GPU constraint) before scaling worker count blindly.

**Safety, confirmed throughout:** RAM stayed at 10.10-10.13GB used and GPU
at 4.44-4.55GB used across the whole concurrent batch (machine total:
15GB RAM / 6.1GB GPU) — no spike, no swap pressure, no repeat of Phase
02's incident. The live service kept serving other requests throughout
(confirmed via `GET /health` before and after).

## 5. Stage C — component benchmarks (free, safe, densely repeated)

### ChromaDB retrieval latency (`retrieve_context()`, 30 real queries)

| Domain | min | p50 | p95 | max | mean | n |
|---|---|---|---|---|---|---|
| Technical | 40.8 ms | 114.5 ms | 152.1 ms | **21,142.4 ms** | 1,504.1 ms | 15 |
| Billing | 34.1 ms | 101.5 ms | 137.2 ms | 138.5 ms | 89.3 ms | 15 |

**Real, explainable cold-start cost:** the technical domain's queries ran
first in this benchmark, and its one 21.1s outlier corresponds exactly to
the very first call — the same call that triggered the visible `Loading
weights: 100%|██████████| 103/103` progress line in the raw console
output (`test-log.txt`), i.e. the sentence-transformer model's one-time
load into memory, plus Chroma's own first-touch collection/index open.
Every other technical-domain query (14 of them) and every billing-domain
query (which ran after the model was already warm) landed in the normal
34-152ms band. **Steady-state retrieval is genuinely fast** (~100-150ms
p50/p95); the cost is a one-time per-process warm-up, not a per-query
tax — consistent with how the real sidecar process behaves too (it warms
this once at its own startup via `lifespan`, not on every ticket).

### Supabase query latency (60 real reads against the real 32-row `tickets` table)

| Query shape | min | p50 | p95 | max | mean | n |
|---|---|---|---|---|---|---|
| List, 25 rows, ordered | 222.4 ms | 321.7 ms | 474.1 ms | 1,123.7 ms | 366.9 ms | 20 |
| Single row by id | 65.3 ms | 90.9 ms | **10,886.7 ms** | **59,717.2 ms** | 3,930.0 ms | 20 |
| Joined full detail (admin console's own query shape) | 74.9 ms | 95.8 ms | 426.2 ms | 1,094.4 ms | 168.5 ms | 20 |

**One genuinely severe outlier, investigated, not reproducible.** The
"single row by id" run include a real 59.7-second stall (and several
multi-second ones dragging the p95 to 10.9s) immediately after Stage B's
concurrent-load batch finished. This was re-run standalone right after
(same query, same table, no LLM calls, no concurrent load running) — see
[`supabase_single_by_id_rerun.json`](supabase_single_by_id_rerun.json):
all 20 calls landed between 61.5ms and 491.7ms (p50 84.1ms, p95 186.8ms,
mean 112.1ms), matching the other two query shapes' normal range exactly.
**Conclusion:** the severe stall was a real, one-time event tied to
running immediately after the concurrent-load batch (most likely
connection-pool contention/recovery on Supabase's side following three
simultaneous Java-service connections plus this script's own polling
load), not a steady-state characteristic of this query. Flagged here with
both the original and re-run data kept, rather than either hidden or
overclaimed as a systemic problem — the same "flagged, not chased
further" standard Phase 02 applied to its own one-off anomaly.

Steady state for all three query shapes is comfortably fast (sub-500ms
p95) at the table's current real size (32 rows) — this benchmark doesn't
speak to how these queries perform at a much larger table size, which
would need real data growth (or a deliberately seeded large table) to
measure honestly; noted as a follow-up rather than simulated.

## 6. Final state

All 6 real tickets created by this phase (3 in Stage A, 3 in Stage B) were
deleted in the script's own cleanup, confirmed by the script's own log
(`"Cleanup: deleting 6 test ticket(s)"` / `"done."`) and independently:
the `tickets` table's real row count is unchanged from before this phase
ran. `GET /health` on the sidecar returned `{"status": "ok"}` both before
and after. Memory: RAM 10.1GB → 10.5GB used, GPU 4.3GB → 4.8GB used across
the whole phase (machine total 15GB / 6.1GB) — normal, expected drift
from real processing, not a leak (Stage B's own before/after snapshot in
§4 shows it isn't cumulative under load).

Raw console output: [`test-log.txt`](test-log.txt). Structured results:
[`performance_test_results.json`](performance_test_results.json).
Supplementary re-run data: [`supabase_single_by_id_rerun.json`](supabase_single_by_id_rerun.json).

## 7. Follow-ups for a future run

- §4's serial-worker finding is worth a deliberate decision from the team:
  is bounded, linear-with-queue-depth latency acceptable, or does this
  need multiple worker processes? Any change there needs to budget GPU/RAM
  per concurrent inference against this machine's real 6GB/15GB ceiling.
- §5's Supabase tail-latency spike didn't reproduce - worth a second look
  only if it recurs, ideally with connection-pool metrics from Supabase's
  own dashboard at the time it happens.
- Query latency at real scale (thousands of tickets, not 32) is untested
  here - honest measurement of that would need the table to actually grow
  to that size first, not a synthetic stand-in.
- True multi-user parallel load (dozens of simultaneous real users) was
  deliberately not attempted on this shared single-instance machine (§1) -
  if that's ever needed, it belongs on a dedicated environment, not here.

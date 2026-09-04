# JMeter Basic Performance Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `main`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `next dev` server (`:3000`), and a locally-run `clario-ml-sidecar` (`:8600`). Tooling: Apache JMeter 5.6.3, downloaded locally (no system install) and run in non-GUI mode (`-n`) with the HTML dashboard report generator (`-e -o`).

**Result: 250 samples, 0 errors (clean run).** A second run executed concurrently with the full Testing/08-Selenium-Functional-Testing browser suite showed 1 timeout out of 250 (0.4%) under that real added contention — both runs are reported below since the contention itself is a real, honest data point about this shared environment, not a flaw in the test.

## 1. Scope and tool choice

Maps to "Basic Performance Testing" in the assigned tool table, which listed four options: JMeter, HP LoadRunner, Gatling, BlazeMeter. **JMeter was used**:
- **HP LoadRunner** is commercial/licensed enterprise software - not installable in this environment, and not free even outside it.
- **BlazeMeter** is a paid cloud service that *runs* JMeter test plans at scale - the `.jmx` file built here is the more fundamental artifact either way, and is what BlazeMeter would consume if that became available later.
- **Gatling** is a legitimate free alternative, not chosen only because JMeter is the more universally-taught tool for this kind of assignment.

**Deliberately "basic":** two endpoints, modest concurrency (10 and 5 threads), no ramping to failure or capacity search. Full load/stress testing of the LangGraph pipeline itself under sustained/heavy concurrency is already [`Testing/04-Performance-Load-Testing`](../04-Performance-Load-Testing/)'s job - this phase exists to demonstrate JMeter specifically, on endpoints light enough to run quickly and repeatably.

## 2. Test plan

`clario-basic-performance.jmx` - two Thread Groups:

| Thread Group | Target | Threads × Loops | Auth |
|---|---|---|---|
| Sidecar Health Check Load | `GET http://127.0.0.1:8600/health` | 10 × 20 = 200 requests | none |
| Staff Ticket List Load | `GET http://localhost:3000/api/tickets` | 5 × 10 = 50 requests | `Authorization: Bearer ${__P(authToken,)}` |

Each sampler has a Response Assertion requiring HTTP 200. `authToken` is a real, disposable staff-account JWT supplied at runtime via `-JauthToken=...` (never hardcoded in the committed `.jmx`).

## 3. Results

### Clean run (no other test suite running concurrently)

| Label | Samples | Errors | Mean | Median | p90 | p95 | Max |
|---|---|---|---|---|---|---|---|
| `GET /health` | 200 | 0 (0%) | 6.6 ms | 3 ms | 5 ms | 5 ms | 154 ms |
| `GET /api/tickets` | 50 | 0 (0%) | 1197 ms | 660 ms | 1708 ms | 7990 ms | 8292 ms |
| **Total** | **250** | **0 (0%)** | 245 ms | 3 ms | 662 ms | 811 ms | 8292 ms |

`/health` is trivially fast and consistent, as expected for a route that does no I/O. `/api/tickets` is a real Supabase query joining `ticket_drafts`/`ticket_classifications`/`resolutions` for every row in the table (see `frontend/src/app/api/tickets/route.ts`) - its median (660ms) is reasonable, but the p95/max jump to ~8s shows real tail-latency variance even under this modest, uncontended load. That variance is consistent with what Testing/04's own report already measured for Supabase query performance under this table's current size - this run corroborates it from a different tool, not a new finding.

### Concurrent-contention run (same plan, run while Testing/08's full Selenium suite was executing against the same live servers)

| Label | Samples | Errors | Mean | Median | p99 | Max |
|---|---|---|---|---|---|---|
| `GET /health` | 200 | 0 (0%) | 4 ms | 2 ms | 166 ms | 169 ms |
| `GET /api/tickets` | 50 | 1 (2%) | 2855 ms | 1333 ms | 15052 ms | 15052 ms (timeout) |
| **Total** | **250** | **1 (0.4%)** | 574 ms | 2 ms | 9778 ms | 15052 ms |

The one failure was a genuine `SocketTimeoutException` at exactly the configured 15s response timeout - not an application error response, a real client-side timeout under real resource contention (this dev machine was simultaneously running a real headless-Chrome-driven Selenium suite plus this JMeter run plus the already-running `clario-ml-sidecar`/frontend dev servers). This is reported transparently rather than discarded, because it's a legitimate observation: this system's single-machine dev environment has a real, measurable capacity ceiling, and `/api/tickets`'s query cost is what shows it first under contention - consistent with Testing/04's finding about this same route.

## 4. No fixes needed

Unlike Phases 07/09, this phase found no application bugs - both runs' `/health` and (in the clean run) `/api/tickets` results are within reasonable bounds for a single-instance dev deployment with unoptimized `/api/tickets` query joins, a fact already known and reported by Testing/04. The one error observed was a real, disclosed environmental effect (concurrent load from this session's own other test suites), not a defect to fix.

## 5. How to reproduce

```bash
Testing/10-JMeter-Performance-Testing/run_tests.sh
```
Or open `report/index.html` after a run for the full interactive HTML dashboard (graphs, response-time-over-time, per-label breakdowns) JMeter generates from `results.jtl`.

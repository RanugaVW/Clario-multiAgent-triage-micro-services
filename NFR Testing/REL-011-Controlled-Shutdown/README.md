# REL-011 — Controlled System Shutdown

**Status before:** ⚠️ Deviates — no graceful shutdown in any Java service; ticket hand-off to Redis ran on daemon threads and inside the DB transaction.
**Status after:** 🟡 Partial → the three Java services shut down in a controlled way; the Python orchestrator (`scheduler.shutdown(wait=False)`) is untouched.

## What was wrong

1. **No graceful HTTP shutdown.** SIGTERM cut in-flight requests.
2. **The queue hand-off could be lost.** After a ticket was saved and answered `202`, the push to the Redis
   `ticket_queue` ran via `CompletableFuture.runAsync` — daemon threads. A deploy landing in that window killed the JVM
   with a ticket that was in the database but would never reach the AI pipeline.
3. **The hand-off was submitted *inside* the `@Transactional` method**, i.e. before commit. Two failure modes: the AI worker
   could be handed a ticket not yet visible, and a save that later rolled back would still leave a queued message
   (a "ghost" ticket).
4. **Docker would have undone any of it.** `docker compose stop` sends SIGTERM and then SIGKILL after 10 s by default.

## What changed

- **`server.shutdown=graceful`** + `spring.lifecycle.timeout-per-shutdown-phase` (`SHUTDOWN_TIMEOUT`, default 20 s) — all three services.
- **`TicketDispatcher`** (`ticket-core-service`, `agent-review-service`) replaces the fire-and-forget async call. It is a
  Spring `SmartLifecycle` at phase 0: stopped **before** the Redis/DB beans are destroyed, and **after** the web server has
  finished draining requests — so every hand-off those requests made is still pending when its drain starts.
  - `stop()` waits for running *and queued* work (`DISPATCH_DRAIN_TIMEOUT_SECONDS`, default 20 s); if that expires it
    abandons the remainder **and logs how many** — it can never hang shutdown.
  - Work submitted while stopping runs **inline** rather than being dropped.
  - Non-daemon threads, bounded queue with caller-runs (backpressure, not unbounded memory).
  - A failing task is logged and doesn't kill the worker thread.
  - It also carries the caller's correlation ID across (moved here from `TicketService`; behaviour unchanged, still tested).
- **Enqueue only after commit.** `TicketService` registers the dispatch with `TransactionSynchronization.afterCommit`
  (immediate when no transaction is active). A rolled-back save can no longer enqueue anything.
- **`stop_grace_period: 45s`** on the three Java services in `docker-compose.yml` (must exceed web drain 20 s + dispatch drain 20 s).

## No Supabase changes needed.

## Tests (CI-like: `.env` hidden, Redis unreachable)

| Test | Verifies |
|---|---|
| `GracefulShutdownTest` (api-gateway) | Real app, real filters, a slow downstream, context closed **mid-request**: graceful → client gets `200`; **control run with `server.shutdown=immediate` must not** (proves the test is sensitive) |
| `TicketDispatcherTest` (×2 services, 8 cases) | `stop()` blocks until in-flight work ends; queued work (50 tasks) is drained too; work after stop runs inline, not dropped; a never-finishing task can't hang shutdown and is reported; correlation ID reaches the worker and never leaks to a later task; a failing task doesn't stop later work; **closing a real Spring context waits for in-flight work** |
| `TicketServiceTransactionTest` (×2) | inside a transaction nothing is enqueued until commit; a rollback enqueues nothing; outside a transaction it is immediate |
| `ShutdownConfigTest` (×3) | shipped config is graceful; `docker-compose` `stop_grace_period` is set and **greater than the sum of the drains** (reads both real files) |

**Mutation checks** (each reverted): `stop()` using `shutdownNow()` instead of draining → 4 failures; dispatching inside the
transaction again → 2 failures; `stop_grace_period` cut to 15 s → the consistency test fails.

```
api-gateway:           Tests run: 39, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 70, Failures: 0, Errors: 0 -- BUILD SUCCESS
ticket-core-service:   Tests run: 73, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## What's still open

- **Python `ai-orchestrator-service`**: `scheduler.shutdown(wait=False)` deliberately doesn't wait for in-flight jobs, and
  the worker's handling of a message mid-LangGraph run on SIGTERM is unchanged (the existing Redis `BLMOVE`/processing-list
  recovery is what protects it). Not modified — its dependencies can't be installed in this sandbox.
- **Graceful HTTP draining is framework behaviour.** It is proven end to end for the gateway (above) and configured
  identically for the other two, but the two ticket services have no equivalent live "in-flight request" test because they
  need a database.
- **A drain that times out still abandons work** (logged). The durable fix for that case is an outbox table
  (persist the pending hand-off with the ticket and have a poller enqueue it) — needs a Supabase table, so it is not built here.
- Ticket-creation writes to other stores (Python side, Next.js API routes) are still separate non-transactional calls (REL-004).

# DC-021 — Logging Constraints (correlation IDs, no sensitive data in logs)

**Status before:** ⚠️ Deviates — no correlation ID in any application log line (the only per-request ID
went to the optional tracing relay), and the gateway logged a decoded JWT header at WARN on every request.
**Status after:** 🟡 Partial — closed for the three Java services and the gateway→downstream hop; the Python services are untouched.

## What was wrong

1. Nothing tied a log line to the request that caused it, so "the ticket failed at 14:02" could not be
   traced through gateway → ticket service → async dispatch.
2. `api-gateway/JwtDebugFilter` printed `=== JWT HEADER: {...} ===` at WARN for every authenticated request.
3. `api-gateway` shipped with `logging.level.org.springframework.security=DEBUG` and
   `...cloud.gateway=DEBUG` as the *default*.

## What changed

- **`CorrelationIdFilter`** (all three Java services, highest filter precedence so it wraps Spring Security):
  reads `X-Correlation-Id`, or generates a UUID; puts it in the SLF4J MDC; sets it on the response; removes it
  in `finally` (servlet threads are pooled — a leaked value would be attributed to an unrelated request).
  - **Untrusted input is validated.** Only `[A-Za-z0-9._-]{1,64}` is honoured; anything else (CR/LF,
    spaces, markup, 65+ chars) is replaced with a fresh UUID, since the value lands in log lines and a header.
  - **Propagation.** The filter wraps the request so a *generated* ID is visible to whatever handles it next —
    at the gateway that is the proxy, so the downstream service receives the same ID.
  - **No duplicate header.** A downstream service echoes the header too; a response wrapper makes `addHeader`
    behave as `setHeader` for this one name, so the client sees one value, not `"id, id"`.
- **Log pattern** `logging.pattern.level=%5p [cid=%X{correlationId:-}]` in all three services.
- **MDC survives the async hop.** `TicketService` dispatches to Redis on a `CompletableFuture` thread; MDC is
  thread-local, so it is now copied across explicitly. Without it, a dispatch failure — the log line an operator
  most needs — carried no ID.
- **`JwtDebugFilter` deleted.**
- **Gateway log levels** default to INFO; DEBUG is opt-in via `LOG_LEVEL_SECURITY` / `LOG_LEVEL_GATEWAY`.

## No Supabase changes needed.

## Tests (CI-like: `.env` hidden, Redis unreachable)

| Test | Verifies |
|---|---|
| `CorrelationIdFilterTest` (×3 services) | generated when absent; well-formed inbound ID honoured and echoed once; CR/LF-injected and over-long IDs replaced; log lines from the request carry the ID; ID does not leak to the next request on the same thread |
| `TicketServiceCorrelationTest` (ticket-core, agent-review) | async Redis-dispatch failure is logged **with the caller's correlation ID** |
| `CorrelationIdPropagationTest` (api-gateway) | against a real stub downstream server through the real Spring Cloud Gateway proxy: client ID reaches downstream; a gateway-*generated* ID is the one downstream receives; response carries it exactly once; rejected (401) requests also get an ID; no token material in any log line; shipped config is INFO-by-default and includes the ID in the pattern |

**Mutation checks** (each change made exactly one test fail, then was reverted): removing the async MDC copy;
removing the request wrapper (generated ID no longer reaches downstream); removing the response de-duplication
wrapper (header doubled).

```
api-gateway:           Tests run: 30, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 41, Failures: 0, Errors: 0 -- BUILD SUCCESS
ticket-core-service:   Tests run: 44, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## What's still open

- **Python services** (`ai-orchestrator-service`, `nlp-classifier-service`, `voice-to-text-service`) have no
  correlation ID, and DC-021 asks for a consistent format across *all* services. Not changed — their test
  environments can't be run in this sandbox.
- **The Redis payload does not carry the ID** to the AI worker, so a trace stops at the queue. Adding a field is
  backward compatible but changes a cross-service contract that couldn't be tested here.
- **A known sensitive-data leak remains in the Python orchestrator:** `main.py` logs the full unredacted ticket
  state on failure (`logger.exception("...state=%r", initial_state)`). Not fixed for the same reason.
- Logs remain plain text, not JSON ("structured logging" is satisfied only loosely by `key=value` on the audit loggers).

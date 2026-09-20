# REL-002 — Fault Tolerance

**Status before:** 🟡 Partial — solid in Python (circuit breakers, try/except around every external call); Java controllers had no equivalent, and a DB/Redis failure fell through to Spring's default unhandled-exception response.
**Status after:** 🟡 Partial → the synchronous-path gap is closed; one related gap is identified but intentionally left open (see below).

## What was wrong

Two separate problems in `ticket-core-service` and `agent-review-service`:

1. **Synchronous path:** `TicketController.createTicket`/`getUserTickets` call
   `ticketRepository`/`ticketService` directly. If the DB write or read threw (connection
   loss, timeout), the exception propagated uncaught to Spring's default error handling —
   a generic response with **no log line anywhere**, so the failure was invisible to anyone
   operating the service.
2. **Async path:** `TicketService.dispatchToSidecar`'s Redis push was already wrapped in
   try/catch, but the catch block used `System.err.println(...)` — not a real logger, so the
   failure wasn't searchable, aggregatable, or alertable through any actual logging
   infrastructure.

## What changed

- Both `TicketController`s gained `@ExceptionHandler(DataAccessException.class)`: logs the
  real exception server-side via SLF4J, and returns a clean `503 Service Unavailable` with a
  generic, non-leaky message (does not echo the underlying exception's message, which could
  contain internal hostnames/connection strings).
- Both `TicketService`s now use a proper SLF4J `Logger` instead of `System.out`/`System.err`
  for the Redis-dispatch success/failure paths.

## No Supabase changes needed.

## Tests

Added to the existing `TicketControllerSecurityTest` in both services:

| Test | Verifies |
|---|---|
| `createTicket_whenDatabaseFails_returns503WithoutLeakingInternals` | A DB failure during ticket creation → 503, and the response body does **not** contain the raw exception message (tested by injecting a message containing an internal hostname and asserting it's absent from the JSON response) |
| `getTickets_whenDatabaseFails_returns503` | Same guarantee on the read path |

```
ticket-core-service:  Tests run: 12, Failures: 0, Errors: 0 -- BUILD SUCCESS (9 in TicketControllerSecurityTest, 3 pre-existing)
agent-review-service: Tests run: 9,  Failures: 0, Errors: 0 -- BUILD SUCCESS
```

Both test runs show the expected `ERROR ... Database failure while handling a ticket
request` log line — proof the failure is now actually recorded, not just swallowed.

## Known gap intentionally left open

If the **async** Redis dispatch fails (not the synchronous DB save), the ticket row is
already committed with `status = "received"` and there is currently no retry, dead-letter
queue, or status update to reflect that it never reached the AI pipeline — the ticket simply
never gets processed, silently, from the customer's point of view (though the failure is now
at least logged, per this fix). Fixing that properly means deciding on retry/backoff policy
and a new ticket status value, which touches ticket-lifecycle semantics (FR-006) and is out
of scope for this specific fault-tolerance pass — flagged here rather than fixed, so it isn't
lost.

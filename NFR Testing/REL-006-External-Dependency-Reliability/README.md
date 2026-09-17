# REL-006 — External Dependency Reliability

**Status before:** 🟡 Partial — circuit breakers + fallback existed on the Python side; no continuous dependency monitoring anywhere; and (newly discovered here) `agent-review-service` couldn't reach Redis **at all** in the real deployment.
**Status after:** 🟡 Partial → the newly-discovered Redis misconfiguration is fixed; general continuous dependency monitoring is still open.

## The bug found while implementing FR-061 (health checks)

`services/agent-review-service` has depended on `spring-boot-starter-data-redis` and used a
`StringRedisTemplate` since it was written, but **never had `spring.data.redis.host`/`port`
configured anywhere** — not in `application.properties`, not in `docker-compose.yml`'s
`agent-review-service` block (compare with `ticket-core-service`, which does set
`SPRING_DATA_REDIS_HOST=redis-broker` there). Spring's own default (`localhost:6379`) means
this service's Redis client tries to reach a broker on its *own* container, where nothing
listens — the real broker is the separate `redis-broker` container.

**Practical effect:** every ticket ever created through `agent-review-service`'s
`POST /api/tickets` silently never reached the Redis `ticket_queue`, and therefore never
reached `ai-orchestrator-service` or the AI pipeline at all. Before the REL-002 fix
(`NFR Testing/REL-002-Fault-Tolerance/`), this failure was swallowed by a bare
`System.err.println` that nothing was watching — so this bug had presumably been silently
dropping tickets since the service was written, undetected.

## The fix

`docker-compose.yml`:
```yaml
agent-review-service:
  environment:
    - SPRING_DATA_REDIS_HOST=redis-broker
    - SPRING_DATA_REDIS_PORT=6379
  depends_on:
    - redis-broker
```
Mirrored in `application.properties` for documentation/consistency with
`ticket-core-service`'s existing pattern (functionally redundant once the env vars are set —
Spring's relaxed property binding already maps `SPRING_DATA_REDIS_HOST` automatically — but
makes the setting discoverable by anyone reading the file instead of only the compose config).

## No Supabase changes needed — this was a `docker-compose.yml`/`application.properties` fix.

## Verification

This can't be end-to-end tested in this sandbox (no real Redis broker or Docker Compose
stack running here) — it's a configuration fix, not application logic, so there's no unit
test that would meaningfully exercise it. Verified instead by:
1. Reading `ticket-core-service`'s working equivalent side-by-side with
   `agent-review-service`'s previous (missing) configuration.
2. Confirming Spring Boot's documented relaxed-binding behavior for `SPRING_DATA_REDIS_HOST`
   → `spring.data.redis.host`.
3. All of `agent-review-service`'s existing tests still pass after the `application.properties`
   change (`Tests run: 11, Failures: 0, Errors: 0 -- BUILD SUCCESS`), confirming nothing else
   broke.

**Recommended manual verification once you have the real stack running:** `docker compose up`,
submit a ticket through whatever path routes to `agent-review-service`, and confirm it
actually appears in `ai-orchestrator-service`'s processing (or watch the Redis queue length)
— this is the one check in today's work I could not perform myself and would specifically
value you confirming.

## What's still open

General continuous background monitoring of external dependencies (not just "checked when
someone calls health") remains unimplemented — see
`NFR Testing/SUP-004-Health-Monitoring/README.md`.

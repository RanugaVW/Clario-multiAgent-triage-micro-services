# FR-061 — Health Check Service

**Status before:** 🟡 Partial, deviates by service — Python services had a static `{"status":"ok"}` stub; **Java services had no health endpoint at all**, and `api-gateway`'s security config permitted `/actuator/**` for an actuator that wasn't even a dependency (a dead rule — the path 404'd before security had anything to protect).
**Status after:** ✅ Implemented on all three Java services.

## What was wrong

`services/ticket-core-service` and `services/agent-review-service` had zero
`spring-boot-starter-actuator` dependency and no `/health`-equivalent route of any kind.
`services/api-gateway` had the dependency-less same gap, masked by a security rule
(`.requestMatchers("/actuator/**", "/error").permitAll()`) that referenced a feature that
didn't exist yet.

## What changed

All three services now depend on `spring-boot-starter-actuator`, exposing exactly one
endpoint publicly: `GET /actuator/health`. Two deliberate scoping decisions:

1. **Only `health` is exposed** (`management.endpoints.web.exposure.include=health`) — not
   the full actuator surface (env, beans, mappings, etc.), which would be a real information
   disclosure risk if left open.
2. **`show-details=never`** — the endpoint returns the aggregate `UP`/`DOWN` status only, not
   a breakdown naming which component failed or its connection string. `ticket-core-service`
   and `agent-review-service` aren't exposed outside the Docker network at all (no `ports:`
   mapping in `docker-compose.yml`), and `api-gateway` *is* the one publicly reachable
   service, so the conservative default was applied everywhere rather than judged
   case-by-case.

The security config change needed to make this reachable *without* a JWT (container
health probes have no token to present) is in `SecurityConfig.java`:
`.requestMatchers("/error", "/actuator/health", "/actuator/health/**").permitAll()` —
`api-gateway` already had the equivalent rule; `ticket-core-service`/`agent-review-service`
needed it added.

Because both `ticket-core-service` and `agent-review-service` have a `DataSource`, Spring
Boot Actuator **automatically** contributes a real database connectivity check to the
aggregate status — this isn't hand-rolled, it's the same mechanism that would report `DOWN`
if Postgres became unreachable. That's a genuine, not cosmetic, health signal.

## No Supabase changes needed.

## A real bug found and fixed while doing this

Writing the H2 test datasource for `agent-review-service` required looking closely at its
Redis configuration, which turned up something unrelated but serious:
`services/agent-review-service` had **no `spring.data.redis.host`/`port` configured
anywhere** (not in `application.properties`, not in `docker-compose.yml`), so its Redis
client defaulted to `localhost:6379` — which is empty inside its own container in the real
deployment (the actual broker runs in a separate `redis-broker` container). Every ticket
created through this service's `/api/tickets` endpoint would silently never reach the AI
pipeline. Fixed in `docker-compose.yml` (added `SPRING_DATA_REDIS_HOST=redis-broker` /
`SPRING_DATA_REDIS_PORT=6379` + `depends_on: redis-broker`, matching `ticket-core-service`)
and documented the same default in `application.properties` for consistency. See
`NFR Testing/REL-006-External-Dependency-Reliability/README.md` for the full writeup — it's
filed there because it's fundamentally a REL-006 finding, not a health-check one, even though
this is where it was discovered.

## Tests

New `HealthEndpointTest` (full `@SpringBootTest`, real HTTP call) in all three services:

| Test | Verifies |
|---|---|
| `healthEndpoint_isReachableWithoutAuthentication_andReportsUp` | `GET /actuator/health` → 200, body contains `"status":"UP"`, and (Java services with a DB) does **not** contain the Supabase hostname |
| `otherEndpoints_stillRequireAuthentication` (ticket-core/agent-review only) | Confirms permitting `/actuator/health` didn't accidentally open anything else — `/api/tickets` still 401s with no token |

`ticket-core-service` and `agent-review-service` needed an in-memory H2 datasource for
tests (`src/test/resources/application.properties`) so this full-context test never touches
the real Supabase Postgres instance, and `management.health.redis.enabled=false` for tests
only, since this sandbox has no real Redis reachable and re-verifying Spring's own
well-tested Redis health indicator isn't this project's job.

```
ticket-core-service:  Tests run: 14, Failures: 0, Errors: 0 -- BUILD SUCCESS (2 new + 12 pre-existing)
agent-review-service: Tests run: 11, Failures: 0, Errors: 0 -- BUILD SUCCESS (2 new + 9 pre-existing)
api-gateway:          Tests run: 8,  Failures: 0, Errors: 0 -- BUILD SUCCESS (1 new + 7 pre-existing)
```

## What's still open

- No health *dashboard* or alerting consumes this endpoint yet (FR-050/FR-062's
  "administrator is notified" / "operational dashboard" halves are unaddressed) — this fix
  makes the signal exist and be trustworthy; wiring it into monitoring is separate work.
- The Python services' `/health` remains a static stub, unchanged by this fix.

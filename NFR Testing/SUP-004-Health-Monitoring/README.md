# SUP-004 — Health Monitoring

**Status before:** 🟡 Partial — Python stubs existed; Java services had no health endpoint or dependency status of any kind.
**Status after:** 🟡 Partial → the endpoint-existence and dependency-status gaps are closed for all three Java services; visibility "through administrative interfaces" is still unaddressed.

Full implementation details: `FR Testing/FR-061-Health-Check-Service/README.md`.

## Acceptance criteria check

- "Health endpoints shall be available for major application services" — ✅ now true for
  `api-gateway`, `ticket-core-service`, `agent-review-service`.
- "Internal dependency status shall be monitored continuously" — 🟡 Partial. The database
  check runs whenever `/actuator/health` is *called*, which is "continuously" only in the
  sense that a poller could call it continuously — nothing in this fix adds a background
  poll independent of a caller hitting the endpoint. That distinction matters and isn't
  papered over here.
- "Service availability shall be visible through administrative interfaces" — 🔴 still not
  implemented. Nothing in the admin frontend (`frontend/src/app/admin/page.tsx`) queries
  these new endpoints; the "system health" cards there remain hardcoded literals
  (`status="Healthy" uptime="99.9%"`), untouched by this fix.
- "Health monitoring shall support automated operational alerts" — 🔴 still not implemented.

## No Supabase changes needed.

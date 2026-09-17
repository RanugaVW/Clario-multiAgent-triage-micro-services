# FR-002 — Authorization

**Status before:** 🟡 Partial (spoofable — see `docs/SRS_Compliance_Report.md` §2)
**Status after:** ✅ Implemented (for the two endpoints this requirement governs)

## What was wrong

`ticket-core-service` and `agent-review-service` both exposed `GET /api/tickets` and `POST /api/tickets`
with **no Spring Security at all**. Authorization was based entirely on a client-supplied
`X-User-Id` HTTP header:

```java
// before — services/ticket-core-service/.../TicketController.java
public ResponseEntity<List<Ticket>> getUserTickets(
        @RequestHeader(value = "X-User-Id", required = false) String userId) {
    if (userId == null) userId = "00000000-0000-0000-0000-000000000000";
    return ResponseEntity.ok(ticketRepository.findByUserId(UUID.fromString(userId)));
}
```

Any authenticated (or even unauthenticated) caller could read or create tickets as an
arbitrary other user simply by setting that header. `POST` on `ticket-core-service` did at
least decode the JWT's `sub` claim, but with **zero signature verification** — a
base64-encoded fake payload was as good as a real token.

## What changed

Both services now:
1. Depend on `spring-boot-starter-security` + `spring-boot-starter-oauth2-resource-server`.
2. Carry a `SecurityConfig` (mirroring the working pattern already in `api-gateway`) that
   verifies the Supabase-issued JWT's signature (HS256 legacy secret, falling back to ES256
   via Supabase's JWKS endpoint) and requires authentication on every route.
3. Derive the caller's identity **exclusively** from `@AuthenticationPrincipal Jwt jwt` /
   `jwt.getSubject()` — the `X-User-Id` header is no longer read anywhere in either
   controller.

Files: `services/ticket-core-service/src/main/java/com/clario/{config/SecurityConfig.java,controllers/TicketController.java,ClarioApplication.java}`,
`services/ticket-core-service/src/main/java/com/clario/config/JpaConfig.java` (new — see note below),
and the mirror set under `services/agent-review-service/...`.

**Incidental fix required to make this testable:** `ClarioApplication` had
`@EnableJpaRepositories` declared directly on the `@SpringBootApplication` class. Spring's
`@WebMvcTest` slice can exclude auto-configuration but not annotations on the root
config class itself, so every attempt to write a pure web-layer security test dragged in
the full JPA/`EntityManagerFactory` stack and failed to start. Moved the annotation into its
own `JpaConfig` class (zero behavior change in production — same base package, same
component scan) so slice tests can exclude it as intended.

## No Supabase changes needed

Both services already load `JWT_SECRET` from the same `.env` file `api-gateway` uses
(`docker-compose.yml` → `env_file: ./clario-app/.env`), and the JWKS URI is Supabase's public
endpoint. Nothing to run in the Supabase SQL editor for this fix.

## Tests

`services/ticket-core-service/src/test/java/com/clario/controllers/TicketControllerSecurityTest.java`
`services/agent-review-service/src/test/java/com/clario/controllers/TicketControllerSecurityTest.java`

| Test | Verifies |
|---|---|
| `getTickets_withNoAuthorizationHeader_isRejected` | No token → 401, never reaches the controller |
| `getTickets_withMalformedToken_isRejected` | Garbage bearer token → 401 |
| `getTickets_withValidToken_usesSubjectFromToken_notSpoofedHeader` | A valid token for user A **plus a spoofed `X-User-Id` for user B** returns user A's tickets — the exact regression case for the original vulnerability |
| `createTicket_withValidToken_createsTicketForSubjectFromToken` | Ticket is created under the JWT's subject, ignoring any other supplied identity |
| `createTicket_withNoAuthorizationHeader_isRejected` | No token → 401 on write path too |

### Result (ticket-core-service)

```
./mvnw test
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0 -- TicketControllerSecurityTest
Tests run: 3, Failures: 0, Errors: 0, Skipped: 0 -- TraceEventPublisherTest (pre-existing, unaffected)
Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

### Result (agent-review-service)

```
./mvnw test -Dtest=TicketControllerSecurityTest
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

## Remaining scope not covered by this fix

- No role-based (admin/agent/customer) distinction was added to these two endpoints, because
  neither endpoint needs one — both are strictly "act on your own resource," which is exactly
  what deriving identity from the verified JWT now guarantees. Endpoints that *do* need
  role gating (if any get added to these services later) still need `hasRole(...)` checks on
  top of this.
- This does not touch the Next.js API routes that talk to Supabase directly
  (`frontend/src/app/api/tickets/route.ts`) — those are a separate code path, protected by
  Supabase RLS, out of scope for this specific fix.

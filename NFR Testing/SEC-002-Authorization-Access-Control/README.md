# SEC-002 — Authorization and Access Control (RBAC)

**Status before:** 🟡 Partial — RLS solid on the Supabase path, but a live IDOR on the Java services
**Status after:** ✅ Implemented for the affected endpoints; the IDOR is closed

See `FR Testing/FR-002-Authorization/README.md` for the full implementation writeup — this
file focuses specifically on the security/attack angle, since SEC-002 and FR-002 shared one
root cause and one fix.

## The vulnerability

`GET /api/tickets` and `POST /api/tickets` on both `ticket-core-service` and
`agent-review-service` trusted a client-supplied `X-User-Id` header outright, with no
verification that the header matched the caller's actual identity. Concretely, before this
fix:

```
curl -H "X-User-Id: <any-other-users-uuid>" http://ticket-core-service:8081/api/tickets
```
returned that other user's tickets — full stop, no authentication of any kind required.
This is a textbook Insecure Direct Object Reference (IDOR / OWASP API1:2023 Broken Object
Level Authorization).

## The fix

Both services now run a real Spring Security OAuth2 resource server filter chain
(`@EnableWebSecurity`, `anyRequest().authenticated()`), independently verifying the
Supabase-issued JWT's signature. The header is no longer read by either controller at all —
identity comes exclusively from the verified token's `sub` claim.

This was implemented as **independent verification in each service**, not just at the
gateway, because `ticket-core-service` and `agent-review-service` are reachable directly on
the Docker network (and on their own ports in local/dev runs) — a defense-in-depth posture,
not reliance on "requests only ever arrive via the gateway."

## Test evidence — the actual attack, reproduced and disproven

`TicketControllerSecurityTest.getTickets_withValidToken_usesSubjectFromToken_notSpoofedHeader`
sends a request with:
- a **valid, correctly-signed JWT** for user A, and
- the **spoofed `X-User-Id` header set to user B**

and asserts the repository is queried for user A's tickets and is **never** queried for user
B's (`verify(ticketRepository, never()).findByUserId(spoofedUserId)`). This is the exact
reproduction of the original exploit, now failing to work.

```
ticket-core-service: Tests run: 5, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service: Tests run: 5, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## A second bug found while writing this test

The JWT decoder (in `api-gateway`, and copied into the two fixed services) threw a plain
`JwtException` when a token failed both HS256 and ES256 verification. Spring Security's
`JwtAuthenticationProvider` only maps `BadJwtException` to a 401; any other `JwtException`
becomes an `AuthenticationServiceException`, which is treated as a server-side failure, not
"the client sent an invalid token" — meaning a forged or malformed token was not reliably
producing a clean 401 in any of the three services, including `api-gateway`, which wasv
already relying on this exact decoder in production. Fixed in all three
(`throw new BadJwtException(...)` instead of `throw new JwtException(...)`), with a unit
test added directly against `api-gateway`'s decoder (`SecurityConfigTest`, previously had
zero tests for this class):

```
api-gateway: Tests run: 7, Failures: 0, Errors: 0 -- BUILD SUCCESS
  (1 new: SecurityConfigTest; 6 pre-existing, unaffected)
```

## No Supabase changes needed for this fix.

## What SEC-002 still doesn't cover

- No role-based (`admin`/`agent`/`customer`) authorization was added — see the note in the
  FR-002 report. These two endpoints don't need it; other endpoints, if added later, will.
- Endpoints served directly by the Next.js app talking to Supabase are unaffected by this
  change and rely on Supabase RLS instead (already found to be correctly enforced, 23/23
  passing per `Testing/05-Security-Access-Control-Testing/`).

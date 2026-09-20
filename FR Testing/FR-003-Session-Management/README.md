# FR-003 — Session Management

**Status before:** 🟡 Partial — gateway validated tokens correctly; downstream services did not.
**Status after:** 🟡 Partial → mostly closed, see caveat below.

Full implementation details: `FR Testing/FR-002-Authorization/README.md`.

## What this fix closes

`ticket-core-service` and `agent-review-service` previously accepted **any** bearer token
(or none at all, on `GET`) without checking its signature or expiry. They now run the same
JWT verification as `api-gateway`, so an expired or tampered access token is rejected with
401 at both of these services, not just at the gateway edge.

Covered by the same tests as FR-002:
`getTickets_withMalformedToken_isRejected`, `getTickets_withNoAuthorizationHeader_isRejected`
(both services, both passing — see FR-002 report for the full run output).

## What's still open

Session *issuance* and *refresh* (access/refresh token lifecycle) remain entirely delegated
to the Supabase Auth SDK on the frontend — this fix only closes the "does every backend
service actually check the token it's handed" gap. That's the correct scope for this item;
token issuance itself is an accepted architectural decision (see
`docs/SRS_Compliance_Report.md` §11).

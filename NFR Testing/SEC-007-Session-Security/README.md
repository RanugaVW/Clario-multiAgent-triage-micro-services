# SEC-007 — Session Security

**Status before:** 🟡 Partial — enforced at the gateway edge only.
**Status after:** 🟡 Partial → most of the gap closed.

Full implementation details: `NFR Testing/SEC-002-Authorization-Access-Control/README.md`.

## What closed

"Expired or invalid tokens shall be rejected" now holds at `ticket-core-service` and
`agent-review-service` too, not just at `api-gateway`. Verified by
`getTickets_withMalformedToken_isRejected` in both services' test suites (401, not a
silently-accepted request).

## What's still open

Access-token expiry and refresh-token rotation policy are still entirely Supabase's, which
is the accepted architecture per `docs/SRS_Compliance_Report.md` §11. This fix is about
*downstream services actually checking* the token, not about who controls its lifecycle.

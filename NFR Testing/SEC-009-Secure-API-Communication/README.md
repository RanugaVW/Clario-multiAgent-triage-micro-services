# SEC-009 — Secure API Communication

**Status before:** 🟡 Partial — gateway required auth; downstream services didn't re-verify.
**Status after:** 🟡 Partial → the re-verification gap is closed; request-audit logging is not.

Full implementation details: `NFR Testing/SEC-002-Authorization-Access-Control/README.md`.

## What closed

"Protected endpoints shall require authentication" and "Authorization shall be verified
before request execution" now hold independently at `ticket-core-service` and
`agent-review-service`, not only at `api-gateway`. This matters specifically because these
two services are reachable directly on the Docker network — a caller that could reach them
without going through the gateway previously bypassed all authentication entirely.

## What's still open

"API requests shall be logged for security monitoring" is not addressed by this fix — there
is still no structured request-audit log in either service (DEBUG-level Spring
Security/Gateway logs only). That remains open, tracked under FR-049/SEC-006 in
`docs/SRS_Compliance_Report.md`.

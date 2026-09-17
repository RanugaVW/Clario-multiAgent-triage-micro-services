# FR-007 — Ticket Retrieval

**Status before:** 🟡 Partial — spoofable on the Java path; real auth on the Next.js staff route.
**Status after:** ✅ Implemented on the Java path.

Full implementation details: `FR Testing/FR-002-Authorization/README.md` (same fix,
`GET /api/tickets` is literally the retrieval endpoint FR-007 describes).

## Acceptance criteria check

- "Authorized users can retrieve tickets" — ✅ a caller with a valid token gets their own
  tickets (`getTickets_withValidToken_usesSubjectFromToken_notSpoofedHeader`).
- "Unauthorized users cannot access restricted tickets" — ✅ no-token and malformed-token
  requests are rejected with 401 before reaching the repository at all.
- "Retrieval operations are logged" — 🔴 still not implemented. No audit/access log is
  written on this path. Left open; tracked as part of the still-outstanding FR-046/FR-049
  audit-logging gap in `docs/SRS_Compliance_Report.md`, not fixed by this change.

# SEC-006 — Audit Logging

**Status before:** 🔴 Not Implemented.
**Status after:** 🟡 Partial — authentication failures and authorization failures are now recorded; administrative operations and log immutability are not.

Full implementation and test evidence: `FR Testing/FR-049-Security-Event-Logging/README.md`
(same change; SEC-006 is the NFR statement of FR-049).

## Acceptance criteria check

- "Authentication attempts shall be logged" — 🟡 failed API authentications: yes. Login
  itself is Supabase's.
- "Authorization failures shall be recorded" — ✅ `ACCESS_DENIED` records (unit-tested; no
  role-restricted endpoint exists yet in these services to trigger it end to end).
- "Administrative operations shall generate audit records" — 🔴 not addressed; there are no
  admin operations in these services.
- "Audit logs shall be protected from unauthorized modification" — 🔴 records are ordinary log
  lines, not an append-only store.

## No Supabase changes needed.

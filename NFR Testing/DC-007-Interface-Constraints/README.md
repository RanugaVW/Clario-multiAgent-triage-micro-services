# DC-007 — Interface Constraints

**Status before:** ⚠️ Deviates — REST/JSON used consistently, but no API versioning and no OpenAPI contracts.
**Status after:** 🟡 Partial → versioned + documented for the ticket API.

Full details and evidence: `NFR Testing/DC-015-API-Design-Constraints/README.md`.

- "API contracts shall remain versioned and documented" — ✅ for the ticket API: `/api/v1/tickets`, OpenAPI at
  `/v3/api-docs`, snapshot-pinned.
- "Interface changes shall preserve backward compatibility whenever feasible" — ✅ the unversioned path still works and
  is announced as deprecated via `Deprecation`/`Link` headers and the contract itself.
- "Breaking interface changes require version updates" — 🟡 enabled (a `v2` would coexist) and now *visible* (the
  contract snapshot fails on any change), but not enforced by tooling that classifies a change as breaking.
- Internal service-to-service contracts (the Redis `ticket_queue` payload, the Python services' endpoints) are not versioned here.

# SUP-003 — Logging and Diagnostic Information

**Status before:** ⚠️ Deviates — inconsistent format and a real sensitive-data leak in the gateway.
**Status after:** 🟡 Partial — Java services fixed; Python services not.

Full details and test evidence: `NFR Testing/DC-021-Logging-Constraints/README.md`.

- "Diagnostic information is available without exposing sensitive user data" — ✅ for the Java services:
  the gateway's per-request JWT-header print is gone, DEBUG is opt-in, and audit/alert records are tested
  to exclude credentials.
- "Log records contain timestamps, component identifiers, and severity levels" — ✅ Spring Boot's default
  pattern supplies timestamp/level/logger; the correlation ID is now added.
- "AI workflow execution shall be traceable through diagnostic logs" — 🔴 the Python side is untouched.

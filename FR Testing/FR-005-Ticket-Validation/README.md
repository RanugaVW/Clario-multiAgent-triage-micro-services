# FR-005 — Ticket Validation

**Status before:** 🔴 Not Implemented on the real submission path (a Pydantic-validated endpoint existed in `ai-orchestrator-service` but the actual flow never calls it).
**Status after:** 🟡 Partial — closed for the Java ingestion path; the Python side is unchanged.

This requirement improved as a side effect of the FR-004/SEC-008 fix
(`FR Testing/FR-004-Ticket-Submission/README.md`) — same code change, so no separate
implementation here, just the acceptance-criteria check specific to this ID.

## Acceptance criteria check

- "Invalid requests are rejected" — ✅ a blank/missing `rawText` is now rejected at
  `ticket-core-service`/`agent-review-service`, before a Redis enqueue or DB write happens.
- "Schema validation is deterministic" — ✅ Bean Validation constraints, not conditional
  logic.
- "Validation failures include descriptive error messages" — ✅ JSON body names the
  specific field and reason (`"rawText: rawText is required and cannot be blank"`).

## What's still open

This only covers the two fields the DTO exposes (`rawText`, `subject`). It does not add
schema validation to `ai-orchestrator-service`'s own `/process_ticket` FastAPI endpoint,
which — per the compliance report — isn't on the real request path anyway. If that endpoint
is ever wired into production traffic, it needs this same treatment independently.

# SEC-008 — Input Validation

**Status before:** 🟡 Partial — solid in Python (Pydantic field constraints); zero `@Valid`/`@NotBlank` anywhere in the Java services.
**Status after:** 🟡 Partial → the Java gap is closed for the ticket-submission endpoints specifically.

Full implementation details: `FR Testing/FR-004-Ticket-Submission/README.md`.

## Acceptance criteria check

- "API requests shall undergo schema validation" — ✅ now true for `POST /api/tickets` on
  both `ticket-core-service` and `agent-review-service`.
- "Invalid or malformed requests shall be rejected" — ✅, before touching the database.
- "Validation failures return descriptive error messages" — ✅, field-named JSON body.
- "Input validation shall reduce the risk of common injection attacks" — not directly
  addressed by this change. `rawText`/`subject` go through JPA/Hibernate parameterized
  queries (no raw SQL string concatenation found in either controller or repository), so
  SQL injection risk was already low on this path; this fix is about malformed/incomplete
  data, not injection specifically.

## What's still open

- No other endpoint in either service was touched — this is scoped to the ticket-submission
  DTO only, matching FR-004/FR-005's scope. Any other request body accepted elsewhere in
  these services (if added later) needs the same treatment.
- Validation on the Python services (`nlp-classifier-service`, `ai-orchestrator-service`)
  was already adequate per the original audit and is unchanged here.

# SUP-005 — Error Diagnosis (also SRS §3.9.1 "Error and Validation Interface")

**Status before:** 🟡 Partial — descriptive messages existed, but no identifier on any error.
**Status after:** ✅ Implemented for `ticket-core-service` and `agent-review-service` and their UI.

## What changed

`ApiExceptionHandler` (`@RestControllerAdvice`, in both services) replaces the two `@ExceptionHandler`
methods that used to live inside `TicketController`. Every error body now carries a `reference`
equal to the request's correlation ID — the same value on the matching server log lines:

```json
{"error":"Ticket service is temporarily unavailable. Please try again shortly.","reference":"7d1c…"}
```

- **Validation** → 400 with `error`, `details`, `reference` (behaviour otherwise unchanged).
- **Database failure** → 503, generic message, **logged with the reference and stack trace**.
- **Any other exception** → 500 with a fixed generic message. Exception text, class name and SQL/host detail
  stay in the log only; a test injects `password=hunter2` into the exception and asserts it is absent from the response.
- **Extends `ResponseEntityExceptionHandler`**, so Spring's own errors keep their correct status and gain the
  reference: malformed JSON stays 400 (not a generic 500) and a wrong HTTP method stays 405.
- **Security exceptions are re-thrown**, not converted. A blanket `Exception` handler would otherwise turn an
  `AccessDeniedException` into a 500 and hide it from Spring Security; a test asserts it stays 403 and is audited.

Frontend: `describeSubmitFailure` appends ` (reference: …)` to the message shown to the user, and ignores a
non-string reference rather than printing it.

## No Supabase changes needed.

## Tests

`ApiExceptionHandlerTest` (×2 services, 6 cases): validation 400 with reference; DB failure 503 with reference,
no `db.internal`/`jdbc` leakage, logged with that reference and a stack trace; unexpected exception 500 generic
with detail only in the log; `AccessDeniedException` stays 403 and is audited; malformed JSON stays 400 with a
reference; wrong method stays 405. Frontend: 4 new cases in `submit-error-messages.test.ts`
(reference appended; kept when the body has no `error`; never invented; non-string ignored).

```
ticket-core-service:   Tests run: 44, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 41, Failures: 0, Errors: 0 -- BUILD SUCCESS
frontend (vitest):     143 passed; eslint 0 errors; tsc: only the pre-existing unrelated error
```

## What's still open

- `api-gateway` errors that it generates itself (its own 401) get the correlation ID *header* but no JSON
  `reference` body — its 401s have no body by Spring Security convention.
- The Python services return their own error shapes without a reference.

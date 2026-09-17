# FR-004 — Ticket Submission

**Status before:** 🟡 Partial — submission worked end to end, but nothing validated mandatory fields; a blank `rawText` fell through to a raw SQL `NOT NULL` constraint violation.
**Status after:** ✅ Implemented.

## What was wrong

```java
// before
public ResponseEntity<Ticket> createTicket(@RequestBody CreateTicketRequest request, ...) {
    Ticket ticket = ticketService.createTicket(request.getRawText(), ...);
    // rawText could be null or "" here - the DB's NOT NULL constraint (or nothing,
    // for "") was the only thing standing between a bad request and a saved ticket.
```

A missing `rawText` produced an unhandled `DataIntegrityViolationException` (Postgres
constraint error) surfacing as a 500 with no useful message. A blank `rawText` (`""`) wasn't
caught by anything at all and would have been saved as a ticket with empty content.

## What changed

`CreateTicketRequest` (in both `ticket-core-service` and `agent-review-service`) now carries
Bean Validation constraints:

```java
@NotBlank(message = "rawText is required and cannot be blank")
@Size(max = 20000, message = "rawText must not exceed 20000 characters")
private String rawText;

@Size(max = 500, message = "subject must not exceed 500 characters")
private String subject;
```

`createTicket(...)` now takes `@Valid @RequestBody CreateTicketRequest request`, and a new
`@ExceptionHandler(MethodArgumentNotValidException.class)` returns HTTP 400 with a
descriptive JSON body instead of letting the request reach the database at all:

```json
{"error": "Validation failed", "details": "rawText: rawText is required and cannot be blank"}
```

The 20,000-character cap on `rawText` and 500-character cap on `subject` are sanity/DoS
guards, not a business rule found anywhere else in the system — there was no existing limit
to mirror, so these are deliberately generous rather than a guess at "the right" limit.

## No Supabase changes needed. Added `spring-boot-starter-validation` to both services' `pom.xml` (a Maven dependency, not a runtime/DB change).

## Tests

Added to the existing `TicketControllerSecurityTest` in both services:

| Test | Verifies |
|---|---|
| `createTicket_withBlankRawText_isRejectedWithDescriptiveError` | `rawText: ""` → 400, JSON body names the failing field, `TicketService.createTicket` is never called |
| `createTicket_withMissingRawText_isRejectedWithDescriptiveError` | `rawText` omitted entirely from the JSON body → 400, service never called |

```
ticket-core-service: Tests run: 10, Failures: 0, Errors: 0 -- BUILD SUCCESS  (7 in TicketControllerSecurityTest, 3 pre-existing)
agent-review-service: Tests run: 7, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## Remaining scope

`imageBase64` is not validated (format, size, or content) by this change — that overlaps
with the OCR/vision pipeline's own input handling and was left out to avoid guessing at
constraints that belong to that service instead.

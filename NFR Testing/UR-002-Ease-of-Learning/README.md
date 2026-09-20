# UR-002 — Ease of Learning

**Status before:** 🟡 Partial — error text was a hardcoded generic string (`"Failed to submit ticket to API Gateway"`) that discarded whatever the backend actually reported.
**Status after:** 🟡 Partial → this specific finding (ticket submission errors) is closed.

## What was wrong

`frontend/src/app/dashboard/page.tsx`'s `handleSubmit` did:
```js
if (!res.ok) {
  throw new Error("Failed to submit ticket to API Gateway");
}
```
regardless of what the backend actually sent back. This is doubly unfortunate given this
session's own FR-005/REL-002 fixes: `ticket-core-service` now returns real, specific,
descriptive error bodies (`{"error": "Validation failed", "details": "rawText: ..."}`, or
`{"error": "Ticket service is temporarily unavailable. Please try again shortly."}`) —
and the frontend was throwing all of that away and showing the same unhelpful string every
time, whether the real problem was a validation failure, an outage, or a timeout.

## What changed

New exported helper `describeSubmitFailure(res: Response): Promise<string>` in
`dashboard/page.tsx`:
- If the response body parses as JSON with a string `error` field, returns that (plus
  `details` if present) — the real, specific message.
- Otherwise falls back to one of two generic-but-friendly messages depending on status code
  (5xx → "temporarily unavailable, try again"; 4xx/other → "check your details and try
  again") — still better than a single one-size-fits-none string, and safe when the response
  isn't JSON at all.

Also fixed the network-failure case: `fetch()` rejects with a `TypeError` (not an HTTP
response) when the request never reaches a server at all (offline, DNS failure, connection
refused). The catch block now distinguishes that case and shows "Couldn't reach the support
system. Check your connection and try again." instead of the browser's raw
`TypeError: Failed to fetch` message leaking into `err.message`.

## No Supabase changes needed.

## Tests

New file `frontend/src/app/__tests__/submit-error-messages.test.ts` — direct unit tests of
`describeSubmitFailure` (no React rendering needed, pure input/output):

| Test | Verifies |
|---|---|
| `surfaces the backend error message when the response has one` | `{error: "Gateway timeout"}` → `"Gateway timeout"` |
| `appends validation details when present (FR-005)` | `{error, details}` → `"error: details"` |
| `falls back to a friendly 5xx message...` | Non-JSON-shaped 503 → generic "temporarily unavailable" text |
| `falls back to a friendly 4xx message...` | Unparseable body on a 400 → generic "check your details" text |

**Three pre-existing tests needed updating**, and this is worth being explicit about: they
asserted the *old* generic string appeared (`/Failed to submit/i`), which is exactly the
behavior this fix removes. Updated them to assert the actual backend message that their own
mocks already specify (`'Server error'`, `'Service Unavailable'`, `'Unauthorized'`) is now
shown — stricter, more meaningful coverage than before, not a weakened test.

- `frontend/src/app/__tests__/ticket-submission-e2e.test.tsx` (1 assertion)
- `frontend/src/app/__tests__/user-workflows.test.tsx` (3 assertions)
- `frontend/src/app/__tests__/ticket-pipeline-simplified.test.tsx` (1 assertion)

```
npx vitest run src/app/__tests__/submit-error-messages.test.ts src/app/__tests__/ticket-submission-e2e.test.tsx
Test Files  2 passed (2)
     Tests  19 passed (19)

npx vitest run   (full suite, regression check)
Test Files  20 passed (20)
     Tests  125 passed (125)   [121 pre-existing (4 updated) + 4 new]

npx tsc --noEmit
Same single pre-existing, unrelated error as before (untouched file). Zero new type errors.
```

## What's still open

Only the ticket-submission error path was touched. No contextual help/tooltips were added
(the other half of UR-002's original finding) — that's a larger UI-design task, not a
one-file fix, and is left for a separate pass.

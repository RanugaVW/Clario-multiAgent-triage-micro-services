# UR-006 — Error Prevention and Recovery

**Status before:** 🟡 Partial — destructive deletes were gated by `window.confirm()`, and failures fell back to raw `window.alert()`, in both the customer dashboard and the admin console.
**Status after:** 🟡 Partial → this specific finding (ticket deletion) is closed; other `alert`/`confirm` usage, if any exists elsewhere in the app, is unaffected.

## What was wrong

`frontend/src/app/dashboard/page.tsx` and `frontend/src/app/admin/page.tsx` each gated ticket
deletion with the browser's native, blocking `confirm(...)`, and reported failures with
native `alert(...)`. Both are unstyled, block the entire page (including any other async
work in flight), and are not reliably announced consistently across screen readers.

## What changed

Added a reusable `ConfirmDialog` component (`frontend/src/components/ui.tsx`), built on the
existing `Modal` primitive, with `title`/`message`/`confirmLabel`/`onConfirm`/`onCancel`
props. In both pages:

- `handleDeleteTicket` no longer confirms synchronously — it just opens the dialog
  (`setTicketPendingDelete(ticketId)`).
- A new `confirmTicketDeletion` function holds the actual delete request, wired to the
  dialog's `onConfirm`.
- Failure messages moved from `alert(...)` into existing (dashboard: new `historyError`
  state + inline banner matching the app's existing error-banner style) or already-present
  (admin: the existing `debugInfo` banner) UI, instead of a blocking dialog.

No behavior change for a user who clicks through correctly — cancel still cancels, confirm
still deletes — the interaction is just no longer a native browser dialog.

## No Supabase changes needed.

## Tests

New file `frontend/src/app/__tests__/delete-confirmation.test.tsx` — a focused harness that
wires `UserTicketRow` to `ConfirmDialog` exactly as `Dashboard` does (without mounting the
whole page and its data-fetching effects):

| Test | Verifies |
|---|---|
| `does not delete immediately - it opens a confirmation dialog first` | Clicking delete does **not** call the delete callback; it shows the dialog |
| `deletes only after the dialog is explicitly confirmed` | Clicking "Delete ticket" in the dialog calls the callback with the right ticket ID, and the dialog closes |
| `cancels without deleting when Cancel is clicked` | Clicking "Cancel" never calls the callback |

Also added a login-form label test earlier in this session's work covers `ConfirmDialog`'s
sibling `Modal` usage pattern, so this isn't the only exercise of that primitive.

```
npx vitest run src/app/__tests__/delete-confirmation.test.tsx
Test Files  1 passed (1)
     Tests  3 passed (3)

npx vitest run   (full suite, regression check)
Test Files  18 passed (18)
     Tests  119 passed (119)   [116 pre-existing + 3 new]

npx tsc --noEmit
1 pre-existing error, in a file this session never touched (admin-ticket-attachment.test.tsx,
unrelated spread-argument typing issue) - confirmed via `git status` showing zero changes to
that file. Zero new type errors from anything changed in this fix.
```

## What's still open

Only the ticket-deletion flows in these two specific pages were touched. If `alert`/`confirm`
appear anywhere else in the frontend, they're unaffected by this fix (a repo-wide grep at the
time of this fix found only these two files using them).

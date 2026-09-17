# UR-003 — Efficient Task Completion

**Status before:** 🟡 Partial — admin's "All Tickets" view had search-by-ID and filters; the customer's own ticket history had none, just a flat list.
**Status after:** 🟡 Partial → the customer-history search gap specifically is closed; admin's list was already fine and untouched.

## What was wrong

`frontend/src/app/dashboard/page.tsx`'s history tab rendered `pastTickets` directly with no
way to narrow it down — a customer with many past tickets had no option but to scroll and
read through all of them to find one.

## What changed

Added a client-side search box (`historySearch` state), styled to match the existing
`glass-input` pattern already used for admin's ticket search. Filtering
(`filteredPastTickets`) matches against the ticket's description (`raw_text`), `subject`, and
ID — case-insensitive substring match, computed on every render from already-fetched data
(no new network request, no Supabase change). Also distinguished the "no results for this
search" state from the "you have no tickets at all" empty state — they need different
messages and previously would have collapsed into the same one had a naive implementation
just checked `filteredPastTickets.length === 0`.

## No Supabase changes needed.

## Tests

New file `frontend/src/app/__tests__/history-search.test.tsx`, rendering the full
`DashboardPage` with three mocked tickets with distinguishable content:

| Test | Verifies |
|---|---|
| `filters the ticket list as the user types, and shows all tickets when cleared` | Typing "invoice" leaves only the matching ticket visible; clearing the box restores all three |
| `shows a no-results message for a query that matches nothing, without claiming there is no history at all` | A query matching nothing shows "No tickets match..." specifically, not the "you haven't submitted any tickets yet" empty state |

```
npx vitest run src/app/__tests__/history-search.test.tsx
Test Files  1 passed (1)
     Tests  2 passed (2)

npx vitest run   (full suite, regression check)
Test Files  19 passed (19)
     Tests  121 passed (121)   [119 pre-existing + 2 new]

npx tsc --noEmit
Same single pre-existing, unrelated error as before (untouched file). Zero new type errors.
```

## What's still open

This is search only (substring match on description/subject/ID) — no status/date filters
were added to the customer view (admin's richer filtering wasn't mirrored here, since the
original finding was specifically "no search at all," not "search is less powerful than
admin's").

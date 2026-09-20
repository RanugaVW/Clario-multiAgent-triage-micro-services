# FR-035 Human Response Editing · FR-036 Ticket Resolution · UR-008 Dashboard Usability (agent role)

**Status before:** 🔴 FR-035 / FR-036 not implemented; ⚠️ UR-008 — the agent dashboard rendered three hard-coded mock tickets
(`SUP-1002`…), fake stats ("2.4 hrs", "14 resolved today") and a *Review* button that navigated to a route that did not exist.
**Status after:** ✅ An agent can open the real escalation queue, review a ticket beside its AI draft, edit the response, send it, and
the ticket becomes resolved and attributed to them. Already-resolved tickets are read-only, enforced on the server.

> Where it lives: the SRS puts this under the review service, but `agent-review-service` is the ticket-intake service in this
> codebase. The admin console already resolves tickets through the Next.js `PUT /api/tickets` route, so the agent workflow reuses and
> hardens that route rather than adding a second, divergent write path.

## What changed (`frontend` only — no Java/Python/Supabase-schema change)

**1. `PUT /api/tickets` hardened** (`src/app/api/tickets/route.ts`) — shared by admin and agent.
- Records **`resolved_by` = the verified caller** (from the token, never from the request body). The column already existed and was never written.
- **404** for an unknown ticket; **409** if the ticket is already resolved (status `resolved` *or* a non-escalated resolution exists) — this is
  the "closed = read-only" rule (FR-036). An escalation-marker row alone does not block resolving.
- **Write order fixed:** the resolution is inserted first, then the status flips. Previously the status changed first, so a failed insert left a
  ticket "resolved" with no answer. If the status update now fails, the inserted resolution is **deleted (compensation)**.
- Malformed JSON, non-string ids and whitespace-only responses → **400** (previously an unhandled exception → HTML 500). Response is trimmed.
- `GET` now also returns `draft_text` so the reviewer can start from the AI draft.

**2. `src/lib/agentQueue.ts`** — pure rules, no React: `needsHumanReview` (identical rule to the admin queue), priority ordering
(Critical/Urgent › High › Medium › Low › unknown; oldest first within a priority), real stats (needs review, oldest waiting, resolved today).

**3. Agent dashboard** (`src/app/agent/page.tsx`) — real data via `/api/tickets` with the session token; loading, error-with-retry, empty
and refresh states; stat cards derived from data (the invented "avg resolution" card was replaced by "Oldest waiting"); Review button is
always visible and keyboard-focusable (it was hover-only, hiding it from keyboard users) with an accessible name.

**4. Review page** (`src/app/agent/[id]/page.tsx`, new) — customer message (OCR block stripped), classification, AI draft pre-filled in an
editable, labelled textarea; *Send response & resolve*; server errors (e.g. 409) shown while **keeping the agent's text**; resolved
tickets show a read-only notice; unknown id → "Ticket not found"; non-staff → `/login` with no data request.

## Tests

| File | Cases | Covers |
|---|---|---|
| `src/app/api/tickets/route.test.ts` (+11) | 20 total | resolved_by from token & not from body, insert-before-status ordering, compensation on status failure, no status write on insert failure, 404, 409 ×2, escalation-marker still resolvable, 400 ×4 (incl. malformed JSON) |
| `src/lib/agentQueue.test.ts` (new) | 14 | queue rule, ordering (+ non-mutation), stats incl. empty queue and same-local-day, headline/category/draft helpers |
| `src/app/__tests__/agent-workflow.test.tsx` (new) | 13 | dashboard: real rows only & sorted, token sent, stats derived (old mock text absent), navigation, empty, error + retry, non-staff redirect; review page: draft prefill, send via PUT, empty blocked, 409 keeps text, already-resolved read-only, unknown id, non-staff |

**Mutation checks (each reverted afterwards, each caught):** dropping `resolved_by` → 2 failures; removing the compensating delete → 1;
disabling the already-resolved guard → 2; agent page showing all tickets instead of the queue → 2; not pre-filling the draft → 2.

**Full verification:** `vitest` 26 files / **206 tests pass** · `eslint` **0 errors** (2 pre-existing `<img>` warnings) · `next build` OK with `/agent` and `/agent/[id]` ·
`tsc` — only the pre-existing `admin-ticket-attachment.test.tsx` error.

## Known limits (honest)

- **Not atomic.** Lookup → insert → update are three calls; two agents answering the same ticket in the same instant could both pass the 409 check.
  Closing that fully needs a DB constraint — optional Supabase SQL (you apply it; nothing in the app depends on it):
  ```sql
  -- at most one non-escalated (final) resolution per ticket
  CREATE UNIQUE INDEX IF NOT EXISTS resolutions_one_final_per_ticket
    ON public.resolutions (ticket_id) WHERE escalated = false;
  ```
  (Check for existing duplicate final resolutions first: `SELECT ticket_id, count(*) FROM resolutions WHERE escalated = false GROUP BY 1 HAVING count(*) > 1;`)
- The agent page does **not** call the Python `/embed_resolved_ticket` step (the admin console does), so agent answers are not fed back into the knowledge base. Blocked on the Python side.
- No customer notification on resolution (customer sees it on their dashboard) and no `human_reviews` audit row for edits of the AI draft.
- Not exercised against the live Supabase/Docker stack in this sandbox; behaviour is verified against mocked Supabase + real Next route handlers and React Testing Library.

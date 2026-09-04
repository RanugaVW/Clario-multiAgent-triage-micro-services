# 07 — API Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md). Original run: 46
assertions, 37 passed, 9 failed — 5 real findings across two endpoints with
**zero authentication** (`POST /process_ticket`, `POST /embed_resolved_ticket`),
a customer-facing **delete-my-ticket feature that always failed** with a
foreign-key violation, an **admin force-delete check that could never pass**
for any real admin, and a broad `except Exception` that **hid 403s behind
500s**. **All 5 have since been fixed and re-verified live: final result
46/46 assertions passed** (see TEST_REPORT.md §7).

**Sample-plan equivalent:** §3.1.2 Function Testing, specialized to the HTTP
API layer.

## Scope

Every directly, independently reachable API in this system: the Next.js API
routes (`:3000`), the `clario-ml-sidecar` FastAPI service (`:8600`), and
`voice-to-text-service` (`:8002`). The Java `api-gateway`/`ticket-core-service`
chain (`:8080`/`:8081`) is Docker-network-only and out of scope here — see
TEST_REPORT.md §1 for why, and what already covers it.

## How to run this

```bash
# 1. Have these running first:
#    - frontend:            cd frontend && npm run dev              (:3000)
#    - clario-ml-sidecar:   cd clario-ml-sidecar && source .venv/bin/activate \
#                              && uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload
#    - voice-to-text-service: cd services/voice-to-text-service && source .venv/bin/activate \
#                              && uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

# 2. Run everything (creates fixtures, runs the Postman collection via Newman, tears down):
Testing/07-API-Testing/run_api_tests.sh
```

Nothing from your side is *required* beyond having those three servers up —
`run_api_tests.sh` downloads Newman on the fly via `npx` (no global install)
and creates/deletes its own disposable Supabase accounts and tickets.

### Exploring it yourself in Postman

You said you're learning Postman, so the collection is a real, importable
one — not just evidence for this report:

1. Open Postman (desktop app or the web version at postman.com).
2. **Import** → `Testing/07-API-Testing/postman/Clario-API.postman_collection.json`.
3. **Import** → `Testing/07-API-Testing/postman/Clario-API.postman_environment.template.json`,
   then either fill in the values by hand (a token from your own browser
   session's `localStorage`/DevTools, a real ticket id from Supabase) or run
   `setup_fixtures.py` once and import the `generated.postman_environment.json`
   it writes (git-ignored, since it holds live JWTs — delete it when you're
   done, or just re-run `teardown_fixtures.py`).
4. Pick the environment from the dropdown (top-right), open any request, hit
   **Send**. The **Tests** tab on each request is where the `pm.test(...)`
   assertions live — that's the part worth reading first.
5. **Collection Runner** (the ▶ icon next to the collection name) replays
   every request in order, exactly like Newman does from the command line —
   good for seeing the whole suite pass/fail without touching a terminal.

## API testing, explained (for future reference)

*(You asked to be walked through this properly — this section is the
answer, kept here so it stays with the collection it describes.)*

**What "API testing" actually checks**, as distinct from the other phases in
this folder:
- **Contract correctness** — does each endpoint return the status code and
  response shape its callers actually depend on? (Phase 01/02's unit/integration
  tests check this too, but from *inside* the code, calling functions
  directly — API testing calls the real HTTP boundary, the same way a real
  client does, so it also catches routing, serialization, and middleware
  bugs unit tests can't see.)
- **Input validation** — missing fields, wrong types, out-of-range values,
  oversized payloads. Every `-> 400` / `-> 422` request in this collection is
  this category.
- **Auth & authorization as a *contract*** — not a full security audit
  (that's Phase 05's job), but: does *this* endpoint require *this* level of
  access, and does it say so with the right status code (401 = "who are
  you", 403 = "I know who you are, and no")? Three of this phase's five
  findings are exactly this category, and they were real production bugs.
- **Error handling** — does a failure surface as a status code and message a
  caller can actually act on, or does it get swallowed/rewritten into
  something misleading (Finding 5)?
- **Idempotency & side effects** — does calling delete twice, or resolving
  an already-resolved ticket, behave sanely? (Worth extending this
  collection with, per §6's follow-ups.)

**Why test at this layer specifically, instead of only unit/integration
tests:** because it's the layer a *client* — the browser, a mobile app, a
future integration partner, an attacker — actually talks to. A unit test can
prove `delete_customer_ticket()`'s Python logic is correct while the HTTP
route wrapping it is unreachable, wrongly authenticated, or returns the
wrong content-type — none of which a function-level test would ever see. All
three findings from `DELETE /customer_tickets/{id}` in this phase are proof:
the underlying logic *intent* was fine, but the deployed contract was broken
in three different ways.

**How you improve API performance** (Phase 04 owns the actual measurement —
this is what its numbers point you toward fixing):
- Cache aggressively at the boundary that changes least often (`/api/tickets`
  already has a Redis-cache code path built in, currently bypassed — see
  its `getRedisClient()` comment).
- Push heavy work off the request/response cycle — `/process_ticket` already
  does this right: it returns immediately and processes in a background
  task instead of making the caller wait for a full LLM pipeline run.
- Index what you filter/sort/join on in the database, and only `select` the
  columns/relations a given response actually returns (the nested
  `ticket_drafts`/`ticket_classifications`/`resolutions` selects in
  `/api/tickets` are a good example of asking Postgres to do a join
  server-side instead of N follow-up queries).
- Measure before optimizing — Phase 04's report has this system's actual
  latency numbers; guessing at bottlenecks without them tends to "optimize"
  code that was never the slow part.

**How you maintain an API over time:**
- Keep the contract and its tests next to each other and re-run them on
  every change — this collection catching Finding 3 (a totally broken
  customer-facing feature, previously untested) is the exact failure mode
  API tests exist to prevent from shipping unnoticed.
- Version deliberately when you must break a contract (a new required field,
  a renamed response key) rather than silently changing behavior existing
  callers rely on. This system doesn't version its routes today (`/api/tickets`
  has no `/v1/`) — fine at its current single-frontend scale, worth revisiting
  before any second, independent client exists.
- Centralize cross-cutting concerns instead of repeating them — this phase's
  fix added one `get_user_role()` helper rather than fixing the same
  `app_metadata` bug three separate times; the codebase already does this
  well on the Next.js side with `requireUser()`/`isStaff()` in `apiAuth.ts`.
- Log enough to diagnose a failure without re-triggering it — Finding 5
  (403 rewritten to a generic 500) is the opposite of this: fix error
  handling so the *real* reason a request failed is visible to whoever's
  debugging it, not just "something went wrong."

**How you customize/extend this collection:**
- New endpoint → new request in the matching numbered folder (or a new
  folder), with a `pm.test` for at least: the happy-path status+shape, one
  auth-rejection case, and one validation-rejection case — that pattern
  covers the large majority of real bugs this phase found.
- New environment (staging, a teammate's machine) → just re-run
  `setup_fixtures.py` pointed at that Supabase project's `.env`, or hand-edit
  a copy of the environment template with that environment's URLs.
- Chained scenarios (create → read → update → delete the *same* resource,
  across requests) → use `pm.environment.set(...)` in a request's **Tests**
  tab to capture a value (e.g. a newly-created id) into an environment
  variable, then reference it in a later request's URL/body as `{{thatVar}}`
  — Postman runs requests in a collection top-to-bottom, so this collection
  already relies on that ordering (canary ids are pre-created by
  `setup_fixtures.py` instead, since every fixture here needed to exist
  *before* the run for auth/ownership testing, but a create-and-use-the-id
  flow would use `pm.environment.set` directly).

## Files in this folder

| File | What it is |
|---|---|
| `postman/Clario-API.postman_collection.json` | The real, importable Postman collection — 35 requests, 46 assertions |
| `postman/Clario-API.postman_environment.template.json` | Committed template environment (placeholder values) — import this to see the variable shape |
| `postman/generated.postman_environment.json` | Git-ignored — written fresh by `setup_fixtures.py` each run, holds real (short-lived) JWTs and canary ticket ids |
| `setup_fixtures.py` / `teardown_fixtures.py` | Create/delete this run's disposable Supabase accounts and canary tickets |
| `run_api_tests.sh` | Runs the whole phase end-to-end |
| `TEST_REPORT.md` | Full findings, root causes, and the fix/re-verification record |
| `test-log*.txt` | Raw Newman CLI output — `-before-fix`/`-after-fix` suffixed, plus the current canonical run |

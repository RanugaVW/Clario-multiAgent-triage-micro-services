# API Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `main`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `next dev` server (`:3000`), a locally-run `clario-ml-sidecar` (`:8600`, `uvicorn app.main:app --reload`), and the already-running `voice-to-text-service` (`:8002`). Tooling: [Postman](https://www.postman.com/) Collection Format v2.1 (`postman/Clario-API.postman_collection.json`, importable into the Postman desktop/web app) executed with [Newman](https://github.com/postmanlabs/newman), Postman's official CLI runner (`npx newman run ...`, no global install).

**Original result: 46 assertions run, 37 passed, 9 failed.** All 9 failures were real, reproducible defects — not test-harness bugs. **All have since been fixed and re-verified live: final result 46/46 assertions passed.** The sections below are left as originally found, then §7 covers the fixes.

## 1. Scope

This phase corresponds to §3.1.2 ("Function Testing") of the reference Master Test Plan, specialized to the HTTP API layer: does each endpoint return the right status code, the right response shape, and enforce the right auth/ownership contract, for both valid and invalid input?

**Covered — every directly, independently reachable API in this system:**
- **Next.js API routes** (`:3000`): `GET/PUT/DELETE /api/tickets`, `GET /api/user_tickets`, `POST /api/customer_feedback`
- **`clario-ml-sidecar` FastAPI service** (`:8600`): `GET /health`, `POST /process_ticket`, `GET /customer_tickets/{user_id}`, `DELETE /customer_tickets/{ticket_id}`, `POST /embed_resolved_ticket`
- **`voice-to-text-service`** (`:8002`): `GET /health`, `POST /transcribe/base64`

**Deliberately out of scope, and why:**
- **`api-gateway` → `ticket-core-service`** (Java/Spring, `:8080`/`:8081`): these only resolve to each other by Docker Compose service name (`http://ticket-core-service:8081`), so they're not independently reachable outside the full `docker-compose` stack. [`Testing/03-UI-E2E-Testing`](../03-UI-E2E-Testing/) already exercised this exact chain live (browser → `/api/tickets` → JPA insert → Redis dispatch) as part of the real ticket-submission flow, so it isn't uncovered — it just isn't *this* phase's tooling. Bringing up the Java + Docker stack solely for Postman contract testing was judged out of proportion to what this phase asks.
- **`nlp-classifier-service`, `ai-orchestrator-service`**: not part of the real request path (`ai-orchestrator-service` is a full mirror of `clario-ml-sidecar`, kept in sync as a matter of repo convention; `nlp-classifier-service` isn't called by anything in the current codebase).
- **`agent-review-service`**: same Docker-network-only reachability as `ticket-core-service`; not exercised.

## 2. Environment & Tooling

| | |
|---|---|
| Collection | `Testing/07-API-Testing/postman/Clario-API.postman_collection.json` — 8 folders, 35 requests, 46 assertions (`pm.test`) |
| Environment | Generated per run by `setup_fixtures.py` into `postman/generated.postman_environment.json` (git-ignored — contains live, short-lived JWTs); `postman/Clario-API.postman_environment.template.json` is the committed, importable template showing the variable shape |
| Runner | `run_api_tests.sh` → `npx newman run ... -e ... --reporters cli` |
| Supabase | Production project `mdvfvtpbwqhccmaarpli`, service-role client for fixture setup/teardown (same pattern as Phase 05/06) |
| Test data | 3 disposable accounts (2 customers, 1 staff — role set directly via `public.users.role`, same as Phase 05) and 7 disposable "canary" tickets (tagged `API-TEST-CANARY-<run-id>`), one per destructive scenario so no two requests' side effects collide. All deleted in `teardown_fixtures.py` regardless of pass/fail. |
| Regression check | `pytest tests -q` in `clario-ml-sidecar` after every fix: 96 passed, 3 skipped throughout — no regressions |

## 3. Findings (original run)

### Finding 1 (High) — `POST /process_ticket` had no authentication at all

**Evidence:** an unauthenticated request with an arbitrary `ticket_id` got `200 {"status": "processing"}`, the same as an authenticated owner. A second request using a *different* customer's token against someone else's ticket also got `200`.

**Root cause:** the route had no `Depends(verify_token)` and no ownership check whatsoever — literally anyone who could reach port 8600 could trigger a full LLM pipeline run (real Gemini/local-model calls) against any `ticket_id` in the database, for free, with no rate limit and no record of who asked. Tracing the real ticket-submission flow (`ticket-core-service`'s `TicketService.dispatchToSidecar` pushes straight to the Redis `ticket_queue`, consumed by `worker.py`) showed this HTTP route isn't even called by anything in the current codebase — it's a live, unauthenticated, **dead** endpoint.

**Severity:** High — real compute/API cost exposure and an open door onto ticket data, reachable by anyone on the network path to the service, regardless of whether the "intended" caller uses it.

### Finding 2 (High) — `POST /embed_resolved_ticket` had no authentication at all

**Evidence:** an unauthenticated request, and a request from an authenticated non-staff customer, both got `200 {"status": "success"}`.

**Root cause:** no auth dependency, and — unlike Finding 1 — this endpoint *is* called for real, from the admin console's "resolve" button (`admin/page.tsx`), but that call itself sends no `Authorization` header either. `add_precedent()` writes straight into the ChromaDB RAG store, and those precedents are later retrieved **verbatim** as suggested answers for other, unrelated future customers (`cache_check_node` / `retrieve_context`). Anyone who found this URL could poison that store with fabricated "precedent" text and have it served to real customers later.

**Severity:** High — data-poisoning / prompt-injection into a system that later trusts this data as ground truth, with no auth barrier at all.

### Finding 3 (Medium) — Non-force ticket delete unconditionally failed with a foreign-key violation

**Evidence:** `DELETE /customer_tickets/{ticket_id}` (no `force`, called by the owning customer — the intended, everyday "delete my ticket" path) returned `500 {"detail": "Failed to delete ticket"}` on every single attempt, for every ticket.

**Root cause, confirmed by calling the function directly in-process to get the real traceback** (the HTTP layer's own `except Exception` was hiding it — see Finding 5):
```
postgrest.exceptions.APIError: insert or update on table "tickets" violates foreign key
constraint "tickets_user_id_fkey" ... Key (user_id)=(00000000-0000-0000-0000-000000000000)
is not present in table "users".
```
The "soft delete" wrote a literal all-zero placeholder UUID into `tickets.user_id` to mean "orphaned/deleted", but that column is `REFERENCES public.users(id)` and no row with that id exists — so Postgres rejects the write, every time, unconditionally.

**Severity:** Medium — a customer-facing feature (delete my own ticket) was completely non-functional in production, always failing with a generic 500.

### Finding 4 (Medium) — Force-delete's admin check read a field this schema never sets

**Evidence:** `DELETE /customer_tickets/{ticket_id}?force=true` as a real staff account (role set in `public.users.role`, the same way every other admin check in this codebase resolves role) still failed.

**Root cause:** `is_admin = getattr(user, 'app_metadata', {}).get('role') == 'admin'` reads the Supabase **auth** user's `app_metadata` — but `supabase_schema.sql` stores role in `public.users.role` (populated by a signup trigger / set directly by admins), never in `app_metadata`. A live probe confirmed a freshly-created user's `app_metadata` is always `{'provider': 'email', 'providers': ['email']}` — `role` is never in it. **No admin account could ever force-delete a ticket through this endpoint.**

**Severity:** Medium — an admin-only feature silently never worked for any real admin.

### Finding 5 (Low) — A broad `except Exception` swallowed intentional 403s into 500s

**Evidence:** `DELETE .../customer_tickets/{ticket_id}?force=true` as a **non-admin** customer — which the code explicitly means to reject with `403 "Only admins can force delete"` — actually returned `500 {"detail": "Failed to delete ticket"}`.

**Root cause:** `HTTPException` is a subclass of `Exception`, and the route's own `raise HTTPException(403, ...)` calls were happening *inside* the same `try` block guarded by a generic `except Exception as e: ... raise HTTPException(500, "Failed to delete ticket")` — so every intentionally-raised 403 was being re-caught and rewritten into an opaque 500, discarding the real reason before it ever reached the client or a log line a caller could act on.

**Severity:** Low on its own, but it directly hid Findings 3 and 4 behind a generic message during initial testing — a good example of why an error-handling bug is worth fixing even when nothing else is wrong underneath it.

## 4. Requests that passed cleanly, first try

Everything on the Next.js side (`/api/tickets`, `/api/user_tickets`, `/api/customer_feedback`) passed every auth, ownership, and validation check on the first run — expected, since Phase 05 already hardened this exact layer. `voice-to-text-service`'s health check, valid-audio transcription, and both malformed-input rejections (empty payload, non-audio base64) also passed cleanly, as did `clario-ml-sidecar`'s `/health` and the read-only `/customer_tickets/{user_id}` GET checks (own-tickets 200, cross-account 403, no-auth 401).

## 5. Summary of findings

| # | Endpoint | Issue | Severity | Status |
|---|---|---|---|---|
| 1 | `POST /process_ticket` | No authentication at all; also a dead endpoint nothing in the real flow calls | **High** | **Fixed — see §7** |
| 2 | `POST /embed_resolved_ticket` | No authentication at all; injects RAG precedents served to future customers | **High** | **Fixed — see §7** |
| 3 | `DELETE /customer_tickets/{id}` (soft) | FK violation on every call — placeholder UUID isn't a real `users` row | **Medium** | **Fixed — see §7** |
| 4 | `DELETE .../{id}?force=true` (admin) | Reads `app_metadata.role`, which this schema never sets — no real admin could force-delete | **Medium** | **Fixed — see §7** |
| 5 | `DELETE /customer_tickets/{id}` (all paths) | Broad `except Exception` rewrites intentional 403s into 500s | **Low** | **Fixed — see §7** |

## 6. Follow-ups for a future run

- Extend coverage to `api-gateway`/`ticket-core-service` once/if a Postman + Newman run against the full `docker-compose` stack is worth the setup cost — Phase 03's E2E run already proves the chain works end-to-end, but it doesn't assert the same per-field contract detail this phase does elsewhere.
- `voice-to-text-service`'s `/transcribe` (multipart file upload) wasn't covered separately from `/transcribe/base64` — both share the same decode/transcribe path (`_transcribe_bytes`), so this was judged low-value duplication, not a gap in the underlying code path.
- No load/soak testing here by design — that's Phase 04's job. This phase is purely functional/contract correctness.

## 7. Fixes applied and re-verified live: 46/46 assertions passed

All 5 findings were fixed in `clario-ml-sidecar/app/main.py` (synced to `services/ai-orchestrator-service`, the established mirror), plus one line in `frontend/src/app/admin/page.tsx`.

### What changed

**A shared `get_user_role(user_id)` helper** (`clario-ml-sidecar/app/main.py`) — looks up a user's real role from `public.users.role` via the service-role client. Replaces every `app_metadata`-based check in this file (Finding 4's root cause) with the same source of truth `frontend/src/lib/apiAuth.ts` already uses (`get_my_role()`), just read directly instead of through an RPC, since this code already holds the service-role client.

**`POST /process_ticket`** — fixes Finding 1: added `user = Depends(verify_token)`, then an ownership check (`tickets.user_id` must equal the caller's id) before any processing starts, mirroring the same pattern `GET /customer_tickets/{user_id}` already used.

**`POST /embed_resolved_ticket`** — fixes Finding 2: added `user = Depends(verify_token)` plus a staff-only check (`get_user_role(user.id) in ("admin", "agent")`). `frontend/src/app/admin/page.tsx`'s call site now sends `...(await authHeaders())`, the same helper the rest of that page already uses for every other authenticated call.

**`DELETE /customer_tickets/{ticket_id}`** — fixes Findings 3, 4, 5 together:
- The soft-delete write now sets `user_id` to `None` (SQL `NULL`) instead of the placeholder all-zero UUID — `tickets.user_id` is declared `REFERENCES public.users(id) ON DELETE SET NULL`, so `NULL` is exactly what this same column already uses for "owner is gone" when a real user is deleted, and a foreign key always permits `NULL`.
- `is_admin` now uses `get_user_role(user.id) == "admin"` instead of the always-empty `app_metadata` read.
- Added `except HTTPException: raise` before the generic `except Exception`, so an intentionally-raised 401/403 is no longer rewritten into a 500.

All fixes synced to `services/ai-orchestrator-service/app/main.py` (confirmed byte-identical to `clario-ml-sidecar/app/main.py` before this phase's edits, same as Phase 06's sync).

**Verification:** `pytest tests -q` in `clario-ml-sidecar`: 96 passed, 3 skipped — unchanged, no regressions.

### Live re-verification (real production Supabase, real running services)

The **exact same** Postman collection and assertions were re-run against the fixed code — nothing in the test scripts changed between the before/after runs, only the server code:

```
before: 46 assertions, 37 passed, 9 failed
after:  46 assertions, 46 passed, 0 failed
```

| Check | Before fix | After fix |
|---|---|---|
| `process_ticket`, no auth | `200` (should be `401`) | **`401`** |
| `process_ticket`, wrong owner | `200` (should be `403`) | **`403`** |
| `customer_tickets` soft-delete, owner | `500` (FK violation) | **`200 {"status":"success"}`** |
| `customer_tickets` force-delete, non-admin | `500` (403 swallowed) | **`403`** |
| `customer_tickets` force-delete, real admin | `500` (broken role check, then swallowed) | **`200 {"status":"success"}`** |
| `embed_resolved_ticket`, no auth | `200` (should be `401`) | **`401`** |
| `embed_resolved_ticket`, non-staff | `200` (should be `403`) | **`403`** |

Full evidence: `test-log-before-fix.txt` (the failing baseline) and `test-log-after-fix.txt` (the fixed re-run); `test-log.txt` mirrors the after-fix run as the phase's current, canonical result.

Cleanup verified after every run: `teardown_fixtures.py` reports each disposable account deleted, and `.fixtures.json` (the only state it needs to find them) is removed once teardown completes.

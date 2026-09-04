# REST Assured Integration Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `main`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `next dev` server (`:3000`), and a locally-run `clario-ml-sidecar` (`:8600`). Tooling: [REST Assured](https://rest-assured.io/) 5.5.0 + JUnit 5 + Java 21, built and run with a locally-downloaded Apache Maven 3.9.9 (no system install — see `run_tests.sh`).

**Result: 13/13 tests passed** (after two real fixes made during the first run — see §4). No app-code bugs found in this phase; both issues were in the test suite itself, and both were caught by actually running it against the live system rather than assumed away.

## 1. Scope

Maps to the "Integration testing → REST Assured (API)" row of the assigned tool table. The defining trait of an *integration* test, as distinct from Testing/07-API-Testing's per-endpoint Postman contract checks, is asserting that **two separate API calls agree on the same underlying data** — not just that each one individually returns the right status code.

Three test classes, 13 tests, against real endpoints:
- `TicketsApiIntegrationTest` — `/api/tickets` (Next.js). Signature scenario: `PUT` resolves a ticket, then an independent `GET` confirms the resolution actually persisted.
- `UserTicketsAndFeedbackIntegrationTest` — `/api/customer_feedback` and `/api/user_tickets` (Next.js), spanning **two different routes**. Signature scenario: `POST` feedback through one route, then confirm it shows up nested inside a completely different route's response.
- `SidecarIntegrationTest` — `clario-ml-sidecar` (`:8600`), a different origin from the two above. Signature scenario: confirm a pre-seeded ticket is present in the owner's real ticket list.

**Not covered:** the Java `api-gateway`/`ticket-core-service` chain's own internal integration (out of scope for the same reason as Testing/07-API-Testing §1 — not independently reachable outside `docker-compose`, though as it happens a real instance was found already running on `:8080` in this environment; see Testing/08's report).

## 2. Environment & Tooling

| | |
|---|---|
| Project | `Testing/09-RestAssured-API-Testing/pom.xml` — REST Assured 5.5.0, JUnit Jupiter 5.11.3, Jackson Databind 2.18.1 |
| Fixtures | `setup_fixtures.py` — 2 disposable customers + 1 disposable staff account (role set directly in `public.users`, same pattern as every other phase), 3 disposable canary tickets, written to `fixtures.json` (git-ignored — live JWTs) |
| Build/run | `run_tests.sh` → downloads Maven locally into `../../.tools/` if absent, then `mvn test` |
| Test data | Every ticket tagged `RESTASSURED-TEST-<run-id>`; `teardown_fixtures.py` deletes every account and ticket afterward |

## 3. Findings (original run)

Both issues below were caught by actually executing the suite against the live system — neither would have been visible from reading the code alone.

### Finding 1 — Missing JSON serializer on the classpath

**Evidence:** every test that sent a JSON body (`.body(Map.of(...))`) failed with:
```
java.lang.IllegalStateException: Cannot serialize object because no JSON
serializer found in classpath. Please put Jackson (Databind), Gson,
Johnzon, or Yasson in the classpath.
```
5 of 13 tests failed this way on the first run.

**Root cause:** `pom.xml` initially declared only `rest-assured` and `junit-jupiter`. REST Assured's `Map`-to-JSON body serialization needs a JSON mapper library present at runtime and doesn't bundle one itself.

**Fix:** added `jackson-databind` 2.18.1 as a test-scope dependency.

### Finding 2 — Test assertions expected fields the real API doesn't return there

**Evidence, after Finding 1 was fixed:** the two genuinely cross-endpoint scenarios still failed:
```
data.find { it.id == '...' }.resolutions[0].final_response
Expected: RestAssured integration test resolution for ...
  Actual: null

data.find { it.id == '...' }.customer_feedback[0].score
Expected: <4>
  Actual: null
```
The `PUT`/`POST` writes themselves had already succeeded (asserted separately, passed) — only the read-back assertions failed.

**Root cause, confirmed by curling the real endpoints directly with the real tokens** rather than guessing from the code:
- `GET /api/tickets`'s own `select()` (`frontend/src/app/api/tickets/route.ts`) explicitly lists `resolutions`'s columns and does not include `final_response` — a deliberate lighter list-view payload; the admin console fetches full resolution text separately, per ticket, when a row is opened.
- `GET /api/user_tickets` returns `customer_feedback` as a **singular nested object** (`{"score": 4}`), not an array like its sibling relations `resolutions`/`ticket_classifications`. PostgREST infers this from the `ticket_id` unique constraint the feedback route's own `upsert(..., {onConflict: 'ticket_id'})` depends on — a ticket can only ever have one feedback row, so PostgREST treats it as a to-one relationship and shapes the JSON accordingly.

**This is not an application bug** — both behaviors are consistent, deliberate API design. It's recorded here because it's exactly the kind of contract detail integration testing is supposed to surface: a client (or a test) that assumes every nested relation is shaped the same way will silently read `null` instead of the real value.

**Fix:** corrected the assertions to check fields the list endpoints actually return — `status`/`resolutions[0].escalated` for the resolve scenario, and `customer_feedback.score` (no array index) for the feedback scenario. Both still genuinely prove the cross-endpoint write-then-read integration; they just check accurate fields.

## 4. Final result: 13/13 passed

| Class | Tests | Result |
|---|---|---|
| `TicketsApiIntegrationTest` | 5 | **5/5 passed** |
| `UserTicketsAndFeedbackIntegrationTest` | 5 | **5/5 passed** |
| `SidecarIntegrationTest` | 3 | **3/3 passed** |

Both cross-endpoint integration scenarios — resolve-then-read and feedback-then-read — now pass against the real, live system, real production Supabase, with no mocks anywhere in the request path.

Full raw output: `test-log.txt`. Surefire's own per-test XML reports are written to `target/surefire-reports/` (git-ignored, regenerated per run).

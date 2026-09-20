# DC-015 — API Design Constraints (also DC-007 Interface Constraints)

**Status before:** 🟡 Partial — REST/JSON were fine, but there was no OpenAPI document anywhere, no versioning (`/api/tickets` was the only path).
**Status after:** ✅ Implemented for the ticket API: OpenAPI documentation (drift-protected) and URL versioning (`/api/v1`) with a deprecated alias.

## What was wrong

DC-015 requires that "APIs shall expose OpenAPI documentation" and that "API documentation is automatically
generated"; DC-007 that "API contracts shall remain versioned and documented". Neither Java service had any
`springdoc`/`swagger` dependency, so nothing described the endpoints, their auth requirement, or their error
responses — a client had to read the controller source.

## What changed (`ticket-core-service`, `agent-review-service`)

- **`springdoc-openapi-starter-webmvc-api` 2.5.0** generates the contract at `GET /v3/api-docs`. The `-api`
  artifact is used on purpose: it ships **no Swagger UI**, so no documentation UI is exposed.
- **The contract requires authentication**, like every other endpoint (a test asserts 401 without a token;
  another asserts `/swagger-ui.html` and `/swagger-ui/index.html` are not served).
- **`OpenApiConfig`** declares title/version, a `bearerAuth` JWT scheme and a global security requirement, so
  every operation is documented as requiring a token.
- **Every documented outcome a client must handle**: POST → 202/400/401/503, GET → 200/401/503.
- **`ApiError`** (a record) is now the *actual* return type of every error handler **and** the schema the spec
  references — the documentation cannot describe a shape the code doesn't produce.
- **Validation rules appear in the contract** (`required`, `maxLength: 20000` / `500`, plus a description that
  `rawText` needs a non-whitespace character; `@NotBlank` has no exact OpenAPI equivalent so it is stated in words).
- **A leftover debug endpoint was removed:** `TestController` (`POST /api/test` → `"OK"`) in `ticket-core-service`,
  referenced by nothing. The spec generation surfaced it; a test now asserts `/api/tickets` is the only path.

## Keeping documentation in sync (SUP-010)

`OpenApiContractTest` compares the generated spec to a committed snapshot
(`src/test/resources/openapi/<service>.json`). Any API change fails the build until the snapshot is regenerated
and committed — turning an API change into a deliberate, reviewable diff:

```
./mvnw test -Dtest=OpenApiContractTest -Dopenapi.update=true
```

## No Supabase changes needed.

## Tests (CI-like: `.env` hidden, Redis unreachable)

`OpenApiContractTest` (8 cases per service): contract requires auth; no docs UI exposed; every outcome documented;
bearer requirement declared; `ApiError` schema built from the handlers' type; validation rules visible;
no leftover debug paths; **generated spec equals the committed snapshot**.
**Mutation check:** changing one operation summary made the snapshot test fail with the regenerate instruction,
then was reverted.

```
ticket-core-service:   Tests run: 52, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 49, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

## What's still open

- **`api-gateway` has no OpenAPI document.** It proxies `/api/tickets/**` and exposes only health; its public
  contract *is* the ticket service's. Documenting the proxy separately would duplicate it.
- **Python services (FastAPI)** already emit OpenAPI automatically; not verified or pinned here.
- `agent-review-service` is documented as it currently is — a near-duplicate of the ticket intake endpoints. Its
  intended human-review endpoints (FR-035/FR-036) don't exist yet, so there is nothing more to document.

## API versioning (second half of DC-015 / DC-007)

**Design:** `/api/v1/tickets` is the versioned contract. The original `/api/tickets` is kept as a **deprecated alias**
(SRS: "interface changes shall preserve backward compatibility whenever feasible"), so nothing breaks while clients migrate.

- **Both Java services** map the same handlers at both paths (`@RequestMapping({"/api/v1/tickets", "/api/tickets"})`).
- **`LegacyApiDeprecationFilter`** adds `Deprecation: true` and `Link: </api/v1/tickets>; rel="successor-version"` to every
  response on the old path — *including 401s*, because a client failing to authenticate against the old path should
  still learn where the supported one is. The v1 path carries neither header.
- **The OpenAPI contract says so too:** both operations of `/api/tickets` are `deprecated: true` with a description
  pointing at v1; `/api/v1/tickets` is not deprecated (asserted, and pinned by the snapshot).
- **Gateway:** the shipped route now matches `Path=/api/v1/tickets/**,/api/tickets/**`; `TraceFilter` recognises both
  submission paths. An unknown version (`/api/v2/tickets`) is **not** proxied (404) and not accidentally served by the services.
- **Frontend** now calls `/api/v1/tickets`; the mocks that matched the gateway URL in 5 test files were updated. The
  frontend's *own* Next.js routes (`/api/tickets`, `/api/user_tickets`, …) are a different service and were not touched.

### Tests (CI-like)

| Where | Verifies |
|---|---|
| `ApiVersioningTest` (×2 services, 6 cases) | v1 serves without a deprecation signal; legacy path still serves and announces its successor; the signal is on 401s too; submission works on both paths; v1 is authenticated like legacy; `/api/v2/...` is 404 |
| `OpenApiContractTest` (×2, now 9 cases) | only `/api/v1/tickets` + deprecated alias in the contract; alias operations `deprecated: true`, v1 not; snapshot regenerated |
| `CorrelationIdPropagationTest` (api-gateway) | reads the **shipped** route predicate: covers both paths; a v1 request is proxied with its correlation ID; `/api/v2/tickets` is not proxied |
| `TraceFilterTest` (api-gateway) | v1 submission publishes a trace event |
| frontend (vitest) | 143 pass; eslint 0 errors |

**Mutation check:** removing `/api/v1/tickets/**` from the *shipped* `application.properties` made both gateway v1 tests fail;
restored.

```
api-gateway:           Tests run: 34, Failures: 0, Errors: 0 -- BUILD SUCCESS
ticket-core-service:   Tests run: 59, Failures: 0, Errors: 0 -- BUILD SUCCESS
agent-review-service:  Tests run: 56, Failures: 0, Errors: 0 -- BUILD SUCCESS
```

### What's still open

- The alias has **no sunset date**; retiring `/api/tickets` is a follow-up once external clients (if any) have moved. A
  `Sunset` header should be added when a date is chosen.
- `frontend/src/app/__tests__/api-integration.test.ts` still hard-codes `http://localhost:8080/api/tickets` in its own
  self-contained fetch mocks; it exercises no application code, so it was left as-is.

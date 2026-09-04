# 09 — REST Assured API Integration Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md). Final result:
**13/13 tests passed**, after fixing a missing JSON-serializer dependency
and two test assertions that expected fields the real API deliberately
doesn't return in that response (found live, not app bugs — see report §3).

**Assigned-table mapping:** Integration testing → REST Assured (API half;
the UI half is [`Testing/08-Selenium-Functional-Testing`](../08-Selenium-Functional-Testing/)).

## Scope

Real, live HTTP integration tests — no mocks — against the Next.js API
routes (`:3000`) and `clario-ml-sidecar` (`:8600`). Distinct from
[`Testing/07-API-Testing`](../07-API-Testing/)'s Postman suite (per-endpoint
contract checks) by focusing on genuinely **cross-call** scenarios: write
through one endpoint, then read back through a *different* call (or a
different endpoint entirely) and confirm they agree.

## How to run this

Requires the frontend (`:3000`) and `clario-ml-sidecar` (`:8600`) running,
and Java 21+ on `PATH` (already required elsewhere in this repo for the
Java services).

```bash
Testing/09-RestAssured-API-Testing/run_tests.sh
```

This downloads Maven locally into `.tools/` at the repo root if it isn't
there yet (no system install, no sudo — same approach `Testing/07`
takes with `npx newman`), creates disposable fixtures, runs `mvn test`,
and tears the fixtures down.

To run it manually instead:
```bash
cd clario-ml-sidecar && source .venv/bin/activate
python ../Testing/09-RestAssured-API-Testing/setup_fixtures.py

cd ../Testing/09-RestAssured-API-Testing
../../.tools/apache-maven-3.9.9/bin/mvn test

cd ../../clario-ml-sidecar && source .venv/bin/activate
python ../Testing/09-RestAssured-API-Testing/teardown_fixtures.py
```

## Why REST Assured specifically (vs. Postman/Newman)

Both hit real HTTP endpoints, but they answer different questions:

- **Postman/Newman** (Testing/07) is fast to write and read for **per-endpoint
  contract** checks — "does this one request, in isolation, return the right
  status/shape?" Good for breadth across many endpoints.
- **REST Assured** is a real programming language (Java) wrapping the same
  HTTP calls, so it's the natural fit when a test needs actual logic between
  requests — capturing a value from one response, computing something, and
  using it to shape the next request or assertion. This suite's two
  signature tests (resolve-then-read, feedback-then-read) are exactly that
  shape: chain two real calls and assert they describe the same underlying
  state, which is what "integration" testing means as distinct from
  "does this endpoint work."

## Files in this folder

| File | What it is |
|---|---|
| `pom.xml` | Maven project — REST Assured, JUnit 5, Jackson Databind |
| `src/test/java/com/clario/apitest/TestFixtures.java` | Reads `fixtures.json` via REST Assured's own `JsonPath` |
| `src/test/java/com/clario/apitest/*Test.java` | The 3 test classes, 13 tests |
| `setup_fixtures.py` / `teardown_fixtures.py` | Create/delete this run's disposable accounts and tickets |
| `run_tests.sh` | Runs the whole phase end-to-end, downloading Maven if needed |
| `TEST_REPORT.md` | Findings and the fix record |
| `test-log.txt` | Raw `mvn test` output |

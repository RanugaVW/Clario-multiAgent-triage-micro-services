# 08 — Selenium Functional Testing

**Status:** Complete — see [`TEST_REPORT.md`](TEST_REPORT.md).

**Assigned-table mapping:** Test Automation + Browser automation/functional
tests + the UI half of Integration testing (the API half is
[`Testing/09-RestAssured-API-Testing`](../09-RestAssured-API-Testing/)).

## Scope

Real, live browser automation with Selenium WebDriver + headless Chrome
against the real `next dev` server (`:3000`) and production Supabase - no
mocks anywhere. 8 scenarios: the login form (positive + negative), the
authorization boundary around `/admin`, session/logout behavior, a real
ticket submitted through the actual dashboard form, and the admin console
finding and opening that ticket.

**Complements, doesn't duplicate,** [`Testing/03-UI-E2E-Testing`](../03-UI-E2E-Testing/)'s
Playwright suite, which already covers the full multi-minute LangGraph
resolve/escalate pipeline end to end. This suite demonstrates Selenium
specifically, across a different scenario shape - auth, authorization,
form submission, and session lifecycle - each finishing in seconds.

## How to run this

Requires the frontend (`:3000`) running. The one scenario that submits a
real ticket also needs the Spring Boot `api-gateway` (`:8080`) reachable -
if it isn't, that one test skips cleanly with a clear reason instead of
faking success (see `gateway_is_reachable()` in the test file).

```bash
Testing/08-Selenium-Functional-Testing/run_tests.sh
```

Or manually:
```bash
cd clario-ml-sidecar && source .venv/bin/activate
python ../Testing/08-Selenium-Functional-Testing/setup_fixtures.py

cd ../Testing/08-Selenium-Functional-Testing
source .venv/bin/activate   # this phase's own venv, see one-time setup below
pytest test_functional_e2e.py -v

cd ../../clario-ml-sidecar && source .venv/bin/activate
python ../Testing/08-Selenium-Functional-Testing/teardown_fixtures.py
```

### One-time environment setup

```bash
cd Testing/08-Selenium-Functional-Testing
python3 -m venv .venv
source .venv/bin/activate
pip install selenium pytest python-dotenv supabase
```

A matching `chromedriver` is expected at
`.tools/chromedriver-linux64/chromedriver` (repo root). Selenium 4's own
built-in driver-resolution (Selenium Manager) was unreliably slow in this
environment - see TEST_REPORT.md §3 for what happened and how this was
worked around. To fetch it yourself:

```bash
google-chrome --version   # note the version, e.g. 145.0.7632.159
# find the matching chromedriver build:
curl -s "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); m=d['milestones']['145']; print(m['version'])"
# then download that version's linux64/chromedriver-linux64.zip from
# https://storage.googleapis.com/chrome-for-testing-public/<version>/linux64/chromedriver-linux64.zip
# and unzip it into .tools/chromedriver-linux64/ at the repo root.
```

## Files in this folder

| File | What it is |
|---|---|
| `test_functional_e2e.py` | The 8 real Selenium scenarios |
| `setup_fixtures.py` / `teardown_fixtures.py` | Create/delete this run's disposable customer + admin accounts and canary ticket |
| `run_tests.sh` | Runs the whole phase end-to-end |
| `TEST_REPORT.md` | Results and the environment issues found along the way |
| `test-log.txt` | Raw `pytest -v` output |

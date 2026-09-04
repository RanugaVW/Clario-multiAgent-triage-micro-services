# Selenium Functional Test Report — Clario System

**Date:** 2026-09-04
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch:** `main`
**Environment:** Production Supabase project (`mdvfvtpbwqhccmaarpli`), the live `next dev` server (`:3000`), and (for one scenario) the real Spring Boot `api-gateway` on `:8080`. Tooling: Selenium 4.48.0 + headless Chrome 145 + pytest 9.1.1, in a dedicated `.venv`.

**Final result: 8/8 tests passed.** Getting there surfaced three real, worth-recording issues along the way - none in the application itself, all in getting Selenium reliably running in this specific environment. Each is documented below with what was actually observed, not assumed.

## 1. Scope

Maps to the assigned table's "Test Automation" + "Browser automation/functional tests" rows, plus the UI half of "Integration testing". 8 real, live scenarios in `test_functional_e2e.py`:

| # | Scenario | Proves |
|---|---|---|
| 1 | Login page renders the real form | Basic page load / element presence |
| 2 | Wrong password is rejected | A real Supabase auth round trip, not client-side-only validation |
| 3 | Customer login redirects to `/dashboard` | Auth + role-based routing |
| 4 | Admin login redirects to `/admin` | Same, for the admin role |
| 5 | Unauthenticated visitor going straight for `/admin` is bounced to `/login` | A real authorization boundary, not just the happy path |
| 6 | Logout clears the session; `/dashboard` afterward also bounces to `/login` | Session actually cleared, not just UI state |
| 7 | Customer submits a real ticket via the dashboard form; it appears in their history | Full real chain: form → real `api-gateway` (`:8080`) → Supabase → history read-back |
| 8 | Admin finds and opens that ticket in the console | Real search + click-through interaction |

**Complements, doesn't duplicate**, [`Testing/03-UI-E2E-Testing`](../03-UI-E2E-Testing/)'s Playwright suite, which already covers the full multi-minute LangGraph resolve/escalate pipeline. This suite demonstrates Selenium specifically, with faster, more numerous scenarios covering auth/authorization/session shapes Playwright's suite doesn't focus on.

## 2. Environment & Tooling

| | |
|---|---|
| Test file | `test_functional_e2e.py` - pytest + Selenium, headless Chrome |
| Fixtures | `setup_fixtures.py` - 1 disposable customer, 1 disposable admin (role set in `public.users`), 1 pre-seeded canary ticket for the admin-visibility scenario |
| chromedriver | Downloaded directly to match the installed Chrome build (145.0.7632.117) - see §3 for why not Selenium's own auto-resolution |
| Regression check | N/A - no application code was touched in this phase |

## 3. Three real issues found getting this running (not application bugs)

### Issue 1 — Selenium Manager's own driver-resolution hung for 5+ minutes

**Evidence:** the very first Selenium smoke test (`webdriver.Chrome(options=options)` with no explicit driver) hung indefinitely; `ps aux` showed a live `selenium-manager` subprocess still running 5+ minutes later, having produced no output.

**Root cause:** Selenium 4's built-in driver auto-resolution queries several Google-hosted endpoints to find and download a matching chromedriver; one or more of those calls was unreliably slow in this specific environment.

**Fix:** looked up the exact matching chromedriver build directly via `googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json` (a small, fast-loading file), downloaded it once into `.tools/chromedriver-linux64/`, and pointed the test suite's `Service(executable_path=...)` at it explicitly - bypassing Selenium Manager's own resolution entirely. Selenium+Chrome then launched immediately.

### Issue 2 — The success modal intercepted the next click

**Evidence:** `ElementClickInterceptedException` clicking the "My tickets" tab right after submitting a ticket - Selenium correctly reported that a modal overlay (`bg-black/60 backdrop-blur-sm`) was covering the intended button.

**Root cause:** the dashboard shows a success modal after submission; the original test tried to click a separate tab button while that modal was still open, instead of using the modal itself.

**Fix:** read `Modal`'s `onClose` handler in `frontend/src/components/ui.tsx` and `dashboard/page.tsx` - closing the modal is what actually switches to the history tab and re-fetches it. The test now clicks the modal's own `Close` button (`aria-label="Close"`) instead of fighting it for a separate click target.

### Issue 3 — The suite's last 1-2 tests intermittently timed out, only when run as part of the full sequential suite

**Evidence:** `test_customer_can_submit_a_real_ticket_via_the_form` (and once, `test_admin_can_find_and_open_a_ticket`) timed out waiting on a real network round trip - but passed cleanly and quickly every time either was run in isolation. `free -h`, checked while diagnosing this, showed the real cause directly:
```
Mem:  15Gi total, 14Gi used, 290Mi free
Swap: 4.0Gi total, 4.0Gi used, 6.7Mi free
```
This machine runs `clario-ml-sidecar` with loaded ML models, the frontend dev server, and `voice-to-text-service` simultaneously - swap was completely exhausted even before this suite ran. A fresh headless Chrome process per test (the original design, one `webdriver.Chrome(...)` per test via a function-scoped fixture) compounded that: by the 7th-8th test, spinning up yet another full Chrome process under an already swap-exhausted machine measurably degraded response times.

**What was tried and rejected:** increasing the wait timeout (15s → 20s → 30s) reduced but did not eliminate the failure - a symptom fix chasing a resource problem, not a fix for the actual cause. Per this project's own debugging discipline, two timeout bumps without a reliable fix is the signal to stop adjusting the number and re-examine the design instead.

**Real fix:** made the Chrome driver **session-scoped** instead of per-test - one browser process for the whole suite instead of 8. To keep tests isolated despite sharing a process, an `autouse` fixture (`_clean_browser_state`) clears cookies and `localStorage`/`sessionStorage` before every test, since Clario keeps its session token in `localStorage` (confirmed: this app sets no auth cookies at all - see the "does Clario use cookies" discussion earlier in this session). Re-run after the fix: **8/8 passed in 82.7s**, down from as long as 267.7s across the failing full-suite attempts, and reliably clean across two consecutive full runs.

## 4. Final result: 8/8 passed

```
test_login_page_renders_the_real_form PASSED
test_login_rejects_wrong_password PASSED
test_customer_login_redirects_to_dashboard PASSED
test_admin_login_redirects_to_admin_console PASSED
test_unauthenticated_visitor_cannot_reach_admin_console PASSED
test_logout_clears_the_session PASSED
test_customer_can_submit_a_real_ticket_via_the_form PASSED
test_admin_can_find_and_open_a_ticket PASSED

8 passed in 82.69s
```

Scenario 7 (real ticket submission) genuinely exercised the live `api-gateway` (`:8080`), found already running in this environment - not simulated. Had it been unreachable, the test is written to skip cleanly with an explicit reason (`gateway_is_reachable()`) rather than silently passing or failing for the wrong reason - this mirrors the scoping decision documented in `Testing/07-API-Testing/TEST_REPORT.md` §1 for the same Docker-network-dependent services.

Full raw output: `test-log.txt`.

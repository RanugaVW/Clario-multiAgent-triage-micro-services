"""Real, live Selenium functional/browser-automation tests for the Clario
frontend. No mocks: a real headless Chrome drives the real `next dev`
server (:3000), which talks to the real production Supabase project - the
same "no mocked network calls" standard every other phase in this folder
holds itself to.

Covers, per Testing/README.md's Phase 08 mapping: Test Automation, Browser
automation/functional tests, and the UI half of Integration testing.

Complements (does not duplicate) Testing/03-UI-E2E-Testing's Playwright
suite, which already exercises the full multi-minute LangGraph
resolve/escalate pipeline end to end. This suite instead demonstrates
Selenium specifically, across a different scenario shape: auth (positive +
negative), authorization/session boundaries, real form submission, and
admin visibility - each scenario finishes in seconds rather than minutes.

Setup:
    cd clario-ml-sidecar && source .venv/bin/activate
    python ../Testing/08-Selenium-Functional-Testing/setup_fixtures.py

Run:
    cd Testing/08-Selenium-Functional-Testing
    source .venv/bin/activate
    pytest test_functional_e2e.py -v

Teardown:
    cd clario-ml-sidecar && source .venv/bin/activate
    python ../Testing/08-Selenium-Functional-Testing/teardown_fixtures.py
"""

from __future__ import annotations

import json
import socket
import time
import uuid
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

PHASE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PHASE_ROOT.parents[1]
# This dev machine shares memory/CPU with the live ML sidecar (same
# characteristic Testing/03-UI-E2E-Testing's Playwright suite documents for
# its own generous timeouts) - a fresh Chrome session late in a long,
# sequential run can occasionally need more than 15s for a login redirect
# that normally takes ~2s. 20s absorbs that without masking a real hang.
WAIT_SECONDS = 20

# Selenium Manager's own driver-resolution network calls were unreliably
# slow in this environment (observed hanging for 5+ minutes). A matching
# chromedriver was downloaded once into .tools/ (see README.md) and is
# used directly here instead, the same way run_tests.sh downloads Maven
# and JMeter locally rather than relying on a system install.
_CHROMEDRIVER_PATH = REPO_ROOT / ".tools" / "chromedriver-linux64" / "chromedriver"


@pytest.fixture(scope="session")
def fixtures() -> dict:
    path = PHASE_ROOT / "fixtures.json"
    if not path.exists():
        pytest.fail(
            "fixtures.json not found - run setup_fixtures.py first "
            "(see this file's module docstring)."
        )
    return json.loads(path.read_text())


@pytest.fixture(scope="session")
def driver():
    # Session-scoped rather than one fresh Chrome process per test: this
    # machine runs at 14/15Gi RAM used with swap fully exhausted (confirmed
    # via `free -h` while diagnosing a real, reproducible failure - the
    # suite's last 1-2 tests reliably timed out waiting on a real network
    # round trip, even at 30s, only when run after 6+ prior tests each spun
    # up and tore down their own Chrome instance; the same test passed
    # cleanly every time run in isolation). One shared browser for the
    # whole suite removes that process churn instead of chasing it with
    # ever-larger timeouts. See _clean_browser_state below for how
    # isolation between tests is still preserved without a fresh process.
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,1000")
    service = Service(executable_path=str(_CHROMEDRIVER_PATH)) if _CHROMEDRIVER_PATH.exists() else Service()
    drv = webdriver.Chrome(options=options, service=service)
    drv.implicitly_wait(0)  # explicit WebDriverWait is used everywhere instead
    yield drv
    drv.quit()


@pytest.fixture(autouse=True)
def _clean_browser_state(driver):
    """Every test gets a logged-out, storage-free browser, even though the
    underlying Chrome process is now shared across the whole session -
    without this, a later test would inherit an earlier test's login
    session, since Clario keeps it in localStorage (the Supabase client's
    default - this app sets no auth cookies at all)."""
    driver.delete_all_cookies()
    try:
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    except Exception:
        pass
    yield


def login(driver, base_url: str, email: str, password: str) -> None:
    driver.get(f"{base_url}/login")
    email_input = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
    )
    email_input.send_keys(email)
    driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()


def wait_for_path(driver, path_fragment: str) -> None:
    WebDriverWait(driver, WAIT_SECONDS).until(EC.url_contains(path_fragment))


def gateway_is_reachable(host: str = "localhost", port: int = 8080, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------- Auth

def test_login_page_renders_the_real_form(driver, fixtures):
    driver.get(f"{fixtures['base_url']}/login")
    email_input = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
    )
    assert email_input.is_displayed()
    assert driver.find_element(By.CSS_SELECTOR, "input[type='password']").is_displayed()
    assert driver.find_element(By.CSS_SELECTOR, "button[type='submit']").is_displayed()


def test_login_rejects_wrong_password(driver, fixtures):
    """Real Supabase auth call with a deliberately wrong password - proves
    the negative path actually round-trips to the real auth backend rather
    than being caught by client-side validation alone."""
    login(driver, fixtures["base_url"], fixtures["customer"]["email"], "definitely-the-wrong-password")
    error = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "form div"))
    )
    # Must not have navigated away - still on /login.
    assert "/login" in driver.current_url
    WebDriverWait(driver, WAIT_SECONDS).until(
        lambda d: "invalid" in d.page_source.lower() or "credentials" in d.page_source.lower()
    )


def test_customer_login_redirects_to_dashboard(driver, fixtures):
    login(driver, fixtures["base_url"], fixtures["customer"]["email"], fixtures["customer"]["password"])
    wait_for_path(driver, "/dashboard")
    assert "/dashboard" in driver.current_url


def test_admin_login_redirects_to_admin_console(driver, fixtures):
    login(driver, fixtures["base_url"], fixtures["admin"]["email"], fixtures["admin"]["password"])
    wait_for_path(driver, "/admin")
    assert "/admin" in driver.current_url


# ---------------------------------------------------------------- Authorization / session

def test_unauthenticated_visitor_cannot_reach_admin_console(driver, fixtures):
    """No login performed - a fresh, cookie-less browser context going
    straight for /admin. A real authorization boundary check, not just an
    auth-flow happy path."""
    driver.get(f"{fixtures['base_url']}/admin")
    try:
        WebDriverWait(driver, WAIT_SECONDS).until(EC.url_contains("/login"))
    except TimeoutException:
        pytest.fail(
            f"Unauthenticated visitor reached {driver.current_url} without "
            "being redirected to /login."
        )
    assert "/login" in driver.current_url


def test_logout_clears_the_session(driver, fixtures):
    login(driver, fixtures["base_url"], fixtures["customer"]["email"], fixtures["customer"]["password"])
    wait_for_path(driver, "/dashboard")

    logout_button = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='Sign Out'], button"))
    )
    # The dashboard's logout control has no stable selector of its own - find
    # it by its own accessible text instead of relying on styling classes.
    buttons = driver.find_elements(By.TAG_NAME, "button")
    logout_candidates = [b for b in buttons if "log out" in b.text.lower() or "sign out" in b.text.lower()]
    assert logout_candidates, "No logout control found on the dashboard."
    logout_candidates[0].click()

    wait_for_path(driver, "/login")

    # With the session actually cleared, going straight back to /dashboard
    # must bounce to /login again, not silently show cached customer data.
    driver.get(f"{fixtures['base_url']}/dashboard")
    WebDriverWait(driver, WAIT_SECONDS).until(EC.url_contains("/login"))
    assert "/login" in driver.current_url


# ---------------------------------------------------------------- Real form submission

def test_customer_can_submit_a_real_ticket_via_the_form(driver, fixtures):
    # The submit form calls the real Spring Boot api-gateway (:8080), which
    # only runs inside the docker-compose stack (see Testing/07-API-Testing/
    # TEST_REPORT.md §1 for why that's out of scope for this environment).
    # Skip cleanly with a clear reason rather than faking success - if the
    # gateway is ever up when this runs, this test genuinely exercises it.
    if not gateway_is_reachable():
        pytest.skip("api-gateway (:8080) is not reachable - requires the docker-compose stack, not running in this environment.")

    marker = f"[SELENIUM-SUBMIT-{uuid.uuid4().hex[:8]}]"
    ticket_text = f"{marker} My card was charged twice for the same order, please refund the duplicate charge."

    login(driver, fixtures["base_url"], fixtures["customer"]["email"], fixtures["customer"]["password"])
    wait_for_path(driver, "/dashboard")

    textarea = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.ID, "ticket-text"))
    )
    textarea.clear()
    textarea.send_keys(ticket_text)

    submit_buttons = [
        b for b in driver.find_elements(By.TAG_NAME, "button")
        if "submit ticket" in b.text.lower()
    ]
    assert submit_buttons, "No 'Submit ticket' button found on the dashboard form."
    submit_buttons[0].click()

    # Real round trip through the real ticket-creation path - give it real time.
    close_button = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Close']"))
    )

    # Closing the success modal is what actually switches the dashboard to
    # the history tab and re-fetches it (see Modal's onClose handler in
    # dashboard/page.tsx) - clicking a separate "My tickets" tab button
    # first is unreliable, since the modal overlay still intercepts it.
    close_button.click()

    # A real round trip (fetchHistory() -> GET /api/user_tickets -> Supabase)
    # under this machine's own resource constraints (see WAIT_SECONDS) - a
    # longer, dedicated wait here rather than the shared default, since this
    # step chains a full extra network round trip on top of everything the
    # global timeout already budgets for.
    WebDriverWait(driver, 30).until(lambda d: marker in d.page_source)
    assert marker in driver.page_source


# ---------------------------------------------------------------- Admin visibility

def test_admin_can_find_and_open_a_ticket(driver, fixtures):
    login(driver, fixtures["base_url"], fixtures["admin"]["email"], fixtures["admin"]["password"])
    wait_for_path(driver, "/admin")

    all_tickets_tab = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'All Tickets') or contains(., 'all tickets')]"))
    )
    all_tickets_tab.click()

    search_box = WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search by ticket ID']"))
    )
    search_box.send_keys(fixtures["canary_ticket_id"])

    row = WebDriverWait(driver, WAIT_SECONDS).until(
        lambda d: next(
            (el for el in d.find_elements(By.CSS_SELECTOR, "div.cursor-pointer") if fixtures["marker"] in el.text),
            None,
        )
    )
    assert row is not None
    row.click()

    # Opening the row should reveal ticket detail content containing the
    # same marker text (the raw ticket body), proving the click actually
    # opened the right ticket's detail view.
    WebDriverWait(driver, WAIT_SECONDS).until(lambda d: d.page_source.count(fixtures["marker"]) >= 2)

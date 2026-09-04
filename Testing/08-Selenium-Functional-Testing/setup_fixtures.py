"""Creates real, disposable test accounts for the Selenium functional-testing
phase and writes their credentials to fixtures.json (git-ignored) for the
test suite to read. Same safety model as every other phase in this folder:
everything created here is tagged and owned by this run, and
teardown_fixtures.py deletes all of it afterwards.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/08-Selenium-Functional-Testing/setup_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPO_ROOT / "clario-ml-sidecar"
PHASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SIDECAR_ROOT))
os.chdir(SIDECAR_ROOT)

from dotenv import load_dotenv  # noqa: E402
from supabase import create_client  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_PROJECT_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SECRET_API"]
admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

RUN_ID = uuid.uuid4().hex[:8]
MARKER = f"SELENIUM-TEST-{RUN_ID}"
TEST_PASSWORD = "ClarioSeleniumTest-Pass-2026!"

CUSTOMER_EMAIL = "clario-seleniumtest-customer@example.com"
ADMIN_EMAIL = "clario-seleniumtest-admin@example.com"


def _cleanup_leftover_users() -> None:
    for u in admin_client.auth.admin.list_users():
        if u.email in (CUSTOMER_EMAIL, ADMIN_EMAIL):
            admin_client.auth.admin.delete_user(u.id)


def main() -> None:
    print(f"Setting up Selenium fixtures (run {RUN_ID})...")
    _cleanup_leftover_users()

    customer = admin_client.auth.admin.create_user(
        {"email": CUSTOMER_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    admin_user = admin_client.auth.admin.create_user(
        {"email": ADMIN_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    admin_client.table("users").update({"role": "admin"}).eq("id", admin_user.id).execute()

    # A pre-seeded ticket for the admin-visibility test, so that test never
    # depends on the "customer submits a ticket" test having already run -
    # each test in the suite stays independently runnable/orderable.
    canary = (
        admin_client.table("tickets")
        .insert(
            {
                "user_id": customer.id,
                "customer_name": "Selenium Test Canary",
                "customer_email": CUSTOMER_EMAIL,
                "subject": MARKER,
                "raw_text": f"{MARKER}: this ticket exists only for Selenium functional testing and is deleted at the end of this run.",
                "status": "received",
            }
        )
        .execute()
        .data[0]
    )

    fixtures = {
        "run_id": RUN_ID,
        "marker": MARKER,
        "base_url": "http://localhost:3000",
        "customer": {"id": customer.id, "email": CUSTOMER_EMAIL, "password": TEST_PASSWORD},
        "admin": {"id": admin_user.id, "email": ADMIN_EMAIL, "password": TEST_PASSWORD},
        "canary_ticket_id": canary["id"],
    }
    out_path = PHASE_ROOT / "fixtures.json"
    out_path.write_text(json.dumps(fixtures, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

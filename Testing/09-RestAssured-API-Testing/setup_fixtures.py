"""Creates real, disposable fixtures for the REST Assured integration-testing
phase and writes fixtures.json (git-ignored - holds live JWTs) for the Java
test suite to read via RestAssured's JsonPath. Same safety model as every
other phase: everything created here is tagged, and teardown_fixtures.py
deletes it all afterwards.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/09-RestAssured-API-Testing/setup_fixtures.py
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
SUPABASE_ANON_KEY = os.environ["SUPABASE_PUBLIC_API"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SECRET_API"]
admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

RUN_ID = uuid.uuid4().hex[:8]
MARKER = f"RESTASSURED-TEST-{RUN_ID}"
TEST_PASSWORD = "ClarioRestAssuredTest-Pass-2026!"

CUSTOMER_A_EMAIL = "clario-restassured-customer-a@example.com"
CUSTOMER_B_EMAIL = "clario-restassured-customer-b@example.com"
STAFF_EMAIL = "clario-restassured-staff@example.com"


def _cleanup_leftover_users() -> None:
    for u in admin_client.auth.admin.list_users():
        if u.email in (CUSTOMER_A_EMAIL, CUSTOMER_B_EMAIL, STAFF_EMAIL):
            admin_client.auth.admin.delete_user(u.id)


def sign_in(email: str, password: str) -> str:
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    return res.session.access_token


def main() -> None:
    print(f"Setting up REST Assured fixtures (run {RUN_ID})...")
    _cleanup_leftover_users()

    a = admin_client.auth.admin.create_user(
        {"email": CUSTOMER_A_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    b = admin_client.auth.admin.create_user(
        {"email": CUSTOMER_B_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    staff = admin_client.auth.admin.create_user(
        {"email": STAFF_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    admin_client.table("users").update({"role": "admin"}).eq("id", staff.id).execute()

    def make_ticket(tag: str) -> str:
        return (
            admin_client.table("tickets")
            .insert(
                {
                    "user_id": a.id,
                    "customer_name": "RestAssured Test Canary",
                    "customer_email": CUSTOMER_A_EMAIL,
                    "subject": f"{MARKER}-{tag}",
                    "raw_text": f"{MARKER}: this ticket exists only for REST Assured integration testing and is deleted at the end of this run.",
                    "status": "received",
                }
            )
            .execute()
            .data[0]["id"]
        )

    ticket_resolve = make_ticket("resolve")
    ticket_feedback = make_ticket("feedback")
    ticket_read = make_ticket("read")

    token_a = sign_in(CUSTOMER_A_EMAIL, TEST_PASSWORD)
    token_b = sign_in(CUSTOMER_B_EMAIL, TEST_PASSWORD)
    token_staff = sign_in(STAFF_EMAIL, TEST_PASSWORD)

    fixtures = {
        "runId": RUN_ID,
        "marker": MARKER,
        "nextjsUrl": "http://localhost:3000",
        "sidecarUrl": "http://127.0.0.1:8600",
        "customerAId": a.id,
        "customerBId": b.id,
        "staffId": staff.id,
        "tokenA": token_a,
        "tokenB": token_b,
        "tokenStaff": token_staff,
        "ticketResolve": ticket_resolve,
        "ticketFeedback": ticket_feedback,
        "ticketRead": ticket_read,
    }
    out_path = PHASE_ROOT / "fixtures.json"
    out_path.write_text(json.dumps(fixtures, indent=2))
    print(f"Wrote {out_path}")

    ids_path = PHASE_ROOT / ".fixture_ids.json"
    ids_path.write_text(
        json.dumps(
            {
                "customer_a_id": a.id,
                "customer_b_id": b.id,
                "staff_id": staff.id,
                "ticket_ids": [ticket_resolve, ticket_feedback, ticket_read],
            },
            indent=2,
        )
    )
    print("Fixtures ready.")


if __name__ == "__main__":
    main()

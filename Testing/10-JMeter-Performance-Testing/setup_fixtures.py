"""Creates one real, disposable staff account for the JMeter performance
phase and prints its access token (also written to fixtures.json) for
run_tests.sh to pass into JMeter via -JauthToken=. Same safety model as
every other phase: teardown_fixtures.py deletes the account afterwards.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/10-JMeter-Performance-Testing/setup_fixtures.py
"""

from __future__ import annotations

import json
import os
import sys
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

STAFF_EMAIL = "clario-jmetertest-staff@example.com"
TEST_PASSWORD = "ClarioJMeterTest-Pass-2026!"


def main() -> None:
    for u in admin_client.auth.admin.list_users():
        if u.email == STAFF_EMAIL:
            admin_client.auth.admin.delete_user(u.id)

    staff = admin_client.auth.admin.create_user(
        {"email": STAFF_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
    ).user
    admin_client.table("users").update({"role": "admin"}).eq("id", staff.id).execute()

    anon_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    token = anon_client.auth.sign_in_with_password(
        {"email": STAFF_EMAIL, "password": TEST_PASSWORD}
    ).session.access_token

    (PHASE_ROOT / "fixtures.json").write_text(
        json.dumps({"staff_id": staff.id, "auth_token": token}, indent=2)
    )
    print(f"Staff account ready: {staff.id}")
    print("Token written to fixtures.json")


if __name__ == "__main__":
    main()

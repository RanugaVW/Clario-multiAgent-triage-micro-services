"""Creates real, disposable fixtures for the API testing phase and writes a
ready-to-run Postman environment file (postman/generated.postman_environment.json)
containing real JWTs and ids for this run.

Same safety model as Testing/05-Security-Access-Control-Testing/run_security_tests.py:
every account and ticket this script creates is tagged and owned by this run only,
and teardown_fixtures.py deletes all of it afterwards. Nothing pre-existing is ever
read, modified, or deleted.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/07-API-Testing/setup_fixtures.py
"""

from __future__ import annotations

import base64
import json
import math
import os
import struct
import sys
import uuid
import wave
from io import BytesIO
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
MARKER = f"API-TEST-CANARY-{RUN_ID}-do-not-treat-as-real-PII"
TEST_PASSWORD = "ClarioApiTest-Pass-2026!"

CUSTOMER_A_EMAIL = "clario-apitest-customer-a@example.com"
CUSTOMER_B_EMAIL = "clario-apitest-customer-b@example.com"
STAFF_EMAIL = "clario-apitest-staff@example.com"


def _cleanup_leftover_users() -> None:
    """Best-effort: remove accounts a previous crashed run left behind."""
    page = admin_client.auth.admin.list_users()
    for u in page:
        if u.email in (CUSTOMER_A_EMAIL, CUSTOMER_B_EMAIL, STAFF_EMAIL):
            admin_client.auth.admin.delete_user(u.id)
    admin_client.table("tickets").delete().like("subject", f"%{MARKER.split('-do-not')[0]}%").execute()


def sign_in(email: str, password: str) -> str:
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    res = client.auth.sign_in_with_password({"email": email, "password": password})
    return res.session.access_token


def make_silent_wav_base64(seconds: float = 0.5, sample_rate: int = 16000) -> str:
    """A tiny, genuinely-decodable silent WAV, base64-encoded - used to exercise
    the transcription endpoints without needing a real recorded voice sample."""
    n_samples = int(seconds * sample_rate)
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<%dh" % n_samples, *([0] * n_samples)))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    print(f"Setting up API-testing fixtures (run {RUN_ID})...")
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

    def make_canary(tag: str) -> str:
        row = (
            admin_client.table("tickets")
            .insert(
                {
                    "user_id": a.id,
                    "customer_name": "API Test Canary",
                    "customer_email": CUSTOMER_A_EMAIL,
                    "subject": f"{MARKER}-{tag}",
                    "raw_text": f"{MARKER}: this ticket exists only for API contract testing and is deleted at the end of this run.",
                    "status": "received",
                }
            )
            .execute()
            .data[0]
        )
        return row["id"]

    # Separate canaries per destructive scenario so one request's side effect
    # (resolving, soft-deleting, force-deleting) never contaminates another.
    canary_read = make_canary("read")          # left alone; GET/read checks
    canary_resolve = make_canary("resolve")    # PUT /api/tickets resolve target
    canary_feedback = make_canary("feedback")  # customer_feedback target
    canary_soft_delete = make_canary("soft-delete")   # sidecar soft-delete target
    canary_force_delete = make_canary("force-delete")  # sidecar force-delete target
    canary_tickets_delete = make_canary("tickets-delete")  # /api/tickets DELETE target
    canary_process = make_canary("process")    # /process_ticket target

    token_a = sign_in(CUSTOMER_A_EMAIL, TEST_PASSWORD)
    token_b = sign_in(CUSTOMER_B_EMAIL, TEST_PASSWORD)
    token_staff = sign_in(STAFF_EMAIL, TEST_PASSWORD)

    environment = {
        "id": f"clario-api-test-{RUN_ID}",
        "name": f"Clario API Test (generated, run {RUN_ID})",
        "values": [
            {"key": "nextjsUrl", "value": "http://localhost:3000", "enabled": True},
            {"key": "sidecarUrl", "value": "http://127.0.0.1:8600", "enabled": True},
            {"key": "voiceUrl", "value": "http://127.0.0.1:8002", "enabled": True},
            {"key": "runId", "value": RUN_ID, "enabled": True},
            {"key": "marker", "value": MARKER, "enabled": True},
            {"key": "customerAId", "value": a.id, "enabled": True},
            {"key": "customerBId", "value": b.id, "enabled": True},
            {"key": "staffId", "value": staff.id, "enabled": True},
            {"key": "tokenA", "value": token_a, "enabled": True},
            {"key": "tokenB", "value": token_b, "enabled": True},
            {"key": "tokenStaff", "value": token_staff, "enabled": True},
            {"key": "canaryRead", "value": canary_read, "enabled": True},
            {"key": "canaryResolve", "value": canary_resolve, "enabled": True},
            {"key": "canaryFeedback", "value": canary_feedback, "enabled": True},
            {"key": "canarySoftDelete", "value": canary_soft_delete, "enabled": True},
            {"key": "canaryForceDelete", "value": canary_force_delete, "enabled": True},
            {"key": "canaryTicketsDelete", "value": canary_tickets_delete, "enabled": True},
            {"key": "canaryProcess", "value": canary_process, "enabled": True},
            {"key": "silentWavBase64", "value": make_silent_wav_base64(), "enabled": True},
        ],
        "_postman_variable_scope": "environment",
    }

    out_path = PHASE_ROOT / "postman" / "generated.postman_environment.json"
    out_path.write_text(json.dumps(environment, indent=2))
    print(f"Wrote {out_path}")

    fixtures_path = PHASE_ROOT / ".fixtures.json"
    fixtures_path.write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "customer_a_id": a.id,
                "customer_b_id": b.id,
                "staff_id": staff.id,
                "canary_ids": [
                    canary_read,
                    canary_resolve,
                    canary_feedback,
                    canary_soft_delete,
                    canary_force_delete,
                    canary_tickets_delete,
                    canary_process,
                ],
            },
            indent=2,
        )
    )
    print(f"Wrote {fixtures_path}")
    print("Fixtures ready.")


if __name__ == "__main__":
    main()

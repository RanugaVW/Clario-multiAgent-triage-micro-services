"""Deletes every disposable account/ticket setup_fixtures.py created for this
run. Safe to re-run: missing rows (already deleted by the tests themselves,
e.g. the soft-delete/force-delete/tickets-delete scenarios) are skipped.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/07-API-Testing/teardown_fixtures.py
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
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SECRET_API"]
admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def main() -> None:
    fixtures_path = PHASE_ROOT / ".fixtures.json"
    if not fixtures_path.exists():
        print("No .fixtures.json found - nothing to tear down.")
        return

    fixtures = json.loads(fixtures_path.read_text())

    for ticket_id in fixtures.get("canary_ids", []):
        for table in ("ticket_drafts", "ticket_classifications", "resolutions", "human_reviews", "customer_feedback"):
            try:
                admin_client.table(table).delete().eq("ticket_id", ticket_id).execute()
            except Exception as e:
                print(f"  (non-fatal) cleanup of {table} for {ticket_id}: {e}")
        try:
            admin_client.table("tickets").delete().eq("id", ticket_id).execute()
        except Exception as e:
            print(f"  (non-fatal) delete ticket {ticket_id}: {e}")

    for key in ("customer_a_id", "customer_b_id", "staff_id"):
        user_id = fixtures.get(key)
        if not user_id:
            continue
        try:
            admin_client.auth.admin.delete_user(user_id)
            print(f"Deleted user {key} = {user_id}")
        except Exception as e:
            print(f"  (non-fatal) delete user {key}: {e}")

    fixtures_path.unlink()
    print("Teardown complete.")


if __name__ == "__main__":
    main()

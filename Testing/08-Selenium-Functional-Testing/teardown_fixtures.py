"""Deletes the disposable accounts (and any tickets they created) that
setup_fixtures.py made for this run. Safe to re-run.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/08-Selenium-Functional-Testing/teardown_fixtures.py
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
    fixtures_path = PHASE_ROOT / "fixtures.json"
    if not fixtures_path.exists():
        print("No fixtures.json found - nothing to tear down.")
        return
    fixtures = json.loads(fixtures_path.read_text())

    # Delete every ticket the customer account created during this run
    # (matched by the marker in the subject, same tagging convention as
    # every other phase) - cascade the FK-referencing rows first.
    customer_id = fixtures["customer"]["id"]
    tickets = (
        admin_client.table("tickets")
        .select("id")
        .eq("user_id", customer_id)
        .execute()
        .data
    )
    for t in tickets:
        tid = t["id"]
        for table in ("ticket_drafts", "ticket_classifications", "resolutions", "human_reviews", "customer_feedback"):
            try:
                admin_client.table(table).delete().eq("ticket_id", tid).execute()
            except Exception as e:
                print(f"  (non-fatal) cleanup of {table} for {tid}: {e}")
        admin_client.table("tickets").delete().eq("id", tid).execute()
    print(f"Deleted {len(tickets)} ticket(s) created during this run.")

    for role in ("customer", "admin"):
        user_id = fixtures[role]["id"]
        try:
            admin_client.auth.admin.delete_user(user_id)
            print(f"Deleted {role} user {user_id}")
        except Exception as e:
            print(f"  (non-fatal) delete {role} user: {e}")

    fixtures_path.unlink()
    print("Teardown complete.")


if __name__ == "__main__":
    main()

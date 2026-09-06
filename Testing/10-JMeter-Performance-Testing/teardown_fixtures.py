"""Deletes the disposable staff account setup_fixtures.py created. Safe to
re-run.

Usage:
    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/10-JMeter-Performance-Testing/teardown_fixtures.py
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
    try:
        admin_client.auth.admin.delete_user(fixtures["staff_id"])
        print(f"Deleted staff user {fixtures['staff_id']}")
    except Exception as e:
        print(f"  (non-fatal) delete staff user: {e}")
    fixtures_path.unlink()
    print("Teardown complete.")


if __name__ == "__main__":
    main()

"""Safety-net cleanup for integration-test data.

run_integration_tests.py deletes every row and Chroma entry it creates in
a `finally` block, scenario by scenario, so normal runs need nothing else.
This script exists only for crash recovery — if a run was killed hard
enough to skip its own cleanup (e.g. the process was SIGKILLed), this
finds and removes anything left behind, by scanning for the
"[INTEGRATION-TEST" subject-prefix marker every test ticket carries.

Usage (must run with clario-ml-sidecar/ as the working directory, inside
its .venv):

    cd clario-ml-sidecar
    source .venv/bin/activate
    python ../Testing/02-Integration-Testing/cleanup_sweep.py [--dry-run]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SIDECAR_ROOT = Path(__file__).resolve().parents[2] / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))
os.chdir(SIDECAR_ROOT)

import chromadb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from supabase import create_client  # noqa: E402

from app.tools.rag_tool import _chroma_path, _COLLECTION_NAME  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")  # load_dotenv() alone searches from this file's own path, not cwd
supabase_client = create_client(
    os.environ.get("SUPABASE_PROJECT_URL", ""), os.environ.get("SUPABASE_SECRET_API", "")
)

MARKER = "[INTEGRATION-TEST"


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    stray = (
        supabase_client.table("tickets")
        .select("id, subject, created_at")
        .like("subject", f"{MARKER}%")
        .execute()
        .data
    )

    if not stray:
        print("No stray integration-test tickets found. Nothing to clean up.")
        return

    print(f"Found {len(stray)} stray integration-test ticket(s):")
    for row in stray:
        print(f"  {row['id']}  {row['created_at']}  {row['subject']}")

    if dry_run:
        print("\n--dry-run set: not deleting anything.")
        return

    try:
        client = chromadb.PersistentClient(path=_chroma_path())
        collection = client.get_collection(_COLLECTION_NAME)
    except Exception:
        collection = None

    for row in stray:
        ticket_id = row["id"]
        supabase_client.table("tickets").delete().eq("id", ticket_id).execute()
        if collection is not None:
            try:
                collection.delete(ids=[f"precedent_{ticket_id}"])
            except Exception:
                pass
        print(f"  cleaned up {ticket_id}")

    print(f"\nDone. Removed {len(stray)} stray ticket(s) and any matching Chroma precedents.")


if __name__ == "__main__":
    main()

"""Track C FINAL, step 4 (after run_pairwise_evaluation.py has been run -
see ../README.md for the exact command): pull that run's rows back out of
Supabase's pairwise_evaluations table into a local CSV, so the rest of
Track C (semantic similarity, groundedness, the final report) can work
from a file like every other track in this project, instead of every
script needing live Supabase credentials.

Filters to one eval_run_id so re-running the pairwise script (e.g. after
fixing something) doesn't silently mix two runs' rows together - pass the
run id printed at the end of run_pairwise_evaluation.py's own output
("Pairwise evaluation run <eval_run_id>: ..."), or omit it to just take
the most recent run_id present in the table.

Usage:
    python3 export_pairwise_from_supabase.py [--run-id EVAL_RUN_ID]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from dotenv import load_dotenv  # noqa: E402
from supabase import create_client  # noqa: E402

load_dotenv(_SIDECAR_ROOT / ".env")

_HERE = Path(__file__).resolve().parent
RESULTS_DIR = _HERE.parent / "results"

FIELDS = [
    "eval_run_id", "source_doc_id", "category", "domain", "priority",
    "ticket_text", "generated_draft", "reference_response",
    "winner_pass1", "winner_pass2", "reasoning_pass1", "reasoning_pass2", "final_winner",
    "absolute_overall_score", "judge_model", "evaluation_latency_ms", "created_at",
]


def get_client():
    url = os.environ.get("SUPABASE_PROJECT_URL", "")
    key = os.environ.get("SUPABASE_SECRET_API", "")
    if not url or not key:
        raise SystemExit("SUPABASE_PROJECT_URL / SUPABASE_SECRET_API not set - check clario-ml-sidecar/.env")
    return create_client(url, key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=str, default=None, help="eval_run_id to export; omit for the most recent")
    args = parser.parse_args()

    client = get_client()
    run_id = args.run_id
    if run_id is None:
        latest = client.table("pairwise_evaluations").select("eval_run_id").order(
            "created_at", desc=True).limit(1).execute()
        if not latest.data:
            print("No rows in pairwise_evaluations yet - run run_pairwise_evaluation.py first.")
            return
        run_id = latest.data[0]["eval_run_id"]
        print(f"No --run-id given, using most recent: {run_id}")

    response = client.table("pairwise_evaluations").select(",".join(FIELDS)).eq("eval_run_id", run_id).execute()
    rows = response.data
    if not rows:
        print(f"No rows found for eval_run_id={run_id}")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "pairwise_results.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    win_counts: dict[str, int] = {}
    for r in rows:
        win_counts[r["final_winner"]] = win_counts.get(r["final_winner"], 0) + 1
    print(f"Wrote {len(rows)} rows to {out_path}")
    print(f"Overall win/lose/tie (draft/reference/tie): {win_counts}")


if __name__ == "__main__":
    main()

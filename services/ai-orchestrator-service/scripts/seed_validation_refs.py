"""Seed validation_refs (ChromaDB) from a reviewed real-response CSV.

Reads ml_finetuning/data/real_responses/real_responses.csv (produced by
ml_finetuning/src/curation/collect_real_responses.py and manually
reviewed by a human before this runs) and upserts each row into the
validation_refs collection (see app/tools/few_shot_selector.py). As of
writing, only the judge LLM (app/graph/response_judge_node.py, via
select_few_shots) actually queries this collection; the drafting agents
under app/agents/ do not. few_shot_selector.py also exposes
select_few_shots_by_category for other/future callers, but nothing
currently calls it.

Manual, one-off run - deliberately not wired into the scheduled
admin-override sync job (app/jobs/sync_judge_references.py). Safe to
re-run after editing the CSV: upsert_reference() upserts by doc_id.

Identifying/rolling back what this script seeded: every row it writes
gets a doc_id of the form real_<source>_<original_id> (e.g.
real_moodle_jira_MDL-1001). upsert_reference() hardcodes
metadata.source = "admin_override" for every caller (existing behavior
in few_shot_selector.py, unrelated to this script), so seeded entries
are NOT distinguishable from real admin corrections by that metadata
field - the only reliable way to find or remove them is by the
"real_" prefix on their Chroma doc id.

Run from anywhere, with clario-ml-sidecar's dependencies installed:
    python clario-ml-sidecar/scripts/seed_validation_refs.py
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from app.tools.few_shot_selector import upsert_reference  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_CSV = _SIDECAR_ROOT.parent / "ml_finetuning" / "data" / "real_responses" / "real_responses.csv"
REQUIRED_FIELDS = ("doc_id", "issue_text", "resolution_text", "domain", "category")


def seed_from_csv(csv_path: Path) -> dict:
    """Upsert every complete row of `csv_path` into validation_refs."""
    summary = {"read": 0, "seeded": 0, "skipped": 0}

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summary["read"] += 1

            if not all(row.get(field) for field in REQUIRED_FIELDS):
                logger.warning(f"Skipping row with missing fields: doc_id={row.get('doc_id')!r}")
                summary["skipped"] += 1
                continue

            upsert_reference(
                ticket_id=row["doc_id"],
                issue_text=row["issue_text"],
                resolution_text=row["resolution_text"],
                domain=row["domain"],
                priority="Unknown",
                category=row["category"],
                doc_id=row["doc_id"],
            )
            summary["seeded"] += 1

    logger.info(f"Seeded validation_refs: read={summary['read']} seeded={summary['seeded']} skipped={summary['skipped']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to the reviewed real_responses.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    seed_from_csv(args.csv)


if __name__ == "__main__":
    main()

"""Track C FINAL, step 1: join each of the 70 real tickets to its real
human reply (`Original Response`) and the suggested fix to that reply
(`Recommended Action`), for the pairwise/semantic-similarity checks that
need something real to compare Clario's draft against.

Reuses the EXACT join already solved and verified in Track B's
prepare_routing_annotation.py (same MANUAL_TEXT_OVERRIDES, same
UNKNOWN_SOURCE_TICKETS) rather than re-deriving it - Q001/Q020 are
verified near-exact rewordings, Q016 could not be reliably matched to any
raw ticket by exact, fuzzy, or keyword search and is left UNKNOWN rather
than guessed.

Produces TWO reference columns per ticket, because the proposal
(DATA_SCIENCE_EVALUATION_PROPOSAL.md Sec7.3) requires deciding up front whether
Clario is judged against the human reply exactly as sent, or a corrected
version - and to report both if they differ materially:
  - human_reply_as_sent: Original Response, verbatim.
  - human_reply_corrected: identical to human_reply_as_sent by default -
    NOT auto-derived from Recommended Action. 69 of 70 raw tickets have
    *some* Recommended Action text, but most are general coaching notes
    ("tighten grammar", "escalate repeat tickets automatically") rather
    than "this specific reply's content was wrong" - auto-appending a
    note for all 69 would make "corrected" differ from "as sent" on
    almost every row, which is noise, not a real corrected-reply
    comparison. See ../HOW_TO_ANNOTATE.md Sec1 option B: a human judges,
    per ticket, whether Recommended Action calls out an actual content
    problem worth a real rewrite, and edits human_reply_corrected
    directly for just those rows.

Usage:
    python3 prepare_human_reference_data.py
"""

from __future__ import annotations

import csv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parents[1] / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
RAW_TICKETS_PATH = _HERE.parents[3] / "CSV Files" / "lms_support_tickets Real - Support Tickets.csv"
DATA_DIR = _HERE.parent / "data"

# Identical to Track-B-Routing-Escalation-Accuracy/scripts/prepare_routing_annotation.py -
# same source data, same verified join, not re-derived.
MANUAL_TEXT_OVERRIDES = {
    "Q001": "Recordings and notes are not available for the student.",
    "Q020": "Submitted a project proposal but cannot see it reflected/confirmed anywhere.",
}
UNKNOWN_SOURCE_TICKETS = {"Q016"}


def load_raw_tickets() -> dict[str, dict]:
    with open(RAW_TICKETS_PATH, newline="", encoding="utf-8-sig") as f:
        return {r["Description"].strip(): r for r in csv.DictReader(f)}


def load_ground_truth() -> list[dict]:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    gt_rows = load_ground_truth()
    raw_by_desc = load_raw_tickets()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    out_path = DATA_DIR / "human_reference_70.csv"
    fields = ["query_id", "query_text", "domain", "human_reply_as_sent",
              "recommended_action", "human_reply_corrected", "source_status"]

    n_unknown = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in gt_rows:
            qid = row["query_id"]
            lookup_text = MANUAL_TEXT_OVERRIDES.get(qid, row["query_text"].strip())
            raw = raw_by_desc.get(lookup_text)

            if qid in UNKNOWN_SOURCE_TICKETS or raw is None:
                n_unknown += 1
                writer.writerow({
                    "query_id": qid, "query_text": row["query_text"], "domain": row["domain"],
                    "human_reply_as_sent": "UNKNOWN", "recommended_action": "UNKNOWN",
                    "human_reply_corrected": "UNKNOWN", "source_status": "unresolvable_source_ticket",
                })
                continue

            as_sent = raw.get("Original Response", "").strip()
            recommended_action = raw.get("Recommended Action", "").strip()
            # Starts identical to as_sent - see module docstring for why this
            # is NOT auto-derived from recommended_action.
            corrected = as_sent

            writer.writerow({
                "query_id": qid, "query_text": row["query_text"], "domain": row["domain"],
                "human_reply_as_sent": as_sent, "recommended_action": recommended_action,
                "human_reply_corrected": corrected, "source_status": "matched",
            })

    print(f"Wrote {len(gt_rows)} rows to {out_path} ({n_unknown} unresolvable, matching Track B's own count)")


if __name__ == "__main__":
    main()

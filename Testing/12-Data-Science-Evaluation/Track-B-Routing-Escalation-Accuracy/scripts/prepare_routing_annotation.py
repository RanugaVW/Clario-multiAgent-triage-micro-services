"""Track B FINAL, step 1: build the annotation file for the 70 real tickets.

Same scoping decision as the 99-query pilot (see
../pilot-99-query/scripts/prepare_routing_annotation_99.py's docstring):
routing_ground_truth is mechanically derived from Track A's own domain
labels wherever that's unambiguous, and the two humans only annotate what's
genuinely new - should_escalate for every ticket, and a routing override
for the rows the mechanical rule can't resolve.

This dataset differs from the 99-query pilot in one real way: it has
Priority and Recommended Action fields (from the raw ticket file), which
the proposal's original escalation-ground-truth definition is built on
("a ticket that names a policy problem or an unresolved repeat issue is
treated as one that should have escalated" - DATA_SCIENCE_EVALUATION_
PROPOSAL.md Sec7.2). Joining those fields to Track A's ground truth needed real
care: exact query_text match works for 67 of 70 rows; 2 more (Q001, Q020)
are a safe, manually-verified near-exact match (minor rewording only); the
last one, Q016 ("Cannot get the Zoom link"), does NOT reliably match any
raw ticket by exact, fuzzy, or keyword search - including the ticket its
position-based number would predict (#17, "Duplicate of ticket #12", whose
own content doesn't match either). Rather than guess and silently attach
the wrong ticket's Priority/Recommended Action to Q016, it's left UNKNOWN
here, flagged for the annotators to judge should_escalate from ticket text
alone for that one row, same as every row in the 99-query pilot.

Usage:
    python3 prepare_routing_annotation.py
"""

from __future__ import annotations

import csv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parents[1] / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
RAW_TICKETS_PATH = _HERE.parents[3] / "CSV Files" / "lms_support_tickets Real - Support Tickets.csv"
DATA_DIR = _HERE.parent / "data"

# Manually verified near-exact matches (minor rewording between Track A's
# query_text and the raw ticket Description) - NOT auto-fuzzy-matched, so a
# future dataset change can't silently attach the wrong ticket's data.
MANUAL_TEXT_OVERRIDES = {
    "Q001": "Recordings and notes are not available for the student.",
    "Q020": "Submitted a project proposal but cannot see it reflected/confirmed anywhere.",
}
# Confirmed unresolvable - see module docstring.
UNKNOWN_SOURCE_TICKETS = {"Q016"}


def mechanical_route(domain: str, relevant_doc_ids: str) -> tuple[str, bool]:
    """Same rule as the 99-query pilot's version. See that module's
    docstring for the full reasoning."""
    domains = sorted(d.strip().lower() for d in domain.split(",") if d.strip())
    has_doc = (relevant_doc_ids or "").strip().lower() not in ("", "none")

    if not has_doc:
        return (domains[0] if domains else "escalation"), True
    if len(domains) == 1:
        return domains[0], False
    if set(domains) == {"technical", "billing"}:
        return "both", False
    return domains[0], True


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

    out_path = DATA_DIR / "routing_annotation_sample.csv"
    fields = [
        "pair_id", "query_id", "query_text", "priority", "recommended_action",
        "track_a_domain", "routing_ground_truth_mechanical", "routing_needs_annotation",
        "human1_should_escalate", "human1_routing_ground_truth_override", "human1_notes",
        "human2_should_escalate", "human2_routing_ground_truth_override", "human2_notes",
    ]
    n_needs_annotation = 0
    n_unknown_source = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(gt_rows, start=1):
            qid = row["query_id"]
            lookup_text = MANUAL_TEXT_OVERRIDES.get(qid, row["query_text"].strip())
            raw = raw_by_desc.get(lookup_text)
            if qid in UNKNOWN_SOURCE_TICKETS or raw is None:
                priority, recommended_action = "UNKNOWN", "UNKNOWN"
                n_unknown_source += 1
            else:
                priority = raw.get("Priority", "UNKNOWN")
                recommended_action = raw.get("Recommended Action", "UNKNOWN")

            mech_route, needs_annotation = mechanical_route(row["domain"], row["relevant_doc_ids"])
            if needs_annotation:
                n_needs_annotation += 1
            writer.writerow({
                "pair_id": f"RB{i:03d}",
                "query_id": qid,
                "query_text": row["query_text"],
                "priority": priority,
                "recommended_action": recommended_action,
                "track_a_domain": row["domain"],
                "routing_ground_truth_mechanical": mech_route,
                "routing_needs_annotation": "yes" if needs_annotation else "no",
                "human1_should_escalate": "", "human1_routing_ground_truth_override": "", "human1_notes": "",
                "human2_should_escalate": "", "human2_routing_ground_truth_override": "", "human2_notes": "",
            })

    print(f"Wrote {len(gt_rows)} rows to {out_path}")
    print(f"{n_needs_annotation} rows flagged routing_needs_annotation=yes")
    print(f"{n_unknown_source} row(s) with UNKNOWN priority/recommended_action (unresolvable source ticket - see docstring)")


if __name__ == "__main__":
    main()

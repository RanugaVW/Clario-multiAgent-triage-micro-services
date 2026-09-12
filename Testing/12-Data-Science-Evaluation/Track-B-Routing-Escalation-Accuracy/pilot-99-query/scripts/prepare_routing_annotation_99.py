"""Track B PILOT, step 1: build the annotation file for the 99-query set.

Per an explicit scoping decision: this does NOT ask the two humans to
re-classify domain from scratch - Track A's own domain labels
(retrieval_ground_truth.csv) already did that independently and well, and
routing_ground_truth is MECHANICALLY DERIVABLE from domain in the vast
majority of cases:

    domain "technical"        -> routing "technical"
    domain "billing"          -> routing "billing"
    domain "hr"                -> routing "hr"
    domain "billing,technical" -> routing "both" (a real route exists)

That mechanical value is filled in automatically below. The two humans
only need to annotate what's genuinely NEW:

1. `should_escalate` (yes/no), for every row - this doesn't exist anywhere
   yet. Judged from query text alone here (the 99-query set has no
   Priority/Recommended Action columns, unlike the 70-ticket set - see
   ../../HOW_TO_ANNOTATE.md for how the two datasets differ on this).
2. `routing_ground_truth_override`, ONLY for rows flagged
   `routing_needs_annotation=yes` - genuinely ambiguous cases the
   mechanical rule can't resolve:
   - a domain combination with no real routing destination
     (e.g. "billing,hr" - only "both" for tech+billing exists)
   - `relevant_doc_ids == "none"` (no correct KB document exists at all,
     per Track A) - does this ticket even belong in a domain queue, or
     should it escalate instead?

Usage:
    python3 prepare_routing_annotation_99.py
"""

from __future__ import annotations

import csv
from pathlib import Path

_HERE = Path(__file__).resolve().parent
GT_PATH = _HERE.parents[2] / "Track-A-Retrieval-Quality" / "data" / "retrieval_ground_truth.csv"
DATA_DIR = _HERE.parent / "data"

VALID_ROUTES = {"technical", "billing", "both", "hr", "escalation"}


def mechanical_route(domain: str, relevant_doc_ids: str) -> tuple[str, bool]:
    """Returns (routing_ground_truth, needs_annotation). See module docstring
    for the rule. `needs_annotation=True` means the mechanical value is a
    placeholder guess, not a confident answer - the human override is
    load-bearing for that row, not optional polish."""
    domains = sorted(d.strip().lower() for d in domain.split(",") if d.strip())
    has_doc = (relevant_doc_ids or "").strip().lower() not in ("", "none")

    if not has_doc:
        # No correct KB document exists for this query at all - the
        # mechanical guess (the annotated domain) is doubtful on its face.
        return (domains[0] if domains else "escalation"), True

    if len(domains) == 1:
        return domains[0], False
    if set(domains) == {"technical", "billing"}:
        return "both", False
    # Any other multi-domain combination (e.g. billing+hr) has no real
    # routing_decision value today - flag for a human to actually decide.
    return domains[0], True


def load_ground_truth() -> list[dict]:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    rows = load_ground_truth()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    out_path = DATA_DIR / "routing_annotation_sample_99.csv"
    fields = [
        "pair_id", "query_id", "query_text", "track_a_domain",
        "routing_ground_truth_mechanical", "routing_needs_annotation",
        "human1_should_escalate", "human1_routing_ground_truth_override", "human1_notes",
        "human2_should_escalate", "human2_routing_ground_truth_override", "human2_notes",
    ]
    n_needs_annotation = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, start=1):
            mech_route, needs_annotation = mechanical_route(row["domain"], row["relevant_doc_ids"])
            if needs_annotation:
                n_needs_annotation += 1
            writer.writerow({
                "pair_id": f"RB{i:03d}",
                "query_id": row["query_id"],
                "query_text": row["query_text"],
                "track_a_domain": row["domain"],
                "routing_ground_truth_mechanical": mech_route,
                "routing_needs_annotation": "yes" if needs_annotation else "no",
                "human1_should_escalate": "", "human1_routing_ground_truth_override": "", "human1_notes": "",
                "human2_should_escalate": "", "human2_routing_ground_truth_override": "", "human2_notes": "",
            })

    print(f"Wrote {len(rows)} rows to {out_path}")
    print(f"{n_needs_annotation} rows flagged routing_needs_annotation=yes (mechanical value is a placeholder guess for these)")


if __name__ == "__main__":
    main()

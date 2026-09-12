"""Track B FINAL, step 2: same computation as
../pilot-99-query/scripts/merge_routing_annotations_99.py, pointed at the
70-real-ticket files. See that script's docstring for the full reasoning
on agreement metrics and dispute resolution.

Usage:
    python3 merge_routing_annotations.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
SAMPLE_PATH = DATA_DIR / "routing_annotation_sample.csv"
OUT_GT_PATH = DATA_DIR / "routing_ground_truth.csv"
DISPUTES_PATH = DATA_DIR / "routing_disputes.txt"

VALID_ROUTES = ["technical", "billing", "both", "hr", "escalation"]


def to_bool(value: str) -> bool | None:
    v = (value or "").strip().lower()
    if v in ("yes", "y", "true", "1"):
        return True
    if v in ("no", "n", "false", "0"):
        return False
    return None


def main() -> None:
    with open(SAMPLE_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    incomplete = [r["pair_id"] for r in rows if to_bool(r["human1_should_escalate"]) is None
                  or to_bool(r["human2_should_escalate"]) is None]
    if incomplete:
        print(f"{len(incomplete)} of {len(rows)} rows are missing a should_escalate answer from at least one human "
              f"(pair_ids: {', '.join(incomplete[:10])}{'...' if len(incomplete) > 10 else ''}).")
        print("Fill in every human1_should_escalate/human2_should_escalate before running this.")
        return

    needs_annotation = [r for r in rows if r["routing_needs_annotation"] == "yes"]
    missing_override = [
        r["pair_id"] for r in needs_annotation
        if not r["human1_routing_ground_truth_override"].strip() or not r["human2_routing_ground_truth_override"].strip()
    ]
    if missing_override:
        print(f"{len(missing_override)} of {len(needs_annotation)} routing_needs_annotation=yes rows are missing "
              f"an override from at least one human (pair_ids: {', '.join(missing_override[:10])}"
              f"{'...' if len(missing_override) > 10 else ''}).")
        print("Fill in human1_routing_ground_truth_override/human2_routing_ground_truth_override for every "
              "routing_needs_annotation=yes row before running this.")
        return

    print(f"All {len(rows)} rows fully annotated. Computing agreement.\n")

    print("=== should_escalate agreement (all rows, unweighted kappa) ===")
    h1_esc = [to_bool(r["human1_should_escalate"]) for r in rows]
    h2_esc = [to_bool(r["human2_should_escalate"]) for r in rows]
    esc_kappa = cohen_kappa_score(h1_esc, h2_esc, labels=[True, False])
    n_agree_esc = sum(1 for a, b in zip(h1_esc, h2_esc) if a == b)
    print(f"  agreement: {n_agree_esc}/{len(rows)} = {100 * n_agree_esc / len(rows):.1f}%, kappa={esc_kappa:.3f}\n")

    print(f"=== routing_ground_truth_override agreement ({len(needs_annotation)} ambiguous rows, unweighted kappa) ===")
    if needs_annotation:
        h1_route = [r["human1_routing_ground_truth_override"].strip().lower() for r in needs_annotation]
        h2_route = [r["human2_routing_ground_truth_override"].strip().lower() for r in needs_annotation]
        for label, vals in (("human1", h1_route), ("human2", h2_route)):
            bad = [v for v in vals if v not in VALID_ROUTES]
            if bad:
                print(f"  WARNING: {label} used values outside {VALID_ROUTES}: {set(bad)}")
        route_kappa = cohen_kappa_score(h1_route, h2_route, labels=VALID_ROUTES)
        n_agree_route = sum(1 for a, b in zip(h1_route, h2_route) if a == b)
        print(f"  agreement: {n_agree_route}/{len(needs_annotation)} = "
              f"{100 * n_agree_route / len(needs_annotation):.1f}%, kappa={route_kappa:.3f}\n")
    else:
        print("  (no ambiguous rows in this dataset)\n")

    disputes = []
    out_rows = []
    for r in rows:
        h1e, h2e = to_bool(r["human1_should_escalate"]), to_bool(r["human2_should_escalate"])
        if h1e == h2e:
            should_escalate = h1e
        else:
            should_escalate = None
            disputes.append((r["pair_id"], r["query_id"], "should_escalate", f"human1={h1e} | human2={h2e}"))

        if r["routing_needs_annotation"] == "yes":
            h1r = r["human1_routing_ground_truth_override"].strip().lower()
            h2r = r["human2_routing_ground_truth_override"].strip().lower()
            if h1r == h2r:
                routing_gt = h1r
            else:
                routing_gt = None
                disputes.append((r["pair_id"], r["query_id"], "routing_ground_truth", f"human1={h1r} | human2={h2r}"))
        else:
            routing_gt = r["routing_ground_truth_mechanical"]

        out_rows.append({
            "pair_id": r["pair_id"],
            "query_id": r["query_id"],
            "query_text": r["query_text"],
            "priority": r["priority"],
            "routing_ground_truth": routing_gt if routing_gt is not None else "NEEDS_REVIEW",
            "should_escalate": str(should_escalate) if should_escalate is not None else "NEEDS_REVIEW",
        })

    with open(OUT_GT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pair_id", "query_id", "query_text", "priority", "routing_ground_truth", "should_escalate"])
        writer.writeheader()
        writer.writerows(out_rows)

    if disputes:
        with open(DISPUTES_PATH, "w", encoding="utf-8") as f:
            f.write(f"{len(disputes)} disputes need manual resolution before run_routing_evaluation.py can use these rows:\n\n")
            for pair_id, qid, field, detail in disputes:
                f.write(f"  {pair_id} ({qid}), {field}: {detail}\n")
        print(f"{len(disputes)} disputes written to {DISPUTES_PATH} - resolve each by hand (edit routing_ground_truth.csv "
              f"directly, replacing NEEDS_REVIEW with the agreed answer) before running the evaluation.")
    else:
        print("No disputes - every row resolved cleanly.")

    print(f"Wrote {len(out_rows)} rows to {OUT_GT_PATH}")


if __name__ == "__main__":
    main()

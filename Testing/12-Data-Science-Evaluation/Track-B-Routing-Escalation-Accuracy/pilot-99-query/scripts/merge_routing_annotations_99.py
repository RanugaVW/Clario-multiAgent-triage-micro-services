"""Track B PILOT, step 2: once both humans have filled in
data/routing_annotation_sample_99.csv, run this to check agreement and
build the final data/routing_ground_truth_99.csv that
run_routing_evaluation_99.py scores the pipeline against.

Two separate agreement checks, since the two annotated fields are
different kinds of judgment:

- should_escalate (every row, binary): unweighted Cohen's kappa.
- routing_ground_truth_override (only the routing_needs_annotation=yes
  rows, 5-class nominal): unweighted Cohen's kappa - NOT the weighted
  kappa Track D/Track A use elsewhere, because these 5 classes
  (technical/billing/both/hr/escalation) have no meaningful ordering for
  a "how far apart" penalty to apply to.

Resolution when the two humans disagree: unlike Track A's document-set
union or Track D's score-averaging, a routing decision has to be exactly
one value for accuracy/precision/recall to even be computable - there is
no "union" of "billing" and "escalation". Disagreements are written to
routing_disputes_99.txt for a manual, written-reason resolution (the same
approach Track A used for its original 3 domain disputes), NOT
auto-resolved by this script.

A blank override is treated as "this human agrees with the mechanical
value" (a human can only write into that field, never delete the
mechanical row it's shown next to - so nothing else a blank could mean).
This applies whether or not routing_needs_annotation flagged the row:
annotators occasionally override a "no" row too (they're allowed to spot
a wrong mechanical value Track A didn't flag), and that correction must
not be silently discarded just because the row wasn't flagged.

Usage:
    python3 merge_routing_annotations_99.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
SAMPLE_PATH = DATA_DIR / "routing_annotation_sample_99.csv"
OUT_GT_PATH = DATA_DIR / "routing_ground_truth_99.csv"
DISPUTES_PATH = DATA_DIR / "routing_disputes_99.txt"

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

    print(f"All {len(rows)} rows have a should_escalate answer from both humans. Computing agreement.\n")
    print("(A blank routing_ground_truth_override counts as 'agrees with the mechanical value' - see this "
          "script's docstring - so no override is ever 'missing', only left blank on purpose.)\n")

    print("=== should_escalate agreement (all rows, unweighted kappa) ===")
    h1_esc = [to_bool(r["human1_should_escalate"]) for r in rows]
    h2_esc = [to_bool(r["human2_should_escalate"]) for r in rows]
    esc_kappa = cohen_kappa_score(h1_esc, h2_esc, labels=[True, False])
    n_agree_esc = sum(1 for a, b in zip(h1_esc, h2_esc) if a == b)
    print(f"  agreement: {n_agree_esc}/{len(rows)} = {100 * n_agree_esc / len(rows):.1f}%, kappa={esc_kappa:.3f}\n")

    def resolved_route(r: dict, human: str) -> str:
        override = r[f"{human}_routing_ground_truth_override"].strip().lower()
        return override or r["routing_ground_truth_mechanical"]

    print(f"=== routing_ground_truth_override agreement ({len(needs_annotation)} flagged rows, unweighted kappa) ===")
    if needs_annotation:
        h1_route = [resolved_route(r, "human1") for r in needs_annotation]
        h2_route = [resolved_route(r, "human2") for r in needs_annotation]
        for label, vals in (("human1", h1_route), ("human2", h2_route)):
            bad = [v for v in vals if v not in VALID_ROUTES]
            if bad:
                print(f"  WARNING: {label} used values outside {VALID_ROUTES}: {set(bad)}")
        route_kappa = cohen_kappa_score(h1_route, h2_route, labels=VALID_ROUTES)
        n_agree_route = sum(1 for a, b in zip(h1_route, h2_route) if a == b)
        print(f"  agreement: {n_agree_route}/{len(needs_annotation)} = "
              f"{100 * n_agree_route / len(needs_annotation):.1f}%, kappa={route_kappa:.3f}\n")
    else:
        print("  (no flagged rows in this dataset)\n")

    stray_overrides = [
        r for r in rows if r["routing_needs_annotation"] == "no"
        and (r["human1_routing_ground_truth_override"].strip() or r["human2_routing_ground_truth_override"].strip())
    ]
    if stray_overrides:
        print(f"=== {len(stray_overrides)} row(s) NOT flagged by the mechanical join, but at least one human "
              f"corrected the mechanical value anyway - these are honored below, not discarded ===")
        for r in stray_overrides:
            print(f"  {r['pair_id']} ({r['query_id']}): mechanical={r['routing_ground_truth_mechanical']} "
                  f"human1='{resolved_route(r, 'human1')}' human2='{resolved_route(r, 'human2')}'")
        print()

    # Build final ground truth: escalation is majority-of-2 (i.e. must
    # agree, else NEEDS_REVIEW). Routing is each human's override where
    # they wrote one, else the mechanical value they're implicitly
    # agreeing with (see docstring) - applied uniformly regardless of
    # routing_needs_annotation, since a human's correction on a "no" row
    # is just as real as one on a flagged row.
    disputes = []
    out_rows = []
    for r in rows:
        h1e, h2e = to_bool(r["human1_should_escalate"]), to_bool(r["human2_should_escalate"])
        if h1e == h2e:
            should_escalate = h1e
        else:
            should_escalate = None
            disputes.append((r["pair_id"], r["query_id"], "should_escalate", f"human1={h1e} | human2={h2e}"))

        h1r, h2r = resolved_route(r, "human1"), resolved_route(r, "human2")
        if h1r == h2r:
            routing_gt = h1r
        else:
            routing_gt = None
            disputes.append((r["pair_id"], r["query_id"], "routing_ground_truth", f"human1={h1r} | human2={h2r}"))

        out_rows.append({
            "pair_id": r["pair_id"],
            "query_id": r["query_id"],
            "query_text": r["query_text"],
            "routing_ground_truth": routing_gt if routing_gt is not None else "NEEDS_REVIEW",
            "should_escalate": str(should_escalate) if should_escalate is not None else "NEEDS_REVIEW",
        })

    with open(OUT_GT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pair_id", "query_id", "query_text", "routing_ground_truth", "should_escalate"])
        writer.writeheader()
        writer.writerows(out_rows)

    if disputes:
        with open(DISPUTES_PATH, "w", encoding="utf-8") as f:
            f.write(f"{len(disputes)} disputes need manual resolution before run_routing_evaluation_99.py can use these rows:\n\n")
            for pair_id, qid, field, detail in disputes:
                f.write(f"  {pair_id} ({qid}), {field}: {detail}\n")
        print(f"{len(disputes)} disputes written to {DISPUTES_PATH} - resolve each by hand (edit routing_ground_truth_99.csv "
              f"directly, replacing NEEDS_REVIEW with the agreed answer and a reason in a new 'resolution_notes' column) "
              f"before running the evaluation.")
    else:
        print("No disputes - every row resolved cleanly.")

    print(f"Wrote {len(out_rows)} rows to {OUT_GT_PATH}")


if __name__ == "__main__":
    main()

"""Reusable merge step for every synthetic annotation round (round-1, round-2, ...).

Takes the two annotators' filled-in CSVs for a round, checks agreement the
same way the original 70-real-ticket ground truth was built (§7.1 of
DATA_SCIENCE_EVALUATION_PROPOSAL.md), and writes:
  - <round_dir>/<round>_agreement_report.txt   - agreement rate + every disputed row
  - <round_dir>/<round>_ground_truth.csv       - agreed rows only; disputes flagged
    NEEDS_REVIEW in the `domain` column until resolved by hand (same as the
    3 disputes in the original 70-ticket round, each resolved with a written
    reason - do the same here rather than picking one side automatically).

Usage:
    python3 merge_annotation_round.py <round_dir> <round_name>

Example:
    python3 merge_annotation_round.py synthetic-rounds/round-1 round1
    (expects round1_mapped_Ranuga.csv and round1_mapped_Sineth.csv, both
    filled in, to already exist in that directory - copy the *_TEMPLATE.csv
    files to those names once annotation is done.)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def load(path: Path) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return {row["query_id"]: row for row in csv.DictReader(f)}


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    round_dir = Path(sys.argv[1])
    round_name = sys.argv[2]

    ranuga_path = round_dir / f"{round_name}_mapped_Ranuga.csv"
    sineth_path = round_dir / f"{round_name}_mapped_Sineth.csv"
    for p in (ranuga_path, sineth_path):
        if not p.exists():
            print(f"Missing {p} - copy the matching *_TEMPLATE.csv to this filename once filled in.")
            sys.exit(1)

    r = load(ranuga_path)
    s = load(sineth_path)
    if set(r) != set(s):
        print("query_id sets don't match between the two files - did both start from the same template?")
        sys.exit(1)

    ids = sorted(r, key=lambda x: int(x.split("-")[-1]))
    rows_out = []
    disputes = []
    n_agree = 0

    for qid in ids:
        rr, ss = r[qid], s[qid]
        dom_agree = rr["domain"].strip().lower() == ss["domain"].strip().lower()
        doc_agree = rr["relevant_doc_ids"].strip().lower() == ss["relevant_doc_ids"].strip().lower()
        if dom_agree and doc_agree:
            n_agree += 1
            domain, doc_ids, note = rr["domain"].strip().lower(), rr["relevant_doc_ids"].strip(), ""
        else:
            domain, doc_ids, note = "NEEDS_REVIEW", "NEEDS_REVIEW", (
                f"Ranuga={rr['domain']}/{rr['relevant_doc_ids']} | "
                f"Sineth={ss['domain']}/{ss['relevant_doc_ids']}"
            )
            disputes.append((qid, rr["query_text"], note))
        rows_out.append({
            "query_id": qid,
            "query_text": rr["query_text"],
            "domain": domain,
            "relevant_doc_ids": doc_ids,
            "notes": note,
        })

    gt_path = round_dir / f"{round_name}_ground_truth.csv"
    with open(gt_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "query_text", "domain", "relevant_doc_ids", "notes"])
        w.writeheader()
        w.writerows(rows_out)

    report_path = round_dir / f"{round_name}_agreement_report.txt"
    pct = 100 * n_agree / len(ids)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"Agreement: {n_agree}/{len(ids)} = {pct:.1f}% (before any discussion)\n\n")
        f.write(f"Disputes needing manual review ({len(disputes)}):\n")
        for qid, text, note in disputes:
            f.write(f"  {qid}: {text}\n    {note}\n")

    print(f"Agreement: {n_agree}/{len(ids)} = {pct:.1f}%")
    print(f"{len(disputes)} disputes need manual review - see {report_path}")
    print(f"Ground truth written to {gt_path} (NEEDS_REVIEW rows must be resolved before evaluation)")


if __name__ == "__main__":
    main()

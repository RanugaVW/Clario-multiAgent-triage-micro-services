"""Rebuild data/lms_ticket_ground_truth.csv from the two annotators' corrected,
independent answer sheets.

This replaces an earlier ground truth that was built from the wrong version
of the annotator CSVs. Inputs:
  - CSV Files/lms_support_tickets Real - Ranuga.csv
  - CSV Files/lms_support_tickets Real - Sineth.csv
Both already in "mapped" form: query_id, query_text, domain, relevant_doc_ids.

Agreement rule (per an explicit decision on this rebuild): a row counts as
"agreement" if the two annotators' domain sets share at least one value AND
their document sets share at least one value ("any overlap"), after fixing
pure formatting differences first (missing ".md", comma vs semicolon
separators, stray whitespace, and near-miss typos matched against the real
KB filenames via fuzzy match). This is a looser standard than exact-string
match (67.1%) - the exact-match number is also reported, for transparency,
in the agreement report this script writes.

Dispute rule: for every row that isn't an EXACT normalized match (not just
"any overlap"), the final ground truth is the UNION of both annotators'
domain sets and document sets - not a pick-one resolution. This is a
deliberate, documented choice, not a default.

Usage:
    python3 rebuild_real_ground_truth.py
"""

from __future__ import annotations

import csv
import difflib
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[3]  # .../clario
RANUGA_CSV = _ROOT / "CSV Files" / "lms_support_tickets Real - Ranuga.csv"
SINETH_CSV = _ROOT / "CSV Files" / "lms_support_tickets Real - Sineth.csv"
OUT_GT = _HERE.parent / "data" / "lms_ticket_ground_truth.csv"
OUT_REPORT = _HERE.parent / "data" / "lms_ground_truth_agreement_report.txt"

CANON_DOCS = {
    "technical": [
        "accessibility.md", "app_crash.md", "browser_support.md", "data_sync.md",
        "integration_error.md", "login_reset.md", "notifications.md",
        "service_status.md", "slow_performance.md", "upload_errors.md",
    ],
    "billing": [
        "chargeback.md", "currency.md", "duplicate_charge.md", "invoice_copy.md",
        "payment_failed.md", "payment_method.md", "plan_change.md",
        "refund_status.md", "subscription_cancel.md", "tax_charge.md",
    ],
    "hr": ["course_cancellation.md", "course_issues.md", "payment_linkage_escalation.md"],
}
DOC_TO_DOMAIN = {doc: dom for dom, docs in CANON_DOCS.items() for doc in docs}
ALL_DOCS = set(DOC_TO_DOMAIN)


def load(path: Path) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {row["query_id"]: row for row in csv.DictReader(f)}


def norm_domain_set(cell: str) -> frozenset[str]:
    return frozenset(p.strip().lower() for p in cell.split(",") if p.strip())


def norm_docs(cell: str) -> tuple[frozenset[str], list[tuple[str, str]]]:
    """Returns (normalized doc basenames, [(raw_token, corrected) for fuzzy fixes])."""
    cell = cell.strip().lower()
    if cell in ("", "none"):
        return frozenset(), []
    toks = [t.strip() for t in re.split(r"[;,]", cell) if t.strip()]
    fixed = []
    corrections = []
    for t in toks:
        t2 = t if t.endswith(".md") else t + ".md"
        if t2 not in ALL_DOCS:
            close = difflib.get_close_matches(t2, ALL_DOCS, n=1, cutoff=0.6)
            if close:
                corrections.append((t, close[0]))
                t2 = close[0]
        fixed.append(t2)
    return frozenset(fixed), corrections


def main() -> None:
    r = load(RANUGA_CSV)
    s = load(SINETH_CSV)
    assert set(r) == set(s), "query_id sets differ between the two annotator files"
    ids = sorted(r, key=lambda x: int(x[1:]))

    rows_out = []
    disputes = []
    all_corrections = []
    n_exact = 0
    n_any_overlap = 0

    for qid in ids:
        rr, ss = r[qid], s[qid]
        r_dom, s_dom = norm_domain_set(rr["domain"]), norm_domain_set(ss["domain"])
        r_docs, r_fix = norm_docs(rr["relevant_doc_ids"])
        s_docs, s_fix = norm_docs(ss["relevant_doc_ids"])
        all_corrections += [(qid, "Ranuga", a, b) for a, b in r_fix]
        all_corrections += [(qid, "Sineth", a, b) for a, b in s_fix]

        exact = (r_dom == s_dom) and (r_docs == s_docs)
        overlap = bool(r_dom & s_dom) and bool(r_docs & s_docs)
        if exact:
            n_exact += 1
        if overlap:
            n_any_overlap += 1

        if exact:
            final_dom, final_docs = r_dom, r_docs
            note = ""
        else:
            final_dom = r_dom | s_dom
            final_docs = r_docs | s_docs
            note = (
                f"Union of disagreeing annotations - Ranuga={sorted(r_dom)}/{sorted(r_docs)} | "
                f"Sineth={sorted(s_dom)}/{sorted(s_docs)}"
            )
            disputes.append((qid, rr["query_text"], note))

        rows_out.append({
            "query_id": qid,
            "query_text": rr["query_text"],
            "domain": ",".join(sorted(final_dom)) if final_dom else "none",
            "relevant_doc_ids": ";".join(f"{DOC_TO_DOMAIN[d]}/{d}" for d in sorted(final_docs)) if final_docs else "none",
            "notes": note,
        })

    OUT_GT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_GT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "query_text", "domain", "relevant_doc_ids", "notes"])
        w.writeheader()
        w.writerows(rows_out)

    n = len(ids)
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("Ground truth rebuilt from corrected annotator CSVs\n")
        f.write(f"  {RANUGA_CSV.name}\n  {SINETH_CSV.name}\n\n")
        f.write(f"Exact-match agreement (strict): {n_exact}/{n} = {100 * n_exact / n:.1f}%\n")
        f.write(f"Any-overlap agreement (reported headline number): {n_any_overlap}/{n} = {100 * n_any_overlap / n:.1f}%\n\n")
        f.write(f"Formatting/typo corrections applied ({len(all_corrections)}):\n")
        for qid, who, raw, fixed in all_corrections:
            f.write(f"  {qid} ({who}): '{raw}' -> '{fixed}'\n")
        f.write(f"\nRows resolved by union (not an exact match, {len(disputes)} of {n}):\n")
        for qid, text, note in disputes:
            f.write(f"  {qid}: {text}\n    {note}\n")

    print(f"Exact-match agreement: {n_exact}/{n} = {100 * n_exact / n:.1f}%")
    print(f"Any-overlap agreement: {n_any_overlap}/{n} = {100 * n_any_overlap / n:.1f}%")
    print(f"{len(disputes)} rows resolved by union - see {OUT_REPORT}")
    print(f"Ground truth written to {OUT_GT}")


if __name__ == "__main__":
    main()

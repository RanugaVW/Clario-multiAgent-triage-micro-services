"""Track A retrieval evaluation - Version 1 (current-system baseline).

Runs every labeled query in data/retrieval_ground_truth.csv through the
REAL, production retrieve_context()/check_relevance() functions (imported
directly from the sidecar app, never reimplemented) against whatever is
currently indexed in this environment's ChromaDB, and computes standard
IR metrics with their formulas documented alongside the code that
implements them (see results/v1_summary_metrics.json and TEST_REPORT_V1.md
for the write-up).

Domain substitution: the human-reviewed ground truth's `domain` column
also contains "HR" for tickets the reviewer judged belong to a domain the
system does not route to today. retrieve_context() only accepts
"technical"/"billing" - anything else raises ValueError. Since
routing_node.py would route these tickets (all originally Payment/Refund/
Billing category, per the source dataset) to "billing" today, this
evaluation substitutes domain="billing" for HR rows to faithfully
reproduce current system behavior, while keeping the reviewer's original
relevant_doc_ids ground truth (almost always "none" - the whole point of
labeling them HR was "no current doc/agent handles this").
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[3] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.tools.rag_tool import retrieve_context, check_relevance  # noqa: E402

_HERE = Path(__file__).resolve().parent
DATA_PATH = _HERE.parent / "data" / "retrieval_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"
K = 4


def load_ground_truth() -> list[dict]:
    with open(DATA_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _basename(source_file: str) -> str:
    """The ground-truth CSV uses bare KB filenames (e.g. "login_reset.md"),
    but the real ChromaDB metadata stores them domain-prefixed (e.g.
    "technical/login_reset.md", per build_index.py's use of
    source.relative_to(KB_ROOT)). Compare on basename so a correct
    retrieval isn't scored as a miss over a path-prefix difference."""
    return source_file.strip().lower().rsplit("/", 1)[-1]


def relevant_set(cell: str) -> set[str]:
    cell = (cell or "").strip().lower()
    if cell in ("", "none"):
        return set()
    return {_basename(x) for x in cell.split(";") if x.strip()}


def eval_domain(raw_domain: str) -> str:
    d = raw_domain.strip().lower()
    return "billing" if d == "hr" else d


# --- Metric formulas -------------------------------------------------------
# ranked_sources: the system's top-k source_file values, best match first.
# relevant: the human-labeled ground-truth set of correct source_file values
#           for this query (empty set = reviewer judged no current doc answers it).

def precision_at_k(ranked_sources: list[str], relevant: set[str], k: int) -> float:
    """Precision@k = |{retrieved top-k} ∩ {relevant}| / k
    Well-defined even when `relevant` is empty (naturally scores 0)."""
    top = ranked_sources[:k]
    if not top:
        return 0.0
    hits = sum(1 for s in top if s in relevant)
    return hits / len(top)


def recall_at_k(ranked_sources: list[str], relevant: set[str], k: int) -> float | None:
    """Recall@k = |{retrieved top-k} ∩ {relevant}| / |relevant|
    Undefined (0/0) when `relevant` is empty - returns None, excluded from
    the average rather than silently coerced to 0 or 1."""
    if not relevant:
        return None
    top = ranked_sources[:k]
    hits = sum(1 for s in top if s in relevant)
    return hits / len(relevant)


def reciprocal_rank(ranked_sources: list[str], relevant: set[str]) -> float | None:
    """RR = 1 / rank of the first relevant item in the ranked list (0 if
    none of the top-k are relevant). Undefined when `relevant` is empty."""
    if not relevant:
        return None
    for i, src in enumerate(ranked_sources, start=1):
        if src in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_sources: list[str], relevant: set[str], k: int) -> float | None:
    """nDCG@k = DCG@k / IDCG@k, binary gains (1 if relevant else 0):
      DCG@k  = sum_{i=1..k} gain_i / log2(i + 1)
      IDCG@k = the same sum if all min(|relevant|, k) relevant items were
               ranked first - the best possible ordering.
    Undefined when `relevant` is empty (IDCG@k = 0)."""
    if not relevant:
        return None
    top = ranked_sources[:k]
    dcg = sum(1.0 / math.log2(i + 1) for i, s in enumerate(top, start=1) if s in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else None


def avg(values: list[float | bool | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def main() -> None:
    rows = load_ground_truth()
    results = []

    for row in rows:
        raw_domain = row["domain"]
        domain_used = eval_domain(raw_domain)
        relevant = relevant_set(row["relevant_doc_ids"])

        matches = retrieve_context(row["query_text"], domain_used, k=K)
        ranked_sources = [m["source_file"] for m in matches]  # raw, for display/audit
        ranked_basenames = [_basename(s) for s in ranked_sources]  # normalized, for scoring
        gate_pass = check_relevance(matches)
        top1_correct = bool(ranked_basenames) and ranked_basenames[0] in relevant
        stale_or_unknown_hits = sum(
            1 for s in ranked_sources
            if not s.startswith(("technical/", "billing/")) and s != "precedent_memory"
        )

        results.append({
            "query_id": row["query_id"],
            "raw_domain": raw_domain,
            "domain_used": domain_used,
            "domain_substituted": raw_domain.strip().lower() == "hr",
            "has_relevant_doc": bool(relevant),
            "relevant_doc_ids": ";".join(sorted(relevant)) if relevant else "none",
            "retrieved_top4": ";".join(ranked_sources),
            "retrieved_scores": ";".join(f"{m['score']:.4f}" for m in matches),
            "stale_or_unknown_hits_in_top4": stale_or_unknown_hits,
            "gate_pass": gate_pass,
            "top1_correct": top1_correct,
            "precision_at_3": precision_at_k(ranked_basenames, relevant, 3),
            "precision_at_4": precision_at_k(ranked_basenames, relevant, 4),
            "recall_at_3": recall_at_k(ranked_basenames, relevant, 3),
            "recall_at_4": recall_at_k(ranked_basenames, relevant, 4),
            "reciprocal_rank": reciprocal_rank(ranked_basenames, relevant),
            "ndcg_at_4": ndcg_at_k(ranked_basenames, relevant, 4),
            "notes": row.get("notes", ""),
        })
        print(f"{row['query_id']}: domain={domain_used}"
              f"{' (substituted from HR)' if results[-1]['domain_substituted'] else ''} "
              f"gt={results[-1]['relevant_doc_ids']} top4={results[-1]['retrieved_top4']} "
              f"gate={gate_pass} P@4={results[-1]['precision_at_4']:.2f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "v1_per_query_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    with_relevant = [r for r in results if r["has_relevant_doc"]]
    without_relevant = [r for r in results if not r["has_relevant_doc"]]

    # Gate confusion matrix: check_relevance()'s pass/fail vs. whether the
    # top-1 result was actually correct (top1_correct is False by
    # construction whenever has_relevant_doc is False).
    tp = sum(1 for r in results if r["gate_pass"] and r["top1_correct"])
    fp = sum(1 for r in results if r["gate_pass"] and not r["top1_correct"])
    fn = sum(1 for r in results if not r["gate_pass"] and r["top1_correct"])
    tn = sum(1 for r in results if not r["gate_pass"] and not r["top1_correct"])

    summary = {
        "k": K,
        "n_total": len(results),
        "n_with_relevant_doc": len(with_relevant),
        "n_no_relevant_doc": len(without_relevant),
        "n_hr_substituted": sum(1 for r in results if r["domain_substituted"]),
        "precision_at_3_all": avg([r["precision_at_3"] for r in results]),
        "precision_at_4_all": avg([r["precision_at_4"] for r in results]),
        "precision_at_3_with_relevant_only": avg([r["precision_at_3"] for r in with_relevant]),
        "precision_at_4_with_relevant_only": avg([r["precision_at_4"] for r in with_relevant]),
        "recall_at_3": avg([r["recall_at_3"] for r in with_relevant]),
        "recall_at_4": avg([r["recall_at_4"] for r in with_relevant]),
        "mrr": avg([r["reciprocal_rank"] for r in with_relevant]),
        "ndcg_at_4": avg([r["ndcg_at_4"] for r in with_relevant]),
        "gate_false_positive_rate_on_no_relevant_docs": (
            sum(1 for r in without_relevant if r["gate_pass"]) / len(without_relevant)
            if without_relevant else None
        ),
        "gate_confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "gate_accuracy": (tp + tn) / len(results) if results else None,
        "gate_precision": tp / (tp + fp) if (tp + fp) else None,
        "gate_recall": tp / (tp + fn) if (tp + fn) else None,
        "avg_stale_or_unknown_hits_per_query": avg([r["stale_or_unknown_hits_in_top4"] for r in results]),
        "pct_of_all_retrieved_slots_that_are_stale_or_unknown": (
            sum(r["stale_or_unknown_hits_in_top4"] for r in results)
            / sum(len(r["retrieved_top4"].split(";")) if r["retrieved_top4"] else 0 for r in results)
        ) if results else None,
    }

    by_domain = {}
    for dom in ("technical", "billing"):
        subset = [r for r in results if r["raw_domain"].strip().lower() == dom]
        subset_rel = [r for r in subset if r["has_relevant_doc"]]
        by_domain[dom] = {
            "n": len(subset),
            "n_with_relevant_doc": len(subset_rel),
            "precision_at_4_all": avg([r["precision_at_4"] for r in subset]),
            "recall_at_4": avg([r["recall_at_4"] for r in subset_rel]),
            "mrr": avg([r["reciprocal_rank"] for r in subset_rel]),
        }
    subset = [r for r in results if r["raw_domain"].strip().lower() == "hr"]
    subset_rel = [r for r in subset if r["has_relevant_doc"]]
    by_domain["hr_substituted_to_billing"] = {
        "n": len(subset),
        "n_with_relevant_doc": len(subset_rel),
        "precision_at_4_all": avg([r["precision_at_4"] for r in subset]),
        "recall_at_4": avg([r["recall_at_4"] for r in subset_rel]),
        "mrr": avg([r["reciprocal_rank"] for r in subset_rel]),
    }
    summary["by_domain"] = by_domain

    print(json.dumps(summary, indent=2))
    with open(RESULTS_DIR / "v1_summary_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()

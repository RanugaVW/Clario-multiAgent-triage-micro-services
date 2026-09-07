"""Track A retrieval evaluation, V3: re-run of eval_retrieval_lms.py against
the CORRECTED ground truth (data/lms_ticket_ground_truth.csv, rebuilt by
rebuild_real_ground_truth.py from the two annotators' fixed CSVs).

Only two things differ from eval_retrieval_lms.py (V2):

1. The ground truth this reads is the corrected one - V2's original ground
   truth was built from the wrong version of the annotator CSVs.
2. Some ground-truth rows now carry more than one domain (e.g. "billing,hr"),
   because disputed rows are resolved by UNION rather than picking one
   annotator - see rebuild_real_ground_truth.py's docstring. retrieve_context()
   only accepts a single domain per call (mirrors how the real pipeline's
   "both_specialists" node runs technical_agent then billing_agent
   sequentially for tech+billing tickets - see graph_builder.py), so for a
   multi-domain row this script calls retrieve_context() once per domain,
   merges every returned match, and keeps the top K by score - the same
   "combine per-domain results" pattern the real pipeline already uses for
   "both", just generalized to whatever domain combination the ground truth
   names. This is a fair test of retrieval, but it does surface a real
   routing-coverage gap: today's routing_decision enum has no destination
   for e.g. "billing+hr" - only "both" (tech+billing) exists - so a few of
   these tickets could never actually reach this combined retrieval in
   production as currently routed. That gap is a Track B finding, not a
   Track A retrieval defect, and is reported as a limitation, not fixed here.

Metric formulas are otherwise identical to eval_retrieval_lms.py.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.tools.rag_tool import retrieve_context, check_relevance  # noqa: E402

_HERE = Path(__file__).resolve().parent
DATA_PATH = _HERE.parent / "data" / "lms_ticket_ground_truth.csv"
RESULTS_DIR = _HERE.parent / "results"
K = 4


def load_ground_truth() -> list[dict]:
    with open(DATA_PATH, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _basename(source_file: str) -> str:
    return source_file.strip().lower().rsplit("/", 1)[-1]


def relevant_set(cell: str) -> set[str]:
    cell = (cell or "").strip().lower()
    if cell in ("", "none"):
        return set()
    return {_basename(x) for x in cell.split(";") if x.strip()}


def retrieve_multi_domain(query: str, domain_cell: str, k: int) -> list[dict]:
    """Query every domain named in a (possibly multi-domain) ground-truth
    cell and merge the results, keeping the best-scoring K overall."""
    domains = [d.strip() for d in domain_cell.split(",") if d.strip()]
    best: dict[str, dict] = {}
    for dom in domains:
        for m in retrieve_context(query, dom, k=k):
            sf = m["source_file"]
            if sf not in best or m["score"] > best[sf]["score"]:
                best[sf] = m
    return sorted(best.values(), key=lambda m: m["score"], reverse=True)[:k]


# --- Metric formulas (identical to eval_retrieval_lms.py) -------------------

def precision_at_k(ranked_sources: list[str], relevant: set[str], k: int) -> float:
    top = ranked_sources[:k]
    if not top:
        return 0.0
    hits = sum(1 for s in top if s in relevant)
    return hits / len(top)


def recall_at_k(ranked_sources: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    top = ranked_sources[:k]
    hits = sum(1 for s in top if s in relevant)
    return hits / len(relevant)


def reciprocal_rank(ranked_sources: list[str], relevant: set[str]) -> float | None:
    if not relevant:
        return None
    for i, src in enumerate(ranked_sources, start=1):
        if src in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_sources: list[str], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    top = ranked_sources[:k]
    dcg = sum(1.0 / math.log2(i + 1) for i, s in enumerate(top, start=1) if s in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else None


def f1_at_k(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def avg(values: list[float | bool | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def main() -> None:
    rows = load_ground_truth()
    results = []

    for row in rows:
        domain_cell = row["domain"].strip().lower()
        relevant = relevant_set(row["relevant_doc_ids"])

        matches = retrieve_multi_domain(row["query_text"], domain_cell, K)
        ranked_sources = [m["source_file"] for m in matches]
        ranked_basenames = [_basename(s) for s in ranked_sources]
        gate_pass = check_relevance(matches)
        top1_correct = bool(ranked_basenames) and ranked_basenames[0] in relevant
        stale_or_unknown_hits = sum(
            1 for s in ranked_sources
            if not s.startswith(("technical/", "billing/", "hr/")) and s != "precedent_memory"
        )

        results.append({
            "query_id": row["query_id"],
            "domain": domain_cell,
            "has_relevant_doc": bool(relevant),
            "relevant_doc_ids": ";".join(sorted(relevant)) if relevant else "none",
            "retrieved_top4": ";".join(ranked_sources),
            "retrieved_scores": ";".join(f"{m['score']:.4f}" for m in matches),
            "stale_or_unknown_hits_in_top4": stale_or_unknown_hits,
            "gate_pass": gate_pass,
            "top1_correct": top1_correct,
            "precision_at_1": precision_at_k(ranked_basenames, relevant, 1),
            "precision_at_2": precision_at_k(ranked_basenames, relevant, 2),
            "precision_at_3": precision_at_k(ranked_basenames, relevant, 3),
            "precision_at_4": precision_at_k(ranked_basenames, relevant, 4),
            "recall_at_1": recall_at_k(ranked_basenames, relevant, 1),
            "recall_at_2": recall_at_k(ranked_basenames, relevant, 2),
            "recall_at_3": recall_at_k(ranked_basenames, relevant, 3),
            "recall_at_4": recall_at_k(ranked_basenames, relevant, 4),
            "reciprocal_rank": reciprocal_rank(ranked_basenames, relevant),
            "ndcg_at_4": ndcg_at_k(ranked_basenames, relevant, 4),
            "notes": row.get("notes", ""),
        })
        results[-1]["f1_at_1"] = f1_at_k(results[-1]["precision_at_1"], results[-1]["recall_at_1"])
        results[-1]["f1_at_2"] = f1_at_k(results[-1]["precision_at_2"], results[-1]["recall_at_2"])
        results[-1]["f1_at_3"] = f1_at_k(results[-1]["precision_at_3"], results[-1]["recall_at_3"])
        results[-1]["f1_at_4"] = f1_at_k(results[-1]["precision_at_4"], results[-1]["recall_at_4"])
        print(f"{row['query_id']}: domain={domain_cell} "
              f"gt={results[-1]['relevant_doc_ids']} top4={results[-1]['retrieved_top4']} "
              f"gate={gate_pass} P@4={results[-1]['precision_at_4']:.2f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "v3_per_query_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    with_relevant = [r for r in results if r["has_relevant_doc"]]
    without_relevant = [r for r in results if not r["has_relevant_doc"]]

    tp = sum(1 for r in results if r["gate_pass"] and r["top1_correct"])
    fp = sum(1 for r in results if r["gate_pass"] and not r["top1_correct"])
    fn = sum(1 for r in results if not r["gate_pass"] and r["top1_correct"])
    tn = sum(1 for r in results if not r["gate_pass"] and not r["top1_correct"])

    summary = {
        "k": K,
        "n_total": len(results),
        "n_with_relevant_doc": len(with_relevant),
        "n_no_relevant_doc": len(without_relevant),
        "precision_at_1_all": avg([r["precision_at_1"] for r in results]),
        "precision_at_2_all": avg([r["precision_at_2"] for r in results]),
        "precision_at_3_all": avg([r["precision_at_3"] for r in results]),
        "precision_at_4_all": avg([r["precision_at_4"] for r in results]),
        "precision_at_1_with_relevant_only": avg([r["precision_at_1"] for r in with_relevant]),
        "precision_at_2_with_relevant_only": avg([r["precision_at_2"] for r in with_relevant]),
        "precision_at_3_with_relevant_only": avg([r["precision_at_3"] for r in with_relevant]),
        "precision_at_4_with_relevant_only": avg([r["precision_at_4"] for r in with_relevant]),
        "recall_at_1": avg([r["recall_at_1"] for r in with_relevant]),
        "recall_at_2": avg([r["recall_at_2"] for r in with_relevant]),
        "recall_at_3": avg([r["recall_at_3"] for r in with_relevant]),
        "recall_at_4": avg([r["recall_at_4"] for r in with_relevant]),
        "f1_at_1": avg([r["f1_at_1"] for r in with_relevant]),
        "f1_at_2": avg([r["f1_at_2"] for r in with_relevant]),
        "f1_at_3": avg([r["f1_at_3"] for r in with_relevant]),
        "f1_at_4": avg([r["f1_at_4"] for r in with_relevant]),
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
    for dom in ("technical", "billing", "hr"):
        # A multi-domain row (e.g. "billing,hr") counts toward every domain
        # it names, since it's a legitimate ground-truth answer for each.
        subset = [r for r in results if dom in r["domain"].split(",")]
        subset_rel = [r for r in subset if r["has_relevant_doc"]]
        by_domain[dom] = {
            "n": len(subset),
            "n_with_relevant_doc": len(subset_rel),
            "precision_at_4_all": avg([r["precision_at_4"] for r in subset]),
            "recall_at_4": avg([r["recall_at_4"] for r in subset_rel]),
            "f1_at_4": avg([r["f1_at_4"] for r in subset_rel]),
            "mrr": avg([r["reciprocal_rank"] for r in subset_rel]),
        }
    summary["by_domain"] = by_domain
    summary["n_multi_domain_rows"] = sum(1 for r in results if "," in r["domain"])

    print(json.dumps(summary, indent=2))
    with open(RESULTS_DIR / "v3_summary_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()

"""Summarise the agentic A/B (run_agentic_ab.py + rejudge.py) into results/summary.json.

Every metric is computed the same way for both arms on the same tickets.
Retrieval:  Hit@1, Hit@4 and MRR of the first relevant KB document, over the
            documents the drafting specialist(s) actually used (pooled, by score).
Quality:    fresh one-shot judge scores (rejudge.py score) - unbiased - plus the
            pairwise new-vs-control verdict in both orders (rejudge.py pairwise).
Routing / escalation: against the human labels of Track B (disputed rows excluded).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean

import pandas as pd
from scipy.stats import wilcoxon

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
EVAL = HERE.parents[1]
GT_DOCS = EVAL / "Track-A-Retrieval-Quality" / "data" / "lms_ticket_ground_truth.csv"
GT_ROUTING = EVAL / "Track-B-Routing-Escalation-Accuracy" / "data" / "routing_ground_truth.csv"
ARMS = ("control", "new")


def load_jsonl(name: str) -> list[dict]:
    path = RESULTS / name
    return [json.loads(line) for line in open(path, encoding="utf-8")] if path.exists() else []


def ranked_docs(run: dict) -> list[str]:
    pooled = [c for ctx in (run.get("retrieved") or {}).values() for c in ctx if c.get("source_file")]
    pooled.sort(key=lambda c: c.get("score") or 0, reverse=True)
    seen: list[str] = []
    for c in pooled:
        if c["source_file"] not in seen:
            seen.append(c["source_file"])
    return seen


def retrieval_metrics(runs: dict, relevant: dict[str, set[str]], qids: list[str]) -> dict:
    hit1 = hit4 = rr = 0.0
    for q in qids:
        docs = ranked_docs(runs[q])[:4]
        rank = next((i + 1 for i, d in enumerate(docs) if d in relevant[q]), None)
        hit1 += rank == 1
        hit4 += rank is not None
        rr += 1 / rank if rank else 0
    n = len(qids)
    return {"n": n, "hit@1": round(hit1 / n, 3), "hit@4": round(hit4 / n, 3), "mrr": round(rr / n, 3)}


def prf(pred: list[bool], truth: list[bool]) -> dict:
    tp = sum(p and t for p, t in zip(pred, truth)); fp = sum(p and not t for p, t in zip(pred, truth))
    fn = sum(t and not p for p, t in zip(pred, truth))
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def main() -> None:
    runs = {arm: {} for arm in ARMS}
    for r in load_jsonl("ab_runs.jsonl"):
        if r.get("drafts") is not None:
            runs[r["arm"]][r["query_id"]] = r
    qids = sorted(set(runs["control"]) & set(runs["new"]))
    summary: dict = {"tickets_compared": len(qids)}

    docs = pd.read_csv(GT_DOCS).set_index("query_id")
    relevant = {q: set(str(docs.loc[q, "relevant_doc_ids"]).split(";")) for q in qids}
    summary["retrieval"] = {arm: retrieval_metrics(runs[arm], relevant, qids) for arm in ARMS}
    crag = [q for q in qids if runs["new"][q].get("corrective_rag")]
    summary["corrective_rag"] = {
        "tickets_triggered": len(crag),
        "rewrite_used": sum(any(v.get("used_rewrite") for v in runs["new"][q]["corrective_rag"].values()) for q in crag),
        "retrieval_on_triggered_tickets": {arm: retrieval_metrics(runs[arm], relevant, crag) for arm in ARMS} if crag else {},
        "mean_best_score_before": round(mean(v["score_before"] for q in crag for v in runs["new"][q]["corrective_rag"].values()), 3) if crag else None,
        "mean_best_score_after": round(mean(v["score_after"] for q in crag for v in runs["new"][q]["corrective_rag"].values()
                                            if v.get("score_after") is not None), 3) if crag else None,
    }

    summary["rewrites"] = {}
    for arm in ARMS:
        sources = Counter(s for q in qids for s in runs[arm][q].get("reflection_sources") or [])
        summary["rewrites"][arm] = {
            "mean_rewrites_per_ticket": round(mean(runs[arm][q].get("reflection_count", 0) for q in qids), 2),
            "rule_driven": sources.get("validation", 0), "judge_driven": sources.get("judge", 0),
            "mean_llm_calls_per_ticket": round(mean(runs[arm][q].get("llm_call_count") or 0 for q in qids), 2),
            "mean_seconds_per_ticket": round(mean(runs[arm][q].get("seconds") or 0 for q in qids), 1),
        }
    kept = [j.get("kept_pre_reflection_draft") for q in qids for j in (runs["new"][q].get("judge") or {}).values()
            if "judge" in (runs["new"][q].get("reflection_sources") or []) and j.get("kept_pre_reflection_draft") is not None]
    summary["rewrites"]["new"]["judge_rewrite_kept_original_instead"] = sum(bool(k) for k in kept)

    scores = {}
    for r in load_jsonl("rejudge_scores.jsonl"):
        if "overall_score" in r:
            scores[(r["arm"], r["query_id"], r["domain"])] = r
    dims = ["overall_score", "priority_tone_match_score", "completeness_score", "accuracy_score",
            "policy_compliance_score", "groundedness_score"]
    pairs = [(scores[("control", q, d)], scores[("new", q, d)]) for (a, q, d) in scores
             if a == "control" and ("new", q, d) in scores]
    if pairs:
        quality = {"paired_drafts": len(pairs)}
        for dim in dims:
            c = [p[0][dim] for p in pairs]; n = [p[1][dim] for p in pairs]
            diffs = [b - a for a, b in zip(c, n)]
            p_value = wilcoxon(n, c).pvalue if any(diffs) else 1.0
            quality[dim] = {"control": round(mean(c), 2), "new": round(mean(n), 2),
                            "better": sum(d > 0 for d in diffs), "worse": sum(d < 0 for d in diffs),
                            "same": sum(d == 0 for d in diffs), "wilcoxon_p": round(float(p_value), 3)}
        quality["share_overall_below_4"] = {
            "control": round(mean(p[0]["overall_score"] < 4 for p in pairs), 3),
            "new": round(mean(p[1]["overall_score"] < 4 for p in pairs), 3)}
        summary["fresh_judge_quality"] = quality

    verdicts = Counter(r["final_winner"] for r in load_jsonl("pairwise.jsonl") if "final_winner" in r)
    if verdicts:
        summary["pairwise_new_vs_control"] = dict(verdicts)

    gt = pd.read_csv(GT_ROUTING).set_index("query_id")
    agreed = [q for q in qids if q in gt.index and gt.loc[q, "routing_ground_truth"] != "NEEDS_REVIEW"
              and gt.loc[q, "should_escalate"] != "NEEDS_REVIEW"]
    summary["routing_and_escalation"] = {}
    for arm in ARMS:
        route_ok = [runs[arm][q]["routing_decision"] == gt.loc[q, "routing_ground_truth"] for q in agreed]
        esc_pred = [bool(runs[arm][q].get("escalation_triggered")) for q in agreed]
        esc_true = [str(gt.loc[q, "should_escalate"]).lower() == "true" for q in agreed]
        summary["routing_and_escalation"][arm] = {"n": len(agreed), "routing_accuracy": round(mean(route_ok), 3),
                                                  "escalation": prf(esc_pred, esc_true)}
    summary["supervisor"] = {"fired": sum(bool((runs["new"][q].get("supervisor") or {}).get("used")) for q in qids),
                             "rules_seen": dict(Counter(runs["new"][q].get("routing_rule") for q in qids))}
    both = [q for q in qids if runs["new"][q].get("routing_decision") == "both"]
    summary["aggregator"] = {"both_tickets": len(both),
                             "merged": sum(bool((runs["new"][q].get("aggregation") or {}).get("merged")) for q in both),
                             "fallback_reasons": dict(Counter((runs["new"][q].get("aggregation") or {}).get("reason") for q in both))}

    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

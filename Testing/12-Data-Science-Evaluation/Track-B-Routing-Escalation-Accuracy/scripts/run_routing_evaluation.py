"""Track B FINAL, step 3: same computation as
../pilot-99-query/scripts/run_routing_evaluation_99.py, pointed at the
70-real-ticket ground truth. See that script's docstring for the full
methodology (live vs. routing-logic-only runs, what escalation triggers
are and aren't tested, why McNemar's test on the reroute retry isn't
computed here).

Only run this AFTER the pilot round (../pilot-99-query/) has been scored
and any response_judge.py/routing_node.py/escalation_node.py fixes it
surfaced have been applied and re-verified - that's the whole point of
running the pilot first.

Usage:
    python3 run_routing_evaluation.py
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[4] / "clario-ml-sidecar"
sys.path.insert(0, str(_SIDECAR_ROOT))

from app.graph.routing_node import decide_routing  # noqa: E402
from app.graph.escalation_node import decide_escalation  # noqa: E402
from app.tools.classification_tool import classify_ticket  # noqa: E402

_HERE = Path(__file__).resolve().parent
DATA_DIR = _HERE.parent / "data"
RESULTS_DIR = _HERE.parent / "results"
GT_PATH = DATA_DIR / "routing_ground_truth.csv"

VALID_ROUTES = ["technical", "billing", "both", "hr", "escalation"]
DIRECT_CATEGORY_ROUTES = {"technical", "billing", "hr"}


def load_ground_truth() -> list[dict]:
    with open(GT_PATH, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    resolved = [r for r in rows if r["routing_ground_truth"] != "NEEDS_REVIEW" and r["should_escalate"] != "NEEDS_REVIEW"]
    skipped = len(rows) - len(resolved)
    if skipped:
        print(f"Skipping {skipped} unresolved NEEDS_REVIEW row(s) - resolve disputes in {GT_PATH} first.")
    return resolved


def confusion_and_prf(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    return {
        "labels": labels,
        "confusion_matrix": cm.tolist(),
        "per_class": {
            labels[i]: {"precision": precision[i], "recall": recall[i], "f1": f1[i], "support": int(support[i])}
            for i in range(len(labels))
        },
        "accuracy": sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true) if y_true else None,
    }


def escalation_prf(y_true: list[bool], y_pred: list[bool]) -> dict:
    from sklearn.metrics import precision_recall_fscore_support
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=[True, False], zero_division=0
    )
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    return {
        "precision": precision[0], "recall": recall[0], "f1": f1[0],
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "missed_escalations_fn": fn,
        "unnecessary_escalations_fp": fp,
    }


async def run() -> None:
    rows = load_ground_truth()

    live_route_true, live_route_pred = [], []
    live_esc_true, live_esc_pred = [], []
    logic_route_true, logic_route_pred = [], []
    logic_esc_true, logic_esc_pred = [], []
    logic_skipped = 0
    n_both_live = 0
    n_low_confidence = 0
    per_row = []

    for i, row in enumerate(rows, start=1):
        qid, text = row["query_id"], row["query_text"]
        gt_route = row["routing_ground_truth"]
        gt_escalate = row["should_escalate"] == "True"
        print(f"[{i}/{len(rows)}] {qid}: gt_route={gt_route} gt_escalate={gt_escalate}", flush=True)

        result = await classify_ticket(text)
        category, priority, sentiment, confidence = (
            result["category"], result["priority"], result["sentiment"], result["confidence"],
        )
        if confidence is not None and confidence < 0.7:
            n_low_confidence += 1

        live_route = decide_routing(category, confidence, text)
        if live_route == "both":
            n_both_live += 1
        live_escalated, live_reasons = decide_escalation(
            priority, sentiment, live_route, confidence,
            failure_type="none", reflection_count=0, max_reflection_attempts=2,
            reroute_attempted=False, needs_reroute=False,
        )
        live_route_true.append(gt_route)
        live_route_pred.append(live_route)
        live_esc_true.append(gt_escalate)
        live_esc_pred.append(live_escalated)

        logic_route = logic_escalated = logic_reasons = None
        if gt_route in DIRECT_CATEGORY_ROUTES:
            logic_route = decide_routing(gt_route, 0.99, text)
            logic_escalated, logic_reasons = decide_escalation(
                priority, sentiment, logic_route, 0.99,
                failure_type="none", reflection_count=0, max_reflection_attempts=2,
                reroute_attempted=False, needs_reroute=False,
            )
            logic_route_true.append(gt_route)
            logic_route_pred.append(logic_route)
            logic_esc_true.append(gt_escalate)
            logic_esc_pred.append(logic_escalated)
        else:
            logic_skipped += 1

        per_row.append({
            "query_id": qid, "gt_route": gt_route, "gt_escalate": gt_escalate,
            "classifier_category": category, "classifier_confidence": confidence,
            "live_route": live_route, "live_escalated": live_escalated, "live_reasons": ";".join(live_reasons),
            "logic_route": logic_route, "logic_escalated": logic_escalated,
            "logic_reasons": ";".join(logic_reasons) if logic_reasons else "",
        })

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "per_query_routing_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_row[0].keys()))
        writer.writeheader()
        writer.writerows(per_row)

    summary = {
        "n_total": len(rows),
        "n_low_confidence_lt_0.7": n_low_confidence,
        "n_routed_both_live": n_both_live,
        "n_skipped_from_logic_only": logic_skipped,
        "live_routing": confusion_and_prf(live_route_true, live_route_pred, VALID_ROUTES),
        "live_escalation": escalation_prf(live_esc_true, live_esc_pred),
        "routing_logic_only_routing": confusion_and_prf(logic_route_true, logic_route_pred, VALID_ROUTES) if logic_route_true else None,
        "routing_logic_only_escalation": escalation_prf(logic_esc_true, logic_esc_pred) if logic_esc_true else None,
        "not_computed": {
            "mcnemar_reroute_retry": "needs a real run through validation_node to produce a genuine misroute event - out of scope here, see README",
            "escalation_triggers_excluded": ["dependency_failure", "misroute_unresolved", "reflection_cap_reached"],
        },
    }
    print(json.dumps(summary, indent=2, default=str))
    with open(RESULTS_DIR / "routing_eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nWrote {RESULTS_DIR / 'routing_eval_summary.json'} and per_query_routing_results.csv")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

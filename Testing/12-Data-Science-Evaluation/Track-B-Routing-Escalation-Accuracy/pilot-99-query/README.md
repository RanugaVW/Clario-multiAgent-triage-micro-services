# Track B PILOT — 99-Query Routing & Escalation Check

**Status: annotation files ready, human annotation not yet started.** Run *before* the final round on the 70 real tickets (see `../README.md`) — same "check a second, independent dataset first" principle Track A and Track D both used.

## What this checks

`DATA_SCIENCE_EVALUATION_PROPOSAL.md` §7.2 — whether `routing_node.py:decide_routing()` and `escalation_node.py:decide_escalation()` (the rule-based logic sitting on top of the classifier) make the correct call, independently of how accurate the classifier itself is. Two runs per query, so classifier mistakes and routing-rule mistakes don't get mixed together — see `scripts/run_routing_evaluation_99.py`'s docstring for the exact methodology.

## Why annotation is scoped the way it is

Track A already produced an independently-verified domain label for every one of these 99 queries. Re-annotating that from scratch here would duplicate real work for no benefit — `routing_ground_truth` is mechanically derivable from domain in the vast majority of cases (`scripts/prepare_routing_annotation_99.py`'s `mechanical_route()`). The two humans annotate only what's genuinely new:

1. **`should_escalate`** (every row) — doesn't exist anywhere yet.
2. **`routing_ground_truth_override`** — only for the rows the mechanical rule can't resolve. In this dataset that's exactly the 40 of 99 queries where Track A found **no correct KB document exists at all** (`relevant_doc_ids: none`) — a real, large fraction of this set, not an edge case.

## Files

| File | Contents |
|---|---|
| `scripts/prepare_routing_annotation_99.py` | Builds the annotation file, with the mechanical routing guess and the `routing_needs_annotation` flag pre-filled |
| `data/routing_annotation_sample_99.csv` | What the two humans fill in |
| `HOW_TO_ANNOTATE_99.md` | Instructions for the two annotators |
| `scripts/merge_routing_annotations_99.py` | Checks agreement (kappa), writes `data/routing_ground_truth_99.csv`, flags disputes to `data/routing_disputes_99.txt` |
| `scripts/run_routing_evaluation_99.py` | Runs the real `routing_node.py`/`escalation_node.py` (live + routing-logic-only) against the finalized ground truth |
| `results/per_query_routing_results_99.csv`, `results/routing_eval_summary_99.json` | Produced by the evaluation script |

## What's deliberately not tested here

`decide_escalation()`'s real signature depends on `sentiment`, `failure_type`, `reflection_count`, and `reroute_attempted` — fields that only get real values after a ticket runs all the way through specialists, validation, and reflection. This pilot (like Track D) stops at classification + routing, so only the escalation triggers decidable from ticket-intrinsic signals are tested: `critical_priority`, `negative_sentiment`, `hr_process_required`, `no_usable_routing_signal`, `low_confidence_dual_domain`. Not tested: `dependency_failure`, `misroute_unresolved`, `reflection_cap_reached` — and the proposal's McNemar's test on the one-time reroute retry, which needs a genuine misroute event from a real run to compare against. An explicit scope decision, not an oversight — see `scripts/run_routing_evaluation_99.py`'s docstring.

## Next step

Two people (Ranuga, Sineth) annotate `data/routing_annotation_sample_99.csv` independently per `HOW_TO_ANNOTATE_99.md`, then run the merge and evaluation scripts in order. A weak result is a signal to fix `routing_node.py`/`escalation_node.py` before moving to the 70-ticket final round — that's the whole point of running this pilot first.

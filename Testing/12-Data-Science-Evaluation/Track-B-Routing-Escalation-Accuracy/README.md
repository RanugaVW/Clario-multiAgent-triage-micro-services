# Track B — Routing and Escalation Accuracy

**Status: annotation files ready for the 70-ticket round, but pilot-99-query/ should be scored FIRST.** Checks whether `routing_node.py:decide_routing()` and `escalation_node.py:decide_escalation()` make the correct call, per `DATA_SCIENCE_EVALUATION_PROPOSAL.md` §7.2.

**Score `pilot-99-query/` first.** Same "check a second, independent dataset before trusting either" discipline Track D used, which caught a real problem there (a rubric fix that had silently reverted). Run the pilot, fix anything it finds in `routing_node.py`/`escalation_node.py`, re-verify, then come back here.

## What Track B checks, in two runs per ticket

1. **Live run** — the real local classifier supplies category/priority/sentiment/confidence exactly as production would, then `decide_routing()`/`decide_escalation()` run on that real output. Realistic, but a wrong answer here could come from the classifier or the routing rules.
2. **Routing-logic-only run** — `decide_routing()` is called again with category replaced by the human-verified ground-truth domain and confidence forced above the 0.7 cutoff. This isolates the routing/escalation *rules* from classifier noise — any mistake left over belongs to the rules themselves.

Metrics: routing accuracy, per-class precision/recall/F1, and a confusion matrix for both runs; escalation checked as a yes/no classifier (precision/recall/F1, with missed-escalation vs. unnecessary-escalation counted separately, since they're not equally bad mistakes).

## How the ground truth is built — and why it's leaner than Track D's

Track A already produced an independently-verified domain label for all 70 tickets. Re-annotating that from scratch would duplicate real work. Instead:

- **`routing_ground_truth`** is derived mechanically from Track A's domain wherever that's unambiguous (`technical`→`technical`, `billing,technical`→`both`, etc.). The two humans only annotate the genuinely unresolved cases — in this dataset, the **11 tickets that need both `billing` and `hr`** expertise, a combination the system has no routing destination for today.
- **`should_escalate`** is new for every ticket, judged from the ticket's real `Priority` and `Recommended Action` fields (joined from the raw ticket log — see `scripts/prepare_routing_annotation.py`'s docstring for the one ticket, Q016, whose source row couldn't be reliably identified and is flagged rather than guessed).

Full annotation instructions: `HOW_TO_ANNOTATE.md`.

## What's deliberately not tested

Same scope boundary as the pilot: `decide_escalation()`'s `dependency_failure`/`misroute_unresolved`/`reflection_cap_reached` triggers, and the proposal's McNemar's test on the reroute retry, all need a real run through validation + reflection to produce genuine events to test against. Not computed here — see `scripts/run_routing_evaluation.py`'s docstring.

## Files

| File | Contents |
|---|---|
| `scripts/prepare_routing_annotation.py` | Builds the annotation file (mechanical routing guess, `routing_needs_annotation` flag, Priority/Recommended Action joined from the raw ticket log) |
| `data/routing_annotation_sample.csv` | What the two humans fill in |
| `HOW_TO_ANNOTATE.md` | Instructions for the two annotators |
| `scripts/merge_routing_annotations.py` | Checks agreement (kappa), writes `data/routing_ground_truth.csv`, flags disputes |
| `scripts/run_routing_evaluation.py` | Runs the real routing/escalation logic (live + routing-logic-only) against the finalized ground truth |
| `results/per_query_routing_results.csv`, `results/routing_eval_summary.json` | Produced by the evaluation script |
| `pilot-99-query/` | The pilot round — run this first, see its own `README.md` |

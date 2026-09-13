# Track C Pilot (99-Query Set)

**Purpose: catch pipeline problems before the real 70-ticket round, same discipline as Track B/D's own pilots.** This round has a real, structural limit: the 99-query set (`retrieval_ground_truth.csv`, Track A's original V1 baseline) has no *usable* real human reply to compare against. Some of these 99 rows do trace back to real tickets (the `notes` column says so), but their ticket numbering doesn't line up with the current raw ticket file, so there's no reliable way to join a real reply to them - practically the same limit as "no real reply exists," just for a different reason than originally stated here. So **two of Track C's four checks can't run here at all** - pairwise win-rate and semantic similarity both need a human reference. What this pilot *can* still validate:

- The full-graph generation script runs end to end on all 99 queries without crashing, including through routing/escalation (a real risk - a "hr"-routed ticket, or any other escalation, must still leave a scoreable draft behind).
- `response_judge.py`'s scores look sane (no repeat of the flat-2/5 bug Track D found and fixed).
- The groundedness-check script works and its threshold isn't obviously wrong.

Only once these run cleanly here is it worth spending the API cost and time on the 70-ticket round.

## Why this reuses none of Track D's already-generated data

Track D's `pilot-99-query/results/clario_drafts_and_judge_scores_99.csv` looks like the same shape of data, but it isn't the same thing: Track D's generator deliberately **bypasses classification_node and routing_node**, calling the correct specialist directly with the ground-truth domain, specifically to isolate "does the judge agree with a human" from "did routing get it right." Track C is the opposite - it exists to check the actual reply a real customer would receive, so it has to go through the same graph a live ticket goes through, `classification_node`/`routing_node` mistakes and all. This is also why this pilot is worth re-running now rather than skipping straight to the 70-ticket round: Track B's routing/escalation fixes made earlier this session change what this full-graph run actually produces.

## Steps

```
python3 scripts/run_full_graph_generation_99.py
python3 scripts/compute_groundedness_99.py
python3 scripts/prepare_response_annotation_99.py   # builds the human notes sheet (see below)
python3 scripts/summarize_track_c_results_99.py
```

`run_full_graph_generation_99.py` calls the real Gemini-backed judge and drafting calls for up to 99 tickets - expect real time and API cost, similar in scale to Track D's own generation run. It appends rather than overwrites, and takes `--start`/`--limit` if it needs to be resumed after a partial run or rate-limit interruption.

## Human notes on the actual generated replies

Checks 1 (pairwise) and 3 (semantic similarity) can't run on this dataset at all - there's no real human reply to compare against. `prepare_response_annotation_99.py` fills that gap a different way: it writes `data/response_annotation_99.csv`, one row per ticket with the ticket text and Clario's actual customer-facing draft side by side, and two humans independently read each row and fill in:

- `human1_flag` / `human2_flag` - one of `good` / `needs_improvement` / `wrong_or_inaccurate` / `too_generic` / `tone_issue` / `missing_info`
- `human1_notes` / `human2_notes` - free text: what specifically should be enhanced

This is qualitative, not a metric this pilot computes automatically - it's meant to surface real, concrete problems (wrong tone, missed part of the question, technically fine but unhelpful) the same way Track B's human annotation caught real routing/escalation gaps, before spending real API cost on the 70-ticket round. If a count is wanted later, the flags are a fixed small set so Cohen's kappa between the two humans can be computed the same way Track A/B/D did.

## Files

| File | Contents |
|---|---|
| `results/clario_full_graph_drafts_99.csv` | One row per domain-drafted ticket (some tickets produce 2, for "both"-routed cases; escalated-before-drafting tickets get one row with an empty draft): routing decision, escalation outcome, draft text, retrieved sources, all 6 judge sub-scores |
| `results/groundedness_99.csv` | Sentence-level: does each sentence in the customer-facing draft have a similar sentence somewhere in what was actually retrieved |
| `data/response_annotation_99.csv` | Ticket + Clario's draft + two humans' flag and free-text notes on what should be enhanced |

## What "done" looks like here

No crashes, no repeat of a known bug, and a groundedness distribution that looks plausible on manual spot-check (not "80% of every draft is unsupported," which would mean the threshold or the sentence-splitting is broken, not that the specialists are actually fabricating most of their replies). Once that's true, move to `../` for the real 70-ticket round.

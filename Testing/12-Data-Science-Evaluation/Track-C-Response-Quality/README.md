# Track C — Final Response Quality vs. Real Human Replies

**Status: folder structure and scripts ready, not yet run.** Checks whether the reply Clario actually writes is as good as what a real human support agent wrote for the same ticket, per `DATA_SCIENCE_EVALUATION_PROPOSAL.md` §7.3. Tracks A and B check that the system finds the right information and sends the ticket to the right place; Track C checks the actual message a customer would receive.

**Score `pilot-99-query/` first** — same discipline as Track B/D. See that folder's `README.md` for why it exists and what it can and can't check.

## Almost no annotation needed

Unlike Track A/B/D, Track C doesn't need a human-built ground truth — it's built on tools that already exist and already produce their own numbers (`response_judge.py`, `run_pairwise_evaluation.py`, embedding models). **Read `HOW_TO_ANNOTATE.md` before running anything** — it covers the one required decision (which reference version to score against) and two optional, recommended checks.

## The four checks (DATA_SCIENCE_EVALUATION_PROPOSAL.md §7.3)

| # | Check | Needs a real human reply? | Tool |
|---|---|---|---|
| 1 | Pairwise win-rate (Clario vs. human, side by side) | Yes | `scripts/run_pairwise_evaluation.py` (existing, reused as-is) |
| 2 | Absolute score (1-5, several dimensions) | No | `response_judge.py` (existing, already runs inside the real graph) |
| 3 | Semantic similarity (MiniLM cosine + BERTScore F1; BLEU/ROUGE as a side note) | Yes | `scripts/compute_semantic_similarity.py` (new) |
| 4 | Groundedness (does the reply say things the retrieved KB content backs up) | No | `scripts/compute_groundedness.py` (new) |

Checks 1 and 3 need a real reply to compare against, which only reliably exists for the 70 real tickets (the `Original Response` column in the raw ticket file) — **the 99-query pilot can only run checks 2 and 4.** This isn't a shortcut, it's a hard data limit: the pilot's dataset (`retrieval_ground_truth.csv`, Track A's original V1 baseline) does partly trace back to real tickets, but its ticket numbering doesn't match the current raw ticket file, so there's no reliable way to join a real reply to it. Same practical limit as "no real reply exists," corrected here from an earlier, less accurate description of why.

## Known limitation: the human reply isn't always the best answer

The real human replies in `Original Response` weren't perfect — some have real problems (one ticket's `Recommended Action` literally says "Never request passwords/credentials from users," meaning that's what the human reply did). This matters differently for each check:

- **Checks 2 and 4 (absolute score, groundedness) are not affected at all.** They never look at the human reply — they judge Clario's draft against the ticket and the retrieved KB content directly.
- **Check 1 (pairwise) is not affected either.** The judge picks whichever reply is actually better each time. If the human reply was bad and Clario's is good, the judge is supposed to pick Clario — that's a correct result, not a warning sign.
- **Check 3 (semantic similarity) IS affected, and this is the one to be careful reading.** It's currently scored against `human_reply_as_sent` — the real reply, flaws included — because nobody has gone through and rewritten the genuinely bad ones yet. So if Clario gets a **low** similarity score on a ticket like the password one, that doesn't mean Clario did worse. It likely means Clario gave the *right* answer and the human didn't, so the two replies naturally don't look alike.

**Fix (not yet done):** `HOW_TO_ANNOTATE.md` §1, option B — someone reads through the `recommended_action` notes, picks out the small handful that flag a real content problem (not just a style note), and rewrites `human_reply_corrected` for those. Once that's done, similarity can be checked against the corrected version too, which is a fair comparison. Until then, report check 3's numbers with this caveat attached, and lean on checks 1, 2, and 4 as the fair ones.

## Why this needs a fresh full-graph run, not Track D's existing data

Track D's already-generated drafts (`../Track-D-Judge-Reliability/results/clario_drafts_and_judge_scores.csv`) deliberately **bypass classification_node and routing_node**, to isolate judge reliability from routing correctness. Track C wants the opposite: the actual end-to-end reply a real customer would get, routing mistakes included. So `run_full_graph_generation.py`/`_99.py` call `build_graph().ainvoke()` directly — the same path a live ticket takes — rather than reusing Track D's bypassed generation. This also means Track B's routing/escalation fixes from earlier this session are "live" in these results in a way they aren't in Track D's frozen data.

A ticket that gets escalated (every `hr`-routed ticket, by current policy — see the escalation_node.py discussion this session) still produces a scoreable draft: `agent_drafts` is populated by the specialist *before* `escalation_node` decides whether to hold it back, so "this would have gone to a human" and "here's how good the underlying draft was" are two separate facts worth keeping both of.

## Steps — 70-ticket round (after the pilot comes back clean)

```
python3 scripts/prepare_human_reference_data.py     # joins Original Response / Recommended Action to each ticket
python3 scripts/run_full_graph_generation.py        # real graph, real API calls - expect real time/cost

# Pairwise check (writes to Supabase - see below):
python3 ../../../clario-ml-sidecar/scripts/run_pairwise_evaluation.py \
    --csv "../../../CSV Files/lms_support_tickets Real - Support Tickets.csv" \
    --ticket-col "Description" --response-col "Original Response"
python3 scripts/export_pairwise_from_supabase.py    # pulls that run back into results/pairwise_results.csv

python3 scripts/compute_semantic_similarity.py
python3 scripts/compute_groundedness.py
python3 scripts/summarize_track_c_results.py
```

**On `run_pairwise_evaluation.py`:** this is the proposal's own named tool, reused exactly as it exists — not rebuilt. It writes to the `pairwise_evaluations` Supabase table (schema in `supabase_pairwise_feedback_schema.sql`, already present in this project's `.env`), not a local file, and it reads the *raw* ticket CSV directly rather than going through Track A's `query_id`s — so its `source_doc_id` values are `rysera_row_0`, `rysera_row_1`, ... (0-indexed against the raw file's row order, which starts at Ticket #2), not `Q001`, `Q002`. `export_pairwise_from_supabase.py` exists specifically so the rest of Track C doesn't need live Supabase credentials for every subsequent script.

**Before running `run_pairwise_evaluation.py` for real:** it inserts real rows into a live Supabase table and calls the graph (real LLM calls) for all 70 tickets. Worth confirming this is actually wanted at this moment before kicking it off, same as any other live-system write in this project.

## Dependencies not yet installed

`sentence-transformers` and `supabase` are already available in `clario-ml-sidecar/.venv`. **`bert-score` is not** (`pip install bert-score` in that venv before running `compute_semantic_similarity.py` — the script runs without it but leaves the BERTScore columns blank). `nltk`/`rouge-score` are optional, only needed for the side-note BLEU/ROUGE numbers the proposal itself says aren't the main result.

## Files

| File | Contents |
|---|---|
| `data/human_reference_70.csv` | Each ticket's real reply (`human_reply_as_sent`), `recommended_action`, and `human_reply_corrected` (identical to as-sent until a human edits it per `HOW_TO_ANNOTATE.md`) |
| `results/clario_full_graph_drafts.csv` | Real end-to-end run: routing decision, escalation outcome, draft, retrieved sources, all 6 absolute judge scores |
| `results/pairwise_results.csv` | Exported from Supabase: Clario's draft vs. the real reply, judge's winner pick, both order-swapped passes |
| `results/semantic_similarity.csv` | MiniLM cosine + BERTScore F1, draft vs. both reference versions |
| `results/groundedness.csv` | Sentence-level: is each customer-facing sentence backed by what was actually retrieved |

## Not computed here

McNemar's test and reflection-vs-no-reflection quality comparisons are Track E's job (§7.5), not Track C's.

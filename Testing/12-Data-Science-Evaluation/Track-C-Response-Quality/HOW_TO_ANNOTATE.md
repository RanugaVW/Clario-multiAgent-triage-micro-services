# Track C — What Actually Needs a Human

Short answer: **almost nothing, by design.** Track C is built entirely on tools that already exist and produce their own numbers automatically (`response_judge.py`, `run_pairwise_evaluation.py`, MiniLM/BERTScore embeddings). Unlike Track A/B/D, there's no ground-truth label to hand-annotate here. There are exactly **one required decision** and **two optional, recommended checks** — read this before running anything in `scripts/`.

## 1. Required: pick a reference version (one decision, not per-ticket work)

`data/human_reference_70.csv` (built by `scripts/prepare_human_reference_data.py`) has two reference columns for every ticket:

- `human_reply_as_sent` — the real reply, exactly as the human agent sent it.
- `human_reply_corrected` — starts **identical** to `human_reply_as_sent`. Not auto-derived.

**Why this isn't automatic:** 69 of the 70 raw tickets have *some* text in `Recommended Action`, but read a few and it's obvious most are general coaching notes, not "this specific reply's content was wrong" — e.g. *"tighten grammar and request a screenshot"* or *"recognize repeat tickets and escalate automatically"* say nothing about the reply being incorrect. A few genuinely do flag a real problem, like *"Never request passwords/credentials from users."* Auto-flagging all 69 as "corrected" would just add noise; auto-flagging none would silently drop the real cases. This has to be a judgment call, ticket by ticket.

The proposal (`DATA_SCIENCE_EVALUATION_PROPOSAL.md` §7.3) requires deciding up front which reference Clario's draft is judged against, and reporting both if they give a meaningfully different result. `scripts/compute_semantic_similarity.py` already scores against both columns and flags if they diverge by more than 0.02 cosine similarity.

**Two ways to proceed, pick one before running the real evaluation:**

- **A — score against `human_reply_as_sent` only.** Simplest, always available, no extra work. Reasonable default: it's the actual number the "did Clario do as well as our real support team" story is more directly about.
- **B — have a human find and fix the real cases.** Read through `data/human_reference_70.csv`'s `recommended_action` column and judge each one: does this call out an actual content problem with the reply that was sent (wrong information, missed the actual question, something that shouldn't have been said), or is it a style/process note that doesn't change whether the reply itself was a reasonable answer? For the ones in the first category only — expect a small handful, not most of the 69 — rewrite `human_reply_corrected` with what the reply should have said, same tone and length as the original. Only do this if the "as sent vs. corrected" comparison is something you actually want to present; option A is a legitimate stopping point on its own.

## 2. Recommended, not required: a small human check on the pairwise judge

Track D already checked whether `response_judge.py`'s **absolute** 1–5 scores can be trusted, against two humans' scores. It did **not** check the **pairwise** judge (`run_pairwise_evaluation.py`'s "which reply is better" verdict) the same way — the proposal's Track D section only re-checks that judge's left/right order-bias control, not whether its winner picks agree with a human.

If you want the same level of confidence Track D gave the absolute score:

1. After `run_pairwise_evaluation.py` + `export_pairwise_from_supabase.py` produce `results/pairwise_results.csv`, sample ~20-25 rows spread across domains (same scale Track D used for its own calibration, given the same "not enough for a tight bound, enough to say broadly agrees/doesn't" caveat the proposal states outright for that track).
2. Two people independently read the ticket, Clario's draft, and the real reply (with the reply's left/right position swapped between the two people, so neither one's own bias about "which side tends to be better" leaks in) — and pick a winner themselves, **without seeing `final_winner` first.**
3. Compare: how often do the two humans agree with each other, and how often does either of them agree with `final_winner`. Cohen's κ over three categories (draft/reference/tie), same tool Track D and Track B both used (`sklearn.metrics.cohen_kappa_score`).

This is genuinely optional — the proposal doesn't require it for Track C itself, but it closes the one calibration gap Track D's own scope left open, and the pattern ("don't trust an automatic judge until it's checked") is what this whole evaluation has run on so far.

## 3. Sanity-check, not annotation: the groundedness threshold

`compute_groundedness.py`/`compute_groundedness_99.py` flag a sentence as "unsupported" below a cosine-similarity threshold (0.35) picked by eyeballing a few examples, not empirically tuned. Before trusting the flagged list:

- Read 10-15 flagged "unsupported" sentences from `results/groundedness.csv` (or the pilot's `groundedness_99.csv`) and confirm they're actually unsupported claims, not just oddly-worded paraphrases the embedding model scored low by coincidence.
- If most flagged sentences look like real paraphrases (not fabrications), the threshold is too strict — raise it. If sentences that look clearly made-up aren't getting flagged, lower it.

This is a five-minute spot-check, not formal annotation - there's no CSV to fill in for it, just read and adjust the constant in the script if needed.

## What NOT to do

Don't build a full annotation sheet with `human1_*`/`human2_*` columns for every one of the 70 tickets the way Track A/B/D did — Track C has no ground-truth label that needs establishing that way. If you find yourself designing one, stop and re-read §7.3 of the proposal: the four checks are all either fully automated or reuse an existing tool.

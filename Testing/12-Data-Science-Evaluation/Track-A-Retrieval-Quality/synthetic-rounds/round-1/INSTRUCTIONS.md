# Round 1 — Synthetic Ticket Annotation

**Status: paused.** Postponed until after Track C is underway. The 50-record sample and
templates below stay ready to use whenever this resumes — nothing here expires.

---

**Source:** `ml_finetuning/data/curated_synthetic_lms/test_split.csv` (6,000 synthetic
tickets, 750 in each of 8 categories). This round is a stratified sample of 50 — 6 or 7
from each category, drawn with a fixed random seed (42) so it's reproducible, not
cherry-picked. The full sampled rows (with all original context columns) are in
`round1_sample.csv` for reference.

**Why synthetic, not more real tickets:** this gives a large pool to draw fresh rounds
from without re-using the same 70 real tickets over and over — which is the thing we're
specifically trying to avoid (see `TEST_REPORT_V2.md` §6 on tuning to the test set). The
70 real tickets stay untouched and get re-tested after every round, as the honest check
that nothing here was overfit.

## What to do

1. Each of you opens your own file — `round1_mapped_Ranuga_TEMPLATE.csv` or
   `round1_mapped_Sineth_TEMPLATE.csv` — **without looking at the other person's file or
   at what the system would say.**
2. For every row, using only the `query_text` column (the `*_context` columns are just
   for your own reference — priority/sentiment/category as the synthetic generator
   assigned them, not the answer), fill in:
   - `domain`: `technical`, `billing`, or `hr` — whichever Clario knowledge area should
     answer this ticket. If none of the three genuinely fit (e.g. a feature request with
     no knowledge-base answer), write `escalation` and leave `relevant_doc_ids` as `none`.
   - `relevant_doc_ids`: the exact KB filename(s), e.g. `technical/login_reset.md`, or
     `none` if no current document answers it. Semicolon-separate if more than one
     genuinely applies.
3. Save your file with the `_TEMPLATE` suffix removed, i.e. rename to
   `round1_mapped_Ranuga.csv` / `round1_mapped_Sineth.csv`.
4. Run the merge script:
   ```
   python3 ../../scripts/merge_annotation_round.py . round1
   ```
   This reports your agreement rate and writes `round1_ground_truth.csv`. Any row you
   two disagreed on comes out marked `NEEDS_REVIEW` — talk those through together (same
   as the 3 disputes in the original 70-ticket round) and hand-edit the final answer
   directly into `round1_ground_truth.csv`, the same way each of those 3 was written up
   with a one-line reason.
5. Once every `NEEDS_REVIEW` row is resolved, this round is ready to evaluate.

## After this round

- Test the system against `round1_ground_truth.csv` (same Precision@k/Recall@k/MRR/nDCG
  approach as `eval_retrieval_lms.py`), see what it gets wrong here.
- Make whatever enhancement the findings point to.
- **Re-run `eval_retrieval_lms.py` against the untouched 70 real tickets.** If it holds up
  or improves there too, the enhancement generalized. If it doesn't, the enhancement was
  shaped around round 1 specifically — a real, useful finding, not a failure.
- Only then move to round 2 (a fresh 50-record sample, same process).

# Track D PILOT — 99-Query Judge-Reliability Check

**Status: draft generation complete, human scoring not yet started.** Run *before* the main Track D round on the 70 real tickets (see `../README.md`) — same "check on a second, independent dataset before trusting either" principle Track A used for its threshold tuning.

## Why this exists

The 70-real-ticket round already found and fixed two real problems in the judge pipeline: a rigid required-phrase rubric that flat-lined 96% of scores at 2/5, and API rate-limiting that silently dropped most drafts on one run. Both fixes were verified there — but a fix that only gets checked against the dataset that found the bug risks being tuned to that one dataset's quirks. The 99-query set is different enough to be a real second check: larger, more billing-heavy (62/27/10 vs. the 70-set's more even split), and includes hand-written edge cases alongside real tickets.

**Running this caught a real process gap, not a code bug:** the response_judge.py rubric fix made during the 70-ticket round was never committed — it existed only as an uncommitted local change. In the days between that round and this one, unrelated real work landed on the same file (a different judge-scoring bug fix, pairwise-preference judging, new provider support), and the file reverted to the version without the fix. The very first smoke test on this 99-query pilot reproduced the exact old bug (flat 2/5 scores citing missing literal phrases), which is what caught it. The fix was reapplied and **committed this time** (`b4bc07f`).

## Result

99/99 queries processed, 99/99 draft+score rows written, 0 skipped, 0 failed. Per-domain: billing 62, technical 27, hr 10 (no multi-domain rows in this ground truth, unlike the 70-ticket set).

Score distribution — healthy and varied, consistent with the fixed rubric:

| Dimension | Distribution (of 99) |
|---|---|
| `overall` | 2→2, 3→53, 4→44 |
| `priority_tone_match` | 2→18, 3→55, 4→26 |
| `completeness` | 2→3, 3→46, 4→36, 5→14 |
| `accuracy` | 2→1, 3→3, 4→36, 5→59 |
| `policy_compliance` | 2→2, 3→7, 4→38, 5→52 |
| `groundedness` | 2→4, 3→10, 4→34, 5→51 |

## Files

| File | Contents |
|---|---|
| `scripts/generate_clario_drafts_99.py` | Generates drafts + judge scores for all 99 queries (same bypass method as the sibling script) |
| `results/clario_drafts_and_judge_scores_99.csv` | All 99 rows |
| `results/generation_run_summary_99.json` | Run counts |
| `scripts/sample_judge_calibration_99.py` | Prepares the human-scoring file — all 99 rows by explicit choice, matching the 70-ticket round |
| `data/judge_calibration_sample_99.csv` | What the two humans fill in |
| `data/judge_calibration_answer_key_99.csv` | The judge's own scores, kept separate until both humans finish |
| `HOW_TO_SCORE_99.md` | Instructions and rubric for the two human raters |
| `scripts/compute_agreement_99.py` | Run once both humans finish |

## Next step

Two people (Ranuga, Sineth) score all 99 rows in `data/judge_calibration_sample_99.csv` independently per `HOW_TO_SCORE_99.md`, then run `scripts/compute_agreement_99.py`. If the result is weak, that's a signal to go back to `response_judge.py` before spending effort scoring the 70-ticket round — that's the whole point of running this pilot first.

# Track D — Judge Reliability

**Status: draft generation complete (final, corrected run), human scoring not yet started.** This track checks whether `ResponseJudge` (the automatic scorer Track C leans on) actually agrees with what a real person would say about the same reply. Methodology: `DATA_SCIENCE_EVALUATION_PROPOSAL.md` §7.4.

Doing this now, ahead of Tracks B and C, since a teammate is handling those separately — Track D only needs a real drafted reply and a real judge score to exist, not a correct routing decision or a finished response-quality comparison.

**Score `pilot-99-query/` first.** Before scoring this folder's 70-ticket data, run the judge-reliability pilot on Track A's 99-query set (`pilot-99-query/README.md`) — a second, independently-built dataset, checked first so any remaining judge gaps get caught there rather than after investing effort on the "real" round. That pilot is exactly how a process gap got caught: the rubric fix described below was made once already, was never committed, and had silently reverted by the time the pilot ran — the pilot's first smoke test reproduced the original bug and led straight back here.

## How the input data was generated

`scripts/generate_clario_drafts.py` deliberately **bypasses classification_node and routing_node**. A smoke test showed the real local classifier + keyword router escalates most of these 70 tickets before any specialist runs at all (a genuine Track B finding — the classifier outputs generic categories like "General Support" that the router's keyword rules don't recognize) — which would leave nothing for Track D to sample from. Since Track D's question ("does the judge's score match a human's?") only needs a real draft to exist, not a realistic routing path, the script calls the correct specialist node(s) directly using Track A's already-verified ground-truth domain for each ticket — the same decoupling principle Track A itself used for retrieval. Real and unmodified: PII redaction, retrieval, the specialist's own LLM draft generation, few-shot selection, and `ResponseJudge`'s scoring.

**Final result:** 70/70 tickets processed, **82/82 draft+score rows written, 0 skipped, 0 failed** (some tickets have 2 domains and produced 2 rows each). Per-domain: billing 31, technical 27, hr 24.

## Two real problems found and fixed while generating this data

**1. The judge's scores were artificially flat (fixed in `response_judge.py`, both mirrored codebases).** An early run returned `judge_overall_score = 2/5` for 67 of 70 drafts (96%) — not noise, and traced directly: `PRIORITY_TONE_REQUIREMENTS`'s prompt wording told the judge every priority level has phrases that **must appear verbatim** in the draft (e.g. Medium priority requires "apologize for the inconvenience", "update within 24"), but the specialist's own draft-writing prompt never saw that checklist, so it could never satisfy it and got marked down the same way every time regardless of actual reply quality. **Fix:** reworded the tone-requirements section of `JUDGE_USER_PROMPT_TEMPLATE` (and the `priority_tone_match` dimension definition) so the listed phrases are explicitly **examples of the expected tone**, not a literal pass/fail checklist — the judge now scores whether the draft conveys the same commitment/urgency in its own words. Verified before re-running the full batch: a spot check moved affected drafts from a flat 2 to graded 2-4 scores tied to real content gaps.

**2. The regenerated batch initially failed 54/70 draft calls from API rate-limiting (fixed in `generate_clario_drafts.py`).** The Gemini free tier caps `generate_content` at 15 requests/minute per model, and draft generation + judging share one model — so each domain-draft costs 2 calls against that budget. The first re-run had no pacing between calls, blew through the quota by ticket ~20, and every retry immediately re-hit the same limit (confirmed directly in the error: `429 RESOURCE_EXHAUSTED ... quota: 15, model: gemini-3.1-flash-lite`). **Fix:** added an 8-second sleep between every domain-draft call (`PACING_SECONDS`), keeping sustained usage comfortably under the shared budget. The final run above completed with zero failures.

**Resulting score distribution is now healthy and varied** — no more artificial flat-lining:

| Dimension | Distribution (of 82) |
|---|---|
| `overall` | 3→45, 4→37 |
| `priority_tone_match` | 2→8, 3→52, 4→22 |
| `completeness` | 2→5, 3→39, 4→24, 5→14 |
| `accuracy` | 4→41, 5→41 |
| `policy_compliance` | 3→13, 4→33, 5→36 |
| `groundedness` | 3→10, 4→33, 5→39 |

## Files

| File | Contents |
|---|---|
| `scripts/generate_clario_drafts.py` | Generates Clario's real drafts + judge scores for all 70 tickets (bypass method, see above; includes the rate-limit pacing fix) |
| `results/clario_drafts_and_judge_scores.csv` | All 82 rows (final, corrected judge + full success run): ticket, domain, draft, retrieved sources, all 6 judge scores + reasoning |
| `results/generation_run_summary.json` | Run counts: processed/written/skipped/failed (70/82/0/0) |
| `scripts/sample_judge_calibration.py` | Picks how many of the 82 rows the two humans score, stratified by domain (`--n 82` = everything, currently used; `--n 28` for a smaller stratified sample if ever needed again) |
| `data/judge_calibration_sample.csv` | What the two humans fill in — **all 82 rows** (billing 31, technical 27, hr 24), not a sample: ticket ref, draft, retrieved sources, blank score columns. Judge scores deliberately withheld. |
| `data/judge_calibration_answer_key.csv` | The judge's own (corrected) scores for the same 82 rows, kept separate until both humans finish |
| `HOW_TO_SCORE.md` | Instructions and rubric for the two human raters |
| `scripts/compute_agreement.py` | Run once both humans finish: weighted Cohen's κ (human vs human) and κ + Spearman (judge vs combined human), per the proposal's §7.4 steps 3-4 |

## Next step

Two people (Ranuga, Sineth) score all 82 rows in `data/judge_calibration_sample.csv` independently per `HOW_TO_SCORE.md`, then run `scripts/compute_agreement.py`. Using the full set instead of the proposal's suggested 25-30-pair sample gives more statistical power (closer to ARES's own ~150-pair benchmark) at the cost of more manual scoring work for both of you — worth knowing going in.

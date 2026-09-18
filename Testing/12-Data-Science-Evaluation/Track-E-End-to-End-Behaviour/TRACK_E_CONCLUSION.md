# Track E — Conclusion

**Track E (End-to-End Behaviour) is complete.** I'm Ranuga, and I did this one on my own. For the full detail — formulas, methodology, every number — see `TRACK_E_FINAL_CONCLUSION_REPORT.md`.

---

## What I was checking

Tracks A-D each checked one part of Clario's pipeline on its own: retrieval, routing, response quality, judge reliability. None of them answered the system-level question: how often does each part of the pipeline actually fire, what goes wrong most, and is the "reflection" step (the system rewriting its own answer) actually worth what it costs?

None of that data existed anywhere before this track. I had to write a script that runs the same 70 real tickets through the real, live pipeline again, capturing cache hits, reflection loops, misroute retries, and escalations — flags nothing before this had ever saved.

---

## Funnel rates (70 real tickets, one live run each)

![Funnel rates](figures/01_funnel_rates.png)

| Funnel step | Rate | 95% confidence range |
|---|---|---|
| Cache-hit rate | 0.0% | 0.0% – 5.2% |
| Reflection-loop rate | 41.4% | 30.6% – 53.1% |
| Misroute-retry rate | 1.4% | 0.2% – 7.7% |
| Escalation rate | 40.0% | 29.3% – 51.7% |

**What I'd say showing this:** "Cache-hit is genuinely zero, and that makes sense — these are 70 different real tickets, not repeats, so there's nothing for the cache to match against. A little over 40% of tickets need at least one reflection pass. Misroute retries are rare. Escalation sits at 40%, though with only 70 tickets I'm reporting the honest range, not a falsely precise single number."

---

## Failure taxonomy — everything Tracks A-D found, in one place

![Failure taxonomy](figures/02_failure_taxonomy.png)

10 real, already-documented failure patterns from across every earlier track, sorted into 4 buckets: 2 wrong-retrieval, 2 fabricated-content, 4 prompt-gap, 2 genuinely-hard-case. Prompt gaps are the biggest group — and every one of them turned out to be fixable once someone actually found it.

---

## Does reflection actually help?

![Reflection value, two fixes applied one at a time](figures/03_reflection_value.png)

My first attempt compared reflected tickets against non-reflected ones and found reflected tickets scoring lower — but that comparison only measured which tickets started out harder. So I built a real paired comparison instead: each ticket's score before and after reflection, from the same judge.

| | 1. Before any fix (n=29) | 2. Fallback fix (n=15) | 3. + critique fix, full 70 (n=28) |
|---|---|---|---|
| Tickets that got worse | 8 | 0 | 1 (judge-rescoring noise, see below) |
| Tickets that improved | 5 | 2 | **5** |
| Tickets unchanged | 16 | 13 | **22** |
| Wilcoxon p-value | 0.265 | 0.157 | **0.103** |

**Three real, connected issues, fixed one at a time — not bundled, and not just reported.**

1. `response_judge_node.py` now scores both the original draft and the rewrite, and keeps whichever one the judge actually prefers — falling back to the original when reflection didn't help. Re-ran live: zero tickets ended up worse, down from eight — guaranteed by construction, not luck, since keeping the higher of two scores can't score lower than the better one.
2. That fix alone left 13 of 15 tickets completely unchanged, so I asked why: `validation_node.py`'s local judge was handing back the same hardcoded, meaningless string — `"local_heuristic_judge"` — as its rejection reason for *every* failure, so the specialist redrafting against it had nothing real to act on. Fixed it to name the specific check that failed instead. A 13-ticket preview looked great (tickets improved 2→5, p=0.063), but rather than trust a small preview I ran the full 70 tickets: same 5 tickets improved, but against a larger base the effect came back smaller and still short of significance (p=0.103) — a real, positive, unproven improvement, reported honestly rather than rounded up.
3. That full run showed one ticket scoring worse, which I chased down rather than wave away: the pipeline's own fallback decision was almost certainly correct, but my external verification script re-scored the saved draft with a second, independently-sampled judge call (temperature 0.1, not fully deterministic) and got a different number than the pipeline's internal comparison used. The real gap was that the pipeline discarded its own internal comparison once the decision was made — it now records it (`pre_reflection_score`, `kept_pre_reflection_draft`) so a future check can read the real decision instead of resampling the judge.

New tests pass for all three fixes (192 in `clario-ml-sidecar`, 181 in `services/ai-orchestrator-service`), and all three are mirrored across codebases.

**A real complication along the way:** the first fix's verification run hit the project's daily Gemini quota partway through (the same limit Track C hit once before). I checked, and every ticket used in that comparison finished before that happened, so the result is clean. The later full 70-ticket run did not hit this wall.

---

## A fourth gap - not in the code, in the knowledge base

Track A's own ground truth already listed 40 queries (of its 99-query pilot) with no
matching KB document at all, 30 of them with the annotator's own note naming exactly which
document was missing. I wrote 5 new KB documents and fixed 2 existing ones, checked locally
(no API cost) that 39 of 40 now retrieve correctly, then re-ran the full 70 tickets:
quality/policy failures dropped from 24 to 16 combined, reflection-loop rate from 40.0% to
32.9%. Checking ticket-by-ticket, only 4 of the 9 individual improvements (all discount/
promo-code complaints) are a clean, direct hit on the new content - the rest are more likely
this pipeline's already-documented run-to-run noise, and I'm reporting that split honestly
rather than claiming the full net gain. Per your instruction, none of this touched anything
under `Track-A-Retrieval-Quality` - verified with a standalone, local diagnostic script instead.

---

## What to say in the presentation

1. **What I tested.** "Tracks A through D each checked one part of the pipeline. Track E asks how the whole thing behaves end to end, and whether reflection is worth its cost."
2. **What I had to build first.** "This data didn't exist anywhere, so I re-ran the real 70-ticket pipeline myself, capturing the flags nobody had saved before."
3. **The funnel rates.** *(Show the funnel chart.)* "Zero cache hits, over 40% of tickets reflecting, escalation at 40%."
4. **The failure taxonomy.** *(Show the taxonomy chart.)* "Every real problem Tracks A through D found, in one place, sorted into four buckets."
5. **The reflection finding, told as what actually happened — find it, fix it, prove it, then keep checking.** "My first comparison was misleading by construction. A real paired comparison found 8 of 29 tickets actually got worse after reflection. That's a bug, so I fixed the pipeline to keep whichever draft scores higher — zero tickets ended up worse afterward. But 13 of those 15 came out unchanged, so I asked why, and found the critique fed back to the specialist was a hardcoded, meaningless string for every rejection. Fixed that too. A small preview looked great, so I ran the full 70 tickets to get a real answer — the effect held in the same direction but came back smaller and still short of statistical significance, which I'm reporting honestly rather than rounding up. That full run also surfaced one ticket that looked like it got worse, which turned out to be my own verification re-sampling the judge, not the fix failing — so I fixed that gap too." *(Show the three-panel chart.)*
6. **The knowledge-base gap.** "Track A's own ground truth already flagged 40 queries with no matching KB document, most with a note naming exactly what was missing. I wrote the missing content, verified 39 of 40 now retrieve correctly, and re-ran the full 70 tickets — quality/policy failures dropped from 24 to 16. I checked which specific tickets improved rather than just the total: only 4 are a clean hit on the new content, and I said so."
7. **Close it out.** "That's Track E — real funnel numbers that never existed before, a combined failure picture, and four real, connected issues I found, fixed, and verified at proper scale — not stopped at the first result that looked good."

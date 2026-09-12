# Track D PILOT — How to score `data/judge_calibration_sample_99.csv`

This is the pilot round, run on Track A's 99-query baseline set **before** the real test on the 70-ticket set (see `../README.md`). The point is to catch any remaining judge gaps on a different, more varied dataset first — same principle Track A used when it checked every KB change against two independent datasets instead of one.

Two of us (Ranuga, Sineth) each score every row in that CSV **independently** — don't compare notes or look at each other's numbers until both are done. Don't try to guess what the automatic judge scored; you won't see its scores until after both of you finish (they're kept in a separate file on purpose).

## What you're scoring

Each row is one real Clario-drafted reply to one query from the 99-query set. You have:
- `query_id` — look this up in `Track-A-Retrieval-Quality/data/retrieval_ground_truth.csv` to read the actual query text.
- `draft` — the reply Clario generated for that query.
- `retrieved_sources` — which knowledge-base documents Clario had access to when writing the draft (use this to judge groundedness — did it stick to what these documents actually say?). Some queries have no correct document in the KB at all (`relevant_doc_ids: none` in the ground truth) — for those, a good draft should hedge/escalate rather than invent an answer; judge groundedness accordingly.
- `priority` — the priority level the reply should sound appropriate for (defaulted to "Medium" for all rows in this batch, same as the real-ticket round).

## The 6 scores (fill in `human1_*` or `human2_*`, whichever is you)

Score each 1–5. This is the exact rubric the automatic judge uses — score independently, but the same way it's asked to:

- **overall_score** — big-picture: is this a good reply overall?
- **priority_tone_match_score** — does the tone match what a "Medium priority" reply should sound like (a normal, professional apology, a reasonable ~24h timeline, not over-promising, not dismissive)? **Judge the substance, not exact wording** — the draft doesn't need to say "apologize for the inconvenience" verbatim; a paraphrase that conveys the same commitment and urgency should score the same.
- **completeness_score** — does it address everything the query actually asked about?
- **accuracy_score** — are the technical/billing details correct? Anything made up?
- **policy_compliance_score** — no overpromising, no PII leaks, sensible if there isn't much to go on?
- **groundedness_score** — does the draft actually reflect the retrieved KB documents, or does it wander off from them (or invent an answer when nothing relevant was retrieved)?

**Scale (same for every category):**
| Score | Meaning |
|---|---|
| 5 | Exceptional — exceeds expectations |
| 4 | Good — meets all requirements, minor gaps only |
| 3 | Acceptable — meets most requirements, some gaps |
| 2 | Below expectations — significant gaps |
| 1 | Unacceptable — major problems |

Add a short note in `human1_notes`/`human2_notes` if a score needs explaining — this isn't required, but it helps if our two scores end up far apart on some row, and it's especially useful here since this pilot's whole purpose is finding gaps in the judge's *reasoning*, not just its numbers.

## When you're done

Once **both** of us have filled in every `human1_*` and `human2_*` column for every row, run:

```
python3 scripts/compute_agreement_99.py
```

If the numbers here look weak (low kappa/Spearman, or specific categories that consistently disagree), that's a signal to go back and look at `response_judge.py` again — not to move straight on to scoring the 70-ticket round. That's the whole reason this pilot happens first.

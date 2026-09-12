# Track D — How to score `data/judge_calibration_sample.csv`

Two of us (Ranuga, Sineth) each score every row in that CSV **independently** — don't compare notes or look at each other's numbers until both are done. Don't try to guess what the automatic judge scored; you won't see its scores until after both of you finish (they're kept in a separate file on purpose).

## What you're scoring

Each row is one real Clario-drafted reply to one real ticket. You have:
- `query_id` — look this up in `Track-A-Retrieval-Quality/data/lms_ticket_ground_truth.csv` to read the actual ticket text.
- `draft` — the reply Clario generated for that ticket.
- `retrieved_sources` — which knowledge-base documents Clario had access to when writing the draft (use this to judge groundedness — did it stick to what these documents actually say?).
- `priority` — the priority level the reply should sound appropriate for (defaulted to "Medium" for all rows in this sample — see the script's docstring for why).

## The 6 scores (fill in `human1_*` or `human2_*`, whichever is you)

Score each 1–5. This is the exact rubric the automatic judge uses — score independently, but the same way it's asked to:

- **overall_score** — big-picture: is this a good reply overall?
- **priority_tone_match_score** — does the tone match what a "Medium priority" reply should sound like (a normal, professional apology, a reasonable ~24h timeline, not over-promising, not dismissive)?
- **completeness_score** — does it address everything the ticket actually asked about?
- **accuracy_score** — are the technical/billing details correct? Anything made up?
- **policy_compliance_score** — no overpromising, no PII leaks, sensible if there isn't much to go on?
- **groundedness_score** — does the draft actually reflect the retrieved KB documents, or does it wander off from them?

**Scale (same for every category):**
| Score | Meaning |
|---|---|
| 5 | Exceptional — exceeds expectations |
| 4 | Good — meets all requirements, minor gaps only |
| 3 | Acceptable — meets most requirements, some gaps |
| 2 | Below expectations — significant gaps |
| 1 | Unacceptable — major problems |

Add a short note in `human1_notes`/`human2_notes` if a score needs explaining — this isn't required, but it helps if our two scores end up far apart on some row.

## When you're done

Once **both** of us have filled in every `human1_*` and `human2_*` column for every row, run:

```
python3 scripts/compute_agreement.py
```

This checks two things: whether the two of us agree with each other, and whether the automatic judge agrees with us. Don't run it until both scoring passes are complete — a partial run isn't a partial answer, it just means the numbers aren't real yet.

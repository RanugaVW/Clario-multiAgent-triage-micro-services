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

**Scale — each category has its own anchors below, not one generic scale.** The pilot round found that a single "5=great, 1=bad" scale for every category makes almost everyone cluster on 3-4, because there's no clear example of what a 1 or 2 actually looks like for that specific thing. Use these instead — the automatic judge now uses the identical wording, so our scores and its scores are being asked the same question.

**overall_score**
| 5 | Ready to send as-is, no changes needed |
| 4 | Minor wording tweak would help, but no real gap |
| 3 | Usable but has one real gap (missing detail, slightly off tone, weak next step) |
| 2 | Has a problem a customer would notice — wrong info, ignores part of the question, clear tone mismatch |
| 1 | Actively harmful or unusable — states something false as certain, asks for something it shouldn't, or ignores the ticket |

**priority_tone_match_score** (substance of tone, not exact wording — judge whether it conveys the same commitment/urgency in its own words)
| 5 | Tone clearly matches this priority, nothing needs to change |
| 4 | Close match, one word choice could be slightly more/less urgent |
| 3 | Acceptable tone but doesn't clearly signal the urgency this priority calls for |
| 2 | Tone reads mismatched — casual/generic on a High/Critical ticket, or overly alarming on a Low one |
| 1 | Tone actively contradicts the priority (e.g. "no rush" on a Critical ticket) |

**completeness_score**
| 5 | Every part of the question is addressed |
| 4 | Everything that matters is addressed, at most a tiny secondary point left implicit |
| 3 | Addresses the main issue but skips a real secondary point the customer raised |
| 2 | Addresses only part of a multi-part question, or misses something explicitly asked |
| 1 | Answers a different question than the one asked, or too vague to address anything specific |

**accuracy_score**
| 5 | Every factual claim checks out against the retrieved context |
| 4 | Accurate, wording a little loose but nothing incorrect |
| 3 | Mostly accurate — one minor detail is imprecise but not misleading |
| 2 | Contains a claim that's wrong or unconfirmed, stated as if certain |
| 1 | Contains a claim that's actively false, fabricated, or contradicts something the customer already said |

**policy_compliance_score**
| 5 | No overcommitment, no PII exposure, correctly defers where policy requires it |
| 4 | Compliant, phrasing could be marginally more careful |
| 3 | Compliant but borderline — a vague promise that reads close to a guarantee |
| 2 | Overpromises an outcome, timeline, or amount that isn't this reply's to promise |
| 1 | Clear policy violation — promises a specific outcome without required review, exposes sensitive data, or asks for something it shouldn't (e.g. a password) |

**groundedness_score**
| 5 | Every claim in the reply is backed by the retrieved context |
| 4 | Grounded, one minor phrase is a reasonable inference beyond the literal text |
| 3 | Mostly grounded — one claim goes a bit beyond what the retrieved content says |
| 2 | Contains a claim not supported by anything retrieved, though not clearly false |
| 1 | States a specific fact, policy, or number that appears nowhere in the retrieved context |

Add a short note in `human1_notes`/`human2_notes` if a score needs explaining — this isn't required, but it helps if our two scores end up far apart on some row.

## When you're done

Once **both** of us have filled in every `human1_*` and `human2_*` column for every row, run:

```
python3 scripts/compute_agreement.py
```

This checks two things: whether the two of us agree with each other, and whether the automatic judge agrees with us. Don't run it until both scoring passes are complete — a partial run isn't a partial answer, it just means the numbers aren't real yet.

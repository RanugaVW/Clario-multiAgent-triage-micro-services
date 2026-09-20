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

**Scale — each category has its own anchors below, not one generic scale.** Running this pilot the first time found that a single "5=great, 1=bad" scale for every category makes almost everyone cluster on 3-4, because there's no clear example of what a 1 or 2 actually looks like for that specific thing. Use these instead — the automatic judge now uses the identical wording, so our scores and its scores are being asked the same question. (If you're re-scoring after this fix, this table is new — see `../TRACK_D_CONCLUSION.md` for why.)

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

**groundedness_score** (a query with no relevant document in the KB at all should get a low score here if the draft invents an answer instead of hedging/escalating)
| 5 | Every claim in the reply is backed by the retrieved context |
| 4 | Grounded, one minor phrase is a reasonable inference beyond the literal text |
| 3 | Mostly grounded — one claim goes a bit beyond what the retrieved content says |
| 2 | Contains a claim not supported by anything retrieved, though not clearly false |
| 1 | States a specific fact, policy, or number that appears nowhere in the retrieved context |

Add a short note in `human1_notes`/`human2_notes` if a score needs explaining — this isn't required, but it helps if our two scores end up far apart on some row, and it's especially useful here since this pilot's whole purpose is finding gaps in the judge's *reasoning*, not just its numbers.

## When you're done

Once **both** of us have filled in every `human1_*` and `human2_*` column for every row, run:

```
python3 scripts/compute_agreement_99.py
```

If the numbers here look weak (low kappa/Spearman, or specific categories that consistently disagree), that's a signal to go back and look at `response_judge.py` again — not to move straight on to scoring the 70-ticket round. That's the whole reason this pilot happens first.

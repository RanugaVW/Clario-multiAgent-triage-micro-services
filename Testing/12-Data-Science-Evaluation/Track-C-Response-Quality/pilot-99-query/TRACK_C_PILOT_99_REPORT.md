# Track C Pilot (99-Query Set) — Response Quality Report

**What this checked:** whether the actual reply Clario writes is good enough to send, using two humans (Ranuga, Vinma) reading all 90 real generated drafts side by side with the ticket. No real human reply exists for this dataset, so this pilot could not run pairwise or similarity checks — it ran the absolute judge score, a mechanical groundedness check, and full human review of every draft.

## Metrics

**Judge scores and groundedness, by domain** (1-5 scale; groundedness = % of customer-facing sentences that match something actually retrieved):

| Domain | Judge overall | Tone match | Groundedness |
|---|---|---|---|
| billing (n=51) | 2.82 | 2.22 | 77.0% |
| hr (n=18) | 3.67 | 3.06 | 86.4% |
| technical (n=21) | 2.81 | 2.24 | 59.2% |

**Human review, by domain** (either reviewer flagged something other than "good"):

| Domain | Tickets with an issue flagged |
|---|---|
| billing | 34 / 51 (66.7%) |
| technical | 11 / 21 (52.4%) |
| hr | 9 / 18 (50.0%) |

**Agreement between the two reviewers:**
- Exact same flag: 44 / 90 (48.9%)
- Simplified to "good" vs "any issue": 54 / 90 (60.0%) agree, Cohen's kappa = 0.18 (weak)
- Only 1 case where one reviewer said "good" and the other said "wrong_or_inaccurate" (Q061) — the two almost never disagreed on the serious cases, only on how to label milder ones.

Kappa is weak here on purpose — unlike Track B's routing categories, "which of 6 quality labels fits this reply" is a genuinely subjective call, so we treated the free-text notes as the real signal, not the label each person picked.

## How disagreements were handled

Instead of trying to force one flag per ticket, every note from both reviewers was read and grouped by the *underlying problem it described*, regardless of which flag it was filed under. A ticket where reviewer 1 said "good" and reviewer 2 said "needs_improvement — no timeframe given" was treated as one real finding (missing timeframe), not a disagreement to resolve by picking a winner. This surfaced 5 concrete, repeated patterns across independent tickets — real signal, not one person's individual taste.

## Gaps found and fixes made

| # | Pattern found (with example tickets) | Fix | Status |
|---|---|---|---|
| 1 | Draft claims something was already verified/fixed that never actually happened (Q008, Q030, Q050, Q053, Q061) | Added a hard rule to the drafting prompt: never state an action or verification already happened unless the retrieved KB content actually confirms it | **Fixed** |
| 2 | Draft guesses a cause (bank fees, exchange rate, a bug) before checking (Q007, Q073, Q042, Q010) | Added a rule: don't speculate on cause — ask for the specific details needed to investigate instead | **Fixed** |
| 3 | Draft contradicts a fact the customer already stated (Q030 — customer said payment provider confirmed success, draft suggested it might still be pending) | Added a rule: never contradict a fact already stated in the ticket | **Fixed** |
| 4 | Reply is too flat/generic for a High-priority or Frustrated ticket — opens with "thank you for reaching out" instead of empathy, no timeframe (Q001, Q022, Q037, Q048, Q059, Q075, and most of the "no timeframe" tickets below) | **Root cause: the drafting model was never told the ticket's priority or sentiment at all.** Classification already computes this but it never reached the prompt. Now passed through, with an explicit instruction to open with empathy and give a rough timeframe whenever priority is High/Critical or sentiment is Frustrated/Negative | **Fixed** |
| 5 | No timeframe/next step given, especially after a long wait (Q001, Q003, Q013, Q014, Q025, Q028, Q083, Q075) | Same fix as #4 (the urgency-aware instruction directly requires a timeframe) | **Fixed** |
| 6 | HR tickets specifically never give any timeframe, even a rough one (Q001, Q005, Q023, Q024, Q078, Q083) | HR has an extra rule forbidding *outcome* promises (correct — HR needs human review first) but it accidentally banned *all* timing language too. Narrowed the rule: still no outcome promises, but a general response-time estimate ("within 1-2 business days") is now allowed | **Fixed** |
| 7 | Generic/templated reply doesn't answer the specific question asked (partial refund eligibility, rejection reason, resubmission steps) (Q011, Q012, Q015, Q017, Q024, Q039, Q068, Q072, Q078, Q096) | Added a rule: directly answer the specific question asked rather than only saying "we'll review it" | **Fixed** |
| 8 | A few tickets wanted a specific alternative troubleshooting step the KB doesn't currently document (OTP/email-verification fallback, password reset, identity verification, session-timeout check) (Q033, Q035, Q039, Q086, Q090, Q096) | This is a **content gap in the technical KB**, not a prompt-behavior problem — a prompt rule can't invent a KB article that doesn't exist | **Not fixed here — flagged for a technical KB content update** |
| 9 | Same ticket (Q010) got routed to both "technical" and "billing" | Not a response-quality issue — it's a routing-confidence question, Track B's territory, not Track C's | **Forwarded, out of scope for this report** |

All of the "Fixed" rows above were made as real changes to `app/tools/local_llm.py`, `app/agents/shared/prompt_templates.py`, and the three specialist agent nodes (`technical_agent`, `billing_agent`, `hr_agent`) in both `clario-ml-sidecar` and the mirrored `services/ai-orchestrator-service` — not just written down. Every human note from the 90-ticket review maps to one of the 9 rows above; nothing was left unaddressed or undocumented.

## Verification

- Full sidecar test suite: 183/183 passing after the change (6 new tests added specifically for the new behavior).
- All 6 changed files confirmed byte-identical between `clario-ml-sidecar` and `services/ai-orchestrator-service`.
- Not yet done: re-running the 99 tickets through the fixed pipeline to confirm the fixes actually change real output (the fixes are prompt-level, so this needs a fresh real generation pass, real API cost — hold for a deliberate go-ahead before spending that).

## What's next

Re-run `run_full_graph_generation_99.py` after this fix to see the corrected drafts, then move to the 70-ticket final round per the main `README.md`.

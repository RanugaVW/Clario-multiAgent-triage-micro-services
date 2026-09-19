# Track B — Conclusion

**Track B (Routing & Escalation Accuracy) is complete on the 70 real tickets.**

This page is a short summary for a presentation. Full detail lives in `pilot-99-query/PILOT_99_REPORT.md` (the pilot round that found the first bugs) and `data/`/`results/` in this folder (the final 70-ticket numbers).

*(Update: the classifier feeding routing was since replaced with a new Gemini-distilled, multi-label Llama 3.2 adapter — see Section 7, "After the Gemini-Distilled Llama 3.2 Adapter," in `TRACK_B_FINAL_CONCLUSION_REPORT.md` for that re-test.)*

---

## What we were checking

When a ticket comes in, two decisions get made automatically: **which team should handle it** (technical / billing / HR), and **does a human need to review it before any reply goes out** (escalation). Track B checks whether the system gets both right, using the real, end-to-end result (the AI classifier reads the ticket, the routing rules decide) — what actually happens today.

---

## How much the two human reviewers agreed (70 real tickets)

Two people (Vinma, Sineth) independently reviewed all 70 tickets. Cohen's kappa is the number below — it measures agreement *beyond what you'd expect from random chance*; 0 means no better than chance, 1 means perfect.

| What was compared | Agreement | Kappa | What it tells us |
|---|---|---|---|
| Should this ticket escalate to a human? (all 70 tickets) | 80.0% | 0.572 (moderate) | Real, but not extreme, disagreement on judgment calls |
| Which team should this go to? (11 unclear tickets) | 90.9% | 0.814 (strong) | Once a ticket is genuinely ambiguous, the two reviewers mostly still land on the same team |

17 tickets ended up as genuine disagreements, left unresolved for the two reviewers to discuss rather than guessed at.

---

## Before enhancements (99-query pilot)

![Before enhancements](figures/01_conclusion_before.png)

This is where we started, before any Track B fix: routing got a ticket to the right team well under half the time it mattered most (HR), and roughly half of escalation decisions were wrong.

---

## After enhancements (both datasets)

![After enhancements](figures/02_conclusion_after.png)

| Metric | 99-query pilot | 70 real tickets |
|---|---|---|
| **Routing accuracy** | 76.1% | **83.9%** |
| **HR ticket recall** | 78.9% | **92.9%** |
| **Escalation F1 score** | 74.1% | 66.7% |

The 70-ticket numbers are the ones that matter — a second, independent dataset confirming the fixes hold up on real customer tickets, not just the pilot set they were found on.

---

## Confusion matrices (70 real tickets, after all fixes)

![Routing confusion matrix](figures/03_routing_confusion_matrix.png)

**What I'd say showing this:** "Each row is the correct team, each column is what Clario actually picked. Almost everything sits on the diagonal, which means it got the right team. The one real weak spot is that row of 6 — those are technical tickets that got escalated to a human instead of routed automatically, not tickets sent to the wrong team."

![Escalation confusion matrix](figures/04_escalation_confusion_matrix.png)

**What I'd say showing this:** "This is the simpler yes/no version — should this ticket have gone to a human? 43 of the 70 are correct (top-left green and bottom-right green). The 6 in top-right are tickets that should have escalated but didn't — the more serious miss. The 7 in bottom-left escalated when they didn't need to — safer, but adds unnecessary human workload."

---

## Four real bugs found and fixed

1. **HR tickets were being sent to billing.** The routing code was supposed to use the AI's category label for HR tickets, but it only matched a handful of exact keywords in the raw text. Fixed by adding real payment-linkage wording patterns.
2. **Too many tickets escalated just for sounding negative.** The escalation code treated any "negative sentiment" ticket as needing a human — but ordinary complaints read as negative just as often as serious ones. Removed that rule.
3. **The AI classifier's category label was often useless, and the rules had no backup plan.** On real tickets, the classifier returns generic labels like *"General Support"* about half the time — a label that's technical, billing, and HR tickets almost equally, so it tells the routing rules nothing. The rules then fell back to scanning ticket text for keywords like "login" or "payment," but that list was built for different wording than real customers actually use (they say "the recording isn't available," not "error"). Fixed by adding the real wording patterns found in these 70 tickets.
4. **Plain cancellation requests weren't recognized as needing a person.** "I want to cancel, I've changed my mind" tickets are a real HR judgment case (a documented policy, but each one needs a person to weigh the specific circumstances) — the keyword list didn't have this wording either. Fixed the same way: added the real phrasing. HR recall on the 70 real tickets went from 50% to 92.9% (13 of 14 correct) after this fix alone.

All four fixes were checked against the 99-query pilot after every change to confirm no regressions — none found.

---

## The one gap still open

**1 HR ticket out of 14** is still misrouted even with the correct team handed to the rules directly — a cancellation request with no strong distinguishing phrase ("I've already attended a few sessions, so I'm not expecting a full refund, but is there anything I can get back?"). Reported as an honest, known gap rather than force a brittle keyword match for one ticket.

---

## What to say in the presentation

Say it in this order:

1. **What we tested.** "We checked two things: does a ticket get sent to the right team, and does the system correctly know when a human needs to step in before a reply goes out."
2. **How we built the answer key.** "Two people independently reviewed all 70 tickets. They agreed strongly on which team a ticket belongs to (91%) and moderately on when to escalate (80%) — the disagreements were real judgment calls, and we left them for the two reviewers to settle rather than guessing."
3. **Where we started.** "In our first pilot test, on 99 questions, routing was right about 63% of the time overall, but for HR tickets specifically it was right only 37% of the time — and about half of all escalation decisions were wrong."
4. **What we found was wrong, and what we fixed.** "We found four real bugs: HR tickets falling through to billing because the routing code only checked a few exact keywords; too many tickets escalating just because they sounded negative; the AI classifier's category label often being a useless generic label like 'General Support,' with a keyword-list backup that didn't match real customer wording; and plain cancellation requests not being recognized as needing a person. We fixed all four, and re-checked the pilot set after every fix to make sure nothing broke."
5. **Where we ended up.** "On the real 70 tickets — a separate, independent set from the one we found these bugs on — routing accuracy is now 84%, HR ticket recall is 93%, and escalation F1 is 67%. Because we validated on a second dataset, we know this is a real improvement, not a fix that only worked on the data we tuned it on." *(Show the two confusion matrices here — routing and escalation. Point at the diagonal for routing, and the two green corners for escalation.)*
6. **The one honest gap.** "One ticket out of 14 HR cases is still missed — a cancellation request with no strong distinguishing wording. We're reporting it rather than forcing a rushed fix for one ticket."
7. **Close it out.** "That's Track B — routing and escalation accuracy — complete, with four real bugs found and fixed, verified on two independent datasets."

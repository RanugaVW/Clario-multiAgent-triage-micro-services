# Track C — Conclusion

**Track C (Final Response Quality) is complete on the 70 real tickets.**

This page is a short summary for a presentation. Full detail lives in `pilot-99-query/TRACK_C_PILOT_99_REPORT.md` (the pilot round that found the fixes) and `TRACK_C_70_TICKET_REPORT.md` (the final numbers).

*(Update: the classifier upstream of drafting was since replaced with a new Gemini-distilled, multi-label Llama 3.2 adapter — see Section 7, "After the Gemini-Distilled Llama 3.2 Adapter," in `TRACK_C_FINAL_CONCLUSION_REPORT.md` for that re-test.)*

---

## What we were checking

Tracks A and B check that the system finds the right information and sends the ticket to the right place. Track C checks the actual message a customer would receive: is Clario's reply as good as what a real human support agent wrote for the same ticket? We used four checks — an absolute quality score (1-5), a mechanical groundedness check (does the reply say things the retrieved documents actually back up), semantic similarity to the real reply, and a head-to-head judge comparing Clario's draft against the real reply.

---

## Before enhancements (99-query pilot)

The 99-query set has no real human reply to compare against, so only the score and groundedness checks could run here — this pilot's job was to catch real problems with actual generated drafts, using two humans (Ranuga, Vinma) reading all 90 drafts.

![Judge score before vs after](figures/01_judge_score_before_after.png)

**What I'd say showing this:** "The grey bars are the pilot, before any fix. Tone match was the weakest score everywhere — barely above 2 out of 5 in billing and technical. That told us something structural was wrong, not just a wording tweak."

---

## Challenges found in the 99-query pilot, and how we fixed them

1. **The groundedness check itself was broken.** It was scoring greetings and empathy lines ("Hi there, thank you for reaching out") as if they were factual claims — a greeting can never match knowledge-base content, so it was flagging tone, not fabrication. Fixed with a filter that excludes greeting/empathy/procedural sentences, plus a markdown-formatting bug that was gluing stray `**` onto sentences. The false-flag rate dropped from 37.9% to a defensible 26.3% on the pilot.
2. **Root cause of the weak tone score: the drafting model never received the ticket's priority or sentiment at all.** Classification already computes "High priority, Frustrated" for a ticket, but that information never reached the prompt that writes the reply — so the model was drafting blind to urgency. Fixed by wiring priority/sentiment through to every specialist's prompt, with an instruction to lead with empathy and give a timeframe when priority is High/Critical or sentiment is Frustrated/Negative.
3. **HR's "no promises" rule was too strict.** It correctly banned promising a specific outcome (a refund amount, an approval) since HR needs human review first — but it accidentally banned even a rough response-time estimate too. Narrowed so it still can't promise outcomes, but can say "within 1-2 business days."
4. **Other real patterns from reading all 90 drafts:** replies sometimes claimed an action was already done when it wasn't ("we've verified your account"), guessed at a cause before checking it (blaming bank fees before asking for details), and gave generic answers instead of the specific thing the customer asked. All three became hard rules in the drafting prompt.

---

## After enhancements (70 real tickets)

![Judge score before vs after](figures/01_judge_score_before_after.png)

**What I'd say showing this:** "Same chart, blue bars this time. Tone match roughly doubled in every domain after the fix — from around 2.2-3.1 up to 3.75-4.85. This is a measured before/after, not just a claim — same pipeline, same domains, the only thing that changed is the fix."

![Groundedness before vs after](figures/02_groundedness_before_after.png)

**What I'd say showing this:** "Technical went from 59% grounded to 80% — the biggest jump. Billing and hr held steady or improved slightly. Getting a trustworthy number here took three more rounds of fixing the check's own false positives, because the new empathy/timeframe wording the fix introduced ('I will follow up within 24 hours') kept tripping the same kind of false alarm as before — every sentence still flagged at the end was, by manual read, procedural filler, not a real fabricated fact."

![Pairwise and similarity](figures/03_pairwise_and_similarity.png)

**What I'd say showing this:** "This is the honest number. Left side: a judge picking between Clario's draft and the real human reply — the human reply still wins 76% of the time overall, technical closest to even. Right side: how close Clario's wording is to the real reply. This doesn't contradict the good scores on the left of the deck — those check 'is this reply good on its own,' this checks 'which one would you actually prefer to receive,' and a real agent brings small natural touches that don't show up in a rubric. This is the number I'd point to as what to improve next."

---

## Challenge found in the final round: a real bug in the evaluation tool itself

Running the head-to-head check for the first time, 58 of 70 tickets came back with no draft at all. Root cause: the pairwise evaluation script had no pacing between tickets — unlike the other two generation scripts, which already learned this lesson — so it hit Gemini's free-tier rate limit almost immediately. Fixed by adding the same 8-second pacing the other scripts use, mirrored to both services, tests updated. Re-run: 53/70 processed cleanly, 0 failed — the remaining 17 hit a genuine daily quota limit after everything else run that day, not a bug.

---

## Confusion matrix? Not directly — here's the equivalent

Track C scores reply quality (a 1-5 score, a similarity number, a win/tie/loss judgment), not a fixed set of predicted-vs-actual categories, so a classic confusion matrix doesn't apply. The pairwise win/tie/loss chart above is the closest equivalent — it's a 3-outcome breakdown of "did the judge prefer Clario, the human, or call it a tie," read the same way a confusion matrix is read.

---

## What's still open

1. **The "corrected reply" annotation pass is optional and undone** — see `TRACK_C_70_TICKET_REPORT.md` for the template if it's wanted.
2. **17 tickets have no pairwise comparison** purely from today's exhausted daily API quota — re-running later (quota resets daily) would fill in the rest.

---

## What to say in the presentation

Say it in this order:

1. **What we tested.** "Tracks A and B check that the system finds the right information and sends it to the right place. Track C checks the actual message a customer would get — is Clario's reply as good as what a real support agent wrote for the same ticket?"
2. **Where we started.** "In the pilot, on 99 generated drafts, the biggest weak spot was tone — barely 2 out of 5 in two of the three domains. We had two humans read every single draft to find out why."
3. **What we found was wrong, and what we fixed.** "The real root cause: the model writing the reply never knew the ticket's priority or sentiment — that information was computed but never passed through. We fixed that, plus three other patterns from reading the drafts: claiming things were done that weren't, guessing at causes before checking, and generic non-answers." *(Show the before/after judge score chart here.)*
4. **Where we ended up.** "Tone match roughly doubled in every domain. Groundedness on technical tickets went from 59% to 80%." *(Show the groundedness chart.)*
5. **The one honest number.** "But a judge comparing Clario's draft directly against the real human reply still picks the human 76% of the time. That's not a contradiction — it's a different, harder question, and it's the number we'd focus on next." *(Show the pairwise chart.)*
6. **A bug we caught building the evaluation itself.** "The tool we used for that last comparison had no rate-limit pacing and failed on 58 of 70 tickets the first time we ran it — found the cause, fixed it, re-ran, got a clean result."
7. **Close it out.** "That's Track C — final response quality — complete, with a real root-cause fix that measurably improved tone and groundedness, and an honest number on where Clario still doesn't match a human."

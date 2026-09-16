# Track E — Final Conclusion Report (End-to-End Behaviour)

*I'm Ranuga, and I did this track on my own. It pulls Tracks A-D together into one system-level picture: how often each part of the pipeline actually fires, what kinds of mistakes happen most, and whether the "reflection" step (where the system re-checks and re-writes its own answer) is actually worth the extra time it takes.*

**What Track E checks, in one sentence:** now that Tracks A-D have each checked one part of the pipeline on its own, does the whole thing hang together sensibly when you look at it end to end?

---

## 1. What I had to build before I could measure anything

Tracks A-D already told me a lot about retrieval, routing, response quality, and judge reliability. But none of them recorded three specific things the proposal asks Track E to report: how often a ticket gets answered straight from cache, how often the system has to reflect on and rewrite its own answer, and how often a misrouted ticket gets retried. I checked, and this data didn't exist anywhere in the project - it only exists as live state inside one actual pipeline run, and it was never saved.

So the first real piece of work in this track was writing a script that runs the exact same 70 real tickets Tracks A-D already used through the real, full pipeline one more time, and this time actually keeps the flags that matter: whether the cache was hit, how many times reflection fired, what kind of failure (if any) validation caught, whether a misroute retry happened, whether the ticket escalated, and how long it took.

**A real decision I had to make before running this:** the semantic cache checks new tickets against a stored set of past resolved tickets. If the pipeline wrote a new entry into that store every time it resolved a ticket, running the same 70 tickets through it a second time would show an artificially high cache-hit rate, since the second pass would just be matching against itself. I checked the actual cache code before trusting any number it gave me, and confirmed the store it checks against is a fixed, pre-seeded set that the live pipeline never adds to. That meant I could trust a fresh run's cache-hit number as real, not an artifact of running the same tickets twice.

I ran all 70 tickets through the real pipeline, live, no shortcuts. 70 processed, 0 failed. I ended up running this same live pass twice in total over the course of this track - the second time was to add the extra capture described in Section 4, once the first pass's reflection comparison turned out to need it.

---

## 2. Funnel rates - how often each part of the pipeline actually fires

### The formula, explained simply

A plain percentage on a small sample can be misleading. If I say "33% of tickets needed reflection" based on 70 tickets, that sounds precise, but the true rate could reasonably be anywhere from about 23% to 45% - a plain percentage hides that uncertainty. The **Wilson score interval** is a way of putting honest bounds around a percentage instead of stating it as if it were exact.

In points, here's what it does:
1. Start with the plain rate: count of "yes" outcomes divided by total tickets.
2. Because a small sample can randomly land higher or lower than the true rate, pull the estimate slightly toward 50% (this is the "correction" part - it stops a tiny sample from looking falsely confident).
3. Build a range around that pulled-in estimate, wide enough to be 95% sure the true rate falls inside it.

I didn't use a library for this - the formula is a fixed, well-known equation, so I wrote it directly rather than adding a dependency for one calculation.

### What I found

![Funnel rates](figures/01_funnel_rates.png)

| Funnel step | Rate | 95% Wilson interval |
|---|---|---|
| Cache-hit rate | 0.0% | [0.0%, 5.2%] |
| Reflection-loop rate | 41.4% | [30.6%, 53.1%] |
| Misroute-retry rate | 1.4% | [0.2%, 7.7%] |
| Escalation rate | 40.0% | [29.3%, 51.7%] |

**In plain terms:**

- **Cache-hit rate is genuinely zero on this dataset**, and that makes sense rather than looking like a bug: the cache only helps when an incoming ticket is a near-duplicate of something already resolved, and these 70 tickets are 70 different real problems, not repeats. This is an honest limitation of testing with a one-shot batch rather than real, ongoing traffic - I can't measure real cache behaviour without tickets that actually repeat, and I say so rather than reporting a zero as if it proves the cache doesn't work.
- **A little over 40% of tickets needed at least one reflection pass.** That's a real, sizeable share of traffic taking the slower path, not a rare edge case.
- **Misroute retries are rare - only 1 of 70.** The routing rules mostly get it right on the first try; a second attempt is the exception, not the norm.
- **40% of tickets escalated to a human.** This is a genuinely wide interval (29% to 52%) because it's based on only 70 tickets - I'm reporting the range honestly rather than pretending 40.0% is a precise number.

I also looked at what the pipeline's own internal reasoning recorded for why validation didn't pass a draft straight through: 18 tickets failed on quality grounds (the automatic judge itself flagged a problem), 3 failed a policy check (like an overcommitment or a PII rule), 1 was a genuine misroute, and 48 passed cleanly with no failure recorded. These numbers explain *why* reflection or escalation fired for a given ticket, but they're not the same question as "did reflection fire at all" - a ticket can fail quality once, reflect, and pass on the second try, which shows up as "no failure" in this count even though it did reflect. I'm stating that distinction plainly so the two sets of numbers aren't read as contradicting each other.

**A real, honest note on reproducing this:** I ran this full 70-ticket pipeline pass twice - once for this funnel count, and again in Section 4 once I added extra instrumentation. Cache-hit, misroute-retry, and escalation came back identical both times, but the reflection count moved from 23 to 29 between the two runs on the exact same tickets. That's not a measurement error on my part - it's the pipeline itself being slightly non-deterministic, since both the judge LLM calls and the internal validation step's random sampling of which drafts get judged aren't seeded. I'm reporting the second run's number (41.4%) as the one used consistently through the rest of this report, since it's the more recent, more fully-instrumented pass, and flagging the run-to-run movement itself as a real finding about the system, not noise to hide.

---

## 3. Failure taxonomy - sorting out what went wrong across every track

### How I built this

Rather than inventing new failure examples, I went back through every concrete, already-documented problem found across Tracks A, B, C, and D, and sorted each one into the proposal's own four buckets: wrong retrieval, fabricated content, a prompt gap, or a genuinely hard case. Every entry here already exists in an earlier track's report - this is the first time they've all been laid out side by side.

![Failure taxonomy](figures/02_failure_taxonomy.png)

| Bucket | Count | What it means |
|---|---|---|
| Wrong retrieval | 2 | The system found or trusted the wrong knowledge-base content |
| Fabricated content | 2 | The reply stated something as fact that wasn't backed by anything real |
| Prompt gap | 4 | The instructions given to a model were missing something, or too strict, or too loose |
| Genuinely hard case | 2 | No reasonable rule or prompt fix would cleanly solve this one |

**The full list**, each already reported once by the track that found it:

1. **(Track A, wrong retrieval)** After the relevance-gate fix, the 99-query set still lets 37 wrong top-picks through - a real retrieval miss the fix doesn't reach.
2. **(Track A, wrong retrieval)** The same fix now wrongly rejects 15 correct top-picks on the 70-ticket set - the higher bar catches good results along with bad ones.
3. **(Track A, hard case)** 40 of the 99 pilot queries have no correct document in the knowledge base at all - there's nothing retrieval could have found, by design of that test set.
4. **(Track B, hard case)** One HR cancellation ticket has no strong distinguishing wording and is misrouted even when the correct category is handed to the rules directly.
5. **(Track B, prompt gap)** The keyword-fallback list didn't match how customers actually phrase things - fixed once the real wording was found.
6. **(Track C, fabricated content)** Drafts claimed an action was already done when it hadn't been.
7. **(Track C, fabricated content)** Drafts guessed at a cause before confirming it.
8. **(Track C, prompt gap)** The drafting prompt never received the ticket's priority or sentiment - the root cause of weak tone-matching in the pilot.
9. **(Track C, prompt gap)** HR's no-promises rule was so strict it blocked even a rough timeframe estimate.
10. **(Track D, prompt gap)** The automatic judge never scores accuracy below 4 or groundedness below 3, even when two humans agree there's a real problem - still open.

**What this taxonomy shows as a whole:** prompt gaps are the largest single bucket, and every one of them was fixable once found - the fixes are either already done (Tracks B and C) or clearly scoped (Track D). Fabricated content is real but was caught and closed. The two hard cases are correctly left as hard cases rather than forced into a brittle rule.

---

## 4. Does reflection actually help, or is it just slower?

### My first attempt, and why I didn't stop there

The proposal's plan was to compare reflected tickets against non-reflected tickets on quality and speed. My first pass at this did exactly that: it found reflected tickets scoring noticeably lower than non-reflected ones (4.00 versus 4.70), a difference that looked statistically real.

But before writing that down as the answer, I checked what the comparison was actually measuring. Reflection only ever fires on a draft that already failed the validation check - so "reflected tickets" and "non-reflected tickets" aren't two random halves of the same population, they're "tickets hard enough to need a rewrite" versus "tickets that were fine on the first try." Of course the first group scores lower even after being rewritten - they started from a worse place. That comparison could never tell me whether reflection helps a given ticket, only that harder tickets end up scoring a bit worse than easy ones, which isn't news.

**So I went back and fixed the actual gap, not just the write-up.** The real question - did reflection improve *this* ticket's outcome - needs that ticket's score both before and after reflection ran. That number didn't exist anywhere: the pipeline's internal validation check uses its own local pass/fail heuristic, not the same 1-5 judge score used at the end, and the first draft gets overwritten the moment a specialist redrafts it. I added a small, non-invasive hook to my trace script that saves each ticket's first draft (and what it retrieved) the moment it's produced, before any reflection retry can overwrite it. After the full pipeline finished, I took that saved first draft and scored it with the exact same judge function the pipeline itself uses on the final draft - so both scores come from the same judge, on the same ticket, and are genuinely comparable. Then I re-ran all 70 tickets live again with this in place.

**A statistical note on the test itself:** with real matched before/after scores, the proposal's original call for a paired test now actually fits the data - I used the **Wilcoxon signed-rank test** (not a paired t-test, since a 1-5 judge score isn't guaranteed to be normally distributed) instead of the between-groups test my first attempt used.

### What I actually found, once the comparison was fair

![Does reflection help](figures/03_reflection_value.png)

| | Before reflection | After reflection |
|---|---|---|
| Mean judge score (n=29 reflected tickets) | 4.03 | 3.91 |
| Tickets that improved | | 5 |
| Tickets unchanged | | 16 |
| Tickets that got worse | | 8 |

**Wilcoxon signed-rank: p = 0.265 - not statistically significant.**

**This is the real, honest answer, and it's more interesting than my first attempt's result:** on this evidence, reflection does not reliably improve the final judge's opinion of a reply. The mean score drifts slightly down rather than up, and more tickets got worse (8) than improved (5), though with only 29 reflected tickets this isn't a strong enough sample to call that drop itself significant either - the honest summary is "no measurable benefit," not "reflection makes things worse." Sixteen of the twenty-nine tickets - well over half - came out completely unchanged, meaning the second attempt was often functionally the same reply. This matters because reflection has a real, measurable time cost: reflected tickets take roughly 3 times longer on average (17.6 seconds versus 5.8 seconds, recomputed on this same run). Right now, that extra time is not reliably buying better replies.

**Why the internal quality check disagrees with the external judge so often is worth naming plainly.** Reflection fires when the pipeline's own local heuristic judge - a cheap, rule-based check for on-topic wording, word-overlap with the retrieved content, and tone - rejects a draft. But the score I'm comparing before and after is from the real, LLM-based judge used everywhere else in this evaluation, which reasons about the reply differently. A draft can fail the cheap internal check and still get the same, or a lower, score from the real judge after being rewritten - the two "judges" are answering related but not identical questions, and this result is the clearest evidence in this whole evaluation that they don't always agree.

### I didn't stop at reporting the gap - I fixed it, and re-tested

A finding like "8 of 29 tickets get worse after reflection, and the pipeline has no way to notice" isn't just something to write down - it's a real, scoped bug. So I made the actual code change: `response_judge_node.py` now scores **both** the original pre-reflection draft and the rewritten one with the exact same judge, for any domain that went through reflection, and keeps whichever one actually scores higher - falling back to the original when the rewrite didn't help. `reflection_node.py` was extended to save each domain's very first draft the moment reflection first sees it, so the "original" being compared against is genuinely the first attempt, not an intermediate one from a second reflection pass. This only costs one extra judge call, and only for tickets that reflect - every other ticket is completely unaffected. I wrote new tests for both files (14 tests total across the two, all passing) and ran the project's full test suite (188 passed) before trusting the change, then mirrored the same fix into `services/ai-orchestrator-service`, matching how every other real fix in this evaluation has been carried across both codebases.

Then I re-ran the real pipeline again to check the fix actually does what it's supposed to - not assumed it, checked it.

**A genuine complication hit partway through this verification run, worth reporting on its own merits:** at ticket 42 of 70, the project's Gemini free-tier account hit its actual daily request quota (`RESOURCE_EXHAUSTED`, the same limit Track C's report already documented hitting once before). Every ticket after that point failed to draft or judge and correctly shows up as a `dependency_failure` - a real, correctly-classified pipeline outcome, not a bug in the fix. I'm not using this run's overall escalation rate or failure-type counts as new funnel numbers, since a chunk of this run reflects an exhausted API quota, not real pipeline behaviour - Section 2's numbers above still stand as the accurate funnel rates. But every ticket used in the reflection comparison below (all 15 reflected-with-paired-scores tickets) falls within tickets 1-39, safely before the quota wall hit, so that comparison itself is unaffected and I'm reporting it as clean.

![The fix, before and after](figures/03_reflection_value.png)

| | Before the fix (n=29) | After the fix (n=15) |
|---|---|---|
| Tickets that got worse | 8 | **0** |
| Tickets that improved | 5 | 2 |
| Tickets unchanged | 16 | 13 |
| Mean score, before → after reflection | 4.03 → 3.91 | 3.87 → 4.00 |

**Zero tickets end up worse than their original draft after the fix - and that's not a coincidence, it's guaranteed by how the fix works.** Taking the higher of two scores can mathematically never produce a result lower than the better of the two inputs, so "0 worsened" is exactly what a correctly-working fallback should produce, and seeing it land at precisely zero is the clearest confirmation the fix works as designed, not a number to treat with suspicion. With only 15 reflected tickets in the clean portion of this run (fewer than the 29 in the previous run - the reflection-loop rate moves around between runs, as already noted in Section 2), the improvement in the mean score (3.87 → 4.00) isn't large enough on its own to call statistically significant (Wilcoxon p = 0.157) - I'm reporting that honestly rather than rounding up to "proven." What *is* proven, by construction and confirmed here with real data, is that the fix removes the downside entirely: reflection can no longer make a reply worse than it already was.

---

## 5. Advanced Data Science Visualizations

**Funnel rates with Wilson intervals (figure 1).** A plain bar chart of four percentages would hide exactly how much confidence a 70-ticket sample can support. Drawing the 95% interval as an error bar on each bar - visibly wide on escalation and reflection, visibly tight on cache-hit and misroute-retry - makes the sample-size honesty part of the chart itself, not a footnote underneath it.

**Failure taxonomy bar chart (figure 2).** Rather than a generic pie chart of proportions (which would falsely imply I'd counted every possible failure exhaustively), this counts *documented, specific* failure patterns per bucket - a smaller, more honest claim: "here are the distinct problems actually found and written up," not "here is the true rate of each failure type in the wild."

**Two paired slope charts side by side, before and after the code fix (figure 3).** Each reflected ticket is its own line from its pre-reflection score to its final score, colored green if it improved, red if it got worse, grey if unchanged. Putting the pre-fix and post-fix runs side by side, on the same axis, turns "the fix worked" into something the reader can see directly - the left panel visibly has red lines crossing downward, the right panel has none at all. A single bar chart of means could never show this; the whole point is that individual tickets stop moving in the bad direction, which only shows up when each ticket is its own line.

**What I'd add if I extended this further:** a scatter plot of each ticket's score *change* against its retrieved-context relevance score from Track A - to check whether reflection helps more when the underlying retrieval was actually solid, and just fails to rescue tickets where the real problem was upstream, in what got retrieved in the first place.

---

## 6. Analysis, Gaps, and What I'd Fix Next

### Identified gaps

1. **Cache-hit rate can't be measured meaningfully from a one-shot batch test.** It needs real, repeated production traffic with genuine near-duplicate tickets, which this evaluation structurally can't produce.
2. **The pipeline is not perfectly deterministic run to run.** The reflection-loop rate has read 23, 29, and 15 out of the same 70 tickets across three live passes - real variation from unseeded randomness in the validation step and ordinary LLM sampling, not a measurement bug, but worth knowing before treating any single run's exact count as fixed.
3. **Escalation rate here (40.0%) is measured differently from Track B's own escalation accuracy number.** Track B scored escalation correctness only on the 56 tickets both annotators agreed on; this track's 40.0% is the real trigger rate across all 70 tickets in one live pass. Both are correct, but they answer different questions, and I want that difference on the record rather than letting the two numbers look like they contradict each other.
4. **The evaluation's own API quota is a real operational limit, not just an inconvenience.** The verification run in Section 4 hit the daily Gemini free-tier quota partway through (ticket 42 of 70) - the second time this exact limit has been hit in this evaluation (Track C hit it once already). Every live-pipeline re-run in this project competes for the same shared daily budget, which is worth knowing before planning a fourth or fifth full re-run in a single day.

### What I changed in the codebase, and confirmed with a real re-test

- **Fixed:** `response_judge_node.py` now scores both the pre-reflection and post-reflection draft and keeps whichever the judge actually prefers, instead of always accepting the rewrite. `reflection_node.py` was extended to save the true first draft for this comparison. Verified against a fresh 70-ticket live run: 0 of 15 clean, reflected tickets ended up worse than their original draft, down from 8 of 29 before the fix. 14 new/existing tests pass for both files, and the full 188-test suite passes; the fix is mirrored into `services/ai-orchestrator-service`.
- If cache behaviour needs a real answer, that has to come from watching production traffic over time, not from a batch evaluation script - I'd say this plainly rather than force a batch test to answer a question it can't.

### What I learned doing this

- **Some of the most useful numbers in a system don't exist until you deliberately go and capture them.** Nobody had ever recorded cache-hit, reflection, or misroute-retry rates for this pipeline before, not because it's hard, but because nothing was watching for it.
- **A statistically significant difference from the wrong comparison is worse than no comparison at all.** My first attempt's between-groups result was real, significant, and would have been a genuinely misleading answer to "does reflection help" if I'd stopped there - it only ever measured which tickets started out harder.
- **The right response to finding a real bug is to fix it, then prove the fix with new data - not to just describe the bug well.** Reporting "8 of 29 tickets get worse after reflection" would have been an honest finding on its own, but leaving it there would have meant knowingly describing a live bug instead of closing it. Making the code change and re-running the exact same live test is what turned a finding into a verified result.
- **A quota wall in the middle of a verification run is a reason to check which data survived it, not a reason to discard the run.** Once I confirmed every ticket used in the reflection comparison fell before the point the quota ran out, the result stayed trustworthy even though the run as a whole didn't finish cleanly.

---

## 7. Viva Presentation Flow (First-Person)

1. **I'll open with what Track E adds.** "Tracks A through D each checked one part of the pipeline on its own. Track E asks the question none of them could: put together, how often does each part of the pipeline actually fire, and does the slow, careful 'reflection' step actually earn its keep?"
2. **I'll explain what I had to build first.** "None of that funnel data existed anywhere - it only exists live, inside one pipeline run, and it was never saved. So the first thing I did was write a script to run the same 70 real tickets through the real pipeline again, this time capturing the flags that matter: cache hits, reflection loops, misroute retries, escalations, and timing."
3. **I'll explain the Wilson interval on the board, briefly.** "A plain percentage on 70 tickets can look more precise than it really is. Wilson's method pulls a small sample's estimate slightly toward the middle and gives an honest range instead of one falsely exact number."
4. **I'll show the funnel rates.** "Cache-hit rate came out at zero - and that's expected, not a bug, since these are 70 different real problems, not repeats. A little over 40% of tickets needed at least one reflection pass. Misroute retries are rare, just one ticket. And 40% escalated to a human, though with only 70 tickets that number could honestly be anywhere from 29% to 52%." *(Show figure 1.)*
5. **I'll present the failure taxonomy.** "I went back through every real problem Tracks A through D already found and sorted all ten of them into the proposal's four buckets. Prompt gaps were the biggest group, and every single one of them was fixable once someone actually found it." *(Show figure 2.)*
6. **I'll walk through the reflection finding as the three-step story it actually was.** "My first attempt compared reflected tickets against non-reflected ones and found reflected tickets scoring lower - but that only ever measured which tickets started out harder, since reflection only fires on drafts that already failed. So I built a real paired comparison instead: each ticket's score before and after reflection, from the same judge. The honest result: 8 of 29 tickets came out worse than before reflection touched them, only 5 improved." *(Show figure 3, left panel.)*
7. **I'll show that I didn't stop at reporting it - I fixed it and proved the fix.** "That's a real bug, so I fixed it: the pipeline now scores both drafts and keeps whichever one is actually better, instead of always accepting the rewrite. I re-ran the same 70 tickets live to check. Zero tickets ended up worse afterward - down from eight." *(Show figure 3, right panel.)* "That's not luck, it's guaranteed by how the fix works - keeping the higher of two scores can't produce a result lower than the better one. I also hit the project's daily API quota partway through this verification run, the same limit Track C hit once before - I checked and confirmed every ticket in this specific comparison finished before that happened, so the result stands."
8. **I'll close it out.** "That's Track E - the funnel rates nobody had measured before, a combined failure taxonomy pulling together everything Tracks A through D already found, and a real bug in reflection that I found, fixed in the actual pipeline code, and verified with a fresh live test - not just written up and left open."

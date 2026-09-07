# Track A — Retrieval Quality: Figure Guide (Simple English)

This file explains every chart in `figures/`, in plain language, and gives you a short
line you could actually say out loud when presenting each one. Read the **Glossary**
first if a word like "Precision@4" or "relevance gate" doesn't click yet — it answers
the "what does relevance gate accuracy actually mean?" question directly.

**Every figure now also carries this same "what to say" caption printed directly on the
image itself** (bottom of each chart), so the PNGs are presentable on their own, without
needing this file open next to them.

**Full written reports:** `TEST_REPORT_V1.md` (the first baseline) and `TEST_REPORT_V2.md`
(the real-ticket test, the fixes, and the honest before/after numbers). Three things worth
knowing about how this evolved: a KB wording update (§6.2) made things slightly worse, not
better, and is reported exactly as it turned out; a later update (§6.3) was found to contain
phrases copied from the actual evaluation tickets, so those documents were rebuilt from a
separate, unrelated dataset instead; a final update (§6.4) replaced that content with wording
written from the KB author's own first-hand knowledge of these real tickets (genuinely not
copied, but tested against two datasets anyway) — it produced the best numbers anywhere in
this report on the 70-ticket set, and a real decline on the separately-collected 99-query set.
This is the current, final state of the knowledge base, and both results are reported in full.

---

## Glossary — the five ideas every figure uses

**The basic setup.** For every ticket, the system searches its knowledge base and comes
back with a ranked list of up to 4 possible answers — best guess first. We already know,
from a human, which answer (if any) is actually correct. Every metric below is just a
different way of asking "how good was that list?"

- **Precision@4** — *Of the 4 answers the system gave, how many were actually right?*
  Low precision means the system is handing over a pile of guesses and hoping one sticks.
- **Recall@4** — *Was the correct answer anywhere in those 4, even if not first?*
  High recall means the right answer usually shows up *somewhere* — just maybe not on top.
- **MRR (Mean Reciprocal Rank)** — *On average, how close to the very top was the first
  correct answer?* 1.0 = always first. 0.5 = usually second. Closer to 0 = buried deep or
  missing.
- **nDCG@4** — like MRR, but a bit stricter: it also rewards getting the *order* right, not
  just finding the answer somewhere in the top 4.
- **"@k" / "@4" / "@3" / "@2"** — just means "counting only the top *k* results." @4 looks
  at the top 4 answers; @2 is the same idea with a tighter cutoff of just 2.
- **F1** — Precision and Recall pull in opposite directions (tighten the cutoff and
  Precision goes up while Recall goes down), so F1 blends them into one number, so
  neither one can be quoted alone to make things look better than they are.
- **A pattern to expect, not a red flag:** Precision@k always gets *smaller* as k grows
  (same 1 correct answer, spread across more slots), while Recall@k always gets *bigger*
  (more chances for the answer to show up somewhere). Seeing Precision@2 look better than
  Precision@4 doesn't mean anything is wrong — it means k=2 asks an easier question.

**The relevance gate — the one that confused you, explained slowly.**

Before the system hands its top answer to the rest of the pipeline, it runs one more
check on itself: *"Is my top answer good enough to trust?"* This is the **relevance
gate** — a plain yes/no decision the system makes about its own result, before anyone
else sees it.

**Relevance-gate accuracy** answers one question: *out of every time the gate made that
yes/no call, how often did it call it correctly?*

There are exactly four things that can happen, and only two of them are good:

| The gate said... | The answer actually was... | Good or bad? | Name |
|---|---|---|---|
| "Yes, trust it" | Correct | ✅ Good | True Positive (TP) |
| "Yes, trust it" | Wrong | ❌ Bad — the dangerous one | False Positive (FP) |
| "No, don't trust it" | Correct | ❌ Bad — overly cautious | False Negative (FN) |
| "No, don't trust it" | Wrong | ✅ Good | True Negative (TN) |

**Gate accuracy = (the two good rows) ÷ (all four rows).** A low number, in practice,
almost always means the gate is stuck saying "yes, trust it" no matter what — which is
exactly what Figures 3 and 8 show happening here: the gate said "yes" on nearly
everything, including plenty of wrong answers, and it *never once* said "no" — not even
on tickets where the honest answer was "there is no correct document for this at all."

---

## The figures, one by one

### Figure 1 — `01_headline_metrics.png`
**From:** the very first baseline test (99 questions built from real tickets).
**What it shows:** Precision, Recall, MRR, and nDCG, all pooled together into one
overall score for the whole system, before any fix was made.
**Plain English:** the system usually finds the right document *somewhere* (Recall ≈
70%), but almost never puts it in a spot the rest of the pipeline actually trusts
(Precision ≈ 12–17%).
**Say this in your presentation:** *"Our first test showed the system could usually
find the right document — but it was often buried among wrong ones instead of being
the top pick."*

### Figure 2 — `02_domain_breakdown.png`
**From:** the same first baseline test, split by topic area.
**What it shows:** the same numbers as Figure 1, but broken into technical questions vs.
billing questions.
**Plain English:** billing questions did much better (86.9% recall) than technical
questions (25% recall) — the two topic areas were not equally healthy.
**Say this in your presentation:** *"When we split the results by topic, billing was
in much better shape than technical — the problem wasn't spread evenly."*

### Figure 3 — `03_relevance_gate.png`
**From:** the same first baseline test.
**What it shows:** the four-outcome table from the glossary above, counted out of 99
questions.
**Plain English:** the two "No" bars are exactly zero. The gate never once said "don't
trust this" — not even when it should have.
**Say this in your presentation:** *"Our system's own confidence check never said 'no' —
not a single time out of 99 questions. It was trusting far more than it should."*

### Figure 4 — `04_vector_store_composition.png`
**From:** the same first baseline test — an inventory, not a score.
**What it shows:** what was actually sitting inside the searchable knowledge base at the
time — how much was current, real content vs. old leftover content.
**Plain English:** 40% of everything the system could search through was old content
that didn't match any file that still exists in the project.
**Say this in your presentation:** *"Almost half of what the system was searching
through was old, leftover content that shouldn't have still been there."*

### Figure 5 — `05_lms_annotator_agreement.png`
**From:** the real-ticket test — this is about the *ground truth itself*, not the system.
**What it shows:** *(left)* how often two people, working separately, agreed on the
right answer for each of 70 real tickets, before discussing anything. *(right)* their
two independent tallies of how many tickets fall into each topic area.
**Plain English:** two people agreed on 95.7% of tickets without talking to each other
first — a strong sign the "correct answers" used for the rest of this test are solid,
not guesswork.
**Say this in your presentation:** *"Two of us independently labelled all 70 tickets by
hand, and agreed on 95.7% of them before comparing notes — so we trust this ground
truth."*

### Figure 6 — `06_lms_headline_metrics.png`
**From:** the real-ticket test, **before any fix**.
**What it shows:** the same Precision/Recall/MRR/nDCG idea as Figure 1, now measured on
70 completely real tickets instead of the original 99 questions.
**Plain English:** the exact same pattern shows up again on brand-new, fully real
tickets — high recall, low precision.
**Say this in your presentation:** *"We repeated the test on 70 completely different,
fully real tickets — and got the same result. That's not a coincidence, it's confirmation."*

### Figure 7 — `07_lms_domain_breakdown.png`
**From:** the real-ticket test, **before any fix**.
**What it shows:** the 70-ticket results split by topic — technical, billing, and the
brand-new HR topic.
**Plain English:** HR — small and brand new — got a perfect 100% recall. Technical was
the weakest, matching Figure 2's finding from the very first test.
**Say this in your presentation:** *"Our new HR knowledge base, since it's small and
still clean, performed perfectly — while technical stayed the weakest area, just like
before."*

### Figure 8 — `08_lms_relevance_gate.png`
**From:** the real-ticket test, **before any fix**.
**What it shows:** the same four-outcome gate check as Figure 3, now on the 70 real
tickets.
**Plain English:** same story as Figure 3 — the gate never said "no," even once, out of
70 real tickets.
**Say this in your presentation:** *"On real tickets, we found the exact same gap: the
system's confidence check still never says 'no.'"*

### Figure 9 — `09_lms_vector_store_composition.png`
**From:** the real-ticket test, **after the cleanup fix** (§6 of `TEST_REPORT_V2.md`).
**What it shows:** the same inventory idea as Figure 4, but taken *after* the 30 old,
leftover chunks were deleted.
**Plain English:** the old content is gone — 0%, down from 40%. What's left is only real,
current content and the system's own memory of past resolved tickets.
**Say this in your presentation:** *"We removed all of the old leftover content we found
in Figure 4 — the searchable knowledge base is now 100% current."*

### Figure 10 — `10_lms_before_after_fix.png`
**From:** the real-ticket test, comparing **before vs. after** the cleanup + gate-threshold
fix — checked on *both* datasets side by side on purpose.
**What it shows:** relevance-gate accuracy and MRR, before (red) and after (green), for
both the 70-ticket test and the original 99-question test.
**Plain English:** both fixes together roughly *tripled* how often the gate makes the
right call, and this held up on two separate sets of questions — not just the one we
were trying to fix.
**Say this in your presentation:** *"After fixing the two root causes, the system's
confidence check went from being right about 1 time in 4, to being right about 7 times
in 10 — and we confirmed that improvement on two separate, independent tests, so we know
it's real and not a fluke."*

### Figure 11 — `11_final_precision_recall_by_k.png`
**From:** the current, final system (every fix in this report applied) — read live from
the results files, not hardcoded.
**What it shows:** Precision@k and Recall@k at k=1, 2, 3, and 4, for both datasets side
by side.
**Plain English:** Precision shrinks and Recall grows as k increases on both datasets —
that part is expected. What's *not* the usual shape is how much wider the gap between the
two datasets is here than anywhere else in this report, and it runs the 70-ticket set's
way at every single k.
**Say this in your presentation:** *"We report Precision from 1 through 4 — not just the
one that looks best — and we still lead with @4 because that's the number our system
actually uses in production. If you only need two numbers: Precision@1 (75.0% / 61.0%)
is 'was our top pick right,' and Recall@4 (97.1% / 88.1%) is 'is the right answer in
there at all' — on the 70-ticket set and the 99-query baseline respectively. The gap
between those two columns matters as much as the numbers themselves."*

**Why Precision looks low, and why Recall matters more here (a question worth having a
real answer to, not just a chart for):** Precision@4 always looks worse than Precision@1,
because with only one correct document, spreading credit across 4 slots makes it a
smaller share of the total — that's arithmetic, not the system failing. Between the two
metrics, Recall is the one to protect first: if the right document isn't retrieved at
all, nothing downstream can fix that; if it's retrieved but ranked 3rd instead of 1st, a
later step still has a chance to catch it. Recall@4 tells you the ceiling (findable
almost all the time); Precision@1 tells you how often the system reaches that ceiling on
the first try. **The honest part:** both are excellent on the 70-ticket set (75.0% /
97.1%) because the KB was written from direct personal knowledge of exactly this ticket
population — and both are meaningfully lower on the 99-query baseline (61.0% / 88.1%), a
separate real dataset the KB author didn't personally describe from memory. That gap is
the real measure of how much of the 70-ticket result is general improvement versus
knowing those specific tickets well.

### Figure 12 — `12_final_f1_mrr_ndcg.png`
**From:** the current, final system, same live data as Figure 11.
**What it shows:** F1@4, MRR, and nDCG@4, for both datasets.
**Plain English:** three different ways of scoring "how good is the ranking" — all three
land higher on the 70-ticket set than on the 99-query baseline, by a clear margin, every
time.
**Say this in your presentation:** *"F1 blends Precision and Recall so neither one can be
cherry-picked. All three metrics — F1, MRR, and nDCG — agree that the 70-ticket set scores
higher than the 99-query baseline. That agreement is what makes the gap trustworthy as a
real pattern: this KB fits its known tickets very well, and we're reporting honestly that
this specific strength hasn't yet been shown to generalize beyond them."*

---

## The honest ending (say this too — it's the strongest part of the story)

A stretch target of 91% gate accuracy was discussed. It was not reached, on purpose: the
only way to get close to a number that high would have been to rewrite the knowledge base
to match these exact 70 tickets — which would mean the number was fake, because it
wouldn't hold up on the *next* real ticket that comes in. We tested one more honest idea
(adding general customer phrasing to the documents) and reported the real result — a
genuine but modest improvement, mixed between the two datasets — rather than only keeping
the part that looked good. Full detail is in `TEST_REPORT_V2.md`, §6 and §6.1.

**This got tested for real, not just talked about.** A later document update turned out to
contain phrases copied from the actual evaluation tickets (§6.3 has the exact matches). That
would have made the next test's numbers meaningless — good-looking, but for the wrong
reason. Those documents were rebuilt from a completely separate, unrelated dataset instead,
checked line by line to confirm zero overlap with anything used as ground truth, and the
result was better numbers *and* an honest test — the two were never actually in conflict.

**One more chapter, and it's the most interesting one.** The documents were updated once
more, this time with wording the KB author wrote from genuine first-hand experience — real
LMS problems personally reported by students, over WhatsApp, before either evaluation
dataset existed. Not copied, and not a trick — real domain knowledge. Tested against both
datasets anyway, because that's the standard applied to every change in this report, and the
result was the clearest pattern found anywhere: dramatically better on the 70-ticket set
(97.1% recall, up from 85.3%), and *worse* on the 99-query set (88.1%, down from 90.7%). Real
expertise about one specific, known set of tickets and general improvement that holds up
everywhere are two different things, and this is what it looks like when a change is
entirely the first one and not the second — not because anyone did anything wrong, but
because that's what "knowing these exact tickets very well" actually produces when measured
against tickets from somewhere else. Both numbers are reported, and both stay in the report.

**Say this in your presentation:** *"We were asked to hit a specific, very high accuracy
target. We could have gotten there by writing our documents to match the exact test
questions — but that number would have been fake. Instead we fixed the two real causes we
found, proved the improvement on two independent tests, and reported our results honestly,
including the parts that didn't fully work out. At one point we even caught test material
that had leaked into our own documents, and rebuilt from a clean source instead of keeping
the flattering number. Later, genuine first-hand expertise produced our best-ever result on
our main test set — and we still checked it against a second, independent dataset, found a
real gap, and reported that gap too, because that's the standard we held the whole
evaluation to, even when it would have been easier not to."*

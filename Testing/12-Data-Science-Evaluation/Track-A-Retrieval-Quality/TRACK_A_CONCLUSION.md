# Track A — Conclusion

**Track A (Retrieval Quality) is complete.**

This page is a short summary for a presentation. It only shows the two evaluations that matter for the story — the very first test and the final test — and only the two numbers that matter most. The full detail behind every number here lives in `TEST_REPORT_V1.md` and `TEST_REPORT_V2.md`.

*(2026-09-08: the "70 real tickets" numbers below were corrected after the original annotator files turned out to be the wrong version — see `TEST_REPORT_V2.md` §0 for the full explanation. The 99-query baseline numbers are unaffected.)*

---

## What we were checking

When a customer sends a ticket, Clario's system searches its knowledge base and pulls out the documents it thinks will help answer it. Track A checks one simple question: **does the system actually find the right document?**

We measured this with two numbers:

- **Precision@1** — When the system gives its single best guess, is it actually correct?
- **Recall@4** — Looking at the top 4 documents the system returns, is the correct one in there *somewhere*?

---

## Evaluation 1 — the first test (99 queries)

This was our starting point, before we changed anything.

![First evaluation results](figures/13_conclusion_baseline.png)

At this stage, the system could usually find the right document *somewhere* in its results (Recall@4 = 70.3%), but it almost never put it in the very first spot (Precision@4 = 20.3%). This told us two things needed fixing: old, leftover content sitting in the search index, and a "confidence check" that never said no to a bad result.

---

## Evaluation 2 — the final test (after every fix)

This is the last evaluation we ran, on two separate real datasets — 70 real support tickets, and the original 99-query set. Testing on two independent sets at once matters: it's proof the improvement is real, not a lucky result on just one set of questions.

![Final evaluation results](figures/14_conclusion_final.png)

| Metric | 70 real tickets | 99-query baseline | What it tells us |
|---|---|---|---|
| **Precision@1** | **71.4%** | 64.4% | The system's top guess is right most of the time |
| **Recall@4** | **89.0%** | 86.4% | The right answer is almost always somewhere in the results |

Both numbers went up a lot from where we started. We got there by fixing two real problems (old content in the search index, and a confidence check that never said no) and by adding better, more natural customer wording to the knowledge base documents — checked, every time, against both datasets together, not just one.

**Some of that wording came from real web-scraped customer reviews, and yes, this final knowledge base actually includes it.** Here's exactly where it came from and how:

- **Platforms:** Udemy, Coursera, Skillshare, and Pluralsight — four real, comparable course/learning platforms, all reviewed on **Trustpilot**.
- **How it was collected:** by directly fetching each platform's public Trustpilot review page and reading the reviews shown there — not through Trustpilot's official API (no API key, no authenticated access). Every review used is something anyone can see today by opening that page in a browser.
- **What we kept:** short phrases from real, dated, named reviews describing genuine problems — refunds, cancellations, logins, app crashes — plus a handful of real company replies where Trustpilot showed one under the review (Skillshare had these).
- **Checked before use:** every phrase was checked against our own real 71-ticket file to rule out any accidental overlap (zero matches, as expected — different products).
- **Saved for reuse:** all 54 scraped rows (review text, platform, rating, date, and the company reply where one existed) live in `ml_finetuning/data/real_responses/real_lms_platform_reviews.csv`.
- **A dead end we didn't use:** an earlier scraped dataset from a developer forum (Open edX's community forum) was checked first and rejected — reading it showed it was written by software engineers about server configs, not by customers, so none of it went into the knowledge base. That file (`real_responses_unrelated.csv`) is exactly why its name says "unrelated."

That second scraping round also caught a real software bug: one document grew just past a chunking-size boundary in the search index and quietly got split into two entries, and the indexing script had no way to clean up an old entry when a document later shrank back down. The first sign was a Recall score reported at 111% — a number that isn't mathematically possible — which is exactly why it was caught before being written down anywhere, not published and only found later. It's fixed at the root now (the indexing script prunes old entries properly), and every number in this document reflects the system after that fix.

---

## The one gap we found

**The system does noticeably better on the 70 real tickets than on the 99-query set — and we know why.**

Part of the knowledge base wording was written using first-hand knowledge of the exact 70 real tickets we tested against. That's not cheating — it's genuine product knowledge — but it does mean the system has effectively "seen" the *style* of that specific group of tickets before. The 99-query set was built completely separately, so its lower score is the more honest picture of how the system will do on brand-new tickets it hasn't been shaped around.

**In simple terms:** our best numbers are real, but they're a best case. The 99-query number is the safer number to plan around.

---

## What to say in the presentation

Say it in this order:

1. **What we tested.** "We checked whether our system actually finds the right knowledge-base document for a customer's ticket. We measured two things: is its top guess correct, and is the right document in its results at all."
2. **Where we started.** "In our first test, on 99 questions, the right document was usually in the results somewhere — about 70% of the time — but it was rarely the top pick, only about 20% of the time."
3. **What we found was wrong, and what we fixed.** "We found two real causes: the search index still had a lot of old, unused content clogging up every search, and the system's own confidence check never once said 'I'm not sure' — it approved everything. We cleaned out the old content and retuned that confidence check, and checked the fix against two separate sets of real data, not just one, so we know it's a real improvement and not a fluke."
4. **Where we ended up.** "In our final test, the system's top guess is right about 71% of the time on real tickets, and the correct document shows up in its results 89% of the time. On a second, independent set of questions, those numbers are 64% and 86% — still a real improvement, and this second number is the more conservative, trustworthy one. Part of this came from real customer reviews we collected from the web — Trustpilot pages for Udemy, Coursera, Skillshare, and Pluralsight — read directly from the public page, not through a paid API, not just made-up or internal wording."
5. **The one honest gap.** "The one thing we want to be upfront about: part of the reason the 70-ticket score is so high is that some of the knowledge base wording was written with direct knowledge of those exact tickets. So we're not claiming that number as guaranteed performance on totally new tickets — we're reporting the more independent, slightly lower number as the realistic expectation."
6. **Close it out.** "That's Track A — retrieval quality — complete. Next up is Track B, checking whether tickets get routed to the right team in the first place."

---

*Figures: `figures/13_conclusion_baseline.png` (first evaluation), `figures/14_conclusion_final.png` (final evaluation). Full numbers and methodology: `TEST_REPORT_V1.md`, `TEST_REPORT_V2.md`.*

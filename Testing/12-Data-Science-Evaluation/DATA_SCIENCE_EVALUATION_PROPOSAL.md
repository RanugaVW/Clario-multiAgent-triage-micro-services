# Data Science Evaluation Proposal

## Clario — Multi-Agent Customer Support Triage System

**Document type:** Evaluation Proposal
**Scope:** Data-science evaluation of retrieval, routing, escalation, and response-generation quality
**Status:** Track A is complete — both the original KB baseline and the new two-person, 70-real-ticket comparison. Full results are in `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`. Tracks B–E are proposed below, using the same real-ticket dataset and the routing labels Track A already built.

---

## 1. Executive Summary

Clario's existing test suites (`Testing/01` through `Testing/11`) already check that the system works correctly, safely, and reliably under load. None of them answer the question this proposal is about: **is the system's core AI decision-making — retrieval, routing, escalation, and response writing — actually good, checked against real answers and reported the way a data-science study should be?**

This proposal covers five evaluation tracks: retrieval quality, routing/escalation accuracy, final response quality, judge reliability, and overall system behaviour. The methods follow established RAG and LLM-evaluation research (RAGAS, ARES, MT-Bench, BERTScore) instead of made-up metrics. Each track states what ground truth is needed, what gets measured, what statistical checks back up each claim, and what tools are used.

An early retrieval baseline was already run, using a 99-query set built from an earlier 100-ticket dataset. That work found real problems in the knowledge base and led to a set of fixes, including a new HR specialist agent — all documented in `Track-A-Retrieval-Quality/TEST_REPORT_V1.md`. That earlier 100-ticket dataset has now served its purpose (building the knowledge base) and is not used again below.

**The main piece of work going forward uses one dataset: a 71-row file of real support tickets and their real human responses** (`CSV Files/lms_support_tickets Real - Support Tickets.csv`). The centrepiece of this proposal is a manual, two-person classification of these real tickets, compared directly against what the system actually does — this is the strongest and most direct test of retrieval quality in the whole evaluation. It is now complete (70 of the 71 tickets classified; one was a plain duplicate and was excluded), and it is described in full in §7.1 and in `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`.

---

## 2. Background and Motivation

Clario processes each incoming support ticket through a pipeline: it classifies the ticket, decides which specialist(s) should answer it, looks up supporting knowledge-base content, writes a customer-facing reply, and decides whether a human needs to check that reply before it goes out. Every one of these steps — classification, routing, retrieval, writing, escalation — is a place the system can quietly do a bad job without any functional test ever failing, because functional tests only check that *a* response comes out, not that it is the *right* response.

This evaluation exists to close that gap: to measure decision quality against real, human-made ground truth, with metrics a data-science reader would accept, and to show clearly *where* the system falls short rather than reporting one pass/fail number.

---

## 3. System Under Evaluation

### 3.1 Pipeline Overview

```
START → cache_check ──(≥0.92 similarity hit, no HR hard-trigger)──→ response_judge → escalation → resolve → handoff → END
   └─(miss)→ surrogate (PII redaction) → analyzer (no-op stub) → classification → routing
                                                                       │
                                    routing_decision ∈ {"technical","billing","both","escalation","hr"}
                                                                       │
                    ┌────────────────┬───────────────────┬──────────────────┬───────────────┐
              technical_agent   billing_agent      both_specialists      hr_agent      escalation (no signal)
                    └────────────────┴───────────────────┴──────────────────┘
                                                      ↓
                                                  validation ──(misroute, 1 retry)──→ routing (flipped)
                                                      │──(quality/policy fail, <2 loops)──→ reflection → re-run specialist
                                                      ↓ (pass)
                                              response_judge (1–5 score, record-only)
                                                      ↓
                                escalation.decide_escalation (rule-based; always
                                                triggers when routing_decision == "hr")
                                                      ↓
                                              resolve (PII restored) → handoff
```

Two decisions in this pipeline need to be kept separate, or errors get blamed on the wrong step:

- **Routing** (`routing_node.py:decide_routing`) — which specialist(s) write the reply. Five options: `technical`, `billing`, `both`, `escalation`, `hr`.
- **Escalation** (`escalation_node.py:decide_escalation`) — whether a human checks the reply before it ships. This is a simple rule: escalate if `priority == "Critical"`, or `sentiment == "Negative"`, or `routing_decision == "escalation"`, or `routing_decision == "both"` with low confidence, or a pipeline failure happened, or — since the HR agent was added — whenever `routing_decision == "hr"` (always, no exceptions).

### 3.2 Points That Matter for the Evaluation

- **Classifier confidence is not fully trustworthy yet.** `classify_ticket_local()` used to return a fixed confidence of `0.85` on success and `0.0` on failure — not a real probability. Since `decide_routing()` sends a ticket to `"both"` specialists whenever confidence is below `0.7`, a fixed value means that path could never be triggered by real uncertainty, only by keyword overlap. A fix is in progress (`_sequence_confidence()`, which reads real confidence from the model's own output). Classifier accuracy itself is being checked on a separate, outside track, and those numbers will be added here once available.
- **Retrieval used two different embedding models.** The system searches for knowledge with the local `all-MiniLM-L6-v2` model, but the original knowledge-base documents were indexed earlier using Google's `gemini-embedding-2` model. Both happen to produce vectors of the same size, so nothing crashes — but comparing vectors from two different embedding models does not produce a meaningful similarity score. This problem is specific to the original technical/billing documents; documents added later (including the new `hr/` folder) use the same model as the live queries. The original Track A baseline tested this directly instead of assuming it, and the fixes that followed are written up in `Track-A-Retrieval-Quality/TEST_REPORT_V1.md`.
- **An HR specialist agent now exists.** It adds a fifth routing option (`hr`), its own `hr/` knowledge folder (kept separate — it never searches billing or technical content), an `hr_agent` node built the same way as `technical_agent`, and a rule that always sends HR tickets to a human reviewer along with the AI's drafted reply, which an admin can edit before it is sent.

---

## 4. Evaluation Objectives

| Track | Question it answers | Ground truth used |
|---|---|---|
| A — Retrieval | Does the system find the right knowledge-base content for a ticket? | 99-query KB baseline (done) **plus** a manual, two-person classification of 70 real tickets (done — see `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`) |
| B — Routing & Escalation | Does the ticket reach the right specialist(s), and does escalation trigger correctly? | Human-labeled routing class + "should escalate" flag, built from the same 70 real tickets |
| C — Response Quality | Is the system's written reply as good as a real human agent's reply? | The same 70 real tickets, each with its own real human reply |
| D — Judge Reliability | Can the automatic response-quality judge be trusted as a stand-in for a human reader? | Human ratings on a sample drawn from Track C |
| E — End-to-End Behaviour | What is the system's overall pass/fail pattern, and why does it fail when it does? | Built from Tracks A–D plus pipeline logs |

Not covered here, because it is already covered elsewhere: unit/integration/end-to-end functional tests, load and speed testing, security checks, failover behaviour, API contract tests, OCR comparison, and classifier accuracy on its own (checked on a separate track; results will be added by reference once shared).

---

## 5. Datasets

### 5.1 Original Dataset — Used to Build the Knowledge Base (100 Tickets, done)

`ml_finetuning/data/real_responses/real_responses.xlsx`: 100 rows, evenly split (25 each) across `Payment Issue`, `Refund Request`, `Billing Issue`, and `Login Issue`. This dataset already did its job: its real ticket text was turned into the 99-query set used for the original Track A baseline, which found the knowledge-base problems fixed in `Track-A-Retrieval-Quality/TEST_REPORT_V1.md`. It is not used again in Tracks B–E below — the evaluation going forward runs entirely on the dataset in §5.2.

### 5.2 Real Ticket Dataset for the Upcoming Evaluation — 71 Tickets (evaluation not yet completed)

`CSV Files/lms_support_tickets Real - Support Tickets.csv`: 71 rows, columns `Ticket #, Reporter Name, Email, Course/Area, Description, Priority, Original Response, Recommended Action`. This is the dataset used for every track from here on — Track A's new comparison exercise, and all of Tracks B, C, D, and E.

This file has no ready-made `Category` or `Sentiment` column, so those need to be built by hand (see §7.1 and §7.2). `Course/Area` is free text (19 different values seen, such as `Payment/Enrollment`, `Instructor/Course Quality`, `General/LMS Access`, `Certification`), and the tickets cover a genuine mix of topics, not one single topic:

- **Billing-flavoured** tickets (payment, enrollment, subscription, refund): roughly 30 of the 71 rows — the largest group.
- **General/technical** tickets (login and course access, course content, certification, project submission): the rest of the non-instructor rows.
- **HR-relevant** tickets: 7 rows contain a clear HR signal — 2 are about a bank-slip payment being linked to the wrong account, and 5 are about an instructor being changed mid-course (including requests to cancel and get a refund because of it). These match the `hr/` knowledge folder built earlier (`course_cancellation.md`, `course_issues.md`, `payment_linkage_escalation.md`) almost exactly.

Because only a small part of this dataset is HR-specific, any HR-only result drawn from it should be read as an early, small-sample look (about 7 tickets), not a full-strength test of the HR agent.

### 5.3 Retrieval Ground Truth from the KB-Building Stage — 99 Queries (done)

A 99-query set, each mapped to the knowledge-base document(s) that should answer it, covering technical, billing, and HR topics. Built from real ticket text from the §5.1 dataset, checked by two people, with any disagreement talked through before the final answer was recorded. This is the dataset behind the Track A baseline already written up in `Track-A-Retrieval-Quality/TEST_REPORT_V1.md`.

### 5.4 Privacy

Both real-ticket files contain real personal information (name, email). Every script that touches either file removes those two columns first, before anything else happens to the data. No report from this evaluation quotes a name, an email address, or any ticket text that contains either. Both files stay out of version control.

---

## 6. Research Foundations

This evaluation follows methods already established in RAG and LLM-evaluation research, rather than inventing new ones:

- **RAGAS** (Es et al., 2023) — defines faithfulness, answer relevancy, context precision, and context recall as the core things to measure in a RAG system; used in Tracks A and C.
- **ARES** (Saad-Falcon et al., 2024) — shows that an automatic RAG judge needs to be checked against human ratings (around 150 examples) before it can be trusted at scale; this is why Track D exists.
- **"Judging LLM-as-a-Judge with MT-Bench"** (Zheng et al., 2023) and later work on judge reliability — shows that LLM judges can favour a certain answer position or a longer answer, and that human judges are not perfectly consistent either; Track D checks judge-vs-human agreement instead of assuming the automatic judge is correct.
- **BERTScore** (Zhang et al., 2020) — shows that comparing the *meaning* of two pieces of text (not just matching words) lines up much better with human judgment; useful here since a good support reply rarely repeats a human agent's exact wording.
- **Standard search-quality metrics** — Precision@k, Recall@k, MRR, and nDCG, used in Track A to score how well the system finds the right knowledge-base content.

Full reading list in §12.

---

## 7. Evaluation Methodology

### 7.1 Track A — Retrieval Quality (complete — see `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`)

**7.1.1 What has already been done.** A 99-query set (from the earlier 100-ticket dataset, §5.1) was run through `retrieve_context()`, and the results were scored with Precision@k, Recall@k, MRR, and nDCG@k (k = 3, 4), alongside a check of the system's own relevance gate (`check_relevance()`) against the human-made answers. This work found real problems — including the two-embedding-model mismatch in §3.2 — and led directly to the knowledge-base fixes and the new HR agent, all written up in `Track-A-Retrieval-Quality/TEST_REPORT_V1.md`.

> **Main method of this track — a two-person manual classification of the real tickets, checked against the system.**
>
> This is the strongest and most direct evidence in the whole retrieval evaluation, and it works like this:
>
> 1. **Independent labelling.** Two team members each go through the real tickets in `CSV Files/lms_support_tickets Real - Support Tickets.csv` on their own, without seeing each other's answers and without looking at what the system returns. For every ticket, each person decides, using only the `Description` and `Course/Area` text: (a) which Clario domain the ticket belongs to (`technical`, `billing`, or `hr`), and (b) which specific knowledge-base document should answer it, if any.
> 2. **Agreement check.** The two answer sheets are compared. Rows where both team members agree become solid ground truth right away. Rows where they disagree are discussed together and settled on one final answer. The percentage that matched *before* any discussion is reported as the inter-annotator agreement rate — this number matters, because every metric computed later depends on how solid this ground truth actually is.
> 3. **Comparison against the system.** The agreed answer sheet is then run through `retrieve_context()` and `decide_routing()`, and the system's actual output is compared, ticket by ticket, against what the two humans decided by hand.
>
> This is treated as the flagship result of Track A because it is fully blind (neither annotator sees the system's answer while labelling), it is done by two independent people rather than one, and it uses real production-style tickets end to end rather than a mix of real and hand-written queries. It is also the most convincing kind of evidence to show a reviewer: a direct, human-vs-machine comparison on the same real data.

**Status: complete.** This exercise has been run in full. 71 real tickets were reviewed; one (ticket #20, a plain duplicate of another ticket with no content of its own) was skipped by both annotators, leaving 70. The two annotators agreed on 67 of 70 (95.7%) before any discussion; the 3 disagreements were reviewed and resolved. Full results, the resolved disagreements, and all charts are in `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`.

**Metrics computed from this comparison:** Precision@k, Recall@k, MRR, and nDCG@k, the same formulas used in the earlier baseline, computed against the 70-ticket human-labelled set and reported as its own result, next to (not merged with) the original 99-query baseline, since the two sets were built differently and at different points in the project. Headline results: Precision@4 = 16.8%, Recall@4 = 63.2%, MRR = 0.406 — the same high-recall/low-precision pattern as the original baseline, again traced to stale content making up 40% of the searchable index. The HR domain, tested here for the first time with a real knowledge folder behind it, came out strongest on every measure (Recall@4 = 100%, MRR = 0.875), on a small sample of 12 tickets. The relevance-gate confusion matrix confirms the same finding as before: it did not correctly say "no" a single time across all 70 tickets. Two root-cause fixes were applied afterward (removing stale index content, retuning the gate threshold — cross-checked on both this set and the original 99-query set to avoid tuning to one dataset), which roughly tripled gate accuracy on both; full before/after detail is in `Track-A-Retrieval-Quality/TEST_REPORT_V2.md` §6. The domain label each annotator assigned in step 1 above is reused directly as the routing ground truth for Track B (§7.2), so this labelling work is not repeated twice.

**Tools:** `retrieve_context()` and `decide_routing()` (imported and run as they are, not rebuilt); `pandas`; `scikit-learn` (`ndcg_score` or a small hand-written version); `matplotlib`/`seaborn` for the comparison chart.

### 7.2 Track B — Routing and Escalation Accuracy

**Objective:** check whether `routing_node.py:decide_routing()` and `escalation_node.py:decide_escalation()` — the rule-based logic sitting on top of the classifier — make the correct call, independently of how accurate the classifier itself is (checked on a separate track, per §4).

**Ground truth:** the domain label each annotator assigns during Track A's manual classification (§7.1) doubles as the correct routing class here — no separate labelling pass is needed for that part. A `should_escalate` flag is added per ticket, based on `Priority` and `Recommended Action` (a ticket that names a policy problem or an unresolved repeat issue is treated as one that should have escalated). Together these make up `routing_ground_truth.csv`, covering all 70 tickets.

**Procedure:** `decide_routing()`/`decide_escalation()` are run two ways on the same 70 tickets, so that classifier mistakes and routing-logic mistakes don't get mixed together:

1. **Live run** — `classification_node.py → routing_node.py → escalation_node.py`, using whatever category and confidence the real classifier produces. This is the realistic, real-world number, but a wrong answer here could come from the classifier or from the routing rules — this run alone can't tell you which.
2. **Routing-logic-only run** — `decide_routing()`/`decide_escalation()` called directly with the human-made category from §7.1, and confidence fixed above the `0.7` cutoff so the low-confidence `"both"` rule can't fire by accident. This removes classifier error completely, so any mistake left over belongs to the routing/escalation rules themselves — which is exactly what this track is meant to measure.

**Metrics:** routing accuracy, per-class precision/recall/F1, and a full confusion matrix for both runs; escalation checked as a yes/no classifier (precision/recall/F1), stating clearly which kind of mistake (missed escalation vs. unnecessary escalation) is worse; how often the keyword-based fallback fires compared to a direct category match, and whether it is as accurate; whether the one-time misroute retry actually helps, checked with McNemar's test on matched before/after pairs. The gap between the live run and the routing-logic-only run is reported as an estimate of how much of the error comes from the classifier — to be checked later against the separately-supplied classifier numbers.

**Tools:** `routing_node.py` / `escalation_node.py` (and `classification_node.py` for the live run only) run directly; `pandas`; `scikit-learn` (`confusion_matrix`, `classification_report`); `statsmodels.stats.contingency_tables.mcnemar`; `matplotlib`/`seaborn` for the confusion-matrix chart.

### 7.3 Track C — Final Response Quality vs. Real Human Replies (planned, not yet completed)

**Objective, in plain terms:** find out if the reply Clario writes is as good as the reply a real human support agent wrote, for the same ticket. This is checked on all 70 tickets, including a first look at the small HR group inside it (§7.1's domain breakdown, n=12).

**Why this track matters:** Tracks A and B check that the system finds the right information and sends the ticket to the right place. Track C checks the actual end product — the message the customer would receive. A system can retrieve and route perfectly and still write a poor reply, so this has to be checked on its own.

**Procedure — four separate checks, run on every ticket:**

1. **Which reply is better, side by side (pairwise win-rate).** Clario's reply and the real human reply are shown to an LLM judge together, and it picks which one is better. The existing script `scripts/run_pairwise_evaluation.py` already swaps the left/right order between runs so the judge can't just always prefer "the first answer" — that control is reused as-is, not rebuilt.
2. **How good is Clario's reply on its own (absolute score).** `ResponseJudge` gives Clario's reply a score from 1 to 5 on several things at once (overall quality, matching the ticket's tone/priority, completeness, accuracy, following policy, staying grounded in real information). The full spread of scores is reported, not just one average number, so a few very bad replies don't get hidden inside a decent-looking average.
3. **How close in meaning is Clario's reply to the human's (semantic similarity).** Two replies can say the same thing in different words, so word-matching scores like BLEU/ROUGE are not enough on their own — they are reported only as a side note. The main number is a meaning-based comparison: MiniLM cosine similarity and BERTScore F1, both of which compare what the text *means* rather than which exact words it uses.
4. **Is the reply actually true, or did it make something up (groundedness).** This check compares Clario's reply against the exact knowledge-base content the system looked up for that specific ticket. If the reply says something that isn't backed by that content, it counts as unsupported — this catches made-up answers even when the wording sounds confident and correct.

**Breaking results down, not just averaging them:** every one of the four checks above is reported separately for each routing class from §7.1 (technical, billing, hr, etc.), including the small HR group on its own. This matters because one strong overall number can quietly hide a specialist that is doing badly.

**One decision made up front:** should Clario's reply be judged against the human reply exactly as it was sent, or against a corrected version that fixes any mistake called out in `Recommended Action`? This is decided before scoring starts. If judging against both versions gives a noticeably different result, both are reported rather than picking one silently.

**Tools:** `run_pairwise_evaluation.py` and `response_judge.py` (both already exist and are reused, not rebuilt); `sentence-transformers` (MiniLM); the `bert-score` package; `pandas`; `matplotlib`.

### 7.4 Track D — Judge Reliability (planned, not yet completed)

**Objective, in plain terms:** Track C leans heavily on `ResponseJudge`, an automatic scorer, to say whether a reply is good. Before trusting that score, it needs to be checked against what a real person would say — otherwise the whole of Track C could be built on a number that doesn't actually mean much. This idea comes directly from the ARES paper (§6), which found that automatic RAG judges need this kind of check before their scores can be trusted at scale.

**Procedure — step by step:**

1. **Pick a sample.** 25–30 ticket/reply pairs are pulled from Track C's results, spread across as many routing classes as the 71-ticket set allows, including the small HR group.
2. **Two people score it by hand.** Two independent people each read every pair and give it the same 1–5 scores `ResponseJudge` uses (overall, tone/priority match, completeness, accuracy, policy, groundedness) — without seeing the automatic judge's scores first.
3. **Check if the two humans agree with each other.** This is done first, using weighted Cohen's κ (a standard way to measure agreement on an ordered 1–5 scale). This step matters because comparing the automatic judge to humans who don't even agree with each other would not mean much.
4. **Compare the automatic judge to the humans.** Once the two humans' scores are combined, the automatic judge's scores are compared against them for each of the six score categories, using weighted κ and Spearman correlation.
5. **Re-check the order-bias control.** The existing check in `run_pairwise_evaluation.py` that stops the judge from always favouring whichever reply is shown first is tested again on this same sample, instead of just assuming it still works.

**A limit stated plainly:** the ARES paper used around 150 pairs to calibrate its judge; this evaluation uses 25–30. That is enough to say "the judge broadly agrees" or "the judge does not agree well," but not enough for a precise, tightly-bounded agreement number. This is said outright rather than implying more confidence than the sample size supports.

**Tools:** `scikit-learn` (`cohen_kappa_score`); `scipy.stats.spearmanr`; `pandas`.

### 7.5 Track E — End-to-End System Metrics and Failure Patterns (planned, not yet completed)

**Objective, in plain terms:** put Tracks A–D together into one overall picture of the system — how often each part of the pipeline actually fires, what kinds of mistakes happen most, and whether the extra "reflection" step (where the system re-checks and re-writes its own answer) is actually worth the extra time it takes.

**Procedure — three parts:**

1. **How often each pipeline step fires (funnel rates).** The cache-hit rate, the reflection-loop rate, the misroute-retry rate, and the real escalation rate are each measured as a percentage, and each one gets a 95% Wilson confidence interval rather than a bare percentage. A plain percentage can be misleading when the group behind it is small, and several groups in this evaluation are small (for example, the 7-ticket HR group), so the interval is reported every time.
2. **Sorting out what went wrong (failure taxonomy).** Every ticket flagged as a low score or a wrong route in earlier tracks is placed into one of a few buckets: the system looked up the wrong information, the system's reply included something made up, the prompt itself had a gap, or the ticket was simply a hard case no reasonable system would get right. Where the pipeline logs make the cause obvious, the logs decide; where they don't, a person makes the call.
3. **Does reflection actually help (optional, time permitting).** The existing speed numbers from `Testing/04` are compared against Track C's quality scores, matching tickets that went through the reflection loop against similar tickets that didn't, within the same routing class. This checks whether the slower, reflection-based answer is actually better, or just slower.

**Tools:** `statsmodels.stats.proportion.proportion_confint` (Wilson interval); `pandas`; `matplotlib`; existing application logs.

---

## 8. Statistical Rigor Requirements

Applied the same way across every track, not just where it's convenient:

- **Every percentage** (accuracy, escalation rate, win-rate) is reported with a confidence interval — the Wilson score interval, since a plain percentage becomes unreliable below roughly 30 examples, and several groups in this evaluation (the 7-ticket HR subgroup especially) are well below that.
- **Every before/after comparison** (routing before vs. after the retry; reflection vs. no reflection) is backed by a proper statistical test for paired data — McNemar's test for yes/no outcomes, a paired t-test or Wilcoxon signed-rank test for numeric scores.
- **Exact sample sizes are stated everywhere**, and anywhere a sample is too small for a strong claim, that is said plainly (the 7-ticket HR group and the 25–30-pair judge sample, in particular).
- **Agreement between human labellers is reported for every hand-built ground-truth set**, not only when it happens to be easy to compute.

---

## 9. Deliverables

| File | Track | Description |
|---|---|---|
| `retrieval_ground_truth.csv` | A | 99-query KB baseline set *(done)* |
| `Track-A-Retrieval-Quality/data/lms_ticket_ground_truth.csv` | A | Manual domain + KB-doc labels for 70 real tickets, agreement rate and resolved disagreements included *(done)* |
| `routing_ground_truth.csv` | B | Routing class (reused from Track A's labels) + `should_escalate` flag, 70 tickets *(planned, not yet completed)* |
| Prepared response set (PII removed) | C | 70 real tickets with real replies, ready for scoring *(planned, not yet completed)* |
| `judge_calibration_sample.csv` | D | 25–30 pairs, rated by two people |
| `Track-A-Retrieval-Quality/TEST_REPORT_V1.md` | A | Original KB baseline and the fixes it led to *(done)* |
| `Track-A-Retrieval-Quality/TEST_REPORT_V2.md` | A–E | Track A write-up complete (70-ticket evaluation); B–E sections to follow |

Every track's final write-up follows the same shape: how the ground truth was built and how much the labellers agreed, one results table and one chart per track, the embedding-mismatch and escalation-rate findings called out on their own since they are the strongest results, a list of failure examples with all personal information removed, a limitations section, and clear next steps for the codebase.

---

## 10. Work Plan

1. ~~Run the two-person manual classification of the real tickets and compare it against the system (§7.1).~~ **Done** — see `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`.
2. Add the `should_escalate` flag and finish `routing_ground_truth.csv`, reusing Track A's domain labels.
3. Run Track B (routing and escalation accuracy, both the live run and the routing-logic-only run).
4. Run Track C (pairwise and standalone response-quality scoring).
5. Run Track D, using a sample drawn from Track C's results.
6. Run Track E, pulling Tracks A–D together into one system-level view.
7. Add the Track B–E sections to `Track-A-Retrieval-Quality/TEST_REPORT_V2.md`.

---

## 11. Limitations

- Classifier confidence is still partly a fixed number rather than a real probability in one part of the code; this is being fixed, and any conclusion it could affect is flagged where it matters (§3.2, §7.2).
- Tracks A, B, C, D, and E all run on one 70-ticket sample. This is real, high-quality data (95.7% two-person agreement), but it is a small sample overall, and the HR group inside it is smaller still (12 tickets) — HR-specific findings, including Track A's very strong HR numbers, should be read as an early look, not a fully powered result.
- This dataset has no `Priority == Critical` examples and no ready-made sentiment label, so the sentiment-driven escalation rule cannot be tested with the same statistical strength as in the earlier 100-ticket baseline.
- Track D's judge-calibration sample (25–30 pairs) supports a general statement about agreement, not a precise number with a tight confidence range, given the ARES paper's own benchmark of roughly 150 pairs for that purpose.
- Classifier accuracy numbers referenced in this proposal come from a separate evaluation track and are treated as outside input here, not recalculated.

---

## 12. References

- Es, S. et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* arXiv:2309.15217.
- Saad-Falcon, J. et al. (2024). *ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems.* arXiv:2311.09476.
- Zheng, L. et al. (2023). *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* arXiv:2306.05685.
- *The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation.* arXiv:2606.13685.
- Li, D. et al. (2024). *Humans or LLMs as the Judge? A Study on Judgement Biases.* EMNLP 2024 / arXiv:2402.10669.
- Zhang, T. et al. (2020). *BERTScore: Evaluating Text Generation with BERT.* arXiv:1904.09675.
- Confident AI. *RAG Evaluation Metrics: Assessing Answer Relevancy, Faithfulness, Contextual Relevancy, And More.*
- Towards Data Science. *How to Evaluate Retrieval Quality in RAG Pipelines: DCG@k and NDCG@k.*
- Weaviate. *Evaluation Metrics for Search and Recommendation Systems.*
- Ragas documentation. *List of available metrics.* docs.ragas.io.

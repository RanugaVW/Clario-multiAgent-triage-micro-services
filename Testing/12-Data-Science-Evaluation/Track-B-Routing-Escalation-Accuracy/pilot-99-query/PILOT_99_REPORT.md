# Track B Pilot (99-Query Set) — Results & Gaps Found

**Status: annotation, evaluation, and both pipeline fixes complete (verified against this pilot's own data).** This is the pilot round (per the top-level `README.md`): find gaps and fix `routing_node.py`/`escalation_node.py` against this independent 99-query set *before* spending effort annotating the "real" 70-ticket round. It worked exactly as intended — it surfaced two real pipeline bugs, both now fixed and re-measured against the same 71 human-labeled rows.

Two annotators (human1, human2) independently filled in `data/routing_annotation_sample_99.csv` per `HOW_TO_ANNOTATE_99.md`. This report covers: how much they agreed, what their disagreements revealed, and what the real `decide_routing()`/`decide_escalation()` code got right and wrong when scored against their combined answer.

## Summary: gaps found and fix status

| Gap | Fix status |
|---|---|
| **HR routing was broken.** `routing_node.py` ignored the AI classifier's category label for HR tickets and only matched 4 exact keywords ("bank slip", "medical", "parental consent", "instructor"). Real HR tickets ("payment went through but course still shows unpaid") used none of these words and got sent to billing. | **Fixed.** Added 12 phrase patterns matching real wording. HR recall 37% → 79%. |
| **Escalation over-fired on sentiment.** `escalation_node.py` auto-flagged any "Negative" sentiment ticket for human review. Ordinary complaints read as negative just as often as genuinely serious ones. | **Fixed.** Removed `negative_sentiment` as a standalone trigger (gating it on priority was tried first and didn't work — priority doesn't correlate with real need either). Unnecessary escalations 32 → 7, F1 0.52 → 0.73. |
| **Merge-script data bug.** The script merging the two humans' answers silently discarded a correction if that ticket wasn't auto-flagged for review. One ticket (RB015) had both humans agree billing→hr and it was being dropped. | **Fixed.** Merge script now honors any override a human writes, flagged or not. RB015 recovered. |
| **Annotation instructions were ambiguous.** A blank override box meant "I agree with the AI's answer," but that was never stated, so blanks looked like missing data. | **Not done.** Needs a line added to `HOW_TO_ANNOTATE.md`. |
| **Humans disagreed on how strict "does the FAQ cover this" should be.** One accepted a close paraphrase as covered, the other wanted an exact match. 28 of 99 tickets disagreed on `should_escalate`. | **Not resolved.** Written to `routing_disputes_99.txt` for the two annotators to settle; recommend a concrete rule in `HOW_TO_ANNOTATE.md`. |
| **6 tickets wrongly flagged "no FAQ doc exists"** when one actually did. | **Not checked.** Low priority — see §6. |
| **19 tickets are genuine FAQ content gaps** — no doc covers the situation. | **Not done.** Candidate list for new KB content, see §7. |

## 0. Two annotation/merge-script gaps found and fixed before trusting any numbers

**0a. Blank overrides.** Both annotators left `routing_ground_truth_override` blank on 59 of the 80 human-columns-to-fill (30 of 40 flagged rows had at least one blank), even though the instructions said to fill it for every `routing_needs_annotation=yes` row. Reading the notes, the reason is consistent everywhere but one row: **both of them treated "blank" as "I agree with the mechanical value, no override needed"** — never stated as a valid option in `HOW_TO_ANNOTATE_99.md`.

**0b. The merge script itself silently discarded overrides on non-flagged rows.** While double-checking (0a), three rows (RB011, RB012, RB015) turned up where at least one annotator corrected the mechanical value even though `routing_needs_annotation=no` — most notably **RB015**, where **both** annotators independently wrote `hr` against a mechanical `billing`. The original `merge_routing_annotations_99.py`/`merge_routing_annotations.py` only ever looked at the override columns when the row was flagged, so this real, agreed-upon correction was being thrown away and the wrong ground-truth label (`billing`) used silently.

**Both are now fixed at the source, not worked around downstream:** `merge_routing_annotations_99.py` and the 70-ticket `merge_routing_annotations.py` were rewritten so a blank override always means "this human agrees with the mechanical value" and an override is honored whenever a human writes one, regardless of the flag — both scripts now print any such stray corrections explicitly rather than absorbing them silently. Re-running the fixed script against the original, unedited `data/routing_annotation_sample_99.csv` reproduces the same agreement statistics below and additionally recovers RB015 as a correctly-labeled HR row (raising HR's true support from 18 to 19).

**Gap #1 (process, still worth doing before the 70-ticket round): tighten the instructions too**, since the code fix doesn't make the ambiguity less confusing for a human filling the sheet in real time. Add an explicit line to both `HOW_TO_ANNOTATE.md` files: *"If you agree with the mechanical value, write it in anyway — a blank cell and an intentional agreement look identical either way."*

## 1. Human1 vs human2 agreement

| Field | Rows | Raw agreement | Cohen's κ | Interpretation |
|---|---|---|---|---|
| `should_escalate` (every row) | 99 | 71/99 = 71.7% | **0.430** (moderate) | A real, substantial disagreement — see §2 |
| `routing_ground_truth_override` (flagged rows only) | 40 | 38/40 = 95.0% | **0.922** (near-perfect) | Only 2 genuine domain disagreements out of 40 |

`data/routing_ground_truth_99.csv` (99 rows) is the merged result: 71 rows resolved cleanly, 28 rows written as `NEEDS_REVIEW` (see `data/routing_disputes_99.txt`) because the two annotators gave different `should_escalate` answers, 2 of which also disagreed on domain.

## 2. What the disagreements actually were

**Domain disagreements (2 of 40 flagged rows) — real, not a data-entry issue:**
- **RB047** (Q047, "duplicate email error blocking a second purchase"): human1 explicitly wrote in their note that it was "unclear whether this is even a billing or technical fix" and left it unresolved; human2 called it `technical` ("reads like a checkout bug ... just an engineering fix"). A genuine open question about whether this specific issue belongs to the specialist or the billing pipeline.
- **RB068** (Q068, "am I inside the refund window"): human1 kept the mechanical `hr` (a policy-exception judgment call); human2 overrode to `billing` ("just a factual question about the window, doesn't need HR-level judgment"). This is a real disagreement about how narrowly to define "needs human judgment."

**`should_escalate` disagreements (28 of 99 rows) — a systematic pattern, not noise:**

| Direction | Count | Pattern |
|---|---|---|
| human1=no, human2=yes | 22 | Human2 sets a stricter bar for "the KB already covers this" — a near-exact phrasing match ("close enough," "similar wording") isn't enough; if the specific scenario detail isn't spelled out verbatim, human2 escalates. |
| human1=yes, human2=no | 6 | The reverse case — human1 occasionally escalates on a doc-adjacency gap that human2 is comfortable inferring from general policy tone. |

The 22-vs-6 split shows this isn't random noise — it's a real difference in where each annotator draws the line between "close enough to the documented case" and "genuinely undocumented, needs a person." Six of the human1=no/human2=yes rows (RB006, RB032, RB040, RB042, RB049, RB093) are a distinct sub-pattern: human1 found an **exact, word-for-word matching KB doc** and argued the row shouldn't have been flagged for review at all, while human2's more conservative default ("it was flagged, so I'll keep it queued for a second look") drove the disagreement rather than an actual content gap.

**Gap #2 (process): tighten the `should_escalate` definition before the 70-ticket round.** `HOW_TO_ANNOTATE.md` should give a concrete rule for "close enough" — e.g., *"if a KB doc names the same underlying scenario, even with different wording, that counts as covered — only escalate when the specific fact pattern (not just the general topic) is absent."* That should collapse most of the 22-count bucket.

## 3. Pipeline evaluation, before and after both fixes

Scored against the 71 rows both annotators agreed on (28 rows are unresolved disputes, excluded — a routing/escalation decision needs a single correct answer to score against). Two runs per the proposal (§7.2): **live** (real local classifier feeds `decide_routing`) vs **routing-logic-only** (ground-truth domain fed directly, confidence forced to 0.99, isolating the routing/escalation rules from classifier error). Numbers below are from the corrected ground truth (§0), run twice — once against the original code, once against both fixes applied (§4, §5).

### Routing accuracy

| Run | Overall accuracy | technical (n=17) | billing (n=35) | hr (n=19) |
|---|---|---|---|---|
| Live, before → after | 63.4% → **74.6%** | P 1.00/R 0.76 (unchanged) | P 0.69→**0.89** / R 0.71 (unchanged) | P 0.78→0.88 / R 0.37→**0.79** |
| Logic-only, before → after | 76.1% → **87.3%** | P 1.00/R 1.00 (unchanged) | P 0.73→**0.91** / R 0.86 (unchanged) | P 0.78→0.88 / R 0.37→**0.79** |

HR recall more than doubles (0.37→0.79) in *both* runs identically — confirming this was a rule bug, not a classifier-accuracy problem, exactly as the pre-fix flat-vs-flat comparison had signaled. Billing precision also jumps because far fewer true-HR tickets are now wrongly counted as billing predictions.

### Escalation accuracy

| Run | Precision | Recall | F1 | Missed (FN) | Unnecessary (FP) |
|---|---|---|---|---|---|
| Live, before → after | 0.396→**0.741** | 0.750→0.714 | 0.519→**0.727** | 7→8 | 32→**7** |
| Logic-only, before → after | 0.383→**0.889** | 0.643→0.571 | 0.480→**0.696** | 10→12 | 29→**2** |

Unnecessary escalations drop by roughly 4-5x for a small increase in missed ones — a clear net improvement (F1 up ~40% in both runs), traded off explicitly and measured, not assumed (§5).

## 4. Gap #3 (pipeline bug, headline finding, fixed): HR routing didn't actually use the classifier's HR category at all

The routing-logic-only run was designed to answer "if the classifier correctly says HR, does the routing logic get it right?" It didn't — **HR recall was identical (0.37) whether or not the classifier's category was even involved**, because it wasn't. Reading `routing_node.py`'s `decide_routing()` (lines 91–102): the HR branch fired *only* from `HR_HARD_TRIGGER_KEYWORDS`/`HR_WEAK_SIGNAL_KEYWORDS` matching the raw ticket text. There was no code path anywhere in the function that checked `category == "hr"` — forcing `category="hr"` in the logic-only run changed nothing for HR tickets, which is exactly what the flat 0.37-vs-0.37 comparison showed.

11 of 19 HR-ground-truth tickets (including RB015, recovered by the §0b merge fix) fell through to `billing` (or once, `escalation`) even with the correct category forced:

| Ticket | What happened | Text pattern the keyword lists miss |
|---|---|---|
| Q001, Q005, Q041 | → billing | "paid but course/dashboard still shows not enrolled / unpaid" |
| Q023 | → billing | "bank **deposit** slip ... Pending Verification" (`"bank slip"` isn't a substring of `"bank deposit slip"`) |
| Q029, Q078 | → billing | "hasn't been linked to my account" / "payment can't be matched" |
| Q053 | → billing | "enrolled in the wrong course level" |
| Q074 | → billing | "name on the slip doesn't match" |
| Q081 | → billing | "entered a smaller amount... due to a typo" |
| Q084 | → escalation | "transaction ID doesn't match the dashboard" |
| Q070 | → billing | "relocating abroad" (a `course_cancellation.md` case, different pattern entirely) |

Every one of these (except Q070) is the exact "paid but not linked/matched to the account" scenario that `payment_linkage_escalation.md` exists for — both annotators cited that doc by name for nearly every one of them — but none of the literal phrases in `HR_HARD_TRIGGER_KEYWORDS` (`"bank slip"`, `"medical"`, `"parental consent"`, `"instructor"`) or `HR_WEAK_SIGNAL_KEYWORDS` (`"sponsorship"`, `"wrong account"`, `"misclassified"`, `"linked to the wrong"`) appeared in the actual ticket wording. Q070 and RB015 belong to a second pattern named directly in `course_cancellation.md` ("relocation," schedule conflicts) that also had no matching keyword.

**Fix applied** to `HR_HARD_TRIGGER_KEYWORDS` in both mirrored `routing_node.py` files (checked against every `billing`/`technical`/`hr` KB doc first for collisions): `"not enrolled"`, `"course as unpaid"`, `"deposit slip"`, `"hasn't been linked"`, `"not been linked"`, `"can't be matched"`, `"cannot be matched"`, `"still doesn't appear"`, `"name on the slip"`, `"relocat"`, `"schedule conflict"`, `"scheduling conflict"`. **Result: HR recall 0.37→0.79** in both runs (§3); Q053, Q081, Q084 remain open (their phrasing — "wrong course level," "typo'd amount," "transaction ID mismatch" — didn't have a safe, generalizable substring without risking new false positives elsewhere; left as a residual gap rather than force a brittle match). Existing routing/escalation/cache-check test suites re-run clean (24/24, both codebases) after the change.

## 5. Gap #4 (pipeline bug, fixed): `negative_sentiment` alone was a harmful escalation trigger, not just a blunt one

`escalation_node.py` escalated unconditionally whenever `sentiment == "Negative"`, with no other condition. That single rule accounted for **27 of 32 (84%)** of the live run's unnecessary escalations, and 27 of 29 (93%) in the logic-only run.

**First attempt, tested and rejected:** gate the trigger on priority (only escalate negative sentiment at Medium+). This did *nothing* — re-running the pilot showed FP unchanged (32→32, 29→29) — because the classifier assigns "High" priority to routine, well-documented complaints just as often as genuinely severe ones (confirmed directly: `classify_ticket()` returned `priority=High` for "payment page froze at checkout" and "charged twice," both textbook, already-documented billing cases).

**Root cause, found by pulling real classifier output for all 71 rows and checking correlation with the human ground truth directly:** priority and sentiment both show essentially *no* correlation with actual escalation need in this dataset — if anything, sentiment is inversely correlated. Of the 36 tickets classified `High priority + Negative sentiment`, **24 (67%) should NOT have escalated** per the humans. Confidence showed no separation either (mean 0.896 for true escalations vs. 0.888 for false positives).

**Fix applied:** removed `negative_sentiment` as a standalone trigger entirely, in both mirrored `escalation_node.py` files — the remaining triggers (`critical_priority`, `hr_process_required`, `low_confidence_dual_domain`, `no_usable_routing_signal`) already cover genuine severity without relying on this classifier's uninformative sentiment output. **Result: FP 32→7 (live), 29→2 (logic-only); F1 0.519→0.727 (live), 0.480→0.696 (logic-only)**, for a recall cost of 0.750→0.714 (live) / 0.643→0.571 (logic-only) — a clear net win given how few escalation needs come from sentiment alone once HR routing (§4) is already catching most of them via `hr_process_required`. The removed-trigger test case was replaced with one asserting the new, intended behavior (`test_negative_sentiment_alone_does_not_escalate`); both suites re-run clean.

## 6. Gap #5 (Track A follow-up): 6 rows' "no relevant KB doc" flag looks stale

`routing_needs_annotation=yes` is supposed to mean Track A found no matching KB doc. Six flagged rows (RB006, RB032, RB040, RB042, RB049, RB093) had human1 report an **exact, word-for-word matching doc** on inspection. Worth a quick check of whether the KB gained content after Track A's original retrieval pass, or whether the join/flagging logic itself has a gap — low priority, but cheap to check before trusting the flag on the 70-ticket round.

## 7. Gap #6: 19 genuine, still-open KB content gaps

Candidates for new KB content before the real round (installment due dates, technical-outage-tied refund eligibility, WebXpay OTP ownership between billing/technical, concurrent-session/device locks, split-card payment enrollment status, "duplicate email" checkout error, loyalty points/wallet balance, company-initiated batch cancellation, forex loss on refunds, outage-inflated progress disputes, corporate sponsorship refund routing, invoice correction, bank-transfer fee shortfalls, mobile-app-specific login failures, session timeout duration, forgotten-signup-email recovery, browser autofill, org email-domain change lockout, multi-account merging) — full list with exact ticket text in `data/routing_annotation_sample_99.csv` notes columns (search for "gap").

## 8. Not computed (unchanged from proposal scoping)

- McNemar's test on the reroute retry — needs a real run through `validation_node` to produce a genuine misroute event.
- 3 of 7 escalation triggers (`dependency_failure`, `misroute_unresolved`, `reflection_cap_reached`) — only fire after specialists + validation + reflection actually run.

## Files

| File | Contents |
|---|---|
| `data/routing_annotation_sample_99.csv` | Raw, unedited human1/human2 submissions — the merge script (§0) now resolves blanks and stray overrides directly from this file |
| `data/routing_ground_truth_99.csv` | Merged ground truth: 71 resolved rows + 28 `NEEDS_REVIEW` |
| `data/routing_disputes_99.txt` | The 28 unresolved rows and both answers, for the two annotators to discuss |
| `results/routing_eval_summary_99.json` | Confusion matrices, P/R/F1 for both runs, **after both fixes** |
| `results/per_query_routing_results_99.csv` | Per-ticket live vs logic-only routing/escalation decisions + fired reasons, **after both fixes** |

## What's left before the 70-ticket round

Both pipeline fixes (§4, §5) and the merge-script bug (§0b) are done and re-validated against this pilot's own 71 human-labeled rows — the code path the 70-ticket round will run against is now the fixed one, not the one that produced the original findings. What's still open:

1. **Fold the two annotation-instruction fixes into `HOW_TO_ANNOTATE.md`** (§0: blank-means-agrees-with-mechanical should be stated explicitly; §2: a concrete rule for how close a KB match has to be to count as "covered," to collapse the 22-row human1/human2 gap).
2. **Resolve the 28 disputed rows** in `data/routing_disputes_99.txt` between the two annotators (a discussion, not something to auto-resolve) — optional for the pilot itself, but the underlying `should_escalate` definition gap (§2) should be settled before it recurs at 70-ticket scale.
3. **The 3 residual HR misses** (Q053, Q081, Q084 — §4) and **19 open KB-content gaps** (§7) remain real, just out of scope for a keyword-list fix; worth a KB content pass before the real round if time allows.
4. Then annotate the 70-ticket round per the top-level `README.md`.

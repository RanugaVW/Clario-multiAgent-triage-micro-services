# Track A — Retrieval Quality Evaluation, Version 1 (Baseline)

**Status:** baseline, pre-enhancement. This is the "before" measurement — no KB content changes, no vector-store cleanup, no code changes have been made yet. A Version 2 report will re-run this exact methodology after those enhancements land, so the two are directly comparable.

**System evaluated:** the real, currently-deployed `retrieve_context()` / `check_relevance()` functions in `app/tools/rag_tool.py`, executed against the ChromaDB instance already populated at `clario-ml-sidecar/vector_store/chroma_data` — no index was rebuilt for this report; this is what the system actually returns today.

**Ground truth:** `Testing/12-Data-Science-Evaluation/data/retrieval_ground_truth.csv` — 99 human-reviewed queries (Q001–Q100, `Q089` absent from the source sheet), covering all 20 KB docs plus 10 queries the reviewer judged belong to a domain the system doesn't route to today ("HR").

**Scripts/artifacts:** `scripts/eval_retrieval.py` (all metric code + formulas as docstrings), `results/v1_per_query_results.csv` (all 99 rows, full detail), `results/v1_summary_metrics.json` (raw numbers behind every table below).

---

## 1. Methodology

### 1.1 Ground truth and its one required adaptation

Each row pairs a real or realistic customer query with the KB doc(s) a human reviewer judged should answer it (`relevant_doc_ids`, empty/`none` where no current doc qualifies). `domain` is `technical`, `billing`, or — for 10 rows — `HR`, a category the reviewer introduced for tickets they judged need a kind of handling the system doesn't have today (see §5).

`retrieve_context()` only accepts `domain ∈ {"technical", "billing"}` — it raises `ValueError` on anything else. Since `routing_node.py` would route these 10 tickets to `billing` today (they all originated as Payment/Refund/Billing-category tickets in the source dataset), this evaluation substitutes `domain="billing"` for HR rows to faithfully reproduce what the deployed system actually does, while keeping the reviewer's original ground truth (9 of the 10 say `none` — no doc should match; `Q024` is the one exception, kept as the reviewer wrote it). Every HR-substituted row is flagged in the results (`domain_substituted=True`) and reported separately, never silently folded into the billing numbers without disclosure.

### 1.2 A scoring bug found and fixed before any number below was trusted

The first run of this evaluation returned **exactly 0.0 on every metric** — a red flag investigated before being reported as a finding (see `superpowers:systematic-debugging`: root cause before fixes). Cause: the ground truth uses bare KB filenames (`login_reset.md`), but the real ChromaDB metadata stores them domain-prefixed (`technical/login_reset.md`, per `build_index.py`'s use of `source.relative_to(KB_ROOT)`). Every correct retrieval was being scored as a miss over a path-prefix string mismatch, nothing more. Fixed by comparing on basename (`_basename()` in `eval_retrieval.py`) before any metric is computed. All numbers below are post-fix.

### 1.3 Metric formulas

Let a query's retrieval return a ranked list of up to `k=4` KB sources, and let `relevant` be the ground-truth set of correct sources for that query (possibly empty).

**Precision@k** — of the k slots returned, what fraction are actually correct:
```
Precision@k = |{top-k results} ∩ relevant| / k
```
Well-defined even when `relevant` is empty (a query with no correct answer naturally scores 0 here, correctly penalizing any confident-but-wrong result).

**Recall@k** — of everything that would count as correct, what fraction did the top-k actually surface:
```
Recall@k = |{top-k results} ∩ relevant| / |relevant|
```
Undefined (0/0) when `relevant` is empty — excluded from the Recall average rather than silently coerced to 0 or 1, so the average reported is only over the 59 queries where a correct answer actually exists to be found.

**Mean Reciprocal Rank (MRR)** — how early the first correct result appears, averaged over queries:
```
RR = 1 / rank of first relevant result   (0 if none of the top-k are relevant)
MRR = mean(RR) over queries with relevant ≠ ∅
```

**Normalized Discounted Cumulative Gain (nDCG@k)** — rewards correct results more when they rank higher, using binary gains (1 = relevant, 0 = not):
```
DCG@k  = Σ_{i=1..k} gain_i / log2(i + 1)
IDCG@k = the same sum if all min(|relevant|, k) relevant items were ranked first (best possible order)
nDCG@k = DCG@k / IDCG@k
```
Undefined when `relevant` is empty (IDCG@k = 0) — same exclusion rule as Recall.

**The relevance gate as a binary classifier.** `check_relevance()` returns a single pass/fail per query (its own top-1 similarity score ≥ 0.3). Treating "the top-1 result is actually correct" (`top1_correct`) as ground truth for that decision gives a standard 2×2 confusion matrix (TP/FP/FN/TN), from which:
```
Gate Accuracy  = (TP + TN) / N
Gate Precision = TP / (TP + FP)     — of the queries the gate approved, how many were actually right
Gate Recall    = TP / (TP + FN)     — of the queries that were actually right, how many did the gate approve
```

---

## 2. Headline Results

| Metric | Value | N |
|---|---|---|
| Precision@3 (all 99 queries) | 14.5% | 99 |
| Precision@4 (all 99 queries) | 12.1% | 99 |
| Precision@3 (queries with a real answer only) | 24.3% | 59 |
| Precision@4 (queries with a real answer only) | 20.3% | 59 |
| **Recall@3** | **62.7%** | 59 |
| **Recall@4** | **70.3%** | 59 |
| **MRR** | **0.469** | 59 |
| **nDCG@4** | **0.518** | 59 |

**Reading these together:** Recall@4 of 70.3% means the correct doc *is* in the top-4 about 7 times in 10 when one exists — not catastrophic. But Precision@4 of only 20.3% on those same queries means that even when the right doc is somewhere in the top 4, on average barely 1 of the 4 returned slots is actually correct — the rest is noise the specialist prompt still has to read past. Both are true at once, and the next section explains why.

## 3. Root Cause: A Contaminated Vector Store, Not (Only) the Suspected Embedding Mismatch

The original hypothesis (from the design spec) was that mismatched embedding models — KB docs indexed with Gemini's `gemini-embedding-2`, queries embedded with local `all-MiniLM-L6-v2` — were the primary quality problem. That mismatch is real and still unverified/unfixed as of this report, but direct inspection of the live `kb_support_docs` collection turned up a **larger, previously unknown problem**:

```
kb_support_docs: 71 total chunks, 51 unique source_file values
  20  →  the real, current KB docs (10 technical/*.md + 10 billing/*.md), 1 chunk each
  21  →  precedent_memory (correctly excluded by retrieve_context()'s own filter — inert, not a live bug)
  30  →  orphaned .txt-named chunks: login_guide.txt, mobile_login.txt, account_lockout.txt,
         auth_errors.txt, password_reset.txt, browser_support.txt, chargeback.txt,
         double_charge.txt, invoice_guide.txt, refund_policy.txt, ... (30 total)
```
Confirmed by direct search: **none of these 30 `.txt` files exist anywhere in the current repository, and none appear anywhere in git history.** They were indexed into this persistent ChromaDB store by some process outside this codebase's current build scripts, and nothing has ever cleaned them out. They compete in every single retrieval call.

**Measured impact:** across all 99 queries, these orphaned chunks occupied **58.1% of every returned slot** (2.32 of the 4 slots, on average) — more than half of everything the system hands to a specialist prompt as "context" is content that no longer corresponds to anything in the actual knowledge base.

**This explains the technical/billing split cleanly:**

| Domain | N | N with a real answer | Precision@4 | Recall@4 | MRR |
|---|---|---|---|---|---|
| technical | 27 | 16 | 3.7% | **25.0%** | 0.130 |
| billing | 62 | 42 | 17.3% | **86.9%** | 0.597 |
| HR → billing (substituted) | 10 | 1 | 2.5% | 100%* | 0.500 |

\* n=1 — a single query, not a stable estimate; do not generalize from it.

Technical-domain recall (25.0%) is dramatically worse than billing (86.9%). The orphaned `.txt` corpus explains why: its login/account/auth-themed entries (`login_guide.txt`, `login_troubleshooting.txt`, `mobile_login.txt`, `auth_errors.txt`, `account_access.txt`, `account_lockout.txt`, `2fa_guide.txt`, `sso_guide.txt`) sit almost exactly on top of the real technical KB's actual subject matter (`login_reset.md`, `browser_support.md`) and are winning the similarity ranking against them directly, most of the time. Billing has its own orphaned entries too (`chargeback.txt`, `double_charge.txt`, `refund_policy.txt`, etc.), but apparently competes with them less destructively — a finding worth a closer look in V2, not fully explained by this V1 run alone.

**A risk that was checked and did *not* materialize:** technical-domain queries also search `kb_codebase` (4,042 source-code chunks). This was flagged as a theoretical crowding-out risk in the original design spec. Checked directly against all 99 result rows: **zero source-code chunks appeared in any top-4 result, for any query.** Recording this explicitly so it isn't re-investigated from scratch later — it's a real risk in principle, just not the one causing today's numbers.

## 4. The Relevance Gate Provides No Real Protection Today

`check_relevance()` (threshold 0.3) is meant to tell the pipeline "don't trust this retrieval, the top match isn't good enough." Measured against whether the top-1 result was actually correct:

| | Gate said "pass" | Gate said "fail" |
|---|---|---|
| **Top-1 was actually correct** | TP = 16 | FN = 0 |
| **Top-1 was NOT actually correct** | FP = 83 | TN = 0 |

- **Gate Accuracy = 16.2%**, **Gate Precision = 16.2%**, **Gate Recall = 100%**.
- On the 40 queries where the reviewer determined *no* current doc should match at all, the gate said "relevant, proceed" on **all 40 (100% false-positive rate)**.

The gate has never once said "no" in this entire dataset — it passes literally everything, including every query with zero correct answer available. At a 0.3 cosine-similarity threshold, this isn't protecting the pipeline from bad retrieval; it's a rubber stamp. (This is very plausibly *downstream* of the stale-data problem in §3 — the orphaned chunks return high-confidence-looking similarity scores of their own, which is exactly the kind of thing a genuinely clean store might change. V2 should re-measure this, not assume it's fixed by the same cleanup.)

## 5. Coverage Gaps the Reviewer Found by Hand (Not a Retrieval Bug — Missing Content)

40 of the 99 queries had no correct doc for the system to find *at all*, independent of any retrieval-quality issue — the content simply doesn't exist yet. The reviewer's notes converge on two different kinds of gap:

**(a) Missing KB docs for existing technical/billing routing** — 32 of the 40 queries name a specific new doc that would resolve them:

| Suggested new doc | Queries | Count |
|---|---|---|
| `WebXPay.md` (gateway-specific failure modes) | Q022, Q041, Q043, Q045, Q047, Q049, Q051, Q084 | 8 |
| `account_issue.md` (lockouts, OTP-device-changed, merged/suspended accounts) | Q032, Q036, Q040, Q086, Q091, Q094, Q096, Q098 | 8 |
| Refund-eligibility-window policy (extend `subscription_cancel.md` or a new doc) | Q017, Q019, Q029, Q068 | 4 |
| `misclassification_billing.md` (payment linked to wrong course/account/amount) | Q027, Q064, Q078, Q081 | 4 |
| `payment_status.md` (bank-slip verification, lost slip, name mismatch) | Q023, Q074, Q076 | 3 |
| `course_cancellation.md` (medical emergency, parental consent, relocation) | Q058, Q059, Q070 | 3 |
| `enrollment_issues.md` (wrong course level enrolled) | Q053 | 1 |
| `course_issues.md` (instructor changed mid-course) | Q057 | 1 |

**(b) Gaps with no specific doc proposed yet** — 8 queries (Q001, Q005, Q006, Q018, Q042, Q052, Q082, Q085) where the reviewer flagged "no current doc answers this" without yet proposing what should. These need product/policy input before a doc can be written, not just KB authoring.

**(c) A structurally different kind of gap — not a KB doc problem.** 10 of the 40 (the `HR`-domain rows) aren't missing *content* so much as missing a *routing destination*: bank-slip name mismatches, medical-emergency refunds, parental-consent issues, and gateway-team escalations that the reviewer judged need human-process handling, not a specialist-drafted response at all. The reviewer's own conclusion after this labeling pass — *"there is no HR agent still, but I think we need to create one"* — is a bigger, separate architectural question (a fourth routing destination alongside `technical`/`billing`/`both`/`escalation`, not just new KB content) and is deliberately **not** addressed in this report or its recommendations below, per the plan to defer enhancement work to a follow-up phase.

## 6. Data-Quality Notes on the Ground Truth Itself

- **N=99, not 100** — `Q089` is absent from the reviewed sheet (Q088 → Q090). Not fabricated or assumed; reported as a real gap in the source.
- **`Q024`** is the one `HR`-domain row with a non-`none` `relevant_doc_ids` (`payment_failed.md`), unlike all 9 other HR rows. Kept exactly as reviewed — not treated as an error to silently correct.
- **This ground truth reflects a single reviewer's pass.** The plan's methodology calls for a second, independent labeler and an inter-annotator agreement figure before treating these labels as fully settled — that second pass has not happened yet. Treat the metrics above as accurate *given this ground truth*, with the ground truth itself still provisional.

## 7. Limitations

- The suspected embedding-mismatch bug (Gemini-index vs. MiniLM-query) is still unverified in isolation — its effect is now entangled with the much larger stale-data problem in §3, and can't be cleanly separated without first cleaning the store. V2's re-embedding ablation should be run *after* stale-data cleanup, not before, or its result will still be contaminated.
- The `HR → billing` domain-substitution numbers (n=10, only 1 with a real answer) are not statistically meaningful on their own — reported for completeness, not as an estimate to generalize from.
- Billing's better-but-still-imperfect performance relative to technical is observed, not fully explained, by this report — worth a closer per-query look in V2 rather than assuming the same root cause applies equally to both domains.

## 8. Recommended Order of Fixes for Version 2

1. **Clean the vector store first** — identify and remove the 30 orphaned `.txt`-named chunks from `kb_support_docs` (and confirm nothing else is stale). This is the highest-leverage, lowest-risk fix and should happen before anything else, since it's currently the dominant source of error and would otherwise contaminate every other measurement.
2. **Re-run this exact evaluation post-cleanup** as a first checkpoint — before touching embeddings or KB content — to isolate how much of today's numbers were purely the stale-data effect.
3. **Then run the embedding re-embed ablation** (MiniLM-indexed KB vs. today's Gemini-indexed KB) on the now-clean store, per the original design spec.
4. **Author the 8 identified missing KB docs** (§5a) — the queries and content requirements are already specified above; no further discovery work needed for these 8.
5. **Re-measure `check_relevance()`'s gate behavior** post-cleanup — don't assume the 100% false-positive rate is fixed just because the store is cleaner; verify it.
6. **Defer the "HR agent" / fourth-routing-destination question** (§5c) to a separate architectural discussion — it's a routing/graph design decision, not a KB or retrieval fix, and out of scope for a Track A retest.

---

*Generated from `scripts/eval_retrieval.py` against `clario-ml-sidecar/vector_store/chroma_data` as it existed at the time of this run. Full per-query detail: `results/v1_per_query_results.csv`. Raw metrics: `results/v1_summary_metrics.json`.*

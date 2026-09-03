# Unit Test Report — Clario System

**Date:** 2026-09-03
**Tester:** Ranuga Weerasekara (ranugaweerasekara2@gmail.com), assisted by Claude Code
**Branch / commit:** `main` @ `a721f69`
**Test case field:** Complete end-to-end unit test suite across every component of the Clario system

## 1. Scope

This phase corresponds to §3.1.2 ("Function Testing") of the reference
Master Test Plan, applied at the unit level: every controller/node/tool/
function in Clario is exercised in isolation with mocked collaborators
(LLM calls, Supabase, ChromaDB, HTTP fetches). Three independently testable
components exist in this repo, each with its own real, pre-existing test
suite — none of it written for this report, all of it executed fresh for
this report:

| Component | What it is | Framework |
|---|---|---|
| `clario-ml-sidecar` | FastAPI + LangGraph agent pipeline (classification, routing, specialist agents, validation, judge, escalation, resolution) | pytest 9.1.1 |
| `ml_finetuning` | Data curation, PII cleaning, distillation, training/eval scaffolding for the fine-tuned triage model | pytest 9.0.3 |
| `frontend` | Next.js dashboard, admin console, API routes | vitest 4.1.10 |

## 2. Environment

- OS: Linux 7.0.0-30-generic
- Python: 3.12.3
- Node: v24.14.0
- `clario-ml-sidecar` run inside its own `.venv` (project-pinned deps, incl. torch/transformers/supabase/fastapi)
- `ml_finetuning` run against system Python 3.12 with `requirements.txt` installed (pytest 9.0.3 resolved instead of the pinned 9.1.1 — did not affect results)
- `frontend` run via `npm test` (`vitest run`) against the repo's `node_modules`
- No network calls were made — every suite mocks its external dependencies (LLM providers, Supabase, HTTP fetch targets)

## 3. Results Summary

| Suite | Files | Executed | Passed | Failed | Skipped | Pass % (of executed) | Duration |
|---|---|---|---|---|---|---|---|
| `clario-ml-sidecar` | 27 | 92 | 85 | **4** | 3 | 95.5% | 21.0s |
| `ml_finetuning` | 10 | 47 | 44 | 0 | 3 | 100% | 17.9s |
| `frontend` | 12 | 91 | 91 | 0 | 0 | 100% | 5.0s |
| **Total** | **49** | **230** | **220** | **4** | **6** | **98.2%** | **~44s** |

Raw, unedited console output for each suite is kept next to this report:
- [`ml-sidecar/test-log.txt`](ml-sidecar/test-log.txt)
- [`ml-finetuning/test-log.txt`](ml-finetuning/test-log.txt)
- [`frontend/test-log.txt`](frontend/test-log.txt)

## 4. Skipped Tests (6) — not failures

All 6 skips are explicit `pytest.skip("<feature> has not been implemented.")`
markers for scaffolding the team has intentionally not built yet, not
environment problems:

| Suite | Test | Reason |
|---|---|---|
| `clario-ml-sidecar` | `test_billing_agent_creates_a_policy_compliant_draft` | Billing specialist agent not implemented |
| `clario-ml-sidecar` | `test_technical_agent_creates_a_grounded_draft` | Technical specialist agent not implemented |
| `clario-ml-sidecar` | `test_rag_tool_returns_relevant_grounded_context` | RAG retrieval tool not implemented |
| `ml_finetuning` | `test_gemini_labeler_returns_a_valid_distilled_example` | Gemini distillation labeler not implemented |
| `ml_finetuning` | `test_evaluation_reports_required_quality_metrics` | Model evaluation not implemented |
| `ml_finetuning` | `test_dataset_split_is_reproducible_and_disjoint` | Dataset preparation not implemented |

These are pre-written specs for planned work — they will start counting as
real pass/fail once that work lands.

## 5. Defects Found — `clario-ml-sidecar` (4 failures)

All 4 failures trace to a **single root cause**, found via
`git log -p app/graph/routing_node.py`:

> Commit `ea3cb59` ("Fix bugs: UI submission hang, Sidecar infinite loop,
> HF Token authentication, cache hit routing crash, and TS typing issues",
> 2026-08-08) rewrote `decide_routing()` in
> [`app/graph/routing_node.py`](../../clario-ml-sidecar/app/graph/routing_node.py).
> The previous version returned `"both"` when confidence was low or when a
> ticket text matched both technical and billing keywords, so an ambiguous
> ticket would be routed to **both** specialist agents. The rewrite replaced
> every path that used to return `"both"` with `"escalation"` instead — but
> the corresponding tests, and the rest of the codebase, were not updated to
> match.

**Impact:** `decide_routing()` can now never return `"both"`. But
`app/graph/state.py:36` still types `routing_decision` as
`Literal["technical", "billing", "both"]`, and both
`app/graph/escalation_node.py` (lines 31, 36, 52) and
`app/graph/validation_node.py:167` still contain live branches keyed on
`routing_decision == "both"`. That means the entire **dual-domain routing
path** — sending one ambiguous ticket to both specialists and escalating
only if both drafts come back low-relevance (`dual_domain_low_relevance`) —
is dead code today. Ambiguous tickets are escalated immediately instead of
getting a dual-specialist attempt first.

**Severity:** Important (behavioral regression in the routing feature, not
a crash — the system still produces a safe outcome by escalating, but a
documented product capability is silently unreachable).

| # | Test | File | Expected | Actual |
|---|---|---|---|---|
| 1 | `test_first_pass_routes_technical_billing_low_confidence_and_missing_category` | `tests/graph/test_routing_node.py:25` | `"both"` for `classification_confidence=0.5` | `"escalation"` |
| 2 | `test_ambiguous_payment_failure_routes_to_both_on_first_pass` | `tests/graph/test_routing_node.py:33` | `"both"` for text matching both domains | `"technical"` |
| 3 | `test_ambiguous_payment_routes_both_initially` | `tests/graph/test_graph_integration.py:67` | `routing_decision == "both"`, routing invoked once | `"technical"` |
| 4 | `test_dual_low_relevance_never_reinvokes_routing` | `tests/graph/test_graph_integration.py:78` | `"dual_domain_low_relevance"` in escalation reasons | `["misroute_unresolved"]` |

Full tracebacks are in [`ml-sidecar/test-log.txt`](ml-sidecar/test-log.txt).

**Disposition:** Not fixed as part of this testing pass — this report's
scope is executing and documenting results, not remediation. Recommend
routing this to `systematic-debugging` as a follow-up: either restore the
`"both"` branch in `decide_routing()` (if dual-domain routing is still
wanted) or remove the now-dead `"both"` handling from `state.py`,
`escalation_node.py`, and `validation_node.py` plus delete/update the 4
tests (if the product decision was to drop dual-domain routing entirely).

## 6. `ml_finetuning` and `frontend` — no defects found

Both suites passed 100% of executed tests with no failures.

## 7. Comments

- Coverage is real but partial: the specialist-agent and RAG-tool gaps
  above (§4) mean the LangGraph pipeline's two most business-critical
  nodes — actually drafting a technical or billing response — have no
  executable unit tests yet, only a skipped placeholder each. Everything
  around them (classification, routing, validation, judging, escalation,
  resolution, caching, PII redaction, circuit breaker) is covered.
- No test infrastructure changes were made to produce these results —
  every suite ran with its existing, pre-committed configuration.

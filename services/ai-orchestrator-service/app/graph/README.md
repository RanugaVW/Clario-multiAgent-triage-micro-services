# Validation Node — v3 failure_type classification

## Always runs (free)

run_policy_checks() — PII-in-draft, length, overcommitment, fallback-phrase enforcement.
If a specialist's draft is None (total LLM failure), skips straight to
failed_rules=["draft_generation_failed"], no judge call.

## Gated (costs money) — decide_judge_call()

Low RAG score -> mandatory judge call (per domain). High score -> random sample only
(17.5% default). Otherwise skipped (judge_skipped=True, logged for evaluation).

## failure_type — the single decision signal graph_builder reads

- "dependency_failure" — an LLM call failed outright (draft generation or judge call
  itself). Escalates immediately. No reroute, no reflection.
- "misroute" + needs_reroute=True — single-domain ticket, wrong specialist, first
  attempt. Reroutes once via routing_node's explicit flip.
- "misroute" + needs_reroute=False + reroute_attempted=True — either an unresolved
  single-domain reroute or a "both" ticket where both specialists had low relevance.
  Escalates immediately to human review.
- "quality" / "policy" — right specialist, fixable draft issue. Bounded reflection retry.
- "none" — validation passed, proceeds to normal escalation-trigger check.

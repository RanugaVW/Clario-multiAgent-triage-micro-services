# Agent Orchestration Service

## Agentic pattern

Multi-Agent Collaboration, single-round. Supervisor (classification + routing)
dispatches once to one or both specialists. No iterative agent-to-agent negotiation.

## v3 status log

- [x] state.py with failure_type + dual-domain fields
- [x] redaction node
- [x] classification node (Gemini stand-in)
- [x] routing node (with explicit reroute-flip logic)
- [x] RAG tool + KB index
- [x] specialist agents (with per-domain relevance flagging)
- [x] validation node (gated judge call + failure_type classification)
- [x] reflection node (bounded)
- [x] escalation node (incl. dual-domain-failure branch)
- [x] handoff node
- [x] graph wired end-to-end, loop-safety tested
- [x] exposed as FastAPI service (backend-only, no frontend yet — see Phase N note)

## state.py — key v3 addition: failure_type

This field is set ONLY by validation_node and is what graph_builder's conditional
routing reads to decide the next step:

- "misroute" -> reroute (capped at 1 attempt) or escalate if already rerouted
- "quality" / "policy" -> bounded reflection retry, then escalate if cap reached
- "dependency_failure" -> immediate escalation (an external call failed after retries)
- "none" -> validation passed, proceed to escalation-trigger check as normal

## redaction_tool.py

Runs first, unconditionally, every ticket. Downstream nodes read redacted_text only.

## classification_tool.py [TEMPORARY]

Gemini stand-in for the fine-tuned model. On total API failure, falls back to a keyword
heuristic (source="gemini_stand_in_fallback") rather than crashing. Swap later: replace
classify_ticket()'s body with an httpx call to {FINE_TUNED_LLM_URL}/classify - no other
file changes.
Status: [ ] swapped to fine-tuned model

## routing_node.py — v3 reroute-flip fix

Two paths: (1) first-time routing via decide_routing() (pure, unit-tested, includes the
dual-keyword "both" trigger tuned so ambiguous tickets like "payment failed, money taken"
route to both specialists immediately rather than relying on reroute-repair), and
(2) reroute path, which is an EXPLICIT domain flip (technical<->billing), never a
re-derivation. "both" routing never reroutes - see validation_node/escalation_node for
how dual-domain failures are handled instead (straight to human review, no flip possible).

## check_relevance() — three callers

1. Specialist agents — flags low_relevance_flags[domain] per ticket
2. validation_node — gates the judge call AND feeds failure_type classification
3. cache_check_node (if built) — near-duplicate confidence check

# Specialist Agents

Each: retrieves KB context -> records top score + relevance flag -> builds grounded
prompt (injects prior critique if this is a reflection retry) -> drafts via Gemini.
On total LLM failure (not just a low-quality answer), writes None into agent_drafts[domain]
instead of fabricating a string - validation_node treats this as failure_type=
"dependency_failure", which escalates immediately rather than looping.

## reflection_node.py

Only triggered for failure_type "quality"/"policy" - never for "misroute" (a redraft by
the same wrong-domain specialist won't fix a relevance problem, so misroutes go straight
to reroute-or-escalate) or "dependency_failure" (a redraft can't fix a broken API call).
Capped at MAX_REFLECTION_ATTEMPTS (default 2).

## escalation_node.py

v3 reason strings distinguish WHY escalation happened, visible to the human reviewer:
urgent_priority / strongly_negative_sentiment / low_confidence_dual_domain /
dependency_failure / dual_domain_low_relevance / misroute_unresolved /
reflection_cap_reached. Per project requirement: if BOTH specialists come back with low
RAG relevance on a "both"-routed ticket, this ALWAYS escalates to human review - there is
no auto-send path for that case, regardless of anything else.

## handoff_node.py

Produces a plain dict - the eventual API/frontend contract, not built yet. During
development, this is what you inspect directly (via test output or a POST to
/process_ticket in Postman) to confirm the pipeline behaved correctly. reasoning_summary
is written to be human-readable on its own, since you don't have a review screen to
render it nicely yet.

## graph_builder.py — v3 loop-safety summary

Exactly two loop-back edges exist, and both are structurally incapable of looping more
than once: reroute is reachable only before routing_node's flip sets reroute_attempted;
reflection is bounded by MAX_REFLECTION_ATTEMPTS. A "both"-routed ticket where both
domains fail relevance goes directly to escalation, never into either loop.

## Running locally

uvicorn app.main:app --reload --port 8600

## Endpoints

- POST /process_ticket {"ticket_id": str, "raw_text": str} -> final TicketState as JSON
- GET /health

## Current integration status

Includes a minimal local testing interface at `GET /`; no production frontend, API Gateway,
or database is wired in yet. The service is also callable directly via curl/Postman for
development and testing. When Member 3's API
Gateway is ready, it calls POST /process_ticket exactly as documented here - no changes
expected on this side unless the TicketState shape itself changes (coordinate first).

## Known limitations

- Classification uses Gemini as a stand-in (swap = one function, see tools/README.md)
- Judge call is gated (RAG score + random sample), not run on every ticket
- Reroute capped at 1 attempt; both-domains-low-relevance tickets never reroute, they
  escalate directly (see graph/README.md)
- Reflection capped at MAX_REFLECTION_ATTEMPTS (default 2)
- Circuit breaker and semantic caching are "build if time allows"

## circuit_breaker.py

Reuses the existing "dependency_failure" -> escalate path - a tripped breaker sets the
same failure_type an actual failed call would, just without wasting time attempting a call
known to be broken. No new escalation logic needed.

"""Policy validation, gated LLM judging, and v3 failure-type classification."""

from __future__ import annotations

import asyncio
import json
import os
import random

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.graph.state import TicketState
from app.tools.redaction_tool import mask_pii

load_dotenv()
FALLBACK_PHRASE = "I don't have enough information to resolve this"
OVERCOMMITMENTS = ("guarantee", "definitely", "promise", "will refund")


def run_policy_checks(draft: str | None, retrieved_context: list[dict], pii_found: list) -> dict:
    """Run free output-policy checks before any optional judge call."""
    if draft is None:
        return {"passed": False, "failed_rules": ["draft_generation_failed"]}
    failed: list[str] = []
    if not draft.strip():
        failed.append("empty_draft")
    if len(draft) > 2000:
        failed.append("draft_too_long")
    if mask_pii(draft)[1]:
        failed.append("pii_in_draft")
    context_text = " ".join(item.get("text", "").lower() for item in retrieved_context)
    if any(phrase in draft.lower() and phrase not in context_text for phrase in OVERCOMMITMENTS):
        failed.append("unsupported_overcommitment")
    threshold = float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))
    context_is_weak = not retrieved_context or all(float(item.get("score", 0)) < threshold for item in retrieved_context)
    if context_is_weak and FALLBACK_PHRASE.lower() not in draft.lower():
        failed.append("missing_low_context_fallback")
    return {"passed": not failed, "failed_rules": failed}


def decide_judge_call(rag_top_score: dict, domain: str, random_seed: int | None = None) -> tuple[bool, str]:
    """Gate the per-domain judge by weak retrieval or random sampling."""
    if float(rag_top_score.get(domain, 0.0)) < float(os.getenv("RAG_SCORE_THRESHOLD", "0.3")):
        return True, "low_rag_score"
    sample = random.Random(random_seed).random() if random_seed is not None else random.random()
    return (True, "random_sample") if sample < float(os.getenv("JUDGE_RANDOM_SAMPLE_RATE", "0.175")) else (False, "none")


async def llm_judge_check(draft: str, ticket_text: str, retrieved_context: list[dict]) -> dict:
    """Run one structured Gemini judge request, returning inconclusive on failure."""
    context = "\n".join(f"[{item.get('source_file')}] {item.get('text')}" for item in retrieved_context)
    prompt = ("Judge this support draft against the ticket and context. Return JSON only: "
              '{"on_topic":bool,"grounded_in_context":bool,"appropriate_tone":bool,"reasoning":str}.\n'
              f"Ticket: {ticket_text}\nDraft: {draft}\nContext: {context}")
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(client.aio.models.generate_content(
                    model=os.getenv("GEMINI_JUDGE_MODEL", "gemini-2.5-flash-lite"), contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")), timeout=10)
                result = json.loads(response.text)
                if all(isinstance(result.get(key), bool) for key in ("on_topic", "grounded_in_context", "appropriate_tone")):
                    return result
                raise ValueError("invalid judge schema")
            except Exception:
                if attempt == 2:
                    break
                await asyncio.sleep(2**attempt)
    except Exception:
        pass
    return {"on_topic": None, "grounded_in_context": None, "appropriate_tone": None, "reasoning": "judge_call_failed"}


async def validation_node(state: TicketState) -> TicketState:
    """Validate all drafted domains and set the graph's single failure decision signal."""
    results: dict[str, dict] = {}
    drafts = state.get("agent_drafts", {})
    for domain, draft in drafts.items():
        rules = run_policy_checks(draft, state.get("retrieved_context", {}).get(domain, []), state.get("pii_found", []))
        result = {**rules, "judge_ran": False, "judge_skipped": False, "judge_reason": "none"}
        if draft is not None:
            should_judge, reason = decide_judge_call(state.get("rag_top_score", {}), domain)
            result["judge_reason"] = reason
            if should_judge:
                judge = await llm_judge_check(draft, state.get("redacted_text", ""), state.get("retrieved_context", {}).get(domain, []))
                result.update(judge, judge_ran=True)
                if judge["on_topic"] is None:
                    result["failed_rules"] = [*result["failed_rules"], "judge_unavailable"]
                    result["passed"] = False
                else:
                    result["passed"] = rules["passed"] and all(judge[key] for key in ("on_topic", "grounded_in_context", "appropriate_tone"))
            else:
                result["judge_skipped"] = True
        results[domain] = result

    domains = list(drafts)
    failed = any(not result["passed"] for result in results.values())
    flags = state.get("low_relevance_flags", {})
    dependency_failure = any("draft_generation_failed" in result["failed_rules"] for result in results.values())
    all_judges_unavailable = bool(domains) and all(
        result["judge_ran"] and result.get("on_topic") is None for result in results.values()
    )
    failure_type, needs_reroute, reroute_attempted = "none", False, state.get("reroute_attempted", False)
    dual_low = False
    if dependency_failure or all_judges_unavailable:
        failure_type = "dependency_failure"
    elif state.get("routing_decision") == "both" and domains and failed and all(flags.get(domain, False) for domain in domains):
        # Both domains failed relevance: no third specialist exists, so exhaust rerouting now.
        failure_type, reroute_attempted, dual_low = "misroute", True, True
    elif state.get("routing_decision") in {"technical", "billing"} and domains:
        domain, result = domains[0], results[domains[0]]
        misrouted = failed and result.get("on_topic") is False and flags.get(domain, False)
        if misrouted:
            failure_type, needs_reroute = "misroute", not reroute_attempted
        elif failed:
            failure_type = "quality" if result["judge_ran"] else "policy"
    elif failed:
        failure_type = "quality" if any(result["judge_ran"] for result in results.values()) else "policy"
    return {**state, "validation_result": results, "failure_type": failure_type,
            "needs_reroute": needs_reroute, "reroute_attempted": reroute_attempted,
            "dual_domain_low_confidence": dual_low}

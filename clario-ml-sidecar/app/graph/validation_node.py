"""Policy validation, local heuristic judging, and v3 failure-type classification."""

from __future__ import annotations

import os
import random

from app.graph.state import TicketState
from app.tools.redaction_tool import mask_pii
import re

FALLBACK_PHRASE = "I don't have enough information to resolve this"
OVERCOMMITMENTS = ("guarantee", "definitely", "promise", "will refund")
# Drafts are structured with bracketed all-caps section markers such as
# [INTERNAL TECHNICAL REPORT]. spaCy NER reads those as ORG entities, so scanning
# them for PII fails every draft on pii_in_draft. Strip the scaffolding first.
SECTION_MARKER_PATTERN = re.compile(r"\[[A-Z][A-Z0-9 /_-]*\]")

def check_for_technical_leaks(draft: str) -> bool:
    """
    Data Loss Prevention (DLP) Guardrail: 
    Checks the [CUSTOMER RESPONSE] section for code-like patterns.
    Returns True if a leak is detected, False otherwise.
    """
    if "[CUSTOMER RESPONSE]" not in draft:
        return False
        
    customer_part = draft.split("[CUSTOMER RESPONSE]")[-1].strip()
    
    # Heuristics for catching technical leaks
    leak_patterns = [
        r'\b[a-z]+[A-Z][a-z]+[A-Z]?[a-z]*\b',  # camelCase variables
        r'\b\w+\.(java|ts|tsx|js|py)\b',       # File extensions
        r'\b(SELECT|UPDATE|INSERT|DELETE)\b.*(?i:FROM|INTO)', # SQL keywords
        r'(\/var\/www|\/usr\/local|C:\\Users\\)', # Common file paths
        r'Exception:|Error:|Traceback',        # Raw error outputs
    ]
    
    for pattern in leak_patterns:
        if re.search(pattern, customer_part):
            return True
            
    return False

def run_policy_checks(draft: str | None, retrieved_context: list[dict], pii_found: list) -> dict:
    """Run free output-policy checks before any optional judge call."""
    if draft is None:
        return {"passed": False, "failed_rules": ["draft_generation_failed"]}
    failed: list[str] = []
    if not draft.strip():
        failed.append("empty_draft")
    if len(draft) > 2000:
        failed.append("draft_too_long")
    if mask_pii(SECTION_MARKER_PATTERN.sub(" ", draft))[1]:
        failed.append("pii_in_draft")
    context_text = " ".join(item.get("text", "").lower() for item in retrieved_context)
    if any(phrase in draft.lower() and phrase not in context_text for phrase in OVERCOMMITMENTS):
        failed.append("unsupported_overcommitment")
    threshold = float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))
    context_is_weak = not retrieved_context or all(float(item.get("score", 0)) < threshold for item in retrieved_context)
    if context_is_weak and FALLBACK_PHRASE.lower() not in draft.lower():
        failed.append("missing_low_context_fallback")
        
    if check_for_technical_leaks(draft):
        failed.append("technical_leak_detected")
        
    return {"passed": not failed, "failed_rules": failed}


def decide_judge_call(rag_top_score: dict, domain: str, random_seed: int | None = None) -> tuple[bool, str]:
    """Gate the per-domain judge by weak retrieval or random sampling."""
    if float(rag_top_score.get(domain, 0.0)) < float(os.getenv("RAG_SCORE_THRESHOLD", "0.3")):
        return True, "low_rag_score"
    sample = random.Random(random_seed).random() if random_seed is not None else random.random()
    return (True, "random_sample") if sample < float(os.getenv("JUDGE_RANDOM_SAMPLE_RATE", "0.175")) else (False, "none")


async def llm_judge_check(draft: str, ticket_text: str, retrieved_context: list[dict]) -> dict:
    """Local heuristic judge — no external API needed.

    Checks:
    - on_topic: key ticket words appear in the draft
    - grounded_in_context: draft content overlaps with retrieved context
    - appropriate_tone: no overly aggressive / inappropriate language
    """
    ticket_words = set(ticket_text.lower().split())
    draft_lower = draft.lower()

    # on_topic: at least 2 meaningful ticket words appear in the draft
    stopwords = {"i", "a", "the", "is", "my", "to", "and", "of", "in", "it", "me", "was", "for", "on", "are"}
    meaningful = [w for w in ticket_words if len(w) > 3 and w not in stopwords]
    on_topic = sum(1 for w in meaningful if w in draft_lower) >= max(1, len(meaningful) // 4)

    # grounded_in_context: draft shares words with context OR says it has no info
    context_text = " ".join(item.get("text", "").lower() for item in retrieved_context)
    context_words = set(context_text.split())
    overlap = sum(1 for w in set(draft_lower.split()) if w in context_words and w not in stopwords)
    fallback_used = FALLBACK_PHRASE.lower() in draft_lower
    grounded_in_context = fallback_used or overlap >= 3

    # appropriate_tone: no aggressive language
    bad_phrases = ("i refuse", "this is stupid", "you idiot", "bad request")
    appropriate_tone = not any(p in draft_lower for p in bad_phrases)

    return {
        "on_topic": on_topic,
        "grounded_in_context": grounded_in_context,
        "appropriate_tone": appropriate_tone,
        "reasoning": "local_heuristic_judge",
    }


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

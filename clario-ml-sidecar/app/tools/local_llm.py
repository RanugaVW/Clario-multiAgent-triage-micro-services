"""Local inference — fully offline, zero model downloads required.

Classification: Enhanced keyword + rule-based classifier (instant, <1ms).
Draft generation: RAG-context template synthesizer (instant, grounded, no hallucinations).

No HuggingFace models are loaded at runtime. The sentence-transformers model
used by rag_tool.py (all-MiniLM-L6-v2) is the ONLY model in this pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# RAG-based draft synthesis — instant, grounded, no model needed
# ──────────────────────────────────────────────────────────────────────────────

def _parse_specialist_prompt(prompt: str) -> tuple[str, list[dict]]:
    """Extract ticket text and context chunks from the specialist prompt string."""
    ticket_text = ""
    context_chunks: list[dict] = []

    if "Ticket:" in prompt and "Retrieved context:" in prompt:
        parts = prompt.split("Retrieved context:")
        ticket_part = parts[0]
        context_raw = parts[1].strip() if len(parts) > 1 else ""

        if "Ticket:" in ticket_part:
            ticket_text = ticket_part.split("Ticket:")[-1].strip()

        # Parse each "Source: <file>\n<text>" block
        for block in context_raw.split("\nSource:"):
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n", 1)
            source = lines[0].strip() if lines else "unknown"
            text = lines[1].strip() if len(lines) > 1 else ""
            if text:
                context_chunks.append({"source": source, "text": text})

    return ticket_text.strip(), context_chunks


def _extract_actionable_sentences(text: str, max_sentences: int = 3) -> list[str]:
    """Pull out the most actionable sentences from a KB chunk."""
    action_starters = (
        "check", "clear", "ensure", "visit", "contact", "please", "try",
        "disable", "use", "open", "go to", "restart", "update", "if you",
        "you can", "you may", "refund", "our system", "this may",
    )
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    action = [s for s in sentences if any(s.lower().startswith(k) for k in action_starters)]
    combined = action + [s for s in sentences if s not in action]
    return [s + "." for s in combined[:max_sentences] if len(s) > 15]


_FALLBACK_MSG = "I don't have enough information to resolve this."

_OPENERS = {
    "technical": "Thank you for reaching out. I'm sorry to hear you're experiencing a technical issue.",
    "billing":   "Thank you for contacting us. I understand how concerning a billing issue can be.",
    "account":   "Thank you for reaching out. I'll help you resolve your account issue right away.",
    "general":   "Thank you for contacting support. I'm happy to help.",
}


def generate_draft(prompt: str) -> str:
    """Synthesize a professional support response directly from RAG context.

    Instant — no model loading, no network calls.
    Only uses sentences grounded in the retrieved KB chunks.
    Returns the canonical low-context fallback if no context was retrieved.
    """
    ticket_text, context_chunks = _parse_specialist_prompt(prompt)

    # Determine domain from the prompt header
    domain = "general"
    pl = prompt.lower()
    if "billing" in pl[:80]:
        domain = "billing"
    elif "technical" in pl[:80]:
        domain = "technical"
    elif "account" in pl[:80]:
        domain = "account"

    if not context_chunks or not ticket_text:
        return _FALLBACK_MSG

    opener = _OPENERS.get(domain, _OPENERS["general"])

    # Gather actionable sentences from top 2 chunks
    steps: list[str] = []
    for chunk in context_chunks[:2]:
        steps.extend(_extract_actionable_sentences(chunk["text"], max_sentences=2))

    if not steps:
        return _FALLBACK_MSG

    body_lines = ["Here are some steps that should resolve your issue:"]
    for i, step in enumerate(steps[:4], 1):
        body_lines.append(f"  {i}. {step}")

    closing = (
        "If the issue persists after trying these steps, "
        "please reply to this message and we'll escalate to a specialist."
    )

    return "\n\n".join([opener, "\n".join(body_lines), closing])


# ──────────────────────────────────────────────────────────────────────────────
# Keyword-based classifier — instant, no model, no download
# ──────────────────────────────────────────────────────────────────────────────

_CATEGORIES = ["Technical", "Billing", "Account", "General", "Other"]
_PRIORITIES_BY_CATEGORY = {
    "Billing": "High",
    "Technical": "Medium",
    "Account": "Medium",
    "General": "Low",
    "Other": "Low",
}

_KEYWORDS: dict[str, set[str]] = {
    "Billing": {
        "payment", "charged", "charge", "refund", "invoice", "billing",
        "billed", "bank", "money", "deducted", "fee", "subscription", "price",
        "cost", "transaction", "credit", "card",
    },
    "Account": {
        "login", "password", "account", "sign in", "signin", "profile",
        "verify", "locked", "access", "username", "email", "register",
        "forgot", "reset", "2fa", "authentication",
    },
    "Technical": {
        "error", "crash", "bug", "failed", "not working", "issue", "broken",
        "video", "stream", "load", "slow", "download", "upload", "app",
        "website", "page", "screen", "freeze", "glitch", "connection",
    },
}

_NEGATIVE_WORDS = {
    "failed", "broken", "error", "cannot", "can't", "not", "never",
    "wrong", "bad", "terrible", "awful", "worst", "frustrat", "disappoint",
    "upset", "angry", "stolen", "fraud", "scam",
}


def classify_ticket_local(text: str) -> dict[str, Any]:
    """Classify a ticket using enhanced keyword rules — instant, no model needed.

    Returns a dict with: category, priority, sentiment, confidence, source.
    """
    t = text.lower()

    # Category — check each domain's keywords
    scores: dict[str, int] = {}
    for cat, words in _KEYWORDS.items():
        scores[cat] = sum(1 for w in words if w in t)

    best_cat = max(scores, key=lambda k: scores[k])
    category = best_cat if scores[best_cat] > 0 else "General"
    confidence = min(0.5 + scores.get(category, 0) * 0.1, 0.95)

    # Sentiment
    neg_count = sum(1 for w in _NEGATIVE_WORDS if w in t)
    if neg_count >= 3:
        sentiment = "Strongly Negative"
    elif neg_count >= 1:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    # Priority — base from category, boost for strong negative sentiment
    priority = _PRIORITIES_BY_CATEGORY.get(category, "Low")
    if sentiment == "Strongly Negative" and priority in ("Low", "Medium"):
        priority = "High"
    elif sentiment == "Negative" and priority == "Low":
        priority = "Medium"

    return {
        "category": category,
        "priority": priority,
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "source": "keyword_classifier",
    }

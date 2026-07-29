"""Temporary Gemini classifier with a deterministic graceful fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
_CATEGORIES = {"Technical", "Billing", "Account", "General", "Other"}
_PRIORITIES = {"Low", "Medium", "High", "Urgent"}
_SENTIMENTS = {"Positive", "Neutral", "Negative", "Strongly Negative"}
_KEYWORDS = {
    "Billing": {"payment", "charged", "charge", "refund", "invoice", "billing", "billed", "bank"},
    "Account": {"login", "password", "account", "sign in", "profile", "verify"},
    "Technical": {"error", "crash", "bug", "failed", "not working", "issue", "broken"},
}
_PROMPT = (
    "Classify this support ticket. Return JSON only with exactly these keys: category "
    "(Technical|Billing|Account|General|Other), priority (Low|Medium|High|Urgent), "
    "sentiment (Positive|Neutral|Negative|Strongly Negative), and confidence (0 to 1)."
    "\n\nTicket:\n"
)


def _fallback_classification(redacted_text: str) -> dict[str, Any]:
    """Return the safe keyword-based result used when Gemini is unavailable."""
    text = redacted_text.lower()
    category = next(
        (name for name, words in _KEYWORDS.items() if any(word in text for word in words)),
        "General",
    )
    return {
        "category": category,
        "priority": "Medium",
        "sentiment": "Neutral",
        "confidence": 0.0,
        "source": "gemini_stand_in_fallback",
    }


def _validate_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate Gemini JSON before it can enter shared state."""
    category, priority, sentiment = payload.get("category"), payload.get("priority"), payload.get("sentiment")
    confidence = payload.get("confidence")
    if category not in _CATEGORIES or priority not in _PRIORITIES or sentiment not in _SENTIMENTS:
        raise ValueError("Gemini returned an unsupported classification label")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("Gemini returned an invalid confidence")
    return {
        "category": category,
        "priority": priority,
        "sentiment": sentiment,
        "confidence": float(confidence),
        "source": "gemini_stand_in",
    }


async def classify_ticket(redacted_text: str) -> dict[str, Any]:
    """Classify a redacted ticket with Gemini; degrade safely after two retries."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("Gemini classification unavailable: GEMINI_API_KEY is not configured")
        return _fallback_classification(redacted_text)

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_CLASSIFY_MODEL", "gemini-2.5-flash-lite")
    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=_PROMPT + redacted_text,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                ),
                timeout=10,
            )
            return _validate_result(json.loads(response.text))
        except Exception as error:  # API, timeout, and malformed output all retry.
            if attempt == 2:
                logger.warning("Gemini classification failed after retries: %s", error)
                break
            await asyncio.sleep(2**attempt)
    return _fallback_classification(redacted_text)

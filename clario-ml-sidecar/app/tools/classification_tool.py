"""Ticket classifier — the fine-tuned Llama-3.2 v2 adapter (see local_llm.py).

Falls back to Gemini, with the same label taxonomy, if the local model can't
load or run (e.g. no CUDA GPU, as in the CPU-only Docker image).
"""

from __future__ import annotations

import logging
from typing import Any

from app.tools.local_llm import classify_ticket_local

logger = logging.getLogger(__name__)


async def classify_ticket(redacted_text: str) -> dict[str, Any]:
    """Classify a redacted ticket; returns category (comma-joined), categories (list),
    priority, sentiment, confidence, source."""
    import asyncio
    # run_in_executor so the blocking model call doesn't stall the event loop
    result = await asyncio.get_event_loop().run_in_executor(
        None, classify_ticket_local, redacted_text
    )
    logger.info(
        "Classification: category=%s priority=%s sentiment=%s confidence=%.2f source=%s",
        result["category"], result["priority"], result["sentiment"],
        result["confidence"], result["source"],
    )
    return result

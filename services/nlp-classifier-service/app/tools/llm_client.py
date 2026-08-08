"""Draft-generation client — uses local HuggingFace models (no external API needed).

The heavy model is loaded once on first use and cached in-process.
"""

from __future__ import annotations

import asyncio
import logging

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker
from app.tools.local_llm import generate_draft

logger = logging.getLogger(__name__)


async def generate(prompt: str) -> str:
    """Generate a specialist draft using a local HuggingFace model.

    Runs the CPU-bound inference in a thread-pool so the FastAPI event loop
    is not blocked.  Raises RuntimeError / CircuitBreakerOpenError on failure.
    """
    breaker = get_breaker("local_draft")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("local_draft circuit breaker is open")
    try:
        # offload blocking inference to a thread so async loop stays free
        text = await asyncio.get_event_loop().run_in_executor(None, generate_draft, prompt)
        breaker.record_success()
        return text
    except Exception as error:
        logger.warning("Local draft generation failed: %s", error)
        breaker.record_failure()
        raise RuntimeError("draft generation failed") from error

"""Draft-generation client — wraps the real Gemini-backed draft generator in
local_llm.py behind a circuit breaker and a thread-pool offload.
"""

from __future__ import annotations

import asyncio
import logging

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker
from app.tools.local_llm import DraftGenerationError, generate_draft

logger = logging.getLogger(__name__)


async def generate(prompt: str) -> tuple[str, int]:
    """Generate a specialist draft.

    Runs the blocking model call in a thread-pool so the FastAPI event loop
    is not blocked. Returns (draft_text, attempts_used). Raises RuntimeError
    (with an `.attempts` attribute carrying the real attempt count, so
    callers can report accurate LLM-call telemetry even on failure) or
    CircuitBreakerOpenError (0 attempts - the breaker blocked before any
    real call was made).
    """
    breaker = get_breaker("local_draft")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("local_draft circuit breaker is open")
    try:
        # offload blocking inference to a thread so async loop stays free
        text, attempts = await asyncio.get_event_loop().run_in_executor(None, generate_draft, prompt)
        breaker.record_success()
        return text, attempts
    except DraftGenerationError as error:
        logger.warning("Local draft generation failed: %s", error)
        breaker.record_failure()
        wrapped = RuntimeError("draft generation failed")
        wrapped.attempts = error.attempts
        raise wrapped from error
    except Exception as error:
        logger.warning("Local draft generation failed: %s", error)
        breaker.record_failure()
        wrapped = RuntimeError("draft generation failed")
        wrapped.attempts = 1  # unexpected error outside generate_draft's own retry loop
        raise wrapped from error

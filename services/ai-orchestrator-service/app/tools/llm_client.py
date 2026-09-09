<<<<<<< HEAD
"""Draft-generation client — wraps the real Gemini-backed draft generator in
local_llm.py behind a circuit breaker and a thread-pool offload.
=======
"""Draft-generation client — uses local HuggingFace models (no external API needed).

The heavy model is loaded once on first use and cached in-process.
>>>>>>> origin/add/voice-to-text-service
"""

from __future__ import annotations

import asyncio
import logging

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker
<<<<<<< HEAD
from app.tools.local_llm import DraftGenerationError, generate_draft
=======
from app.tools.local_llm import generate_draft
>>>>>>> origin/add/voice-to-text-service

logger = logging.getLogger(__name__)


<<<<<<< HEAD
async def generate(prompt: str) -> tuple[str, int]:
    """Generate a specialist draft.

    Runs the blocking model call in a thread-pool so the FastAPI event loop
    is not blocked. Returns (draft_text, attempts_used). Raises RuntimeError
    (with an `.attempts` attribute carrying the real attempt count, so
    callers can report accurate LLM-call telemetry even on failure) or
    CircuitBreakerOpenError (0 attempts - the breaker blocked before any
    real call was made).
=======
async def generate(prompt: str) -> str:
    """Generate a specialist draft using a local HuggingFace model.

    Runs the CPU-bound inference in a thread-pool so the FastAPI event loop
    is not blocked.  Raises RuntimeError / CircuitBreakerOpenError on failure.
>>>>>>> origin/add/voice-to-text-service
    """
    breaker = get_breaker("local_draft")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("local_draft circuit breaker is open")
    try:
        # offload blocking inference to a thread so async loop stays free
<<<<<<< HEAD
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
=======
        text = await asyncio.get_event_loop().run_in_executor(None, generate_draft, prompt)
        breaker.record_success()
        return text
    except Exception as error:
        logger.warning("Local draft generation failed: %s", error)
        breaker.record_failure()
        raise RuntimeError("draft generation failed") from error
>>>>>>> origin/add/voice-to-text-service

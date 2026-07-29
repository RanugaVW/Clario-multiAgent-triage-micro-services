"""Gemini draft-generation client with bounded retries and no fabricated fallback."""

from __future__ import annotations

import asyncio
import logging
import os

from google import genai
from dotenv import load_dotenv

from app.tools.circuit_breaker import CircuitBreakerOpenError, get_breaker

logger = logging.getLogger(__name__)
load_dotenv()


async def generate(prompt: str) -> str:
    """Generate a specialist draft or raise after the initial call and two retries."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    breaker = get_breaker("gemini_draft")
    if not breaker.allow_request():
        raise CircuitBreakerOpenError("gemini_draft circuit breaker is open")
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_DRAFT_MODEL", "gemini-2.5-flash")
    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=model, contents=prompt), timeout=20
            )
            if not response.text or not response.text.strip():
                raise ValueError("Gemini returned an empty draft")
            breaker.record_success()
            return response.text.strip()
        except Exception as error:
            if attempt == 2:
                logger.warning("Gemini draft generation failed after retries: %s", error)
                breaker.record_failure()
                raise RuntimeError("draft generation failed") from error
            await asyncio.sleep(2**attempt)
    raise RuntimeError("draft generation failed")

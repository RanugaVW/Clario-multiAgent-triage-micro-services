"""Gemini-based OCR extraction: both direct image and text-only cleanup paths."""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_OCR_CLEANUP_PROMPT_TEMPLATE = (
    "You are cleaning up noisy OCR output from a customer's screenshot. "
    "Both inputs below have already had personal information redacted - "
    "any [REDACTED_X] token is intentional, not an error.\n\n"
    "The customer described their issue as:\n{customer_text}\n\n"
    "The following text was extracted via OCR from their attached "
    "screenshot and may contain unrelated interface text (buttons, menus, "
    "timestamps, navigation) mixed in with the real error:\n{ocr_text}\n\n"
    "Identify and return ONLY the real error message, exception, or stack "
    "trace - using the customer's description above as a hint for what "
    "kind of error to expect. Do not summarize, paraphrase, or add "
    "commentary - reproduce the error text as it appears in the OCR "
    "output. If no real error can be identified, respond with exactly: "
    "NO_ERROR_TEXT_FOUND"
)


async def extract_error_from_ocr_text(masked_ocr_text: str, masked_customer_text: str) -> str:
    """Text-only Gemini call - both inputs must already be PII-masked by
    the caller (see app/tools/redaction_tool.mask_pii). No image is ever
    sent here; this is the primary extraction path, with extract_error_text
    (direct image) kept as main.py's fallback when this returns ""."""
    try:
        client = genai.Client()
        prompt = _OCR_CLEANUP_PROMPT_TEMPLATE.format(
            customer_text=masked_customer_text, ocr_text=masked_ocr_text
        )
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        text = response.text.strip()
        return "" if text == "NO_ERROR_TEXT_FOUND" else text
    except Exception as e:
        logger.error(f"Gemini OCR-cleanup call failed: {e}")
        return ""

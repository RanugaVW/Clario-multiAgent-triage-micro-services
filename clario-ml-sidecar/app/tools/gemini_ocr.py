"""Production image-attachment extraction. Gemini-only, deliberately - no
torch/transformers/bitsandbytes import here, so production never loads a
vision model into memory. The local Qwen2-VL vision model still exists in
app/tools/local_ocr.py, but is used only by the standalone comparison in
Testing/11-OCR-Vision-Evaluation, never by a real ticket."""

from __future__ import annotations

import base64
import logging
from io import BytesIO

from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)

_ERROR_EXTRACTION_PROMPT = (
    "You are an error-log extractor analyzing a screenshot. Identify and "
    "output ONLY the literal error message(s), exception text, stack trace "
    "lines, or warning/error codes visible in the image. Do not include "
    "button labels, menu items, navigation bars, timestamps, watermarks, "
    "decorative graphics, background patterns, or any other visual noise. "
    "Do not summarize, paraphrase, or add commentary - reproduce the error "
    "text exactly as it appears. If no error text is visible in the image, "
    "respond with exactly: NO_ERROR_TEXT_FOUND"
)


async def extract_error_text(image_base64: str) -> str:
    """Extracts error text from a base64-encoded screenshot via Gemini."""
    try:
        client = genai.Client()
        image_data = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_data)).convert("RGB")

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[image, _ERROR_EXTRACTION_PROMPT],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini OCR extraction failed: {e}")
        return f"OCR Extraction Failed: {e}"

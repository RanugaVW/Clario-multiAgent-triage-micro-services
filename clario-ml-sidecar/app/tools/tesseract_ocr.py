"""Production's local OCR step - no network call, no PII ever leaves the
machine here. Runs before app/tools/redaction_tool.mask_pii() and the
text-only Gemini cleanup call in gemini_ocr.py; see main.py's
background_orchestration for the full pipeline."""

from __future__ import annotations

import base64
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


def extract_raw_text(image_base64: str) -> str:
    """Returns raw (unmasked, possibly noisy) OCR text, or "" on any
    failure - a missing tesseract binary, a corrupt image, or a decode
    error must never raise, since main.py's caller falls back to the
    direct-image Gemini call when this returns nothing usable."""
    try:
        import pytesseract
        from PIL import Image

        image_data = base64.b64decode(image_base64)
        with Image.open(BytesIO(image_data)) as img:
            return pytesseract.image_to_string(img).strip()
    except Exception as e:
        logger.warning(f"Tesseract extraction failed: {e}")
        return ""


def check_tesseract_available() -> bool:
    """Probes for the tesseract binary once (e.g. at startup) so a missing
    installation is a loud, visible log line instead of a per-ticket silent
    degrade to the image-to-Gemini fallback - see main.py's lifespan."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        logger.error(
            f"Tesseract binary not found or not runnable ({e}) - every ticket "
            "attachment will silently fall through to the direct-image Gemini "
            "fallback until this is fixed. Install the tesseract-ocr system "
            "package (see Testing/11-OCR-Vision-Model-Evaluation/README.md's "
            "one-time setup, or the Dockerfile for the production install)."
        )
        return False

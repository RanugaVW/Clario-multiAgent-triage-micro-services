"""extract_raw_text() is production's local, no-network OCR step - it must
never raise, since a missing tesseract binary or a corrupt image must not
break ticket processing (main.py falls back to gemini_ocr.extract_error_text
when this returns nothing usable)."""

import base64
from io import BytesIO

from PIL import Image

from app.tools.tesseract_ocr import extract_raw_text


def _tiny_image_base64() -> str:
    buf = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_extract_raw_text_returns_a_string_for_a_valid_image() -> None:
    result = extract_raw_text(_tiny_image_base64())
    assert isinstance(result, str)


def test_extract_raw_text_returns_empty_string_for_garbage_input() -> None:
    result = extract_raw_text("not-valid-base64-image-data")
    assert result == ""

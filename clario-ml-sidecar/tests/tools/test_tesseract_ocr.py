"""extract_raw_text() is production's local, no-network OCR step - it must
never raise, since a missing tesseract binary or a corrupt image must not
break ticket processing (main.py falls back to gemini_ocr.extract_error_text
when this returns nothing usable)."""

import base64
from io import BytesIO

from PIL import Image

from app.tools.tesseract_ocr import check_tesseract_available, extract_raw_text


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


def test_check_tesseract_available_returns_true_when_binary_is_runnable(monkeypatch) -> None:
    import pytesseract

    monkeypatch.setattr(pytesseract, "get_tesseract_version", lambda: "5.3.0")

    assert check_tesseract_available() is True


def test_check_tesseract_available_returns_false_and_does_not_raise_when_binary_is_missing(monkeypatch) -> None:
    import pytesseract

    def _raise():
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "get_tesseract_version", _raise)

    assert check_tesseract_available() is False

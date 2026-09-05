"""Gemini-based OCR extraction: both direct image and text-only cleanup paths."""

import pytest

from app.tools.gemini_ocr import extract_error_from_ocr_text


class _FakeResponse:
    def __init__(self, text_or_error):
        if isinstance(text_or_error, Exception):
            self._error = text_or_error
            self.text = None
        else:
            self._error = None
            self.text = text_or_error

    def __getattr__(self, name):
        if name == "text":
            if self._error:
                raise self._error
            return self.text
        raise AttributeError(name)


class _FakeModels:
    def __init__(self, text_or_error):
        self._text_or_error = text_or_error

    def generate_content(self, **kwargs):
        return _FakeResponse(self._text_or_error)


class _FakeClient:
    def __init__(self, text_or_error):
        self.models = _FakeModels(text_or_error)


@pytest.mark.asyncio
async def test_extract_error_from_ocr_text_returns_the_models_stripped_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.gemini_ocr.genai.Client",
        lambda: _FakeClient("  KeyError: 'user_id'  "),
    )

    result = await extract_error_from_ocr_text(
        masked_ocr_text="Settings Cancel OK KeyError: 'user_id' Menu Home",
        masked_customer_text="I got this error when logging in",
    )

    assert result == "KeyError: 'user_id'"


@pytest.mark.asyncio
async def test_extract_error_from_ocr_text_degrades_to_empty_string_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.gemini_ocr.genai.Client",
        lambda: _FakeClient(RuntimeError("rate limited")),
    )

    result = await extract_error_from_ocr_text(
        masked_ocr_text="some noisy ocr text",
        masked_customer_text="I got this login issue",
    )

    assert result == ""

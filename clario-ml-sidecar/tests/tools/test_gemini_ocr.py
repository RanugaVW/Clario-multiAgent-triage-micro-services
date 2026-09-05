"""extract_error_text() is production's only image-attachment path (see
app/main.py) - it must never import torch/transformers/bitsandbytes, and
must degrade to an error string rather than raise, since a bad attachment
must never break ticket processing."""

import base64
from io import BytesIO

import pytest
from PIL import Image

from app.tools.gemini_ocr import extract_error_text


def _tiny_image_base64() -> str:
    buf = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, response_or_exc) -> None:
        self._response_or_exc = response_or_exc

    def generate_content(self, **kwargs):
        if isinstance(self._response_or_exc, Exception):
            raise self._response_or_exc
        return _FakeResponse(self._response_or_exc)


class _FakeClient:
    def __init__(self, response_or_exc) -> None:
        self.models = _FakeModels(response_or_exc)


@pytest.mark.asyncio
async def test_extract_error_text_returns_the_models_stripped_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.gemini_ocr.genai.Client",
        lambda: _FakeClient("  ConnectionError: timed out at 0x892  "),
    )

    result = await extract_error_text(_tiny_image_base64())

    assert result == "ConnectionError: timed out at 0x892"


@pytest.mark.asyncio
async def test_extract_error_text_degrades_to_an_error_string_instead_of_raising(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.gemini_ocr.genai.Client",
        lambda: _FakeClient(RuntimeError("rate limited")),
    )

    result = await extract_error_text(_tiny_image_base64())

    assert "rate limited" in result

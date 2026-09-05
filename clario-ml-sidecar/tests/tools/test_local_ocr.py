"""local_ocr.py is no longer used by production (see app/tools/gemini_ocr.py
for that) - it exists solely for the standalone Testing/11 comparison
against a naive OCR baseline. These tests cover the one thing that must
never regress even without a GPU to actually load Qwen2-VL on: the Gemini
fallback, and the OcrResult.backend label the evaluation report depends on
to say which extraction path actually served each image.

The local-model path itself isn't exercised here - it requires a real GPU
with the Qwen2-VL-2B weights loaded (same reasoning as local_llm.py's
classify_ticket_local()).
"""

import base64
import importlib
from io import BytesIO

import pytest
from PIL import Image

from app.tools import local_ocr


def _reload_local_ocr():
    return importlib.reload(local_ocr)


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
async def test_falls_back_to_gemini_and_labels_the_backend_when_local_model_unavailable(monkeypatch) -> None:
    ocr = _reload_local_ocr()
    monkeypatch.setattr(ocr, "_load_model_singleton", lambda: None)  # simulate no GPU/insufficient VRAM
    monkeypatch.setattr(ocr.genai, "Client", lambda: _FakeClient("NullPointerException at line 42"))

    result = await ocr.process_image_async(_tiny_image_base64())

    assert result.backend == "gemini-3.1-flash-lite-fallback"
    assert result.text == "NullPointerException at line 42"


@pytest.mark.asyncio
async def test_reports_both_failed_when_local_model_and_gemini_fallback_both_fail(monkeypatch) -> None:
    ocr = _reload_local_ocr()
    monkeypatch.setattr(ocr, "_load_model_singleton", lambda: None)
    monkeypatch.setattr(ocr.genai, "Client", lambda: _FakeClient(RuntimeError("no network")))

    result = await ocr.process_image_async(_tiny_image_base64())

    assert result.backend == "both-failed"
    assert "no network" in result.text

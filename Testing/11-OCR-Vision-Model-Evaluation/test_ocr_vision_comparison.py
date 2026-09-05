"""render_report() must never crash on empty/error outputs - a missing
sample image, a busted Tesseract install, or a failed vision-model call
must all show up clearly in TEST_REPORT.md, not blow up the whole run.

Run from clario-ml-sidecar's venv (has PIL + google-genai, which
run_comparison.py's import of app.tools.local_ocr needs even though these
tests never actually call the model or Tesseract):
    cd clario-ml-sidecar && source .venv/bin/activate
    python -m pytest ../Testing/11-OCR-Vision-Model-Evaluation/test_ocr_vision_comparison.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_comparison import ComparisonResult, render_report


def test_render_report_includes_every_image_and_the_backend_actually_used() -> None:
    results = [
        ComparisonResult(
            filename="login_error.png",
            tesseract_text="Er ror: t1meout Cancel OK Settings v2.3.1",
            tesseract_error=None,
            tesseract_elapsed_s=0.1,
            vision_text="ConnectionError: timed out at 0x892",
            vision_backend="qwen2-vl-local",
            vision_elapsed_s=1.2,
        ),
    ]

    report = render_report(results)

    assert "login_error.png" in report
    assert "Er ror: t1meout Cancel OK Settings v2.3.1" in report
    assert "ConnectionError: timed out at 0x892" in report
    assert "qwen2-vl-local" in report


def test_render_report_shows_the_tesseract_error_when_extraction_failed() -> None:
    results = [
        ComparisonResult(
            filename="broken.png",
            tesseract_text="",
            tesseract_error="tesseract is not installed or it's not in your PATH",
            tesseract_elapsed_s=0.0,
            vision_text="KeyError: 'user_id'",
            vision_backend="gemini-3.1-flash-lite-fallback",
            vision_elapsed_s=0.8,
        ),
    ]

    report = render_report(results)

    assert "tesseract is not installed" in report
    assert "gemini-3.1-flash-lite-fallback" in report


def test_render_report_on_no_images_is_still_valid_markdown() -> None:
    report = render_report([])

    assert "Images evaluated:** 0" in report

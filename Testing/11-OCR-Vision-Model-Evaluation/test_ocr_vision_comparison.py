"""render_report() must never crash on empty/error outputs - a missing
sample image, a busted Tesseract install, or a failed vision-model call
must all show up clearly in TEST_REPORT.md, not blow up the whole run.
similarity() and load_ground_truth() are the scoring logic the summary
table depends on - both are pure and covered directly.

Run from clario-ml-sidecar's venv (has PIL + google-genai, which
run_comparison.py's import of app.tools.local_ocr needs even though these
tests never actually call the model or Tesseract):
    cd clario-ml-sidecar && source .venv/bin/activate
    python -m pytest ../Testing/11-OCR-Vision-Model-Evaluation/test_ocr_vision_comparison.py -v
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_comparison import ComparisonResult, load_ground_truth, render_report, similarity


def test_similarity_is_1_for_an_exact_match_ignoring_case_and_whitespace() -> None:
    assert similarity("  Login Failed - fetch failed  ", "login failed - fetch failed") == 1.0


def test_similarity_is_0_when_ground_truth_is_missing() -> None:
    assert similarity("anything", "") == 0.0


def test_similarity_penalizes_output_padded_with_unrelated_noise() -> None:
    ground_truth = "Upload failed: Bucket not found"
    clean = similarity(ground_truth, ground_truth)
    noisy = similarity(
        "Settings Cancel OK Menu Home " * 10 + ground_truth,
        ground_truth,
    )
    assert noisy < clean


def test_load_ground_truth_reads_the_real_csv_schema(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "ground_truth.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Image Name", "Original Error"])
        writer.writerow(["shot1.png", "Failed to load submissions"])

    import run_comparison
    monkeypatch.setattr(run_comparison, "GROUND_TRUTH_CSV", csv_path)

    assert load_ground_truth() == {"shot1.png": "Failed to load submissions"}


def test_load_ground_truth_strips_a_leading_bom_instead_of_silently_loading_empty(tmp_path, monkeypatch) -> None:
    """A CSV exported from Excel/Google Sheets commonly starts with a UTF-8
    BOM. Opened as plain utf-8, that BOM attaches to the first header name
    ("﻿Image Name" instead of "Image Name"), so row.get("Image Name")
    returns None for every row and the whole file silently loads as
    empty - no exception, just wrong. This is the exact bug found against
    the user's real ground_truth.csv (saved with a BOM)."""
    csv_path = tmp_path / "ground_truth.csv"
    csv_path.write_bytes(
        b'\xef\xbb\xbf"Image Name","Original Error"\r\n"shot1.png","Failed to load submissions"\r\n'
    )

    import run_comparison
    monkeypatch.setattr(run_comparison, "GROUND_TRUTH_CSV", csv_path)

    assert load_ground_truth() == {"shot1.png": "Failed to load submissions"}


def test_load_ground_truth_returns_empty_dict_when_csv_is_absent(tmp_path, monkeypatch) -> None:
    import run_comparison
    monkeypatch.setattr(run_comparison, "GROUND_TRUTH_CSV", tmp_path / "does_not_exist.csv")

    assert load_ground_truth() == {}


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


def test_render_report_summary_table_shows_scores_and_declares_a_winner() -> None:
    results = [
        ComparisonResult(
            filename="upload_error.png",
            tesseract_text="Bucket n0t f0und Cancel OK Menu Home Settings",
            tesseract_error=None,
            tesseract_elapsed_s=0.1,
            vision_text="Upload failed: Bucket not found",
            vision_backend="qwen2-vl-local",
            vision_elapsed_s=1.0,
            ground_truth="Upload failed: Bucket not found",
            tesseract_similarity=0.4,
            vision_similarity=1.0,
        ),
    ]

    report = render_report(results)

    assert "## Summary" in report
    assert "upload_error.png" in report
    assert "0.40" in report
    assert "1.00" in report
    assert "Vision 1/1" in report

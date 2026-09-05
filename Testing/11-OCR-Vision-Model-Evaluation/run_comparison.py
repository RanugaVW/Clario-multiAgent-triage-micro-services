"""Testing/11 - OCR Vision Model vs Tesseract comparison.

Runs every image in sample_images/ through two independent extractors and
records their raw, unedited output:

1. Tesseract (`pytesseract`) - a naive, generic OCR engine with no concept
   of what matters in the image. It transcribes everything it can find,
   including UI chrome, buttons, watermarks, and background noise.
2. The Qwen2-VL-2B-Instruct vision-language model in
   clario-ml-sidecar/app/tools/local_ocr.py, explicitly prompted to
   extract ONLY the real error text and ignore everything else. Falls
   back to Gemini 3.1 Flash-Lite automatically if the local model can't
   load (e.g. insufficient VRAM) - this script never has to know or care
   which one actually ran; local_ocr.py reports it via OcrResult.backend.

If ground_truth.csv exists (columns: "Image Name", "Original Error" - the
real error each image depicts, with noise excluded), each extractor's raw
output is also scored against it via difflib.SequenceMatcher: a fuzzy
similarity ratio in [0, 1], not exact-match, since neither extractor is
expected to reproduce the ground truth character-for-character. This is
deliberately sensitive to length: an extractor whose output is padded with
unrelated noise text scores lower even if the real error is in there
somewhere, which is exactly the failure mode this evaluation is trying to
surface. Without ground_truth.csv, only raw side-by-side output is shown.

This tool is standalone: it is never imported by production code, and
production (clario-ml-sidecar/app/main.py) never imports it or the vision
model - see app/tools/gemini_ocr.py for what real tickets actually use.

Usage:
    cd clario-ml-sidecar && source .venv/bin/activate
    pip install -r ../Testing/11-OCR-Vision-Model-Evaluation/requirements.txt
    python ../Testing/11-OCR-Vision-Model-Evaluation/run_comparison.py

Drop screenshots into sample_images/ first (PNG/JPG/JPEG/WEBP/BMP) - each
one should contain a real error/exception/stack trace plus some amount of
surrounding UI chrome, so the comparison has noise to actually measure.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import difflib
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPO_ROOT / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(SIDECAR_ROOT / ".env")  # GEMINI_API_KEY, needed for the local model's Gemini fallback

from app.tools.local_ocr import process_image_async  # noqa: E402

PHASE_DIR = Path(__file__).resolve().parent
SAMPLE_IMAGES_DIR = PHASE_DIR / "sample_images"
GROUND_TRUTH_CSV = PHASE_DIR / "ground_truth.csv"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class ComparisonResult:
    filename: str
    tesseract_text: str
    tesseract_error: str | None
    tesseract_elapsed_s: float
    vision_text: str
    vision_backend: str
    vision_elapsed_s: float
    ground_truth: str | None = None
    tesseract_similarity: float | None = None
    vision_similarity: float | None = None


def load_ground_truth() -> dict[str, str]:
    """Returns {image filename: real error text (noise excluded)}. Empty
    dict if ground_truth.csv doesn't exist - the report just skips scoring."""
    if not GROUND_TRUTH_CSV.exists():
        return {}
    # utf-8-sig: transparently strips a leading BOM if present (e.g. a CSV
    # exported from Excel/Google Sheets), without affecting plain utf-8
    # files - a BOM otherwise silently corrupts the first column's header
    # name, and row.get("Image Name") returns None for every row instead
    # of raising, so the whole file quietly loads as empty.
    with GROUND_TRUTH_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {
            row["Image Name"]: row["Original Error"]
            for row in reader
            if row.get("Image Name")
        }


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def similarity(extracted: str, ground_truth: str) -> float:
    """Fuzzy match ratio in [0, 1] between an extractor's raw output and
    the real error. Deliberately not exact-match - real OCR/VLM output
    rarely reproduces the ground truth character-for-character - and
    deliberately length-sensitive: padding the output with unrelated noise
    text lowers the ratio even when the real error is present somewhere in
    it, which is exactly the failure mode this evaluation measures."""
    if not ground_truth:
        return 0.0
    return difflib.SequenceMatcher(None, _normalize(extracted), _normalize(ground_truth)).ratio()


def _run_tesseract(image_path: Path) -> tuple[str, str | None]:
    """Returns (raw_text, error). Never raises - a missing tesseract binary
    or an unreadable image must show up as an error string in the report,
    not crash the whole comparison run."""
    try:
        import pytesseract
        from PIL import Image

        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img)
        return text.strip(), None
    except Exception as e:
        return "", str(e)


async def _run_vision_model(image_path: Path) -> tuple[str, str, float]:
    """Returns (text, backend, elapsed_seconds). backend is whichever of
    "qwen2-vl-local" / "gemini-3.1-flash-lite-fallback" / "both-failed"
    local_ocr.py actually used - see OcrResult."""
    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    start = time.monotonic()
    result = await process_image_async(image_b64)
    elapsed = time.monotonic() - start
    return result.text, result.backend, elapsed


async def run_comparison() -> list[ComparisonResult]:
    images = sorted(
        p for p in SAMPLE_IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        print(f"No images found in {SAMPLE_IMAGES_DIR} - drop screenshots there and re-run.")
        return []

    ground_truth_map = load_ground_truth()
    if ground_truth_map:
        print(f"Loaded {len(ground_truth_map)} ground-truth rows from {GROUND_TRUTH_CSV.name}")

    results: list[ComparisonResult] = []
    for image_path in images:
        print(f"Processing {image_path.name}...")

        t_start = time.monotonic()
        tesseract_text, tesseract_error = _run_tesseract(image_path)
        tesseract_elapsed = time.monotonic() - t_start

        vision_text, vision_backend, vision_elapsed = await _run_vision_model(image_path)

        ground_truth = ground_truth_map.get(image_path.name)
        tesseract_sim = similarity(tesseract_text, ground_truth) if ground_truth else None
        vision_sim = similarity(vision_text, ground_truth) if ground_truth else None

        results.append(ComparisonResult(
            filename=image_path.name,
            tesseract_text=tesseract_text,
            tesseract_error=tesseract_error,
            tesseract_elapsed_s=tesseract_elapsed,
            vision_text=vision_text,
            vision_backend=vision_backend,
            vision_elapsed_s=vision_elapsed,
            ground_truth=ground_truth,
            tesseract_similarity=tesseract_sim,
            vision_similarity=vision_sim,
        ))
    return results


def _winner(r: ComparisonResult) -> str:
    if r.tesseract_similarity is None or r.vision_similarity is None:
        return "n/a"
    if r.vision_similarity > r.tesseract_similarity:
        return "Vision"
    if r.tesseract_similarity > r.vision_similarity:
        return "Tesseract"
    return "Tie"


def _summary_table(results: list[ComparisonResult]) -> list[str]:
    scored = [r for r in results if r.ground_truth is not None]
    if not scored:
        return []

    lines = [
        "## Summary",
        "",
        "| Image | Tesseract similarity | Vision similarity | Winner |",
        "|---|---|---|---|",
    ]
    for r in scored:
        lines.append(
            f"| {r.filename} | {r.tesseract_similarity:.2f} | {r.vision_similarity:.2f} | {_winner(r)} |"
        )

    avg_tesseract = sum(r.tesseract_similarity for r in scored) / len(scored)
    avg_vision = sum(r.vision_similarity for r in scored) / len(scored)
    vision_wins = sum(1 for r in scored if _winner(r) == "Vision")
    tesseract_wins = sum(1 for r in scored if _winner(r) == "Tesseract")
    ties = sum(1 for r in scored if _winner(r) == "Tie")

    lines += [
        "",
        f"**Average similarity to ground truth:** Tesseract {avg_tesseract:.2f} | Vision {avg_vision:.2f}",
        "",
        f"**Wins:** Vision {vision_wins}/{len(scored)} | Tesseract {tesseract_wins}/{len(scored)} | Ties {ties}/{len(scored)}",
        "",
        "Similarity is a fuzzy match ratio (0-1) against the ground-truth error text in "
        "`ground_truth.csv`, not an exact match - it's deliberately sensitive to length, so "
        "an extractor that pads its output with unrelated noise scores lower even when the "
        "real error is present somewhere in it.",
        "",
        "---",
        "",
    ]
    return lines


def render_report(results: list[ComparisonResult], findings: str | None = None) -> str:
    """findings: a hand-written analysis of THIS specific run, inserted
    right after the summary table. Optional - a fresh run (or a unit test)
    with no analysis written yet just omits the section, rather than
    repeating a generic placeholder under every single image (unhelpful
    noise once there are dozens of images)."""
    lines = [
        "# Testing/11 - OCR Vision Model vs Tesseract: Evaluation Report",
        "",
        f"**Images evaluated:** {len(results)}",
        "",
        "Two independent extractors ran against every image below:",
        "- **Tesseract** (`pytesseract`) - a naive, generic OCR engine with no",
        "  concept of what matters in the image; it transcribes everything it",
        "  can find, including UI chrome, buttons, watermarks, and background",
        "  noise.",
        "- **Vision model** (Qwen2-VL-2B-Instruct via",
        "  `clario-ml-sidecar/app/tools/local_ocr.py`, falling back to Gemini",
        "  3.1 Flash-Lite if the local model can't load) explicitly prompted to",
        "  extract only the real error text and ignore everything else.",
        "",
        "---",
        "",
    ]
    lines += _summary_table(results)

    if findings:
        lines += ["## Findings", "", findings, "", "---", ""]

    for r in results:
        lines += [
            f"## {r.filename}",
            "",
            f"**Vision backend used:** `{r.vision_backend}` ({r.vision_elapsed_s:.2f}s) "
            f"| **Tesseract:** {r.tesseract_elapsed_s:.2f}s",
            "",
        ]
        if r.ground_truth is not None:
            lines += [
                "**Ground truth (real error, noise excluded):**",
                "```",
                r.ground_truth,
                "```",
                f"Similarity - Tesseract: {r.tesseract_similarity:.2f} | Vision: {r.vision_similarity:.2f}",
                "",
            ]
        lines += [
            "### Tesseract raw output",
            "```",
            r.tesseract_text if r.tesseract_text else (r.tesseract_error or "(empty)"),
            "```",
            "",
            "### Vision model raw output",
            "```",
            r.vision_text if r.vision_text else "(empty)",
            "```",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    results = asyncio.run(run_comparison())
    if not results:
        return

    report = render_report(results)
    report_path = PHASE_DIR / "TEST_REPORT.md"
    report_path.write_text(report)
    print(f"\nWrote {report_path}")


if __name__ == "__main__":
    main()

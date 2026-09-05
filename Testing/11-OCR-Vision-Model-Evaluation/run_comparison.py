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
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPO_ROOT / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))

from app.tools.local_ocr import process_image_async  # noqa: E402

PHASE_DIR = Path(__file__).resolve().parent
SAMPLE_IMAGES_DIR = PHASE_DIR / "sample_images"
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

    results: list[ComparisonResult] = []
    for image_path in images:
        print(f"Processing {image_path.name}...")

        t_start = time.monotonic()
        tesseract_text, tesseract_error = _run_tesseract(image_path)
        tesseract_elapsed = time.monotonic() - t_start

        vision_text, vision_backend, vision_elapsed = await _run_vision_model(image_path)

        results.append(ComparisonResult(
            filename=image_path.name,
            tesseract_text=tesseract_text,
            tesseract_error=tesseract_error,
            tesseract_elapsed_s=tesseract_elapsed,
            vision_text=vision_text,
            vision_backend=vision_backend,
            vision_elapsed_s=vision_elapsed,
        ))
    return results


def render_report(results: list[ComparisonResult]) -> str:
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
    for r in results:
        lines += [
            f"## {r.filename}",
            "",
            f"**Vision backend used:** `{r.vision_backend}` ({r.vision_elapsed_s:.2f}s) "
            f"| **Tesseract:** {r.tesseract_elapsed_s:.2f}s",
            "",
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
            "### Analysis",
            "_TODO: filled in by hand after reviewing the raw outputs above -_",
            "_does Tesseract's output include UI/noise text the vision model_",
            "_correctly excluded?_",
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

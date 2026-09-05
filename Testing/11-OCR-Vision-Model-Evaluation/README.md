# 11 — OCR Vision Model vs Tesseract Evaluation

**Status:** Infrastructure ready — awaiting real sample images (see
"Providing sample images" below) before `TEST_REPORT.md` reflects a real
run.

**Assigned-table mapping:** none. Unlike phases 01–10, this phase doesn't
map to a section of the course's Master Test Plan template — it's an ML
model-quality comparison (naive OCR vs. a vision-language model), not a
functional/integration/performance/security test of the system. It follows
the phase-folder convention (README + raw log + written report) established
by phases 01–10 purely for consistency, not because the sample plan calls
for it.

## Scope

Clario's production ticket pipeline extracts error text from a customer's
attached screenshot via Gemini 3.1 Flash-Lite only
(`clario-ml-sidecar/app/tools/gemini_ocr.py`) — deliberately lightweight, no
vision model loaded into memory. This phase exists to justify *why* a real
vision-language model is worth having at all, by comparing two extraction
approaches side by side on the same real screenshots:

1. **Tesseract** (`pytesseract`) — a naive, generic OCR engine with no
   concept of what matters in an image. It transcribes everything it can
   find: the real error, and also UI chrome, buttons, watermarks, and
   background noise indiscriminately.
2. **Qwen2-VL-2B-Instruct** (`clario-ml-sidecar/app/tools/local_ocr.py`) —
   a vision-language model explicitly prompted to extract *only* the real
   error/exception/stack-trace text and ignore everything else. Falls back
   automatically to Gemini 3.1 Flash-Lite if the local model can't load on
   this machine (e.g. insufficient VRAM) — the comparison script never has
   to know or care which one actually ran; it's recorded per image as the
   "vision backend used" in the report.

This vision model is **not** used by production — see
`clario-ml-sidecar/app/tools/gemini_ocr.py` for what a real ticket actually
calls. `local_ocr.py` exists solely so this phase can demonstrate the
difference in quality.

## One-time setup

Install the system Tesseract binary (not a pip package):

```bash
# Debian/Ubuntu
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

`clario-ml-sidecar/.venv` must already exist (see
`clario-ml-sidecar/README.md`) — this phase reuses it rather than keeping a
separate one, since it needs to import `local_ocr.py` directly and that
already depends on `torch`/`transformers`/`bitsandbytes`/Pillow/`google-genai`.
`run_evaluation.sh` installs this phase's extra dependencies (`pytesseract`,
`torchvision`) into that same venv.

To actually exercise the local Qwen2-VL-2B-Instruct model (rather than
having every image silently fall back to Gemini), you need a CUDA GPU with
~2GB+ free VRAM. Without one, `local_ocr.py`'s own fallback still makes the
run succeed — every image just reports `vision_backend` as
`gemini-3.1-flash-lite-fallback` instead of `qwen2-vl-local`, and the report
becomes a Tesseract-vs-Gemini comparison instead. The first real run also
downloads ~4.5GB of model weights from Hugging Face on first use.

## Providing sample images

Drop screenshots into `sample_images/` — PNG/JPG/JPEG/WEBP/BMP. Each one
should contain a real error/exception/stack trace *plus* some amount of
surrounding UI chrome (buttons, nav bars, timestamps, watermarks), so the
comparison actually has noise to measure. Nothing in this repo populates
that folder automatically — no fabricated results.

## How to run this

```bash
Testing/11-OCR-Vision-Model-Evaluation/run_evaluation.sh
```

This writes `test-log.txt` (raw console output) and `TEST_REPORT.md` (the
side-by-side comparison per image). The report's per-image "Analysis"
section is a placeholder in the generated file — it gets filled in by hand
after reviewing what each extractor actually produced on the real images.

To run just the unit tests (report-formatting logic only — no real images,
Tesseract, or model calls needed):

```bash
cd clario-ml-sidecar && source .venv/bin/activate
python -m pytest ../Testing/11-OCR-Vision-Model-Evaluation/test_ocr_vision_comparison.py -v
```

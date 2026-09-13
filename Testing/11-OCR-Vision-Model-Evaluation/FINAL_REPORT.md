# Final Report — 11 OCR Vision Model vs Tesseract Evaluation

This is the summary we are submitting for this stage, in the generic
reporting format our reference Master Test Plan asks for in its own §4.2,
adapted where it doesn't map cleanly — this stage compares model quality
rather than checking pass/fail behavior, since it isn't part of the
reference plan at all (it's an ML model-quality comparison we added for
our own product's benefit). The full narrative writeup is in
[`TEST_REPORT.md`](TEST_REPORT.md); this page is the short version for
the record.

**Date:** 2026-09-05, status corrected 2026-09-13
**Team:** Clario QA Team
**Test case field:** Side-by-side comparison of two ways to extract error
text from a customer's screenshot — plain OCR (Tesseract) and a
vision-language model (Qwen2-VL-2B-Instruct, with a Gemini fallback) — to
justify why our real pipeline uses the vision-capable option

## Metrics

| Metric | Value |
|---|---|
| Real images evaluated | 34 |
| Images where the vision model produced a better extraction | 22 (65%) |
| Images where Tesseract produced a better extraction | 12 (35%) |
| Average similarity to ground truth — vision model | 0.59 |
| Average similarity to ground truth — Tesseract | 0.38 |
| Vision model false-negative rate (missed a real, visible error) | 41% (14 of 34) |
| Supporting unit tests (report-formatting logic) | 10/10 passed |

## Comments

We compared a naive OCR engine against a vision-language model explicitly
prompted to extract only the real error text from a customer's screenshot
and ignore the surrounding interface noise, using 34 real screenshots and
the real local model running on GPU, not the cloud fallback. The vision
model won on most images and by a meaningful margin, and where it did
work, it demonstrated exactly the noise-filtering behavior we built it to
test — returning just the real error where Tesseract returned an entire
unrelated form.

We also found a real limitation worth stating plainly rather than
smoothing over: on 14 of the 34 images, the local model reported no error
found at all, even though a real, legible error was on screen and
Tesseract actually caught it correctly on those same images. This tells
us the small, quantized model we can run locally is not yet a safe
default on its own — which is exactly why our real production pipeline
uses a larger cloud model instead of this local one, and why we keep this
comparison here rather than in the live pipeline.

This stage's status previously said we were still waiting on real sample
images, but that was out of date — the real run described above, with 34
real images, had already completed and been sitting in this same folder.
We corrected the status once we noticed the mismatch while reviewing
every stage's report against the current state of this folder.

## Files referenced

- [`TEST_REPORT.md`](TEST_REPORT.md) — the full per-image comparison and findings
- [`test-log.txt`](test-log.txt) — raw console output from the real run
- [`ground_truth.csv`](ground_truth.csv) — the real ground-truth error text for each image
- [`sample_images/`](sample_images/) — the 34 real screenshots evaluated

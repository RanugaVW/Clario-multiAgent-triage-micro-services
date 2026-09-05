#!/usr/bin/env bash
# Runs the OCR vision-model-vs-Tesseract comparison phase end to end:
# installs this phase's one extra dependency (pytesseract) into
# clario-ml-sidecar's existing venv, runs the comparison against every
# image in sample_images/, and captures the raw console output.
#
# Requires:
# - clario-ml-sidecar/.venv already set up (see clario-ml-sidecar/README.md)
# - the system Tesseract binary installed (see README.md's "One-time setup")
# - GEMINI_API_KEY set in clario-ml-sidecar/.env, for the Gemini fallback
#   path if the local Qwen2-VL model can't load on this machine
set -euo pipefail

PHASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
pip install -q -r "$PHASE_DIR/requirements.txt"

cd "$PHASE_DIR"
set +e
python run_comparison.py 2>&1 | tee "$PHASE_DIR/test-log.txt"
RUN_EXIT=${PIPESTATUS[0]}
set -e

exit "$RUN_EXIT"

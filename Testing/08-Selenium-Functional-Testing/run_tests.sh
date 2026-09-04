#!/usr/bin/env bash
# Runs the Selenium functional-testing phase end to end: creates disposable
# fixtures, runs the real pytest+Selenium suite, then tears the fixtures
# down. Requires the frontend (:3000) running, and this phase's own .venv
# (see README.md's "One-time environment setup") plus a matching
# chromedriver at ../../.tools/chromedriver-linux64/chromedriver.
set -euo pipefail

PHASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"

if [ ! -d "$PHASE_DIR/.venv" ]; then
  echo "This phase's .venv doesn't exist yet - see README.md's one-time setup." >&2
  exit 1
fi

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
python "$PHASE_DIR/setup_fixtures.py"

cd "$PHASE_DIR"
source .venv/bin/activate
set +e
python -m pytest test_functional_e2e.py -v 2>&1 | tee "$PHASE_DIR/test-log.txt"
PYTEST_EXIT=${PIPESTATUS[0]}
set -e

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
python "$PHASE_DIR/teardown_fixtures.py"

exit "$PYTEST_EXIT"

#!/usr/bin/env bash
# Runs the full API testing phase: creates disposable fixtures, runs the
# Postman collection with Newman (Postman's official CLI runner), then tears
# the fixtures down. Requires clario-ml-sidecar running on :8600, the
# frontend on :3000, and voice-to-text-service on :8002.
#
# Usage:
#   Testing/07-API-Testing/run_api_tests.sh
set -euo pipefail

PHASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate

python "$PHASE_DIR/setup_fixtures.py"

set +e
npx --yes newman run "$PHASE_DIR/postman/Clario-API.postman_collection.json" \
  -e "$PHASE_DIR/postman/generated.postman_environment.json" \
  --reporters cli \
  | tee "$PHASE_DIR/test-log.txt"
NEWMAN_EXIT=${PIPESTATUS[0]}
set -e

python "$PHASE_DIR/teardown_fixtures.py"

exit "$NEWMAN_EXIT"

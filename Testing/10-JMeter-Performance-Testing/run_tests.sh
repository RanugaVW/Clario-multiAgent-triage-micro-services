#!/usr/bin/env bash
# Runs the JMeter basic-performance-testing phase end to end: creates a
# disposable staff account, runs the real JMeter test plan in non-GUI mode
# (downloading JMeter locally into ../../.tools if it isn't there yet),
# generates the HTML dashboard report, then tears the fixtures down.
# Requires the frontend (:3000) and clario-ml-sidecar (:8600) running.
set -euo pipefail

PHASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
TOOLS_DIR="$REPO_ROOT/.tools"
JMETER_VERSION="5.6.3"
JMETER_HOME="$TOOLS_DIR/apache-jmeter-$JMETER_VERSION"

if [ ! -x "$JMETER_HOME/bin/jmeter" ]; then
  echo "JMeter not found locally - downloading..."
  mkdir -p "$TOOLS_DIR"
  curl -sL "https://dlcdn.apache.org/jmeter/binaries/apache-jmeter-$JMETER_VERSION.tgz" \
    -o "$TOOLS_DIR/jmeter.tgz"
  tar -xzf "$TOOLS_DIR/jmeter.tgz" -C "$TOOLS_DIR"
  chmod +x "$JMETER_HOME/bin/jmeter"
fi

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
python "$PHASE_DIR/setup_fixtures.py"

AUTH_TOKEN=$(python -c "import json; print(json.load(open('$PHASE_DIR/fixtures.json'))['auth_token'])")

rm -rf "$PHASE_DIR/results.jtl" "$PHASE_DIR/report"
set +e
"$JMETER_HOME/bin/jmeter" -n \
  -t "$PHASE_DIR/clario-basic-performance.jmx" \
  -JauthToken="$AUTH_TOKEN" \
  -l "$PHASE_DIR/results.jtl" \
  -e -o "$PHASE_DIR/report" \
  2>&1 | tee "$PHASE_DIR/test-log.txt"
JMETER_EXIT=${PIPESTATUS[0]}
set -e

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
python "$PHASE_DIR/teardown_fixtures.py"

exit "$JMETER_EXIT"

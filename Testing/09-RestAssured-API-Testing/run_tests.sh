#!/usr/bin/env bash
# Runs the REST Assured integration-testing phase end to end: creates
# disposable fixtures, runs `mvn test` (downloading Maven locally into
# ../../.tools if it isn't there yet), then tears the fixtures down.
# Requires the frontend (:3000) and clario-ml-sidecar (:8600) running.
set -euo pipefail

PHASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PHASE_DIR/../.." && pwd)"
TOOLS_DIR="$REPO_ROOT/.tools"
MAVEN_VERSION="3.9.9"
MAVEN_HOME="$TOOLS_DIR/apache-maven-$MAVEN_VERSION"

if [ ! -x "$MAVEN_HOME/bin/mvn" ]; then
  echo "Maven not found locally - downloading..."
  mkdir -p "$TOOLS_DIR"
  curl -sL "https://archive.apache.org/dist/maven/maven-3/$MAVEN_VERSION/binaries/apache-maven-$MAVEN_VERSION-bin.tar.gz" \
    -o "$TOOLS_DIR/maven.tar.gz"
  tar -xzf "$TOOLS_DIR/maven.tar.gz" -C "$TOOLS_DIR"
fi
MVN="$MAVEN_HOME/bin/mvn"

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
python "$PHASE_DIR/setup_fixtures.py"

cd "$PHASE_DIR"
set +e
"$MVN" test | tee "$PHASE_DIR/test-log.txt"
MVN_EXIT=${PIPESTATUS[0]}
set -e

cd "$REPO_ROOT/clario-ml-sidecar"
source .venv/bin/activate
python "$PHASE_DIR/teardown_fixtures.py"

exit "$MVN_EXIT"

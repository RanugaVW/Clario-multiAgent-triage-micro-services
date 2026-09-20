"""DC-012: dependency versions are documented, and the inventory in DEPENDENCIES.md stays complete.

Fails when a manifest (pom.xml, package.json, requirements*.txt, Dockerfile) is added to the repository without its
directory being listed in DEPENDENCIES.md, so the documented inventory cannot silently go stale.
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "DEPENDENCIES.md").read_text(encoding="utf-8")

# Manifests deliberately outside the process, each with the reason (also stated under "Known exceptions").
EXCLUDED = {
    "requirements.txt": "root pip freeze is UTF-16 encoded",
    "clario-app/pom.xml": "legacy monolith, only its .env is still used by docker-compose",
}
EXCLUDED_PREFIXES = ("legacy/", "Testing/", ".worktrees/")
MANIFEST_NAMES = {"pom.xml", "package.json", "Dockerfile"}


def tracked_manifest_dirs():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    found = set()
    for f in files:
        name = Path(f).name
        if f in EXCLUDED or f.startswith(EXCLUDED_PREFIXES):
            continue
        if name in MANIFEST_NAMES or (name.startswith("requirements") and name.endswith(".txt")):
            found.add(str(Path(f).parent))
    return sorted(found)


@pytest.mark.parametrize("directory", tracked_manifest_dirs())
def test_every_manifest_directory_is_listed_in_the_policy_document(directory):
    assert f"{directory}/" in DOC, f"{directory}/ holds a dependency manifest but is not listed in DEPENDENCIES.md"


def test_the_inventory_is_not_empty_and_the_parser_sees_the_known_manifests():
    dirs = set(tracked_manifest_dirs())
    assert {"frontend", "services/api-gateway", "services/ai-orchestrator-service", "clario-ml-sidecar"} <= dirs


def test_the_policy_names_every_ecosystem_and_the_ci_gate():
    for word in ("npm", "Maven", "pip", "Docker", "GitHub Actions", "CI", "major"):
        assert word.lower() in DOC.lower(), word


def test_no_bot_configuration_is_committed():
    """Updates are made by hand from a maintainer's account; no bot may open PRs or push commits."""
    for name in ("dependabot.yml", "dependabot.yaml", "renovate.json", ".renovaterc", ".renovaterc.json"):
        assert not (ROOT / ".github" / name).exists() and not (ROOT / name).exists(), f"{name} must not be committed"

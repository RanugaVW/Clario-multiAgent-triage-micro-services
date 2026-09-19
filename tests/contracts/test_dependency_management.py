"""DC-012: dependency versions are managed with the project's tooling, and updates are proposed for evaluation.

Fails when a manifest is added without being registered with Dependabot (so it would silently never get
update proposals), or when dependabot.yml points at a directory/manifest that does not exist.
"""
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

MANIFEST_ECOSYSTEM = {
    "pom.xml": "maven",
    "package.json": "npm",
    "Dockerfile": "docker",
}
# requirements*.txt -> pip, handled separately below.

# Manifests deliberately not covered, each with the reason.
EXCLUDED = {
    "requirements.txt": "root pip freeze is UTF-16 encoded; Dependabot may misread it. Re-save as UTF-8 to include it",
    "clario-app/pom.xml": "legacy monolith, only its .env is still used by docker-compose",
}
EXCLUDED_PREFIXES = ("legacy/", "Testing/", ".worktrees/")


def tracked_manifests():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    found = []
    for f in files:
        name = Path(f).name
        if f in EXCLUDED or f.startswith(EXCLUDED_PREFIXES):
            continue
        if name in MANIFEST_ECOSYSTEM:
            found.append((f, MANIFEST_ECOSYSTEM[name]))
        elif name.startswith("requirements") and name.endswith(".txt"):
            found.append((f, "pip"))
    return found


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))


def entries(config):
    return [(u["package-ecosystem"], u["directory"]) for u in config["updates"]]


def test_config_is_version_2_with_weekly_schedules(config):
    assert config["version"] == 2
    for update in config["updates"]:
        assert update["schedule"]["interval"] == "weekly", update


@pytest.mark.parametrize("manifest,ecosystem", tracked_manifests())
def test_every_tracked_manifest_is_registered(config, manifest, ecosystem):
    directory = "/" + str(Path(manifest).parent).replace("\\", "/")
    directory = "/" if directory == "/." else directory
    assert (ecosystem, directory) in entries(config), f"{manifest} is not covered by a {ecosystem} entry for {directory}"


def test_every_entry_points_at_a_real_manifest(config):
    manifests = {(eco, "/" + str(Path(f).parent).replace("\\", "/")) for f, eco in tracked_manifests()}
    for eco, directory in entries(config):
        if eco == "github-actions":
            assert (ROOT / ".github" / "workflows").is_dir()
            continue
        assert (eco, directory) in manifests, f"dependabot entry {eco} {directory} matches no tracked manifest"


def test_no_duplicate_entries(config):
    e = entries(config)
    assert len(e) == len(set(e))


def test_core_framework_major_upgrades_are_not_automatic(config):
    ignored = {}
    for u in config["updates"]:
        for rule in u.get("ignore", []):
            ignored.setdefault(u["package-ecosystem"], set()).add(rule["dependency-name"])
    assert {"next", "react", "react-dom"} <= ignored["npm"]
    assert "org.springframework.boot:spring-boot-starter-parent" in ignored["maven"]


def test_dependency_policy_document_exists_and_names_every_ecosystem():
    text = (ROOT / "DEPENDENCIES.md").read_text(encoding="utf-8")
    for word in ("npm", "Maven", "pip", "Docker", "GitHub Actions", "Dependabot", "CI"):
        assert word in text

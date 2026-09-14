#!/usr/bin/env python3
"""Fails the PR check if the diff looks like an architectural change rather
than a normal feature/bugfix change.

"Architectural" here means: adding or removing a whole service, changing how
a service is containerized, or touching several unrelated services/top-level
areas in one PR. It does NOT mean "large diff" - a big change confined to one
service (e.g. a big refactor inside the frontend) is not flagged.

Run as: python3 check_architecture.py <base_sha> <head_sha>
"""
import subprocess
import sys

# Every top-level area that counts as its own "service" boundary for the
# cross-service check below. Anything not listed here (docs, Testing, Plan,
# scripts, etc.) is treated as non-architectural regardless of how much of
# it changes.
SERVICE_ROOTS = [
    "frontend",
    "clario-ml-sidecar",
    "clario-app",
    "ml_finetuning",
    "agent_orchestration",
    "services/agent-review-service",
    "services/ai-orchestrator-service",
    "services/api-gateway",
    "services/nlp-classifier-service",
    "services/ocr-vision-service",
    "services/ticket-core-service",
    "services/voice-to-text-service",
]

DOCKERFILE_NAMES = {"Dockerfile", "Dockerfile.dev", "Dockerfile.prod"}


def service_root_for(path: str) -> str | None:
    for root in SERVICE_ROOTS:
        if path == root or path.startswith(root + "/"):
            return root
    return None


def diff_status(base_sha: str, head_sha: str) -> list[tuple[str, str]]:
    """Returns a list of (status, path) tuples, e.g. ('A', 'frontend/foo.ts')."""
    out = subprocess.run(
        ["git", "diff", "--name-status", f"{base_sha}...{head_sha}"],
        capture_output=True, text=True, check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        rows.append((status[0], path))
    return rows


def compose_service_keys(ref: str, path: str) -> set[str]:
    """Top-level service names under `services:` in a docker-compose.yml at
    a given git ref. Returns an empty set if the file doesn't exist there.
    """
    try:
        content = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return set()

    keys = set()
    in_services = False
    for line in content.splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if in_services:
            if line.strip() and not line.startswith(" "):
                break  # left the services: block
            if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
                keys.add(line.strip().rstrip(":"))
    return keys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_architecture.py <base_sha> <head_sha>")
        return 2
    base_sha, head_sha = sys.argv[1], sys.argv[2]

    rows = diff_status(base_sha, head_sha)
    if not rows:
        print("No changed files detected - nothing to check.")
        return 0

    failures: list[str] = []

    # 1. A brand-new or fully-removed top-level service directory.
    touched_roots = {r for r in (service_root_for(p) for _, p in rows) if r}
    for root in touched_roots:
        root_paths = [p for _, p in rows if service_root_for(p) == root]
        statuses = {s for s, p in rows if service_root_for(p) == root}
        # Every file under this root was newly added -> looks like a brand
        # new service was introduced in this PR.
        if statuses == {"A"} and len(root_paths) > 1:
            failures.append(
                f"'{root}' looks like a brand-new service (every file under it is newly added). "
                "Adding a new service is an architectural change and needs a design discussion "
                "before it goes into a PR."
            )
        if statuses == {"D"} and len(root_paths) > 1:
            failures.append(
                f"'{root}' looks like it was fully deleted. Removing a whole service is an "
                "architectural change and needs a design discussion before it goes into a PR."
            )

    # 2. Any Dockerfile added, removed, or modified anywhere in the repo.
    for status, path in rows:
        if path.split("/")[-1] in DOCKERFILE_NAMES:
            failures.append(
                f"'{path}' was changed. Editing how a service is containerized "
                "(its Dockerfile) is an architectural change and needs a design "
                "discussion before it goes into a PR."
            )

    # 3. A service added/removed from docker-compose.yml's `services:` block.
    for status, path in rows:
        if path.endswith("docker-compose.yml"):
            before = compose_service_keys(base_sha, path)
            after = compose_service_keys(head_sha, path)
            added, removed = after - before, before - after
            if added:
                failures.append(
                    f"'{path}' adds a new service to docker-compose: {', '.join(sorted(added))}. "
                    "This is an architectural change and needs a design discussion before it goes into a PR."
                )
            if removed:
                failures.append(
                    f"'{path}' removes a service from docker-compose: {', '.join(sorted(removed))}. "
                    "This is an architectural change and needs a design discussion before it goes into a PR."
                )

    # 4. The PR touches 3 or more separate service boundaries at once. A
    # frontend-only PR (the common case for UI-enhancement issues) never
    # trips this, since it only ever touches one root.
    if len(touched_roots) >= 3:
        failures.append(
            f"This PR touches {len(touched_roots)} different services at once "
            f"({', '.join(sorted(touched_roots))}). Changes spanning many services at "
            "once usually mean an architectural change is hiding inside what looked like "
            "a small PR - please split this up or flag it for an architecture review."
        )

    if failures:
        print("Architecture guard failed:\n")
        for f in failures:
            print(f" - {f}")
        print(
            "\nIf this really is an intended architectural change, it should be discussed "
            "and approved outside of a routine PR, not merged through this check."
        )
        return 1

    print("Architecture guard passed - no structural/cross-service changes detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

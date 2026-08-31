"""Guards the dependency set the service actually needs at runtime.

`faster-whisper` imports `requests` without declaring it (it used to arrive via
huggingface-hub, which moved to httpx in 1.0). A missing pin only shows up in a
freshly built image, so pin and test are kept together here.
"""

from __future__ import annotations

import re
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements.txt"


def pinned_packages() -> set[str]:
    names = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # "uvicorn[standard]==0.41.0" -> "uvicorn"
        names.add(re.split(r"[\[=<>!~]", line, maxsplit=1)[0].lower())
    return names


def test_requests_is_pinned_explicitly():
    # Removing this pin breaks `import faster_whisper` at container start.
    assert "requests" in pinned_packages()


def test_core_runtime_packages_are_pinned():
    assert {"fastapi", "uvicorn", "faster-whisper", "numpy"} <= pinned_packages()

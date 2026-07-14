import json
from pathlib import Path


REGISTRY = Path(__file__).parents[2] / "models" / "registry.json"


def test_model_registry_has_a_version_history_container() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert registry == {"models": []} or isinstance(registry.get("models"), list)

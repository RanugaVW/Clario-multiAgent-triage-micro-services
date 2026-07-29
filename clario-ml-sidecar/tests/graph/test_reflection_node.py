"""Tests for the bounded reflection feedback node."""

import pytest

from app.graph.reflection_node import reflection_node


def test_reflection_appends_validation_critique_and_increments(monkeypatch) -> None:
    monkeypatch.setenv("MAX_REFLECTION_ATTEMPTS", "2")
    result = reflection_node({
        "failure_type": "quality", "reflection_count": 0, "reflection_critiques": [],
        "validation_result": {"technical": {"passed": False, "failed_rules": ["pii_in_draft"], "reasoning": "Contains PII"}},
    })
    assert result["reflection_count"] == 1
    assert result["reflection_critiques"] == ["technical: failed pii_in_draft; judge: Contains PII"]


def test_reflection_rejects_invalid_failure_types_and_cap(monkeypatch) -> None:
    monkeypatch.setenv("MAX_REFLECTION_ATTEMPTS", "2")
    with pytest.raises(ValueError, match="quality or policy"):
        reflection_node({"failure_type": "misroute"})
    with pytest.raises(ValueError, match="cap"):
        reflection_node({"failure_type": "policy", "reflection_count": 2})

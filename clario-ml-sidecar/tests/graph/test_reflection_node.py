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


def test_first_reflection_snapshots_the_current_draft(monkeypatch) -> None:
    monkeypatch.setenv("MAX_REFLECTION_ATTEMPTS", "2")
    result = reflection_node({
        "failure_type": "quality", "reflection_count": 0, "reflection_critiques": [],
        "agent_drafts": {"technical": "first draft"},
        "validation_result": {"technical": {"passed": False, "failed_rules": [], "reasoning": "weak"}},
    })
    assert result["pre_reflection_drafts"] == {"technical": "first draft"}


def test_second_reflection_does_not_overwrite_the_first_snapshot(monkeypatch) -> None:
    # A second reflection pass sees the redrafted text in agent_drafts, but the
    # snapshot must still hold the ORIGINAL draft, not this intermediate one -
    # otherwise response_judge_node's fallback would compare against the wrong draft.
    monkeypatch.setenv("MAX_REFLECTION_ATTEMPTS", "2")
    result = reflection_node({
        "failure_type": "quality", "reflection_count": 1, "reflection_critiques": ["first critique"],
        "agent_drafts": {"technical": "second draft, after one redraft"},
        "pre_reflection_drafts": {"technical": "first draft"},
        "validation_result": {"technical": {"passed": False, "failed_rules": [], "reasoning": "still weak"}},
    })
    assert result["pre_reflection_drafts"] == {"technical": "first draft"}
    assert result["reflection_count"] == 2

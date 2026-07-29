"""Tests for independent per-domain judge gating."""

from app.graph.validation_node import decide_judge_call


def test_low_score_always_triggers_per_domain(monkeypatch) -> None:
    monkeypatch.setenv("RAG_SCORE_THRESHOLD", "0.3")
    assert decide_judge_call({"technical": 0.2, "billing": 0.9}, "technical") == (True, "low_rag_score")
    assert decide_judge_call({"technical": 0.9, "billing": 0.2}, "billing") == (True, "low_rag_score")


def test_high_score_sampling_rate_is_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("JUDGE_RANDOM_SAMPLE_RATE", "0.175")
    sampled = sum(decide_judge_call({"technical": 0.9}, "technical", seed)[0] for seed in range(1000))
    assert 120 <= sampled <= 230

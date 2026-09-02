"""Record-only Gemini judge node: scores drafts, redacts cache-hit text, never fails the graph."""

import asyncio

from app.graph import response_judge_node as rjn


class _StubScore:
    def __init__(self, overall=4):
        self.overall = overall

    def to_dict(self):
        return {"overall_score": self.overall, "judge_model": "stub-model"}


def _state(**overrides: object) -> dict:
    base = {"agent_drafts": {"technical": "Please wait for reversal."}, "retrieved_context": {},
            "redacted_text": "Payment failed but the money was taken from my bank account.",
            "raw_text": "Payment failed but the money was taken from my bank account.",
            "priority": "High", "category": "Billing"}
    return {**base, **overrides}


def test_scores_every_domain_with_a_draft(monkeypatch) -> None:
    async def few_shots(*_: object) -> list:
        return []

    async def evaluate(*_: object) -> _StubScore:
        return _StubScore(overall=4)

    monkeypatch.setattr(rjn, "select_few_shots", few_shots)
    monkeypatch.setattr(rjn, "evaluate_draft", evaluate)

    result = asyncio.run(rjn.response_judge_node(_state()))
    assert result["judge_evaluations"] == {"technical": {"overall_score": 4, "judge_model": "stub-model"}}


def test_skips_domains_with_no_draft(monkeypatch) -> None:
    calls = []

    async def few_shots(*_: object) -> list:
        return []

    async def evaluate(*_: object) -> _StubScore:
        calls.append(1)
        return _StubScore()

    monkeypatch.setattr(rjn, "select_few_shots", few_shots)
    monkeypatch.setattr(rjn, "evaluate_draft", evaluate)

    result = asyncio.run(rjn.response_judge_node(_state(agent_drafts={"technical": None})))
    assert result["judge_evaluations"] == {} and not calls


def test_no_drafts_short_circuits_without_judge_evaluations_key(monkeypatch) -> None:
    def boom(*_: object):
        raise AssertionError("judge should not be called when there are no drafts")

    monkeypatch.setattr(rjn, "evaluate_draft", boom)
    result = asyncio.run(rjn.response_judge_node(_state(agent_drafts={})))
    assert "judge_evaluations" not in result


def test_cache_hit_ticket_redacts_raw_text_before_judging(monkeypatch) -> None:
    seen = {}

    async def few_shots(ticket_text, *_: object) -> list:
        seen["ticket_text"] = ticket_text
        return []

    async def evaluate(draft, priority, category, ticket_issue, *_: object) -> _StubScore:
        seen["ticket_issue"] = ticket_issue
        return _StubScore()

    def fake_mask_pii(text: str):
        return "[REDACTED] but the money was taken from my bank account.", [{"type": "email"}]

    monkeypatch.setattr(rjn, "select_few_shots", few_shots)
    monkeypatch.setattr(rjn, "evaluate_draft", evaluate)
    monkeypatch.setattr(rjn, "mask_pii", fake_mask_pii)

    state = _state(redacted_text=None)
    asyncio.run(rjn.response_judge_node(state))
    assert seen["ticket_text"].startswith("[REDACTED]")
    assert seen["ticket_issue"].startswith("[REDACTED]")


def test_judge_failure_is_swallowed_not_raised(monkeypatch) -> None:
    async def few_shots(*_: object) -> list:
        return []

    async def evaluate(*_: object):
        raise RuntimeError("gemini unavailable")

    monkeypatch.setattr(rjn, "select_few_shots", few_shots)
    monkeypatch.setattr(rjn, "evaluate_draft", evaluate)

    result = asyncio.run(rjn.response_judge_node(_state()))
    assert result["judge_evaluations"] == {}

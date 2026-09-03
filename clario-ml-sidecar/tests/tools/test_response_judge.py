"""ResponseJudge: a judge outage must raise, never come back disguised as a real 1/5 score."""

import asyncio

import pytest

from app.tools.response_judge import JudgeConfig, ResponseJudge


def _judge(**config_overrides) -> ResponseJudge:
    """Build a ResponseJudge without ever constructing a real client."""
    judge = ResponseJudge.__new__(ResponseJudge)
    config_overrides.setdefault("max_retries", 0)
    # Most of these tests monkeypatch a specific provider's _call_* method,
    # so pin the provider explicitly rather than relying on JudgeConfig's
    # default - which one that is may change independently of these tests.
    config_overrides.setdefault("provider", "gemini")
    judge.config = JudgeConfig(**config_overrides)
    judge.client = None
    return judge


VALID_JSON = (
    '{"overall_score": 4, "priority_tone_match_score": 4, "completeness_score": 4, '
    '"accuracy_score": 4, "policy_compliance_score": 4, "groundedness_score": 4, '
    '"reasoning": "Solid response.", "improvement_suggestions": [], '
    '"required_phrases_present": [], "required_phrases_missing": [], "forbidden_phrases_found": []}'
)


def test_parse_response_raises_on_malformed_json_instead_of_faking_a_score() -> None:
    judge = _judge()
    with pytest.raises(ValueError):
        judge._parse_response("not json at all", latency_ms=10)


def test_parse_response_parses_valid_json_normally() -> None:
    judge = _judge()
    score = judge._parse_response(VALID_JSON, latency_ms=10)
    assert score.overall_score == 4
    assert score.judge_model == judge.config.model_name


def test_evaluate_raises_after_every_retry_is_exhausted(monkeypatch) -> None:
    judge = _judge()

    async def always_fails(prompt: str) -> str:
        raise RuntimeError("gemini unavailable")

    monkeypatch.setattr(judge, "_call_gemini", always_fails)

    with pytest.raises(RuntimeError):
        asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))


def test_evaluate_retries_a_malformed_json_response_instead_of_returning_it_as_a_score(
    monkeypatch,
) -> None:
    judge = _judge(max_retries=1)
    calls = {"n": 0}

    async def flaky(prompt: str) -> str:
        calls["n"] += 1
        return "not json" if calls["n"] == 1 else VALID_JSON

    async def no_backoff(attempt: int) -> None:
        return None

    monkeypatch.setattr(judge, "_call_gemini", flaky)
    monkeypatch.setattr(judge, "_backoff", no_backoff)

    score = asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))
    assert score.overall_score == 4
    assert calls["n"] == 2


def test_evaluate_still_returns_a_real_score_for_an_empty_draft() -> None:
    """An empty draft is a genuine 1/5, not a judge failure - must not raise."""
    judge = _judge()
    score = asyncio.run(judge.evaluate("   ", "High", "Technical", "issue"))
    assert score.overall_score == 1
    assert "Empty draft" in score.reasoning


def test_openai_is_the_default_provider() -> None:
    config = JudgeConfig()
    assert config.provider == "openai"
    assert config.model_name == "gpt-5.6-luna"


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs) -> _FakeCompletion:
        self.calls.append(kwargs)
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeOpenAIClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def test_evaluate_scores_a_draft_via_the_openai_path() -> None:
    judge = _judge(provider="openai", model_name="gpt-5.6-luna")
    judge.client = _FakeOpenAIClient(VALID_JSON)

    score = asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))

    assert score.overall_score == 4
    assert score.judge_model == "gpt-5.6-luna"
    call = judge.client.chat.completions.calls[0]
    assert call["model"] == "gpt-5.6-luna"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["role"] == "user"


def test_evaluate_raises_after_every_retry_is_exhausted_on_openai_too(monkeypatch) -> None:
    judge = _judge(provider="openai")

    async def always_fails(prompt: str) -> str:
        raise RuntimeError("openai unavailable")

    monkeypatch.setattr(judge, "_call_openai", always_fails)

    with pytest.raises(RuntimeError):
        asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))

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


def test_gemini_is_the_default_provider() -> None:
    """Gemini, not OpenAI, because the configured GEMINI_API_KEY runs on a
    free tier - every OpenAI model requires paid credits regardless of tier."""
    config = JudgeConfig()
    assert config.provider == "gemini"
    assert config.model_name == "gemini-flash-latest"


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
    judge = _judge(provider="openai", model_name="gpt-5.4-mini")
    judge.client = _FakeOpenAIClient(VALID_JSON)

    score = asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))

    assert score.overall_score == 4
    assert score.judge_model == "gpt-5.4-mini"
    call = judge.client.chat.completions.calls[0]
    assert call["model"] == "gpt-5.4-mini"
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][1]["role"] == "user"


def test_evaluate_scores_a_draft_via_the_deepseek_path() -> None:
    """DeepSeek is OpenAI-API-compatible, so it shares _call_openai - this
    proves the shared path also carries the deepseek model name through."""
    judge = _judge(provider="deepseek", model_name="deepseek-v4-flash")
    judge.client = _FakeOpenAIClient(VALID_JSON)

    score = asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))

    assert score.overall_score == 4
    assert score.judge_model == "deepseek-v4-flash"
    call = judge.client.chat.completions.calls[0]
    assert call["model"] == "deepseek-v4-flash"
    assert call["response_format"] == {"type": "json_object"}


def test_deepseek_provider_builds_an_openai_compatible_client_at_deepseeks_base_url(
    monkeypatch,
) -> None:
    """The only deepseek-specific code is in __init__ (model default + base_url) -
    the _judge() test helper bypasses __init__ entirely, so this exercises it for real."""
    monkeypatch.setenv("RESPONSE_JUDGE_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.delenv("DEEPSEEK_JUDGE_MODEL", raising=False)

    judge = ResponseJudge()

    assert judge.config.provider == "deepseek"
    assert judge.config.model_name == "deepseek-v4-flash"
    assert str(judge.client.base_url) == "https://api.deepseek.com"
    assert judge.client.api_key == "test-deepseek-key"


def test_evaluate_raises_after_every_retry_is_exhausted_on_openai_too(monkeypatch) -> None:
    judge = _judge(provider="openai")

    async def always_fails(prompt: str) -> str:
        raise RuntimeError("openai unavailable")

    monkeypatch.setattr(judge, "_call_openai", always_fails)

    with pytest.raises(RuntimeError):
        asyncio.run(judge.evaluate("Some draft.", "High", "Technical", "issue"))


def test_compare_draft_to_reference_agrees_across_both_passes() -> None:
    judge = _judge()
    call_count = {"n": 0}

    async def fake_call_gemini(prompt, system_prompt=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return '{"winner": "A", "reasoning": "More complete."}'
        return '{"winner": "B", "reasoning": "More complete (order 2)."}'

    judge._call_gemini = fake_call_gemini

    verdict = asyncio.run(judge.compare_draft_to_reference(
        ticket_issue="Cannot log in",
        priority="Medium",
        category="Login Issue",
        draft="Try resetting your password.",
        reference="Please clear your cache.",
    ))

    assert verdict.winner_pass1 == "draft"
    assert verdict.winner_pass2 == "draft"
    assert verdict.final_winner == "draft"
    assert verdict.reasoning_pass1 == "More complete."
    assert verdict.reasoning_pass2 == "More complete (order 2)."
    assert call_count["n"] == 2


def test_compare_draft_to_reference_reconciles_disagreement_to_tie() -> None:
    judge = _judge()
    call_count = {"n": 0}

    async def fake_call_gemini(prompt, system_prompt=None):
        call_count["n"] += 1
        # pass1: draft in slot A -> "A" wins -> winner_pass1 = "draft"
        # pass2: reference in slot A, draft in slot B -> "A" wins -> winner_pass2 = "reference"
        return '{"winner": "A", "reasoning": "A wins this round."}'

    judge._call_gemini = fake_call_gemini

    verdict = asyncio.run(judge.compare_draft_to_reference(
        ticket_issue="x", priority="Medium", category="Bug Report", draft="d", reference="r",
    ))

    assert verdict.winner_pass1 == "draft"
    assert verdict.winner_pass2 == "reference"
    assert verdict.final_winner == "tie"


def test_parse_pairwise_response_raises_on_malformed_json() -> None:
    judge = _judge()
    with pytest.raises(ValueError):
        judge._parse_pairwise_response("not json at all")


def test_parse_pairwise_response_defaults_unrecognized_winner_to_tie() -> None:
    judge = _judge()
    result = judge._parse_pairwise_response('{"winner": "C", "reasoning": "weird"}')
    assert result["winner"] == "tie"


def test_parse_pairwise_response_defaults_missing_reasoning() -> None:
    judge = _judge()
    result = judge._parse_pairwise_response('{"winner": "A"}')
    assert result["reasoning"] == "No reasoning provided by judge."


def test_compare_draft_to_reference_raises_after_retries_exhausted() -> None:
    judge = _judge(max_retries=0)

    async def fake_call_gemini(prompt, system_prompt=None):
        raise RuntimeError("boom")

    judge._call_gemini = fake_call_gemini

    with pytest.raises(RuntimeError):
        asyncio.run(judge.compare_draft_to_reference(
            ticket_issue="x", priority="Medium", category="Bug Report", draft="d", reference="r",
        ))

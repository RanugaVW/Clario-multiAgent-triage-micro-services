"""Shared fixtures for orchestration unit tests."""

import pytest


@pytest.fixture
def ticket_state() -> dict[str, str]:
    return {
        "ticket_id": "TCK-1001",
        "category": "technical",
        "description": "The password reset link has expired.",
        "state": "new",
    }


@pytest.fixture(autouse=True)
def _fresh_gemini_pool(monkeypatch):
    """Give every test an empty, environment-independent Gemini client pool.

    gemini_pool builds its clients once and keeps them in module globals. Tests replace ``genai.Client`` with a
    fake per test, but the pool would keep whichever fake it built first and hand that stale client to every later
    test (results then depend on test order). And a developer's own GEMINI_API_KEY* - from the shell or from a
    gitignored .env that local_llm re-reads on each call - makes the pool call ``genai.Client(api_key=...)``,
    which the no-argument fakes do not accept, so the suite passed only where no key exists (CI).
    """
    import sys

    from app.tools import gemini_pool

    for name in gemini_pool._KEY_ENV_NAMES + ["GOOGLE_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    local_llm = sys.modules.get("app.tools.local_llm")
    if local_llm is not None:
        monkeypatch.setattr(local_llm, "load_dotenv", lambda *args, **kwargs: False)

    def _reset() -> None:
        gemini_pool._clients = None
        gemini_pool._cycle = None
        gemini_pool._dead.clear()

    _reset()
    yield
    _reset()

"""Tests for circuit-breaker state transitions and short-circuiting."""

from app.tools.circuit_breaker import CircuitBreaker


def test_breaker_opens_and_short_circuits_after_threshold() -> None:
    breaker = CircuitBreaker("test", failure_threshold=2, window_size=3, cooldown_seconds=60)
    assert breaker.allow_request()
    breaker.record_failure()
    assert breaker.allow_request()
    breaker.record_failure()
    assert breaker.state == "open"
    assert not breaker.allow_request()


def test_half_open_success_closes_breaker(monkeypatch) -> None:
    breaker = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=1)
    breaker.record_failure()
    monkeypatch.setattr("app.tools.circuit_breaker.time.monotonic", lambda: breaker.opened_at + 2)
    assert breaker.allow_request() and breaker.state == "half_open"
    breaker.record_success()
    assert breaker.state == "closed"

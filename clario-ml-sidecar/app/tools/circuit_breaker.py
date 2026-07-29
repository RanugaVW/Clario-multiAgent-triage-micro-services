"""Small in-process circuit breakers for external orchestration dependencies."""

from __future__ import annotations

import os
import time
from collections import deque


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a dependency is short-circuited without making a call."""


class CircuitBreaker:
    """Track a rolling outcome window with closed, open, and half-open states."""

    def __init__(self, name: str, failure_threshold: int | None = None,
                 window_size: int | None = None, cooldown_seconds: int | None = None) -> None:
        self.name = name
        self.failure_threshold = failure_threshold or int(os.getenv("BREAKER_FAILURE_THRESHOLD", "5"))
        self.window_size = window_size or int(os.getenv("BREAKER_WINDOW_SIZE", "10"))
        self.cooldown_seconds = cooldown_seconds or int(os.getenv("BREAKER_COOLDOWN_SECONDS", "60"))
        self.outcomes: deque[bool] = deque(maxlen=self.window_size)
        self.state = "closed"
        self.opened_at: float | None = None
        self._half_open_in_flight = False

    def allow_request(self) -> bool:
        """Return whether one dependency call may be attempted right now."""
        if self.state == "closed":
            return True
        if self.state == "open" and time.monotonic() - (self.opened_at or 0) >= self.cooldown_seconds:
            self.state, self._half_open_in_flight = "half_open", False
        if self.state == "half_open" and not self._half_open_in_flight:
            self._half_open_in_flight = True
            return True
        return False

    def record_success(self) -> None:
        """Close the breaker after a successful dependency call."""
        self.outcomes.append(True)
        self.state, self.opened_at, self._half_open_in_flight = "closed", None, False

    def record_failure(self) -> None:
        """Record failure and open once the rolling failure threshold is reached."""
        self.outcomes.append(False)
        self._half_open_in_flight = False
        if self.state == "half_open" or sum(not outcome for outcome in self.outcomes) >= self.failure_threshold:
            self.state, self.opened_at = "open", time.monotonic()


_BREAKERS: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    """Return the named process-local breaker shared by all relevant tool calls."""
    if name not in _BREAKERS:
        _BREAKERS[name] = CircuitBreaker(name)
    return _BREAKERS[name]

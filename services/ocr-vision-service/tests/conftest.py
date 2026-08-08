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

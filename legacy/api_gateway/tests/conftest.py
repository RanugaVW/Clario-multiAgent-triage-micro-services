"""Shared API-gateway fixtures.

Replace the placeholders with a test database session and ASGI client when the
gateway application exposes them.
"""

import pytest


@pytest.fixture
def ticket_payload() -> dict[str, str]:
    return {
        "subject": "Cannot sign in",
        "description": "The password reset link has expired.",
        "category": "technical",
        "priority": "high",
    }

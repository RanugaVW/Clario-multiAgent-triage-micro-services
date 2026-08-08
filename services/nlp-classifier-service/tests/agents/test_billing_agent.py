import pytest

pytestmark = pytest.mark.skip(reason="The billing agent has not been implemented.")


def test_billing_agent_creates_a_policy_compliant_draft() -> None:
    """Billing replies should handle charges without exposing sensitive information."""

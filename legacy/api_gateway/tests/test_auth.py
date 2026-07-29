import pytest

pytestmark = pytest.mark.skip(reason="Authentication endpoints have not been implemented.")


def test_authentication_requires_valid_credentials() -> None:
    """Define the expected rejection behavior once auth routes exist."""

import pytest

pytestmark = pytest.mark.skip(reason="The runtime redaction tool has not been implemented.")


def test_redaction_tool_removes_sensitive_values() -> None:
    """Runtime redaction must not pass raw PII to downstream agents."""

"""run_policy_checks: expected_placeholders exempt our own fake stand-ins from the PII-leak check."""

from app.graph.validation_node import run_policy_checks


def test_sanctioned_placeholder_does_not_trip_pii_in_draft() -> None:
    draft = "Hi Jordan Blake, please clear your cache and cookies."
    result = run_policy_checks(draft, [], [], frozenset({"Jordan Blake"}))
    assert "pii_in_draft" not in result["failed_rules"]


def test_unsanctioned_pii_still_trips_pii_in_draft() -> None:
    """A name that snuck into the draft but isn't one of our sanctioned stand-ins is still a leak."""
    draft = "Hi Jordan Blake, by the way your colleague Sam Carter also has this issue."
    result = run_policy_checks(draft, [], [], frozenset({"Jordan Blake"}))
    assert "pii_in_draft" in result["failed_rules"]


def test_no_placeholders_preserves_prior_behavior() -> None:
    draft = "Hi Jordan Blake, please clear your cache and cookies."
    result = run_policy_checks(draft, [], [])
    assert "pii_in_draft" in result["failed_rules"]


def test_clean_draft_passes_with_no_placeholders_needed() -> None:
    draft = "Please clear your cache and cookies, then try again."
    result = run_policy_checks(draft, [], [])
    assert "pii_in_draft" not in result["failed_rules"]

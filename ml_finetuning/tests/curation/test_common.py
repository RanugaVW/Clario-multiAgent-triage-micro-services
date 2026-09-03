from src.curation.sources.common import RawExample, has_pii, strip_html


def test_has_pii_detects_email():
    assert has_pii("contact me at jane.doe@example.com") is True


def test_has_pii_detects_phone_number():
    assert has_pii("call me at +1 415-555-0134") is True


def test_has_pii_false_for_clean_text():
    assert has_pii("I cannot log in to the course dashboard.") is False


def test_has_pii_checks_every_argument():
    assert has_pii("clean text", "email me: a@b.com") is True


def test_strip_html_removes_tags_and_collapses_whitespace():
    html = "<p>Please  <strong>clear</strong>\n your cache.</p>"
    assert strip_html(html) == "Please clear your cache."


def test_raw_example_is_a_plain_dataclass():
    example = RawExample(
        issue_text="I can't log in",
        resolution_text="Try resetting your password",
        source_url="https://example.com/t/1",
        original_id="1",
        responder_role="staff",
    )
    assert example.issue_text == "I can't log in"

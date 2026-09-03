from src.curation.sources import moodle_jira


def _search_result():
    return {
        "issues": [
            {
                "key": "MDL-1001",
                "fields": {
                    "summary": "Cannot log in after password reset",
                    "description": "I reset my password but still can't sign in.",
                    "reporter": {"accountId": "reporter-1"},
                },
            }
        ]
    }


def test_fetch_returns_example_from_non_reporter_comment(monkeypatch):
    monkeypatch.setattr(moodle_jira, "_search_issues", lambda jql, max_results: _search_result()["issues"])
    monkeypatch.setattr(
        moodle_jira,
        "_fetch_comments",
        lambda key: {
            "comments": [
                {"author": {"accountId": "reporter-1"}, "body": "Still broken for me too."},
                {"author": {"accountId": "dev-1"}, "body": "This is fixed by clearing the session cache table."},
            ]
        },
    )

    results = moodle_jira.fetch("Login Issue", ["login"], limit=5)

    assert len(results) == 1
    assert results[0].original_id == "MDL-1001"
    assert results[0].resolution_text == "This is fixed by clearing the session cache table."
    assert results[0].source_url == "https://moodle.atlassian.net/browse/MDL-1001"


def test_fetch_skips_issue_with_no_non_reporter_comment(monkeypatch):
    monkeypatch.setattr(moodle_jira, "_search_issues", lambda jql, max_results: _search_result()["issues"])
    monkeypatch.setattr(
        moodle_jira,
        "_fetch_comments",
        lambda key: {"comments": [{"author": {"accountId": "reporter-1"}, "body": "bump"}]},
    )

    results = moodle_jira.fetch("Login Issue", ["login"], limit=5)

    assert results == []


def test_fetch_skips_short_comments(monkeypatch):
    monkeypatch.setattr(moodle_jira, "_search_issues", lambda jql, max_results: _search_result()["issues"])
    monkeypatch.setattr(
        moodle_jira,
        "_fetch_comments",
        lambda key: {"comments": [{"author": {"accountId": "dev-1"}, "body": "ok"}]},
    )

    results = moodle_jira.fetch("Login Issue", ["login"], limit=5)

    assert results == []


def test_fetch_returns_empty_list_for_empty_keywords():
    assert moodle_jira.fetch("Login Issue", [], limit=5) == []


def test_fetch_returns_empty_list_on_search_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise moodle_jira.httpx.HTTPError("boom")

    monkeypatch.setattr(moodle_jira, "_search_issues", _raise)

    assert moodle_jira.fetch("Login Issue", ["login"], limit=5) == []

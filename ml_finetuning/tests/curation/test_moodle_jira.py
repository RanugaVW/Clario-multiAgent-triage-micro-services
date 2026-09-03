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


def test_fetch_builds_jql_with_project_and_keywords(monkeypatch):
    captured = {}

    def _capture_search(jql, max_results):
        captured["jql"] = jql
        return []

    monkeypatch.setattr(moodle_jira, "_search_issues", _capture_search)

    moodle_jira.fetch("Login Issue", ["login", "sign in"], limit=5)

    assert "project = MDL" in captured["jql"]
    assert 'text ~ "login"' in captured["jql"]
    assert 'text ~ "sign in"' in captured["jql"]


def test_fetch_returns_empty_list_on_search_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise moodle_jira.httpx.HTTPError("boom")

    monkeypatch.setattr(moodle_jira, "_search_issues", _raise)

    assert moodle_jira.fetch("Login Issue", ["login"], limit=5) == []


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"issues": []}


def test_search_issues_follows_redirects(monkeypatch):
    captured = {}

    def _fake_get(url, **kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(moodle_jira.httpx, "get", _fake_get)

    moodle_jira._search_issues("project = MDL", max_results=5)

    assert captured.get("follow_redirects") is True


def test_fetch_comments_follows_redirects(monkeypatch):
    captured = {}

    def _fake_get(url, **kwargs):
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(moodle_jira.httpx, "get", _fake_get)

    moodle_jira._fetch_comments("MDL-1001")

    assert captured.get("follow_redirects") is True


def test_search_issues_uses_the_non_deprecated_search_endpoint(monkeypatch):
    captured = {}

    def _fake_get(url, **kwargs):
        captured["url"] = url
        return _FakeResponse()

    monkeypatch.setattr(moodle_jira.httpx, "get", _fake_get)

    moodle_jira._search_issues("project = MDL", max_results=5)

    # GET /rest/api/2/search was deprecated by Atlassian (returns 410 Gone);
    # /rest/api/2/search/jql is the documented replacement.
    assert captured["url"] == "https://moodle.atlassian.net/rest/api/2/search/jql"

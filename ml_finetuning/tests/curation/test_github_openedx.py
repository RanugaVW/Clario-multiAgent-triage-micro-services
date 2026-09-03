import httpx

from src.curation.sources import github_openedx


def _issue():
    return {
        "number": 42,
        "title": "Video player crashes on lesson open",
        "body": "The video player throws an error whenever I open a lesson.",
        "html_url": "https://github.com/openedx/edx-platform/issues/42",
    }


def test_fetch_returns_example_from_staff_comment(monkeypatch):
    monkeypatch.setattr(github_openedx, "_search_issues", lambda query, per_page: [_issue()])
    monkeypatch.setattr(
        github_openedx,
        "_fetch_comments",
        lambda number: [
            {"author_association": "NONE", "body": "same issue here"},
            {
                "author_association": "MEMBER",
                "body": "This was fixed in the latest release, please update your player package.",
            },
        ],
    )

    results = github_openedx.fetch("Bug Report", ["crash"], limit=5)

    assert len(results) == 1
    assert results[0].responder_role == "MEMBER"
    assert results[0].original_id == "42"
    assert "fixed in the latest release" in results[0].resolution_text


def test_fetch_skips_issue_with_no_staff_comment(monkeypatch):
    monkeypatch.setattr(github_openedx, "_search_issues", lambda query, per_page: [_issue()])
    monkeypatch.setattr(
        github_openedx,
        "_fetch_comments",
        lambda number: [{"author_association": "NONE", "body": "same issue here, please fix"}],
    )

    assert github_openedx.fetch("Bug Report", ["crash"], limit=5) == []


def test_fetch_skips_short_staff_comments(monkeypatch):
    monkeypatch.setattr(github_openedx, "_search_issues", lambda query, per_page: [_issue()])
    monkeypatch.setattr(
        github_openedx,
        "_fetch_comments",
        lambda number: [{"author_association": "MEMBER", "body": "ok"}],
    )

    assert github_openedx.fetch("Bug Report", ["crash"], limit=5) == []


def test_fetch_returns_empty_list_for_empty_keywords():
    assert github_openedx.fetch("Bug Report", [], limit=5) == []


def test_fetch_returns_empty_list_on_search_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise github_openedx.httpx.HTTPError("boom")

    monkeypatch.setattr(github_openedx, "_search_issues", _raise)

    assert github_openedx.fetch("Bug Report", ["crash"], limit=5) == []


def test_fetch_builds_query_with_repo_and_keywords(monkeypatch):
    captured = {}

    def _capture_search(query, per_page):
        captured["query"] = query
        return []

    monkeypatch.setattr(github_openedx, "_search_issues", _capture_search)

    github_openedx.fetch("Bug Report", ["crash", "error"], limit=5)

    assert "repo:openedx/edx-platform" in captured["query"]
    # Keywords must be grouped in parentheses - GitHub's search API returns
    # 422 Unprocessable Entity for a bare "qualifier qualifier term OR term"
    # query; explicit grouping is the documented way to combine terms with OR.
    assert "(crash OR error)" in captured["query"]


class _FakeResponse:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_data


def test_get_json_retries_once_after_403_with_retry_after(monkeypatch):
    calls = {"n": 0}

    def _fake_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResponse(403, headers={"Retry-After": "1"})
        return _FakeResponse(200, json_data={"items": [_issue()]})

    monkeypatch.setattr(github_openedx.httpx, "get", _fake_get)
    monkeypatch.setattr(github_openedx.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        github_openedx,
        "_fetch_comments",
        lambda number: [
            {
                "author_association": "MEMBER",
                "body": "This was fixed in the latest release, please update your player package.",
            }
        ],
    )

    results = github_openedx.fetch("Bug Report", ["crash"], limit=5)

    assert len(results) == 1
    assert calls["n"] == 2


def test_get_json_follows_redirects(monkeypatch):
    captured = {}

    def _fake_get(url, **kwargs):
        captured.update(kwargs)
        return _FakeResponse(200, json_data={"items": []})

    monkeypatch.setattr(github_openedx.httpx, "get", _fake_get)

    github_openedx._get_json("https://api.github.com/search/issues", params={"q": "x"})

    assert captured.get("follow_redirects") is True

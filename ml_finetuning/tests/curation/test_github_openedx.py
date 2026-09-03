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

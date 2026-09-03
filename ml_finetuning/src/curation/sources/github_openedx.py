"""Fetch real bug-report/login/performance resolutions from Open edX's
GitHub Issues.

Works unauthenticated at GitHub's default rate limit; set GITHUB_TOKEN
(a read-only, public-repo-scope personal access token) in
ml_finetuning/.env for a much higher rate limit.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

from .common import RawExample

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.github.com/search/issues"
_COMMENTS_URL = "https://api.github.com/repos/openedx/edx-platform/issues/{number}/comments"
_REPO_QUERY = "repo:openedx/edx-platform is:issue"
_STAFF_ASSOCIATIONS = {"MEMBER", "COLLABORATOR", "OWNER"}
_MIN_COMMENT_LEN = 40
_REQUEST_DELAY_SECONDS = 1.0
_DEFAULT_RETRY_AFTER_SECONDS = 60


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning("GITHUB_TOKEN not set; github_openedx fetcher runs at the unauthenticated rate limit.")
    return headers


def _get_json(url: str, params: dict | None = None):
    response = httpx.get(url, params=params, headers=_headers(), timeout=30.0, follow_redirects=True)
    if response.status_code in (403, 429):
        retry_after = int(response.headers.get("Retry-After", _DEFAULT_RETRY_AFTER_SECONDS))
        logger.warning(f"GitHub rate limited on {url}; waiting {retry_after}s and retrying once.")
        time.sleep(retry_after)
        response = httpx.get(url, params=params, headers=_headers(), timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def _search_issues(query: str, per_page: int) -> list[dict]:
    result = _get_json(_SEARCH_URL, params={"q": query, "per_page": per_page})
    return result.get("items", [])


def _fetch_comments(number: int) -> list[dict]:
    return _get_json(_COMMENTS_URL.format(number=number))


def fetch(category: str, keywords: list[str], limit: int) -> list[RawExample]:
    """Fetch up to `limit` real issue+maintainer-response pairs matching `keywords`."""
    if limit <= 0 or not keywords:
        return []

    query = f"{_REPO_QUERY} ({' OR '.join(keywords)})"

    try:
        issues = _search_issues(query, per_page=min(limit * 3, 100))
    except httpx.HTTPError as e:
        logger.warning(f"GitHub issue search failed for category={category!r}: {e}")
        return []

    examples: list[RawExample] = []
    for issue in issues:
        if len(examples) >= limit:
            break

        number = issue["number"]
        issue_text = f"{issue.get('title', '')}\n\n{issue.get('body') or ''}".strip()

        time.sleep(_REQUEST_DELAY_SECONDS)
        try:
            comments = _fetch_comments(number)
        except httpx.HTTPError as e:
            logger.warning(f"GitHub comment fetch failed for issue #{number}: {e}")
            continue

        resolution_text = ""
        responder_role = ""
        for comment in comments:
            association = comment.get("author_association", "")
            if association not in _STAFF_ASSOCIATIONS:
                continue
            body = comment.get("body") or ""
            if len(body) < _MIN_COMMENT_LEN:
                continue
            resolution_text = body
            responder_role = association
            break

        if not issue_text or not resolution_text:
            continue

        examples.append(
            RawExample(
                issue_text=issue_text,
                resolution_text=resolution_text,
                source_url=issue.get("html_url", f"https://github.com/openedx/edx-platform/issues/{number}"),
                original_id=str(number),
                responder_role=responder_role,
            )
        )

    return examples

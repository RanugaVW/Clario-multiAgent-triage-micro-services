"""Fetch real login/bug-report resolutions from Moodle's public Jira.

No authentication required. Moodle's Jira (moodle.atlassian.net) exposes
a public, unauthenticated REST API for the MDL project.
"""

from __future__ import annotations

import logging
import time
from typing import List

import httpx

from .common import RawExample

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://moodle.atlassian.net/rest/api/2/search"
_COMMENT_URL = "https://moodle.atlassian.net/rest/api/2/issue/{key}/comment"
_MIN_COMMENT_LEN = 40
_REQUEST_DELAY_SECONDS = 0.5


def _search_issues(jql: str, max_results: int) -> list[dict]:
    response = httpx.get(
        _SEARCH_URL,
        params={"jql": jql, "fields": "summary,description,reporter", "maxResults": max_results},
        timeout=30.0,
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json().get("issues", [])


def _fetch_comments(key: str) -> dict:
    response = httpx.get(_COMMENT_URL.format(key=key), timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def fetch(category: str, keywords: List[str], limit: int) -> List[RawExample]:
    """Fetch up to `limit` real issue+resolution pairs matching `keywords`."""
    if limit <= 0 or not keywords:
        return []

    jql_text = " OR ".join(f'text ~ "{keyword}"' for keyword in keywords)
    jql = f"project = MDL AND ({jql_text})"

    try:
        issues = _search_issues(jql, max_results=limit * 3)
    except httpx.HTTPError as e:
        logger.warning(f"Moodle Jira search failed for category={category!r}: {e}")
        return []

    examples: List[RawExample] = []
    for issue in issues:
        if len(examples) >= limit:
            break

        key = issue["key"]
        fields = issue.get("fields", {})
        summary = fields.get("summary") or ""
        description = fields.get("description") or ""
        issue_text = f"{summary}\n\n{description}".strip()
        reporter_id = (fields.get("reporter") or {}).get("accountId")

        time.sleep(_REQUEST_DELAY_SECONDS)
        try:
            comments = _fetch_comments(key).get("comments", [])
        except httpx.HTTPError as e:
            logger.warning(f"Moodle Jira comment fetch failed for {key}: {e}")
            continue

        resolution_text = ""
        for comment in comments:
            if (comment.get("author") or {}).get("accountId") == reporter_id:
                continue
            body = comment.get("body") or ""
            if len(body) < _MIN_COMMENT_LEN:
                continue
            resolution_text = body
            break

        if not issue_text or not resolution_text:
            continue

        examples.append(
            RawExample(
                issue_text=issue_text,
                resolution_text=resolution_text,
                source_url=f"https://moodle.atlassian.net/browse/{key}",
                original_id=key,
                responder_role="commenter",
            )
        )

    return examples

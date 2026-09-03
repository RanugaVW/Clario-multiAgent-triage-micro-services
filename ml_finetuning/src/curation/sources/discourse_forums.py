"""Fetch real support-thread resolutions from Discourse-based community
forums, across all 7 categories on a best-effort basis.

Uses each forum's public Discourse JSON API (search.json + t/<id>.json).
No authentication required.

community.udemy.com's platform is unverified as of writing this (it was
hedged as "Discourse or Vanilla" during research, with a Vanilla-style
example URL) - if it isn't actually Discourse, requests against it will
404, get logged, and be skipped (see fetch()'s per-host error handling)
rather than crash, but that host will silently contribute 0 examples.
discuss.openedx.org is confirmed Discourse.
"""

from __future__ import annotations

import logging
import time

import httpx

from .common import RawExample, strip_html

logger = logging.getLogger(__name__)

_HOSTS = ("community.udemy.com", "discuss.openedx.org")
_MIN_POST_LEN = 40
_REQUEST_DELAY_SECONDS = 1.0


def _search_topics(host: str, keyword: str) -> list[dict]:
    response = httpx.get(f"https://{host}/search.json", params={"q": keyword}, timeout=30.0)
    response.raise_for_status()
    return response.json().get("topics", [])


def _fetch_thread(host: str, topic_id: int) -> dict:
    response = httpx.get(f"https://{host}/t/{topic_id}.json", timeout=30.0)
    response.raise_for_status()
    return response.json()


def _is_staff(post: dict) -> bool:
    return bool(post.get("staff") or post.get("admin") or post.get("moderator"))


def fetch(category: str, keywords: list[str], limit: int) -> list[RawExample]:
    """Fetch up to `limit` real thread+staff-reply pairs matching `keywords`."""
    if limit <= 0 or not keywords:
        return []

    examples: list[RawExample] = []
    seen: set[tuple[str, int]] = set()

    for host in _HOSTS:
        for keyword in keywords:
            if len(examples) >= limit:
                return examples

            try:
                topics = _search_topics(host, keyword)
            except httpx.HTTPError as e:
                logger.warning(f"Discourse search failed on {host} for keyword={keyword!r}: {e}")
                continue

            for topic in topics:
                if len(examples) >= limit:
                    return examples

                topic_id = topic["id"]
                if (host, topic_id) in seen:
                    continue
                seen.add((host, topic_id))

                time.sleep(_REQUEST_DELAY_SECONDS)
                try:
                    thread = _fetch_thread(host, topic_id)
                except httpx.HTTPError as e:
                    logger.warning(f"Discourse thread fetch failed on {host} for topic={topic_id}: {e}")
                    continue

                posts = thread.get("post_stream", {}).get("posts", [])
                if not posts:
                    continue

                issue_text = strip_html(posts[0].get("cooked", ""))
                resolution_text = ""
                for post in posts[1:]:
                    if not _is_staff(post):
                        continue
                    body = strip_html(post.get("cooked") or "")
                    if len(body) < _MIN_POST_LEN:
                        continue
                    resolution_text = body
                    break

                if not issue_text or not resolution_text:
                    continue

                slug = thread.get("slug", str(topic_id))
                examples.append(
                    RawExample(
                        issue_text=issue_text,
                        resolution_text=resolution_text,
                        source_url=f"https://{host}/t/{slug}/{topic_id}",
                        original_id=f"{host}:{topic_id}",
                        responder_role="staff",
                    )
                )

            time.sleep(_REQUEST_DELAY_SECONDS)

    return examples

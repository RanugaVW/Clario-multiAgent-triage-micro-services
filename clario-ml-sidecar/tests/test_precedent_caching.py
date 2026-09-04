"""Coverage for should_cache_precedent() - the gate that decides whether a
resolved ticket's response is safe to store as a reusable RAG precedent.

Real bug this exists to prevent: a customer got a response referencing
"your assignment deadline" that was never mentioned in their own ticket -
a stale cached precedent from an unrelated, semantically-similar ticket was
reused verbatim (see app/graph/cache_check_node.py). should_cache_precedent()
closes two guards found while diagnosing that: never re-cache an already
cache-hit response (which would compound the leak every time it's reused),
and only cache a freshly-generated response the judge independently scored
as grounded in retrieved KB content, not the customer's own narrative.
"""

from app.main import should_cache_precedent


def test_a_cache_hit_is_never_re_cached_regardless_of_score() -> None:
    should_cache, reason = should_cache_precedent(cache_hit=True, groundedness_score=5, min_groundedness=4)
    assert should_cache is False
    assert reason == "cache_hit"


def test_a_well_grounded_fresh_response_is_cached() -> None:
    should_cache, _ = should_cache_precedent(cache_hit=False, groundedness_score=5, min_groundedness=4)
    assert should_cache is True


def test_a_response_scored_below_threshold_is_not_cached() -> None:
    should_cache, reason = should_cache_precedent(cache_hit=False, groundedness_score=2, min_groundedness=4)
    assert should_cache is False
    assert "groundedness_score=2" in reason


def test_exactly_at_threshold_is_cached() -> None:
    should_cache, _ = should_cache_precedent(cache_hit=False, groundedness_score=4, min_groundedness=4)
    assert should_cache is True


def test_a_missing_score_fails_closed_rather_than_caching_unverified_content() -> None:
    """No score usually means the judge call itself errored - treated the
    same as a low score, not as "no reason to block"."""
    should_cache, reason = should_cache_precedent(cache_hit=False, groundedness_score=None, min_groundedness=4)
    assert should_cache is False
    assert "None" in reason

"""Feeds admin-corrected judge scores back into the judge's few-shot pool.

Runs on a 24h schedule (wired up in app/main.py's lifespan via APScheduler).
Only upward score overrides are synced: an admin raising a score means the
judge under-rated a response that was actually good, so it's added to
validation_refs as a new ground-truth reference. A downward override means
the response was bad - embedding it as a "reference" would corrupt the pool,
which few_shot_selector.py treats as all-positive examples - so those are
only logged, not embedded. See Plan/RESPONSE_VALIDATION.md for the full
design rationale.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client, Client

from app.tools.few_shot_selector import upsert_reference
from app.tools.redaction_tool import mask_pii

logger = logging.getLogger(__name__)

_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    """Lazy singleton so importing this module never requires env vars to be set."""
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_PROJECT_URL", "")
        key = os.environ.get("SUPABASE_SECRET_API", "")
        _supabase = create_client(url, key)
    return _supabase


def sync_judge_references(lookback_hours: int = 24) -> dict:
    """Sync recent upward score overrides into validation_refs.

    Returns a summary dict ({"considered", "synced", "skipped"}) for logging/
    testing rather than raising - a failed sync run should never take down
    the sidecar, matching how response_judge_node treats judge failures.
    """
    summary = {"considered": 0, "synced": 0, "skipped": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

    try:
        supabase = _get_supabase()
        result = (
            supabase.table("evaluation_score_overrides")
            .select("*, response_evaluations(*, ticket_drafts(*), tickets(id, raw_text))")
            .gte("created_at", cutoff)
            .execute()
        )
    except Exception as e:
        logger.error(f"Failed to fetch score overrides for judge-reference sync: {e}")
        return summary

    overrides = result.data or []
    summary["considered"] = len(overrides)

    for override in overrides:
        try:
            if _sync_one(override):
                summary["synced"] += 1
            else:
                summary["skipped"] += 1
        except Exception as e:
            logger.warning(f"Failed to sync override {override.get('id')}: {e}")
            summary["skipped"] += 1

    logger.info(
        f"Judge-reference sync: considered={summary['considered']} "
        f"synced={summary['synced']} skipped={summary['skipped']}"
    )
    return summary


def _sync_one(override: dict) -> bool:
    """Sync a single override if it's an upward correction. Returns True if synced."""
    new_score = override.get("overall_score")
    previous_scores = override.get("previous_scores") or {}
    prev_score = previous_scores.get("overall_score")

    if new_score is None or prev_score is None or new_score <= prev_score:
        # Downward or unchanged correction - not a positive reference example.
        return False

    evaluation = override.get("response_evaluations")
    if not evaluation:
        return False

    draft = evaluation.get("ticket_drafts")
    ticket = evaluation.get("tickets")
    if not draft or not ticket:
        return False

    resolution_text = draft.get("draft_text")
    raw_text = ticket.get("raw_text")
    if not resolution_text or not raw_text:
        return False

    redacted_issue, _ = mask_pii(raw_text)
    # Real bug, found live: this only masked the issue side. The draft_text
    # side is an admin-approved response to ONE customer - it can carry that
    # customer's real name (e.g. "Hi Deshan, ...") - and select_few_shots()
    # hands it, unmasked, straight into the judge LLM's prompt for every
    # OTHER customer's ticket it happens to match. Same failure mode as the
    # cache/RAG precedent leaks, different pipeline.
    redacted_resolution, _ = mask_pii(resolution_text)

    upsert_reference(
        ticket_id=ticket["id"],
        issue_text=redacted_issue,
        resolution_text=redacted_resolution,
        domain=evaluation.get("domain") or "technical",
        priority=evaluation.get("priority_at_evaluation") or "Unknown",
        category=evaluation.get("category_at_evaluation") or "Unknown",
        doc_id=f"admin_override_{override['id']}",
    )
    return True

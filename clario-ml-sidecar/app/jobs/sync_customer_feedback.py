"""Feeds customer ratings back into the reference pool.

Runs every 24h (see app/jobs/learning_schedule.py), behind
CUSTOMER_FEEDBACK_LEARNING_ENABLED. A rating of 4-5 on a resolved ticket makes
that ticket+reply a positive exemplar in validation_refs. A rating of 1-2 is
never embedded (the pool is all-positive, see sync_judge_references.py); if
the judge had scored that reply 4+ it is logged to a JSONL file instead - a
"judge missed it" case for later calibration and KB-gap analysis.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.tools.feedback_learning import (
    as_list,
    deterministic_id,
    feature_enabled,
    first_row,
    get_supabase as _get_supabase,
    issue_text,
    masked,
)
from app.tools.few_shot_selector import upsert_reference

logger = logging.getLogger(__name__)

FLAG = "CUSTOMER_FEEDBACK_LEARNING_ENABLED"
_ROOT = Path(__file__).resolve().parents[2]
_SELECT = (
    "id, ticket_id, score, comment, tickets(id, raw_text, "
    "ticket_classifications(category, priority, sentiment), ticket_drafts(domain), "
    "resolutions(final_response, escalated, resolved_at), response_evaluations(overall_score))"
)


def _positive_min() -> int:
    return int(os.getenv("CUSTOMER_FEEDBACK_POSITIVE_MIN", "4"))


def _negative_max() -> int:
    return int(os.getenv("CUSTOMER_FEEDBACK_NEGATIVE_MAX", "2"))


def _judge_high() -> int:
    return int(os.getenv("CUSTOMER_FEEDBACK_JUDGE_HIGH", "4"))


def _disagreements_path() -> Path:
    configured = Path(os.getenv("FEEDBACK_DISAGREEMENTS_PATH", "./vector_store/feedback_disagreements.jsonl"))
    return configured if configured.is_absolute() else _ROOT / configured


def sync_customer_feedback(lookback_hours: int = 24) -> dict:
    summary = {"considered": 0, "synced": 0, "disagreements": 0, "skipped": 0}
    if not feature_enabled(FLAG):
        return {**summary, "disabled": True}

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    try:
        rows = _get_supabase().table("customer_feedback").select(_SELECT).gte("updated_at", cutoff).execute().data or []
    except Exception as e:
        logger.error(f"Failed to fetch customer feedback: {e}")
        return summary

    summary["considered"] = len(rows)
    for row in rows:
        try:
            outcome = _sync_one(row)
        except Exception as e:
            logger.warning(f"Failed to sync feedback {row.get('id')}: {e}")
            outcome = "skipped"
        summary[outcome] += 1

    logger.info(f"Customer-feedback sync: {summary}")
    return summary


def _sync_one(row: dict) -> str:
    score = row.get("score")
    ticket = row.get("tickets")
    if not isinstance(score, int) or not isinstance(ticket, dict) or not ticket.get("raw_text"):
        return "skipped"
    classification = first_row(ticket.get("ticket_classifications"))
    if score >= _positive_min():
        return _sync_positive(row, ticket, classification)
    if score <= _negative_max():
        return _log_disagreement(row, ticket, classification)
    return "skipped"


def _latest_answer(ticket: dict) -> dict | None:
    answered = [r for r in as_list(ticket.get("resolutions")) if not r.get("escalated") and r.get("final_response")]
    return max(answered, key=lambda r: r.get("resolved_at") or "", default=None)


def _sync_positive(row: dict, ticket: dict, classification: dict) -> str:
    answer = _latest_answer(ticket)
    if not answer:
        return "skipped"
    upsert_reference(
        ticket_id=ticket["id"],
        issue_text=masked(issue_text(ticket["raw_text"])),
        resolution_text=masked(answer["final_response"]),
        domain=first_row(ticket.get("ticket_drafts")).get("domain") or "technical",
        priority=classification.get("priority") or "Unknown",
        category=classification.get("category") or "Unknown",
        doc_id=deterministic_id("customer_feedback", ticket["id"]),
        source="customer_feedback",
        extra_metadata={"sentiment": classification.get("sentiment") or "Unknown", "customer_score": row["score"]},
    )
    return "synced"


def _logged_ticket_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            ids.add(json.loads(line)["ticket_id"])
        except (ValueError, KeyError):
            continue
    return ids


def _log_disagreement(row: dict, ticket: dict, classification: dict) -> str:
    judge_scores = [
        e["overall_score"] for e in as_list(ticket.get("response_evaluations")) if isinstance(e.get("overall_score"), int)
    ]
    if not judge_scores or max(judge_scores) < _judge_high():
        return "skipped"
    path = _disagreements_path()
    if ticket["id"] in _logged_ticket_ids(path):
        return "skipped"
    record = {
        "ticket_id": ticket["id"],
        "customer_score": row["score"],
        "judge_overall": max(judge_scores),
        "category": classification.get("category") or "Unknown",
        "priority": classification.get("priority") or "Unknown",
        "sentiment": classification.get("sentiment") or "Unknown",
        "issue": masked(issue_text(ticket["raw_text"])),
        "comment": masked(row.get("comment")),
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return "disagreements"

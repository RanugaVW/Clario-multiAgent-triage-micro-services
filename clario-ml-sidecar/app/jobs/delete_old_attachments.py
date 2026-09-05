"""Scheduled job (see main.py's lifespan) - deletes ticket attachments
older than 3 days from Supabase Storage and clears the DB path reference.
Only the stored image and its path column are affected; the ticket row
and its full text history are untouched."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

RETENTION_DAYS = 3

_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    """Lazy singleton so importing this module never requires env vars to be set."""
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_PROJECT_URL", "")
        key = os.environ.get("SUPABASE_SECRET_API", "")
        _supabase = create_client(url, key)
    return _supabase


def delete_old_attachments() -> None:
    supabase = _get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    result = (
        supabase.table("tickets")
        .select("id, image_storage_path")
        .not_.is_("image_storage_path", "null")
        .lt("created_at", cutoff)
        .execute()
    )
    for row in result.data or []:
        ticket_id = row["id"]
        path = row["image_storage_path"]
        try:
            supabase.storage.from_("ticket-attachments").remove([path])
            supabase.table("tickets").update({"image_storage_path": None}).eq("id", ticket_id).execute()
        except Exception as e:
            logger.error(f"Failed to delete attachment for ticket {ticket_id}: {e}")

"""Shared rules for the live-feedback learning jobs.

One place for the lessons already paid for in this project: text is masked
before it is stored anywhere reusable (MLflow.md, bug 3), Chroma IDs are
deterministic so a re-run is a no-op, and every job sits behind an env flag.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from supabase import Client, create_client

from app.tools.redaction_tool import mask_pii

_WHITESPACE = re.compile(r"\s+")
_CUSTOMER_MARKER = "[CUSTOMER RESPONSE]"
_OCR_MARKER = "[OCR EXTRACTED TEXT FROM ATTACHMENT]"
_TRUTHY = {"1", "true", "yes", "on"}

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    """Lazy singleton so importing a job never requires env vars to be set."""
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            os.environ.get("SUPABASE_PROJECT_URL", ""),
            os.environ.get("SUPABASE_SECRET_API", ""),
        )
    return _supabase


def feature_enabled(flag: str) -> bool:
    return os.getenv(flag, "false").strip().lower() in _TRUTHY


def normalize_ws(text: str | None) -> str:
    return _WHITESPACE.sub(" ", text or "").strip()


def customer_section(draft: str | None) -> str:
    """The customer-facing part of a draft (drafts carry an internal report first)."""
    if not draft:
        return ""
    return draft.split(_CUSTOMER_MARKER)[-1].strip()


def issue_text(raw_text: str | None) -> str:
    """The customer's own words, without any OCR text extracted from attachments."""
    return (raw_text or "").split(_OCR_MARKER)[0].strip()


def masked(text: str | None) -> str:
    return mask_pii(text)[0] if text else ""


def contains_pii(text: str | None) -> bool:
    return bool(text) and bool(mask_pii(text)[1])


def deterministic_id(prefix: str, key: str) -> str:
    return f"{prefix}_{key}"


def as_list(value: Any) -> list[dict]:
    """PostgREST returns an object for to-one embeds and a list for to-many."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def first_row(value: Any) -> dict:
    rows = as_list(value)
    return rows[0] if rows else {}

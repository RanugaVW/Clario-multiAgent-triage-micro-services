"""Generate a balanced, validated LMS-support ticket dataset with Gemini.

The raw dataset has randomly assigned labels, so this creates 2,500 synthetic,
category-consistent examples per category for the Rysera STEM LMS context. It
uses a dedicated cache and output folder, so generic generated data stays intact.

Run from the repository root:
    python ml_finetuning/src/curation/generate_curated_synthetic_dataset.py
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Literal

import pandas as pd
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pydantic import BaseModel


# Gemini 2.5 Flash is unavailable to newly created Gemini API projects.
MODEL = "gemini-3.1-flash-lite"
TARGET_PER_CATEGORY = 2_500
BATCH_SIZE = 50
CATEGORIES = (
    "Login Issue",
    "Payment Problem",
    "Account Suspension",
    "Bug Report",
    "Feature Request",
    "Performance Issue",
    "Refund Request",
    "Subscription Cancellation",
)
SEEDS = {
    "Login Issue": "I cannot sign in to the LMS to access the STEM course I purchased.",
    "Payment Problem": "My payment for a course was deducted, but the enrolment still shows as unpaid.",
    "Account Suspension": "My student LMS account was suspended and I need to regain access to my courses.",
    "Bug Report": "The course video player crashes when I open a lesson in my STEM course.",
    "Feature Request": "I would like downloadable lesson notes and offline viewing for my courses.",
    "Performance Issue": "The LMS dashboard and course videos load very slowly during study sessions.",
    "Refund Request": "I would like a refund for a course purchase because the course was not suitable.",
    "Subscription Cancellation": "I want to cancel my learning-plan subscription but keep access until the billing period ends.",
}
PRIORITIES = ("Low", "Medium", "High", "Urgent")
SENTIMENTS = ("Positive", "Neutral", "Negative", "Strongly Negative")
PRODUCTS = (
    "Course Marketplace", "Student Web Portal", "Student Mobile App", "Learning Dashboard",
    "Video Classroom", "Assessment Module", "Course Certificate Service", "Payment & Billing",
    "Learning Plan Subscription", "Course Content Library",
)
STATUSES = ("Open", "In Progress", "Pending Customer", "Resolved", "Closed")
CHANNELS = ("Chat", "Email", "Phone", "Social Media", "Web Form")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_DIR = PROJECT_ROOT / "data" / "curated_synthetic_lms"
CACHE_DIR = OUTPUT_DIR / "batch_cache"
OUTPUT_CSV = OUTPUT_DIR / "curated_lms_tickets.csv"
PARTIAL_OUTPUT_CSV = OUTPUT_DIR / "partial_curated_lms_tickets.csv"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d .()-]{7,}\d)")
RETRY_DELAY_PATTERN = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)


class GeneratedTicket(BaseModel):
    category: str
    issue_description: str
    priority: Literal["Low", "Medium", "High", "Urgent"]
    sentiment: Literal["Positive", "Neutral", "Negative", "Strongly Negative"]
    product: Literal[
        "Course Marketplace", "Student Web Portal", "Student Mobile App", "Learning Dashboard",
        "Video Classroom", "Assessment Module", "Course Certificate Service", "Payment & Billing",
        "Learning Plan Subscription", "Course Content Library",
    ]
    resolution_notes: str
    status: Literal["Open", "In Progress", "Pending Customer", "Resolved", "Closed"]
    channel: Literal["Chat", "Email", "Phone", "Social Media", "Web Form"]
    language: Literal["English"]
    issue_complexity_score: int


class GeneratedBatch(BaseModel):
    tickets: list[GeneratedTicket]


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def cache_path(category: str, batch_number: int) -> Path:
    return CACHE_DIR / f"{category.casefold().replace(' ', '_')}_{batch_number:02d}.json"


def valid_ticket(ticket: GeneratedTicket, category: str) -> bool:
    text_fields = (ticket.issue_description, ticket.resolution_notes)
    return (
        ticket.category == category
        and len(ticket.issue_description.strip()) >= 20
        and 1 <= ticket.issue_complexity_score <= 10
        and not any(EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text) for text in text_fields)
    )


def load_cached(category: str) -> list[GeneratedTicket]:
    tickets: list[GeneratedTicket] = []
    for path in sorted(CACHE_DIR.glob(f"{category.casefold().replace(' ', '_')}_*.json")):
        tickets.extend(GeneratedTicket.model_validate(item) for item in json.loads(path.read_text()))
    return tickets


def write_progress_snapshot() -> dict[str, int]:
    """Export all currently cached unique examples for review before completion."""
    rows: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    for category in CATEGORIES:
        unique = {normalized(ticket.issue_description): ticket for ticket in load_cached(category)}
        counts[category] = len(unique)
        for ticket in unique.values():
            rows.append(
                {
                    **ticket.model_dump(),
                    "platform": "Rysera STEM LMS",
                    "source": "gemini_synthetic_lms",
                }
            )
    if rows:
        pd.DataFrame(rows).to_csv(PARTIAL_OUTPUT_CSV, index=False)
    return counts


def generate_batch(client: genai.Client, category: str, count: int) -> list[GeneratedTicket]:
    prompt = f"""Generate exactly {count} distinct, realistic English customer-support tickets for Rysera STEM LMS.
Rysera STEM LMS is an online learning platform where students buy courses, learn through lessons and
videos, complete assessments, and manage course enrolments or learning-plan subscriptions.
Every ticket must be correctly classified as {category!r}; do not include another issue type.
Use this seed only as semantic guidance: {SEEDS[category]!r}

Vary wording, tone, formality, detail, product, channel, priority, and sentiment. Include a small
number of natural typos, but keep text understandable. Priority must match urgency: Low for minor
or non-blocking requests, Medium for ordinary issues, High for major access/payment/workflow impact,
and Urgent only for explicitly time-critical serious impact. Keep product, resolution_notes, status,
channel, language, and complexity consistent with the issue. Do not generate names, email addresses,
phone numbers, account numbers, card numbers, URLs, or any personal data."""
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=GeneratedBatch,
                ),
            )
            batch = GeneratedBatch.model_validate_json(response.text).tickets
            accepted = [ticket for ticket in batch if valid_ticket(ticket, category)]
            if len(accepted) >= count:
                return accepted[:count]
            raise ValueError(f"Expected at least {count} valid tickets, received {len(accepted)}.")
        except ClientError as error:
            if error.code != 429:
                raise
            retry_match = RETRY_DELAY_PATTERN.search(str(error))
            delay = float(retry_match.group(1)) + 1 if retry_match else 30.0
            if attempt == 3:
                raise RuntimeError(
                    f"Gemini quota remained exhausted for {category}. Rerun later to resume: {error}"
                ) from error
            print(f"Gemini quota reached; waiting {delay:.0f}s before retrying {category}.")
            time.sleep(delay)
        except (ValueError, json.JSONDecodeError, httpx.RequestError, ServerError) as error:
            if attempt == 3:
                raise RuntimeError(
                    f"Gemini could not complete a batch for {category}. Rerun the script to resume: {error}"
                ) from error
            time.sleep(2**attempt)
    raise AssertionError("Unreachable")


def collect_category(client: genai.Client, category: str) -> list[GeneratedTicket]:
    """Resume cached generation until one category has the requested unique count."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tickets = load_cached(category)
    batch_number = len(list(CACHE_DIR.glob(f"{category.casefold().replace(' ', '_')}_*.json")))
    while True:
        unique = {normalized(ticket.issue_description): ticket for ticket in tickets}
        if len(unique) >= TARGET_PER_CATEGORY:
            return list(unique.values())[:TARGET_PER_CATEGORY]
        count = min(BATCH_SIZE, TARGET_PER_CATEGORY - len(unique))
        batch = generate_batch(client, category, count)
        path = cache_path(category, batch_number)
        path.write_text(json.dumps([ticket.model_dump() for ticket in batch], indent=2), encoding="utf-8")
        tickets.extend(batch)
        batch_number += 1
        progress = write_progress_snapshot()
        print(f"{category}: {progress[category]}/{TARGET_PER_CATEGORY} unique")


def write_dataset(tickets: list[GeneratedTicket]) -> None:
    """Validate balance and write the curated fine-tuning dataset and manifest."""
    counts = Counter(ticket.category for ticket in tickets)
    expected = {category: TARGET_PER_CATEGORY for category in CATEGORIES}
    if dict(counts) != expected:
        raise RuntimeError(f"Class balance validation failed: {dict(counts)}")

    random.Random(42).shuffle(tickets)
    rows = []
    for number, ticket in enumerate(tickets, start=1):
        rows.append(
            {
                "ticket_id": f"LMS-SYN-{number:05d}",
                **ticket.model_dump(),
                "platform": "Rysera STEM LMS",
                "source": "gemini_synthetic_lms",
            }
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_CSV, index=False)
    MANIFEST_PATH.write_text(
        json.dumps({"model": MODEL, "rows": len(rows), "per_category": dict(counts), "columns": list(rows[0])}, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY is required in {ENV_PATH}.")
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=120_000,
            retry_options=types.HttpRetryOptions(
                attempts=3, initial_delay=1, max_delay=20, http_status_codes=[429, 500, 502, 503, 504]
            ),
        ),
    )
    try:
        tickets = [ticket for category in CATEGORIES for ticket in collect_category(client, category)]
        write_dataset(tickets)
        print(f"Created {len(tickets):,} validated rows: {OUTPUT_CSV}")
    except ClientError as error:
        if error.code == 401:
            raise RuntimeError(
                "Gemini rejected GEMINI_API_KEY. Create a new Gemini Developer API key in Google AI Studio "
                "and update ml_finetuning/.env before resuming."
            ) from error
        raise
    finally:
        client.close()


if __name__ == "__main__":
    main()

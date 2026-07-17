"""Create Gemini-assisted ground-truth labels for unique ticket descriptions.

Run from the repository root after setting GEMINI_API_KEY in ml_finetuning/.env:
    python ml_finetuning/src/curation/get_ground_truth_labels.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel


CATEGORIES = [
    "Login Issue",
    "Payment Problem",
    "Account Suspension",
    "Bug Report",
    "Feature Request",
    "Performance Issue",
    "Refund Request",
    "Subscription Cancellation",
    "Security Concern",
    "Data Sync Issue",
]
MODEL = "gemini-2.5-flash"
ISSUE_DESCRIPTION_COLUMN = "issue_description"
CATEGORY_COLUMN = "category"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "raw" / "customer_support_tickets_200k.csv"
ENV_PATH = PROJECT_ROOT / ".env"
OUTPUT_PATH = PROJECT_ROOT / "data" / "curation_reports" / "ground_truth_template_labels.json"


class GroundTruthLabel(BaseModel):
    """The required structured Gemini response for one ticket description."""

    category: Literal[
        "Login Issue",
        "Payment Problem",
        "Account Suspension",
        "Bug Report",
        "Feature Request",
        "Performance Issue",
        "Refund Request",
        "Subscription Cancellation",
        "Security Concern",
        "Data Sync Issue",
    ]
    confidence: Literal["high", "medium", "low"]
    reasoning: str


def classify_description(client: genai.Client, description: str) -> GroundTruthLabel:
    """Classify one unique ticket description using Gemini structured output."""
    prompt = f"""Classify this customer-support issue into exactly one category.

Allowed categories: {json.dumps(CATEGORIES)}
Issue description: {description!r}

Choose the category that best reflects the issue itself. Do not infer a category
from any potentially incorrect dataset label."""
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GroundTruthLabel,
        ),
    )
    return GroundTruthLabel.model_validate_json(response.text)


def most_common_original_labels(dataframe: pd.DataFrame) -> dict[str, str]:
    """Return the modal original category for each issue-description template."""
    crosstab = pd.crosstab(
        dataframe[ISSUE_DESCRIPTION_COLUMN], dataframe[CATEGORY_COLUMN], dropna=False
    )
    return {description: row.idxmax() for description, row in crosstab.iterrows()}


def print_comparison(labels: dict[str, GroundTruthLabel], original_labels: dict[str, str]) -> None:
    """Print a concise human-review table for the generated labels."""
    print(f"{'Issue description':60} | {'Gemini category':26} | {'Original mode':26} | Result")
    print("-" * 132)
    for description, label in labels.items():
        shortened = description if len(description) <= 60 else f"{description[:57]}..."
        original = original_labels[description]
        result = "MATCH" if label.category == original else "MISMATCH"
        print(f"{shortened:60} | {label.category:26} | {original:26} | {result}")


def main() -> None:
    """Load configuration, label unique descriptions, and write the review JSON."""
    load_dotenv(ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(f"GEMINI_API_KEY is required; add it to {ENV_PATH}.")
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"Raw dataset was not found: {DATASET_PATH}")

    dataframe = pd.read_csv(DATASET_PATH)
    missing = {ISSUE_DESCRIPTION_COLUMN, CATEGORY_COLUMN} - set(dataframe.columns)
    if missing:
        raise KeyError(f"Dataset is missing required columns: {', '.join(sorted(missing))}")

    descriptions = dataframe[ISSUE_DESCRIPTION_COLUMN].dropna().drop_duplicates().tolist()
    client = genai.Client(api_key=api_key)
    labels = {description: classify_description(client, description) for description in descriptions}

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({key: value.model_dump() for key, value in labels.items()}, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(labels)} Gemini labels to {OUTPUT_PATH}")
    print_comparison(labels, most_common_original_labels(dataframe))


if __name__ == "__main__":
    main()

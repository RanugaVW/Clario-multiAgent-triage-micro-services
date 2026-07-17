"""Diagnose whether resolution notes contain a useful category-label signal.

Run from the repository root:
    python ml_finetuning/src/curation/inspect_resolution_notes.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "data" / "raw" / "customer_support_tickets_200k.csv"
REPORT_PATH = PROJECT_ROOT / "data" / "curation_reports" / "resolution_notes_crosstab.csv"
RESOLUTION_NOTES_COLUMN = "resolution_notes"
CATEGORY_COLUMN = "category"
UNIQUE_VALUE_THRESHOLD = 50
DOMINANT_CATEGORY_SHARE = 0.60
SIGNAL_VALUE_SHARE = 0.10


def resolution_note_category_shares(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return category shares for each non-empty resolution-note value."""
    usable = dataframe.dropna(subset=[RESOLUTION_NOTES_COLUMN, CATEGORY_COLUMN])
    crosstab = pd.crosstab(usable[RESOLUTION_NOTES_COLUMN], usable[CATEGORY_COLUMN])
    return crosstab.div(crosstab.sum(axis=1), axis=0)


def main() -> None:
    """Inspect resolution notes and print a shell-friendly diagnostic conclusion."""
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"Raw dataset was not found: {DATASET_PATH}")

    dataframe = pd.read_csv(DATASET_PATH)
    missing = {RESOLUTION_NOTES_COLUMN, CATEGORY_COLUMN} - set(dataframe.columns)
    if missing:
        raise KeyError(f"Dataset is missing required columns: {', '.join(sorted(missing))}")

    unique_notes = dataframe[RESOLUTION_NOTES_COLUMN].nunique(dropna=False)
    print(f"Unique {RESOLUTION_NOTES_COLUMN} values: {unique_notes:,}")

    shares = resolution_note_category_shares(dataframe)
    dominant = shares.max(axis=1) > DOMINANT_CATEGORY_SHARE
    dominant_count = int(dominant.sum())
    note_count = len(shares)
    dominant_fraction = dominant_count / note_count if note_count else 0.0

    if unique_notes > UNIQUE_VALUE_THRESHOLD:
        crosstab = pd.crosstab(
            dataframe[RESOLUTION_NOTES_COLUMN], dataframe[CATEGORY_COLUMN], dropna=False
        )
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        crosstab.to_csv(REPORT_PATH)
        print(f"Saved resolution-note crosstab: {REPORT_PATH}")
    else:
        print(
            f"Crosstab not saved: {unique_notes} unique values is not above "
            f"the {UNIQUE_VALUE_THRESHOLD}-value threshold."
        )

    print(
        f"Dominant-category notes (> {DOMINANT_CATEGORY_SHARE:.0%}): "
        f"{dominant_count}/{note_count} ({dominant_fraction:.1%})"
    )
    has_signal = dominant_fraction >= SIGNAL_VALUE_SHARE
    print(f"RESOLUTION_NOTES_HAS_SIGNAL: {has_signal}")


if __name__ == "__main__":
    main()

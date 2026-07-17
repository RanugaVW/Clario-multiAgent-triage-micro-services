"""Inspect raw ticket labels without changing the source dataset.

Run from the repository root:
    python ml_finetuning/src/curation/inspect_dataset.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


DATASET_PATH = Path(
    r"C:\Users\ranug\Clario\clario\ml_finetuning\data\raw\customer_support_tickets_200k.csv"
)
REPORT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "curation_reports" / "label_crosstab.csv"
)
ISSUE_DESCRIPTION_COLUMN = "issue_description"

# Representative labels expected in the support-ticket dataset.  The matching
# column is selected from its values, rather than only from its column name.
KNOWN_CATEGORY_LABELS = {
    "login issue",
    "payment problem",
    "bug report",
    "account suspension",
    "performance issue",
    "billing issue",
    "technical issue",
}


def find_category_column(dataframe: pd.DataFrame) -> str:
    """Return the column whose values most closely match known category labels."""
    candidates: list[tuple[float, str]] = []

    for column in dataframe.columns:
        values = dataframe[column].dropna()
        if values.empty:
            continue

        normalized = values.astype(str).str.strip().str.casefold()
        match_rate = normalized.isin(KNOWN_CATEGORY_LABELS).mean()
        name_bonus = 1.0 if "categor" in column.casefold() else 0.0
        candidates.append((match_rate + name_bonus, column))

    if not candidates:
        raise ValueError("Could not identify a category column: the dataset has no populated columns.")

    score, category_column = max(candidates)
    if score == 0:
        raise ValueError(
            "Could not identify a category label column from known support-category values."
        )
    return category_column


def main() -> None:
    """Print a label diagnostic and save the issue-description/category crosstab."""
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"Raw dataset was not found: {DATASET_PATH}")

    dataframe = pd.read_csv(DATASET_PATH)
    if ISSUE_DESCRIPTION_COLUMN not in dataframe.columns:
        raise KeyError(f"Expected column '{ISSUE_DESCRIPTION_COLUMN}' was not found.")

    category_column = find_category_column(dataframe)

    print(f"Total row count: {len(dataframe):,}")
    print("\nColumns and dtypes:")
    for column, dtype in dataframe.dtypes.items():
        print(f"- {column}: {dtype}")

    print(f"\nCategory label column: {category_column}")
    print(
        f"Unique {ISSUE_DESCRIPTION_COLUMN} values: "
        f"{dataframe[ISSUE_DESCRIPTION_COLUMN].nunique(dropna=False):,}"
    )
    print(
        f"Unique {category_column} values: "
        f"{dataframe[category_column].nunique(dropna=False):,}"
    )

    crosstab = pd.crosstab(
        dataframe[ISSUE_DESCRIPTION_COLUMN],
        dataframe[category_column],
        dropna=False,
    )
    print("\nIssue description vs. category label crosstab:")
    print(crosstab.to_string())

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    crosstab.to_csv(REPORT_PATH)
    print(f"\nSaved crosstab report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

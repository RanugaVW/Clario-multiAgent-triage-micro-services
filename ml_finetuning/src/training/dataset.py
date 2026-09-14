"""Prepare the QLoRA fine-tuning train/test splits for Llama 3.2 3B.

Consolidates the raw `distilled_train.jsonl` (399 free-text category
variants, a noisy 3-way sentiment field) into a stable 12-class multi-label
category taxonomy and a 3-class sentiment scheme (Neutral / Negative /
Frustrated), then writes a stratified train/test split. Chain-of-thought
(`reasoning`) is kept only on the training side — the test set is graded on
the final priority/sentiment/category fields alone.
"""

import json
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = PROJECT_ROOT / "data" / "curated_synthetic_lms" / "distilled_train.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "data" / "splits"

TRAIN_SIZE = 10_000
RANDOM_STATE = 42
RARE_COMBO_THRESHOLD = 10  # category combos rarer than this get pooled before stratifying

PRIORITY_LABELS = ["Low", "Medium", "High", "Critical"]
SENTIMENT_LABELS = ["Neutral", "Negative", "Frustrated"]

CATEGORY_KEYWORDS = {
    "Billing & Invoicing": ["billing", "payment", "invoicing", "checkout", "financial",
                            "e-commerce", "fulfillment", "transaction"],
    "Refunds": ["refund"],
    "Subscription Management": ["subscription", "enrollment", "enrolment", "cancellation"],
    "Account Access": ["account access", "account management", "account", "entitlement",
                        "permission", "profile", "access management", "access control",
                        "provisioning"],
    "Authentication": ["authentication", "login", "session management", "security", "sso"],
    "Performance": ["performance", "latency", "stability", "system performance",
                     "connectivity", "network"],
    "Technical Support": ["technical support", "technical bug", "software bug", "bug report",
                           "bug", "technical issue", "technical", "document generation",
                           "integration", "api", "notification", "email delivery"],
    "UI/UX": ["ui/ux", "ui", "ux", "usability", "accessibility", "navigation", "interface",
              "user experience"],
    "Feature Request": ["feature request", "feature inquiry", "how-to", "configuration"],
    "Data Integrity": ["data integrity", "data synchronization", "data accuracy",
                        "data correction", "data loss", "data access", "data"],
    "Service Outage": ["service outage", "system outage", "availability", "outage",
                        "system status", "service failure"],
    "Content & Media": ["content access", "content quality", "playback", "content", "video"],
}
CATEGORY_LABELS = sorted(CATEGORY_KEYWORDS)

_SENTIMENT_STEP_RE = re.compile(
    r"Step 3[:.]?\s*Determine sentiment\s*-?\s*(.*?)(?:Step 4|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_FRUSTRATION_RE = re.compile(r"frustrat\w*", re.IGNORECASE)
_NEGATION_RE = re.compile(
    r"\b(without|no|not|lacks?|lacking|free of|absence of|isn't|aren't|devoid of)\b",
    re.IGNORECASE,
)


def load_raw_records(path: Path = RAW_PATH) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def map_categories(raw_category: str) -> list[str]:
    """Split a messy free-text category string into canonical multi-label tags."""
    tokens = [t.strip().lower() for t in re.split(r"\s*(?:&|/|,|\band\b)\s*", raw_category) if t.strip()]
    if not tokens:
        tokens = [raw_category.lower()]

    labels = set()
    for token in tokens:
        for canon, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in token for kw in keywords):
                labels.add(canon)

    if not labels:
        low = raw_category.lower()
        for canon, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in low for kw in keywords):
                labels.add(canon)

    return sorted(labels) if labels else ["Other"]


def _mentions_frustration(step3_text: str) -> bool:
    """True if `step3_text` affirmatively names frustration (not negated, e.g.
    'without frustration' or 'lacks frustrated language' don't count)."""
    for match in _FRUSTRATION_RE.finditer(step3_text):
        window = step3_text[max(0, match.start() - 40):match.start()]
        if _NEGATION_RE.search(window):
            continue
        return True
    return False


def derive_sentiment(raw_sentiment: str, reasoning: str) -> str:
    """Fold Positive into Neutral, then promote to Frustrated wherever Gemini's
    own sentiment-reasoning step affirmatively names frustration."""
    step3_match = _SENTIMENT_STEP_RE.search(reasoning)
    step3_text = step3_match.group(1) if step3_match else ""

    base = "Neutral" if raw_sentiment == "Positive" else raw_sentiment
    if step3_text and _mentions_frustration(step3_text):
        return "Frustrated"
    return base


def build_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        labels = r["labels"]
        rows.append({
            "input_product": r["input_product"],
            "input_issue_description": r["input_issue_description"],
            "reasoning": r["reasoning"],
            "priority": labels["priority"],
            "sentiment": derive_sentiment(labels["sentiment"], r["reasoning"]),
            "category_list": map_categories(labels["category"]),
        })
    return pd.DataFrame(rows)


def build_stratify_key(df: pd.DataFrame, rare_threshold: int = RARE_COMBO_THRESHOLD) -> pd.Series:
    """Build the composite (category-combo, priority, sentiment) key used to
    stratify the train/test split so the test set mirrors the full dataset's
    joint label distribution."""
    combo = df["category_list"].apply(lambda cats: "+".join(cats))
    combo_counts = combo.value_counts()

    combo_bucketed = combo.where(combo.map(combo_counts) >= rare_threshold, "RARE_COMBO")

    key = combo_bucketed + "|" + df["priority"] + "|" + df["sentiment"]

    # Bucketing the combo alone still leaves singleton (combo, priority, sentiment)
    # crossings — e.g. one record is the only "Critical" ticket for its combo.
    # `stratify` needs every class to have >= 2 members, so fall back to the
    # coarser (priority, sentiment) key for whichever specific keys are still
    # too rare; priority x sentiment has only 12 combinations, each with
    # thousands of records, so it's always safe to land on.
    key_counts = key.value_counts()
    fallback_key = df["priority"] + "|" + df["sentiment"]
    return key.where(key.map(key_counts) >= 2, fallback_key)


def split_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    strat_key = build_stratify_key(df)
    train_df, test_df = train_test_split(
        df,
        train_size=TRAIN_SIZE,
        random_state=RANDOM_STATE,
        stratify=strat_key,
    )
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)


def _distribution_report(full: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame) -> str:
    lines = ["# Split verification: full vs train vs test\n"]

    for col, labels in (("priority", PRIORITY_LABELS), ("sentiment", SENTIMENT_LABELS)):
        lines.append(f"\n## {col.capitalize()}\n")
        lines.append("| Label | Full % | Train % | Test % |")
        lines.append("|---|---|---|---|")
        for label in labels:
            f_pct = (full[col] == label).mean() * 100
            tr_pct = (train[col] == label).mean() * 100
            te_pct = (test[col] == label).mean() * 100
            lines.append(f"| {label} | {f_pct:.1f} | {tr_pct:.1f} | {te_pct:.1f} |")

    lines.append("\n## Category (multi-label presence rate)\n")
    lines.append("| Label | Full % | Train % | Test % |")
    lines.append("|---|---|---|---|")
    for label in CATEGORY_LABELS:
        f_pct = full["category_list"].apply(lambda c: label in c).mean() * 100
        tr_pct = train["category_list"].apply(lambda c: label in c).mean() * 100
        te_pct = test["category_list"].apply(lambda c: label in c).mean() * 100
        lines.append(f"| {label} | {f_pct:.1f} | {tr_pct:.1f} | {te_pct:.1f} |")

    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records = load_raw_records()
    df = build_dataframe(records)
    train_df, test_df = split_dataset(df)

    train_out = train_df[[
        "input_product", "input_issue_description", "reasoning", "priority", "sentiment",
    ]].copy()
    train_out["category"] = train_df["category_list"].apply(json.dumps)
    train_out.to_csv(OUTPUT_DIR / "train_with_cot.csv", index=False)

    test_out = test_df[[
        "input_product", "input_issue_description", "priority", "sentiment",
    ]].copy()
    test_out["category"] = test_df["category_list"].apply(json.dumps)
    test_out.to_csv(OUTPUT_DIR / "test.csv", index=False)

    with open(OUTPUT_DIR / "label_maps.json", "w", encoding="utf-8") as f:
        json.dump({
            "categories": CATEGORY_LABELS,
            "priorities": PRIORITY_LABELS,
            "sentiments": SENTIMENT_LABELS,
        }, f, indent=2)

    report = _distribution_report(df, train_df, test_df)
    (OUTPUT_DIR / "split_report.md").write_text(report, encoding="utf-8")

    print(f"Train: {len(train_out)} | Test: {len(test_out)}")
    print(f"Wrote outputs to {OUTPUT_DIR}")
    print(report)


if __name__ == "__main__":
    main()

"""Few-shot Gemini distillation: label tickets with reasoning in the final taxonomy.

    python -m src.distill_with_gemini                       # from ml_finetuning/
    python -m src.distill_with_gemini --input other.csv --output other.jsonl

Safe to stop and rerun: tickets already in the output file are skipped.
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from src.distillation.fewshot import format_examples, label_ticket, load_bank, save_bank, select_bank
from src.distillation.gemini_pool import AllKeysExhausted, GeminiPool

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "curated_synthetic_lms" / "train_split.csv"
DEFAULT_OUTPUT = ROOT / "data" / "distilled" / "fewshot_distilled.jsonl"
DEFAULT_BANK = ROOT / "data" / "fewshot" / "teacher_bank.json"
# Seed pool for the example bank: the v2 labels, already mapped onto the taxonomy.
BANK_SOURCE = ROOT / "data" / "splits" / "train_with_cot.csv"

logger = logging.getLogger(__name__)


def normalized(text: str) -> str:
    return " ".join(str(text).casefold().split())


def ensure_bank(path: Path) -> list[dict]:
    """Load the example bank, building it on first run. Review/edit the JSON by hand
    before a full run: every example is copied into every teacher call."""
    if path.exists():
        return load_bank(path)
    source = pd.read_csv(BANK_SOURCE)
    source["category"] = source["category"].apply(json.loads)
    bank = select_bank(source)
    save_bank(bank, path)
    logger.info("Built a %d-example bank at %s", len(bank), path)
    return bank


def done_issues(output: Path) -> set[str]:
    if not output.exists():
        return set()
    with open(output, encoding="utf-8") as f:
        return {normalized(json.loads(line)["input_issue_description"]) for line in f if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    examples_text = format_examples(ensure_bank(args.bank))
    tickets = pd.read_csv(args.input)[["product", "issue_description"]].dropna()
    done = done_issues(args.output)
    todo = tickets[~tickets["issue_description"].map(normalized).isin(done)].drop_duplicates("issue_description")
    logger.info("%d tickets, %d already distilled, %d to go", len(tickets), len(done), len(todo))

    pool = GeminiPool()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ok = failed = 0
    with open(args.output, "a", encoding="utf-8") as out, ThreadPoolExecutor(args.workers) as executor:
        futures = [executor.submit(label_ticket, pool, examples_text, row.product, row.issue_description)
                   for row in todo.itertuples()]
        try:
            for n, future in enumerate(as_completed(futures), start=1):
                try:
                    record = future.result()
                except AllKeysExhausted:
                    raise
                except Exception as error:  # one bad ticket must not stop a multi-day run
                    logger.warning("Ticket failed: %s", error)
                    record = None
                if record is None:
                    failed += 1
                else:
                    ok += 1
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out.flush()
                if n % 100 == 0:
                    logger.info("%d/%d done (%d ok, %d invalid)", n, len(todo), ok, failed)
        except AllKeysExhausted:
            for future in futures:
                future.cancel()
            logger.error("All keys exhausted for today; rerun tomorrow to resume.")
    logger.info("Finished this session: %d labelled, %d rejected as invalid", ok, failed)


if __name__ == "__main__":
    main()

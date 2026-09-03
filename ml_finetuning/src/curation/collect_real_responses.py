"""Collect real support responses from ToS-compliant public sources, as a
reference dataset for validating LLM-generated response quality.

Sources: Moodle Jira (moodle.atlassian.net), GitHub Issues
(openedx/edx-platform), and Discourse forums (community.udemy.com,
discuss.openedx.org). Deliberately excludes BBB.org, Trustpilot, and
Reddit — see docs/superpowers/specs/2026-09-03-real-response-dataset-design.md.

Output is a reviewable CSV, not something that touches the live judge or
drafting agents by itself — see scripts/seed_validation_refs.py in
clario-ml-sidecar for the separate, manual seeding step.

Run from the repository root:
    python ml_finetuning/src/curation/collect_real_responses.py
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_ML_FINETUNING_ROOT = Path(__file__).resolve().parents[2]
if str(_ML_FINETUNING_ROOT) not in sys.path:
    sys.path.insert(0, str(_ML_FINETUNING_ROOT))

from src.curation.sources.common import RawExample, has_pii  # noqa: E402
from src.curation.sources import discourse_forums, github_openedx, moodle_jira  # noqa: E402

load_dotenv(_ML_FINETUNING_ROOT / ".env")

logger = logging.getLogger(__name__)

TARGET_PER_CATEGORY = 20
MAX_FIELD_LENGTH = 4000

CATEGORY_CONFIG = {
    "Login Issue": {
        "domain": "technical",
        "sources": [
            (moodle_jira, ["login", "sign in", "authentication"]),
            (github_openedx, ["login", "authentication", "signin"]),
            (discourse_forums, ["login", "sign in", "password"]),
        ],
    },
    "Bug Report": {
        "domain": "technical",
        "sources": [
            (moodle_jira, ["bug", "error", "crash"]),
            (github_openedx, ["bug", "crash", "error"]),
            (discourse_forums, ["bug", "not working", "broken"]),
        ],
    },
    "Performance Issue": {
        "domain": "technical",
        "sources": [
            (github_openedx, ["slow", "performance", "timeout"]),
            (discourse_forums, ["slow", "loading", "performance"]),
        ],
    },
    "Account Suspension": {
        "domain": "technical",
        "sources": [
            (discourse_forums, ["suspended", "banned", "account locked"]),
        ],
    },
    "Payment Problem": {
        "domain": "billing",
        "sources": [
            (discourse_forums, ["payment failed", "charged twice", "billing issue"]),
        ],
    },
    "Refund Request": {
        "domain": "billing",
        "sources": [
            (discourse_forums, ["refund"]),
        ],
    },
    "Subscription Cancellation": {
        "domain": "billing",
        "sources": [
            (discourse_forums, ["cancel subscription", "cancel my subscription"]),
        ],
    },
}

OUTPUT_DIR = _ML_FINETUNING_ROOT / "data" / "real_responses"
CACHE_DIR = OUTPUT_DIR / "batch_cache"
OUTPUT_CSV = OUTPUT_DIR / "real_responses.csv"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
CSV_FIELDS = [
    "doc_id", "category", "domain", "issue_text", "resolution_text",
    "source", "source_url", "responder_role", "collected_at",
]


def _source_name(source_module) -> str:
    return source_module.__name__.rsplit(".", 1)[-1]


def _csv_safe(value: str) -> str:
    """Prefix values that would be interpreted as spreadsheet formulas."""
    if value and value[0] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


def _cache_path(category: str, source_name: str) -> Path:
    safe_category = category.lower().replace(" ", "_")
    return CACHE_DIR / f"{safe_category}__{source_name}.json"


def _fetch_with_cache(category: str, source_module, keywords: list[str], limit: int) -> list[RawExample]:
    source_name = _source_name(source_module)
    cache_file = _cache_path(category, source_name)

    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        return [RawExample(**item) for item in cached]

    examples = source_module.fetch(category, keywords, limit)
    if examples:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps([asdict(example) for example in examples], indent=2))
    return examples


def collect() -> dict:
    """Run the full collection pass and write real_responses.csv + manifest.json."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"target_per_category": TARGET_PER_CATEGORY, "categories": {}}
    rows = []
    seen_doc_ids: set[str] = set()

    for category, config in CATEGORY_CONFIG.items():
        domain = config["domain"]
        collected: list[tuple[RawExample, str]] = []

        for source_module, keywords in config["sources"]:
            remaining = TARGET_PER_CATEGORY - len(collected)
            if remaining <= 0:
                break

            source_name = _source_name(source_module)
            for example in _fetch_with_cache(category, source_module, keywords, remaining):
                if has_pii(example.issue_text, example.resolution_text):
                    continue
                collected.append((example, source_name))

        category_counts: dict = {}
        for example, source_name in collected[:TARGET_PER_CATEGORY]:
            doc_id = f"real_{source_name}_{example.original_id}".replace(" ", "_")
            if doc_id in seen_doc_ids:
                logger.warning(f"Duplicate doc_id {doc_id!r} — keeping first occurrence")
                continue
            seen_doc_ids.add(doc_id)
            rows.append({
                "doc_id": doc_id,
                "category": category,
                "domain": domain,
                "issue_text": _csv_safe(example.issue_text[:MAX_FIELD_LENGTH]),
                "resolution_text": _csv_safe(example.resolution_text[:MAX_FIELD_LENGTH]),
                "source": source_name,
                "source_url": example.source_url,
                "responder_role": example.responder_role,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            })
            category_counts[source_name] = category_counts.get(source_name, 0) + 1

        manifest["categories"][category] = {
            "domain": domain,
            "total": sum(category_counts.values()),
            "by_source": category_counts,
        }
        logger.info(f"{category}: collected {sum(category_counts.values())}/{TARGET_PER_CATEGORY}")

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collect()

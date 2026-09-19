"""Category tags for the knowledge-base documents, used for label-aware retrieval.

The classifier predicts labels from the fine-tuned taxonomy (see taxonomy.py);
the KB chunks in Chroma only carry ``domain`` and ``source_file``. This module
bridges the two without re-indexing: it maps a chunk's ``source_file``
("<domain>/<file>.md") to the taxonomy labels that document is about.

Tags were assigned from what each document says, never from evaluation
tickets or their relevance judgements. Feature Request has no KB document at
all, and Content & Media has only two - those gaps are real and are reported
by ``uncovered_categories()`` rather than papered over.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.tools.taxonomy import CATEGORY_LABELS

KB_DOC_CATEGORIES: dict[str, tuple[str, ...]] = {
    # technical
    "technical/accessibility.md": ("UI/UX", "Technical Support"),
    "technical/account_issues.md": ("Account Access", "Authentication"),
    "technical/app_crash.md": ("Technical Support", "Performance"),
    "technical/browser_support.md": ("UI/UX", "Technical Support"),
    "technical/data_sync.md": ("Data Integrity", "Technical Support"),
    "technical/enrollment_issues.md": ("Account Access", "Data Integrity", "Technical Support"),
    "technical/integration_error.md": ("Technical Support",),
    "technical/login_reset.md": ("Authentication", "Account Access"),
    "technical/notifications.md": ("Technical Support",),
    "technical/service_status.md": ("Service Outage",),
    "technical/slow_performance.md": ("Performance",),
    "technical/upload_errors.md": ("Content & Media", "Technical Support"),
    # billing
    "billing/chargeback.md": ("Billing & Invoicing", "Refunds"),
    "billing/currency.md": ("Billing & Invoicing",),
    "billing/duplicate_charge.md": ("Billing & Invoicing", "Refunds"),
    "billing/invoice_copy.md": ("Billing & Invoicing",),
    "billing/misclassification_billing.md": ("Billing & Invoicing", "Data Integrity"),
    "billing/payment_failed.md": ("Billing & Invoicing",),
    "billing/payment_method.md": ("Billing & Invoicing",),
    "billing/payment_status.md": ("Billing & Invoicing",),
    "billing/plan_change.md": ("Subscription Management", "Billing & Invoicing"),
    "billing/refund_eligibility.md": ("Refunds",),
    "billing/refund_status.md": ("Refunds", "Billing & Invoicing"),
    "billing/subscription_cancel.md": ("Subscription Management", "Billing & Invoicing"),
    "billing/tax_charge.md": ("Billing & Invoicing",),
    "billing/webxpay_checkout_issues.md": ("Billing & Invoicing", "Technical Support"),
    # hr (human-review policies)
    "hr/course_cancellation.md": ("Refunds", "Subscription Management"),
    "hr/course_issues.md": ("Content & Media", "Refunds"),
    "hr/payment_linkage_escalation.md": ("Billing & Invoicing", "Data Integrity"),
}


def categories_for_doc(source_file: str) -> tuple[str, ...]:
    """Return the taxonomy labels for a KB document, or () for untagged sources
    (codebase chunks, precedent memory, anything new)."""
    return KB_DOC_CATEGORIES.get(source_file.strip().lower(), ())


def category_overlap(source_file: str, categories: Iterable[str]) -> int:
    """How many of the given labels the document is tagged with."""
    tags = set(categories_for_doc(source_file))
    return sum(1 for category in set(categories) if category in tags)


def uncovered_categories() -> list[str]:
    """Taxonomy labels that no KB document is tagged with (retrieval cannot help these)."""
    covered = {label for tags in KB_DOC_CATEGORIES.values() for label in tags}
    return [label for label in CATEGORY_LABELS if label not in covered]

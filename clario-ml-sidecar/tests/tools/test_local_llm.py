"""Classification taxonomy: locks in the categories the adapter was fine-tuned on.

classify_ticket_local() itself isn't exercised here - it requires loading the
real ~1B-param Gemma-3 model. Empirically verified against the live adapter
(gemma3-lms-ticket-adapter-final) that it correctly classifies into every one
of these six categories when the prompt asks for them, rather than the
coarser Technical/Billing/Account/General/Other set it was previously
constrained to.
"""

from app.tools.local_llm import FINE_GRAINED_CATEGORIES


def test_fine_grained_categories_match_the_adapters_training_taxonomy() -> None:
    assert FINE_GRAINED_CATEGORIES == (
        "Login Issue",
        "Payment Problem",
        "Account Suspension",
        "Bug Report",
        "Refund Request",
        "Subscription Cancellation",
    )

"""Grounding-first prompts used by every specialist agent."""


def build_specialist_prompt(
    ticket_text: str,
    retrieved_context: list[dict],
    domain: str,
    prior_critique: str | None = None,
) -> str:
    """Build a source-citing, KB-grounded specialist prompt."""
    context = "\n\n".join(
        f"Source: {item['source_file']}\n{item['text']}" for item in retrieved_context
    ) or "No knowledge-base context was retrieved."
    critique = (
        f"Your previous draft was rejected for this reason: {prior_critique}. "
        "Revise to address this specifically.\n\n"
        if prior_critique
        else ""
    )
    return (
        f"{critique}You are the {domain} support specialist. Answer ONLY from the "
        "retrieved context. Cite the source_file for every factual claim. If the context "
        "does not cover the ticket, reply exactly: I don't have enough information to "
        "resolve this.\n\n"
        f"Ticket:\n{ticket_text}\n\nRetrieved context:\n{context}"
    )

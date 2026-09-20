"""Grounding-first prompts used by every specialist agent."""


def build_specialist_prompt(
    ticket_text: str,
    retrieved_context: list[dict],
    domain: str,
    prior_critique: str | None = None,
    extra_instructions: str | None = None,
    priority: str | None = None,
    sentiment: str | None = None,
) -> str:
    """Build a source-citing, KB-grounded specialist prompt.

    priority/sentiment are classification_node's own output for this
    ticket - threading them through here is what lets generate_draft()
    actually adapt tone/urgency to a High-priority or Frustrated ticket,
    rather than drafting blind to it (Track C's pilot annotation found
    several "reads too flat for someone frustrated" notes traced back to
    this data simply never reaching the drafting prompt before).
    """
    context = "\n\n".join(
        f"Source: {item['source_file']}\n{item['text']}" for item in retrieved_context
    ) or "No knowledge-base context was retrieved."
    critique = (
        f"Your previous draft was rejected for this reason: {prior_critique}. "
        "Revise to address this specifically.\n\n"
        if prior_critique
        else ""
    )
    extra = f"{extra_instructions}\n\n" if extra_instructions else ""
    classification = (
        f"Ticket priority: {priority}\nCustomer sentiment: {sentiment}\n\n"
        if priority or sentiment
        else ""
    )
    return (
        f"{critique}{extra}You are the {domain} support specialist. Answer ONLY from the "
        "retrieved context. Cite the source_file for every factual claim. If the context "
        "does not cover the ticket, reply exactly: I don't have enough information to "
        "resolve this. Never invent or guess the customer's name - only use a name if it "
        "appears verbatim in the ticket text below; otherwise use a neutral greeting such "
        "as \"Hello,\" or no greeting at all.\n\n"
        f"{classification}Ticket:\n{ticket_text}\n\nRetrieved context:\n{context}"
    )

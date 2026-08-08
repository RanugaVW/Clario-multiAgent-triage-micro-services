import asyncio
import time
import uuid
import sys
from app.main import background_orchestration, TicketRequest

async def main():
    ticket_id = str(uuid.uuid4())
    ticket = TicketRequest(
        ticket_id=ticket_id, 
        raw_text="I got this error\n\n[OCR EXTRACTED TEXT FROM ATTACHMENT]\nFailed to register for event: Cannot coerce the result to a single JSON object"
    )
    initial_state = {
        "ticket_id": ticket_id,
        "raw_text": ticket.raw_text,
        "reflection_count": 0,
        "reflection_critiques": [],
        "reroute_attempted": False,
        "needs_reroute": False,
        "agent_drafts": {},
        "retrieved_context": {},
        "rag_top_score": {},
        "low_relevance_flags": {},
        "validation_result": {},
    }
    try:
        await background_orchestration(ticket, initial_state, time.time())
        print("Success! Check Supabase.")
    except Exception as e:
        print(f"Orchestration threw an uncaught exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

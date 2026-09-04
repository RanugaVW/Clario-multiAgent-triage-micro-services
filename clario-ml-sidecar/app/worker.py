import os
import json
import time
import asyncio
import redis
import logging
from dotenv import load_dotenv

load_dotenv()

# We configure logging for the worker
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RedisWorker")

from app.main import background_orchestration, TicketRequest, lifespan
from app.tracing.pipeline_tracer import emit

# Assuming a mock FastAPI app to reuse the lifespan preload logic
class MockApp:
    pass

QUEUE_KEY = "ticket_queue"
# A ticket lives here for the exact duration it's being handled by this
# worker - BLMOVE puts it here atomically as it leaves QUEUE_KEY, and it's
# only removed (see the `finally` below) once this process has actually had
# a chance to react to it. A bare BRPOP (the old approach) instead removes
# the message from Redis the instant it's read, before any processing even
# starts - if the worker process dies right after (crash, OOM, a deploy)
# that ticket is gone forever, stuck in Supabase in whatever status it had
# when it was enqueued, with nothing to ever retry it. Found and reproduced
# in Testing/06-Failover-Recovery-Testing (findings D1/D2).
PROCESSING_KEY = "ticket_queue:processing"


def _recover_stale_messages(r: redis.Redis) -> None:
    """Move anything left in PROCESSING_KEY by a previous run's crash back
    onto the main queue, so it gets retried instead of sitting lost."""
    recovered = 0
    while r.rpoplpush(PROCESSING_KEY, QUEUE_KEY) is not None:
        recovered += 1
    if recovered:
        logger.warning(f"Recovered {recovered} ticket(s) left in-flight by a previous run; requeued for retry.")


async def process_queue():
    # Preload models just like the main API does
    async with lifespan(MockApp()):
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        _recover_stale_messages(r)
        logger.info("Listening for tickets on Redis queue 'ticket_queue'...")

        while True:
            try:
                # BLMOVE atomically pops from the right of QUEUE_KEY and pushes
                # to the left of PROCESSING_KEY - the message is never absent
                # from both lists at once, so if THIS process crashes before
                # finishing, _recover_stale_messages() picks it back up on the
                # next startup instead of it being lost like a bare BRPOP.
                message = r.blmove(QUEUE_KEY, PROCESSING_KEY, timeout=0, src="RIGHT", dest="LEFT")
                if not message:
                    continue
                logger.info(f"Received message from {QUEUE_KEY}")
                try:
                    payload = json.loads(message)
                    emit(payload.get("ticket_id", "unknown"), "ai-orchestrator-service", "queue", "dequeued",
                         {"queue_depth": r.llen(QUEUE_KEY)})
                    ticket = TicketRequest(
                        ticket_id=payload['ticket_id'],
                        raw_text=payload['raw_text'],
                        image_base64=payload.get('image_base64')
                    )

                    initial_state = {
                        "ticket_id": ticket.ticket_id,
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
                        "llm_call_count": 0,
                    }

                    start_time = time.time()

                    # Await the processing directly
                    await background_orchestration(ticket, initial_state, start_time)
                    logger.info(f"Finished processing ticket {ticket.ticket_id}")
                finally:
                    # Whatever just happened above (success, or a failure
                    # background_orchestration already handles internally) -
                    # this process is still alive and got a chance to react,
                    # so the message is no longer "in flight". Only an actual
                    # process death (which skips this `finally` entirely)
                    # leaves it in PROCESSING_KEY for recovery on restart.
                    r.lrem(PROCESSING_KEY, 1, message)

            except Exception as e:
                logger.error(f"Error processing message from queue: {e}")
                await asyncio.sleep(5) # Prevent tight loop on failure

if __name__ == "__main__":
    asyncio.run(process_queue())

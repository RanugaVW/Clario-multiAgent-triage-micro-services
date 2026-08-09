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
from app.main import background_orchestration, TicketRequest

async def process_queue():
    r = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'), port=6379, db=0, decode_responses=True)
    logger.info("Listening for tickets on Redis queue 'ticket_queue'...")
        
    while True:
        try:
            # Block until a message is available (timeout 0 means block indefinitely)
            result = r.brpop("ticket_queue", timeout=0)
            if result:
                queue_name, message = result
                logger.info(f"Received message from {queue_name}")
                
                payload = json.loads(message)
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
                }
                
                start_time = time.time()
                
                # Await the processing directly
                await background_orchestration(ticket, initial_state, start_time)
                logger.info(f"Finished processing ticket {ticket.ticket_id}")
                
        except Exception as e:
            logger.error(f"Error processing message from queue: {e}")
            await asyncio.sleep(5) # Prevent tight loop on failure

if __name__ == "__main__":
    asyncio.run(process_queue())

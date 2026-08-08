import redis
import json
import uuid
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv('/home/ranuga-weerasekara/Desktop/clario/clario-ml-sidecar/.env')

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
supabase = create_client(
    os.environ.get("SUPABASE_PROJECT_URL", "https://mdvfvtpbwqhccmaarpli.supabase.co"),
    os.environ.get("SUPABASE_SECRET_API")
)

ticket_id = str(uuid.uuid4())
user_id = '00000000-0000-0000-0000-000000000000' # System user ID

# 1. Insert mock ticket into Supabase directly to simulate API Gateway
supabase.table("tickets").insert({
    "id": ticket_id,
    "raw_text": "I can't login, I forgot my password. Can you help me reset it? My email is ranuga@example.com",
    "subject": "Mock Ticket",
    "user_id": user_id,
    "status": "received"
}).execute()
print(f"Created mock ticket {ticket_id} in Supabase.")

# 2. Push to Redis queue
payload = {
    "ticket_id": ticket_id,
    "raw_text": "I can't login, I forgot my password. Can you help me reset it? My email is ranuga@example.com"
}
r.lpush("ticket_queue", json.dumps(payload))
print(f"Pushed mock ticket {ticket_id} to Redis.")

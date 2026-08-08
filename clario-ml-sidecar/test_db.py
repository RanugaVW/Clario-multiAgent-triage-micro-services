from supabase import create_client, Client
import os

SUPABASE_URL = "https://mdvfvtpbwqhccmaarpli.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_API", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

response = supabase.table("tickets").select("id, status, raw_text, resolutions(*), human_reviews(*)").order("created_at", desc=True).limit(1).execute()
print(response.data)

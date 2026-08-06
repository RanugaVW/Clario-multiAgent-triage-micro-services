import os
import json
import asyncio
import threading
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
import logging
import time

load_dotenv(dotenv_path=r"C:\Users\ranug\Clario\clario\ml_finetuning\.env")

# Setup Logging
log_file = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\distillation_progress.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# ── API Key Rotation Setup ────────────────────────────────────────────────────
# Load all 9 keys from .env and build a pool of genai clients.
_KEY_ENV_NAMES = [
    "GEMINI_API_KEY",  "GEMINI_API_KEY2", "GEMINI_API_KEY3",
    "GEMINI_API_KEY4", "GEMINI_API_KEY5", "GEMINI_API_KEY6",
    "GEMINI_API_KEY7", "GEMINI_API_KEY8", "GEMINI_API_KEY9",
]

_clients = []
for _name in _KEY_ENV_NAMES:
    _key = os.getenv(_name)
    if _key:
        _clients.append(genai.Client(api_key=_key))

if not _clients:
    raise RuntimeError("No GEMINI API keys found in .env file!")

logging.info(f"Loaded {len(_clients)} API keys for rotation.")

# Thread-safe round-robin key rotation state.
# exhausted_clients tracks indices of keys that hit daily quota.
_lock = threading.Lock()
_current_idx = 0
_exhausted = set()

def _get_client():
    """Get the next available (non-exhausted) client in round-robin order."""
    with _lock:
        available = [i for i in range(len(_clients)) if i not in _exhausted]
        if not available:
            return None, -1
        global _current_idx
        # find the next available index >= _current_idx (wrap around)
        candidates = [i for i in available if i >= _current_idx]
        if not candidates:
            candidates = available
        idx = candidates[0]
        _current_idx = (idx + 1) % len(_clients)
        return _clients[idx], idx

def _mark_exhausted(idx):
    """Mark a key index as daily-quota exhausted."""
    with _lock:
        _exhausted.add(idx)
        remaining = len(_clients) - len(_exhausted)
        logging.warning(f"Key [{idx+1}] daily quota exhausted. {remaining}/{len(_clients)} keys still available.")

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert IT Support Triage Analyst. Your task is to analyze a customer support ticket based on the 'Product' and 'Issue Description', and classify it.

Before providing the final labels, you must provide a step-by-step logical reasoning process (Chain-of-Thought). Analyze the user's intent, the urgency of the problem, the emotional tone, and the technical complexity. 

Your output MUST be a valid JSON object with the exact following structure (do NOT wrap it in markdown code blocks, just raw JSON):
{
  "reasoning": "Step 1: Analyze intent... Step 2: Evaluate urgency... Step 3: Determine sentiment... Step 4: Assess complexity...",
  "labels": {
    "category": "<String>",
    "priority": "<Low|Medium|High|Critical>",
    "sentiment": "<Positive|Neutral|Negative>",
    "issue_complexity_score": <Integer 1-5>
  }
}
"""

# ── Core API Call with Key Rotation ──────────────────────────────────────────
async def call_gemini(product, issue_description, semaphore):
    async with semaphore:
        prompt = f"Product: {product}\nIssue Description: {issue_description}"

        for attempt in range(10):  # up to 10 attempts (covers rotating through all keys)
            client, key_idx = _get_client()
            if client is None:
                logging.error("All API keys have hit their daily quota. Cannot process more tickets today.")
                return None

            try:
                # Rate limit: ~15 RPM per key. With 9 keys we could go faster,
                # but we keep a small sleep to be safe across all keys.
                await asyncio.sleep(1.0)

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model='gemini-3.1-flash-lite',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        response_mime_type="application/json"
                    )
                )

                result = json.loads(response.text)
                return {
                    "input_product": product,
                    "input_issue_description": issue_description,
                    "reasoning": result.get("reasoning", ""),
                    "labels": result.get("labels", {})
                }

            except Exception as e:
                error_msg = str(e)

                # Daily quota exhausted for this key → rotate immediately
                if ('GenerateRequestsPerDayPerProject' in error_msg or
                        ('429' in error_msg and 'limit:' in error_msg)):
                    _mark_exhausted(key_idx)
                    # Don't sleep — immediately try with the next key
                    continue

                # Per-minute rate limit → short wait then retry same pool
                elif '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                    logging.warning(f"Key [{key_idx+1}] per-minute rate limited. Waiting 65s... (Attempt {attempt+1})")
                    await asyncio.sleep(65)

                # Network / transient error → short wait then retry
                else:
                    logging.warning(f"Network/API error on key [{key_idx+1}]: {error_msg[:120]}. Waiting 10s... (Attempt {attempt+1})")
                    await asyncio.sleep(10)

        logging.error("Failed to process ticket after 10 attempts across all keys.")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    input_csv = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\train_split.csv"
    output_jsonl = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\distilled_train.jsonl"

    logging.info(f"Loading data from {input_csv}...")
    df = pd.read_csv(input_csv)

    # Resume from last saved position
    start_index = 0
    if os.path.exists(output_jsonl):
        with open(output_jsonl, 'r', encoding='utf-8') as f:
            start_index = sum(1 for _ in f)
        if start_index > 0:
            logging.info(f"Found {start_index} existing records. Resuming from index {start_index}...")
            df = df.iloc[start_index:]

    total_rows = len(df)
    logging.info(f"Total rows left to process: {total_rows}")
    logging.info(f"Using {len(_clients)} API keys in rotation (effective daily capacity: {len(_clients) * 500:,} requests)")

    # With 9 keys we can run slightly more concurrent requests safely
    semaphore = asyncio.Semaphore(3)

    tasks = [
        asyncio.create_task(call_gemini(row['product'], row['issue_description'], semaphore))
        for _, row in df.iterrows()
    ]

    logging.info("Starting Gemini distillation API calls with key rotation...")

    processed = 0
    success = 0
    start_time = time.time()
    last_log_time = start_time

    with open(output_jsonl, 'a', encoding='utf-8') as f:
        for coro in asyncio.as_completed(tasks):
            res = await coro
            processed += 1
            if res is not None:
                success += 1
                f.write(json.dumps(res) + "\n")
                f.flush()

            current_time = time.time()
            if current_time - last_log_time >= 3600 or processed % 100 == 0:
                elapsed = current_time - start_time
                rate = success / (elapsed / 3600) if elapsed > 0 else 0
                logging.info(
                    f"Progress: {processed}/{total_rows} processed | "
                    f"{success} successful | {len(_exhausted)}/{len(_clients)} keys exhausted | "
                    f"Rate: {rate:.0f} req/hr | Elapsed: {elapsed/3600:.2f}h"
                )
                last_log_time = current_time

            # If all keys exhausted, stop gracefully
            if len(_exhausted) == len(_clients):
                logging.error("All API keys exhausted for today. Stopping. Restart tomorrow to continue.")
                break

    logging.info(f"Distillation session complete! Processed {success}/{processed} tickets successfully.")


if __name__ == "__main__":
    asyncio.run(main())

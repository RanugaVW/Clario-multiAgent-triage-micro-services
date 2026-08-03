import os
import json
import asyncio
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Load Gemini client
# Note: Ensure GEMINI_API_KEY is in your .env file.
client = genai.Client()

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

async def call_gemini(product, issue_description, semaphore):
    async with semaphore:
        prompt = f"Product: {product}\nIssue Description: {issue_description}"
        try:
            # STRICT FREE TIER RATE LIMITING: 15 Requests Per Minute
            # We must wait 4 seconds between requests to avoid the 429 Resource Exhausted error.
            await asyncio.sleep(4.1)
            
            # Run blocking API call in a thread pool
            response = await asyncio.to_thread(
                client.models.generate_content,
                model='gemini-1.5-flash-8b', # The designated model for high-volume/bulk work
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            
            # The response text should be JSON
            result = json.loads(response.text)
            
            # Return the input along with the distilled outputs
            return {
                "input_product": product,
                "input_issue_description": issue_description,
                "reasoning": result.get("reasoning", ""),
                "labels": result.get("labels", {})
            }
        except Exception as e:
            print(f"Error processing ticket: {e}")
            return None

async def main():
    # File paths
    input_csv = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\train_split.csv"
    output_jsonl = r"C:\Users\ranug\Clario\clario\ml_finetuning\data\curated_synthetic_lms\distilled_train.jsonl"
    
    print(f"Loading data from {input_csv}...")
    df = pd.read_csv(input_csv)
    
    print(f"Total rows to process: {len(df)}")
    
    # Concurrency control: Set to 1 to strictly respect the 15 RPM limit
    semaphore = asyncio.Semaphore(1)
    
    tasks = []
    for index, row in df.iterrows():
        tasks.append(call_gemini(row['product'], row['issue_description'], semaphore))
        
    print("Starting Gemini distillation API calls...")
    results = await asyncio.gather(*tasks)
    
    # Filter out failures
    valid_results = [r for r in results if r is not None]
    
    print(f"Successfully processed {len(valid_results)} tickets.")
    
    # Save to JSONL
    print(f"Saving distilled data to {output_jsonl}...")
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for res in valid_results:
            f.write(json.dumps(res) + "\n")
            
    print("Distillation complete!")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from app.graph.graph_builder import build_graph
import os
from dotenv import load_dotenv

load_dotenv()
graph = build_graph()

initial_state = {
    "ticket_id": "test_mock_123",
    "raw_text": "I got this error\n[OCR EXTRACTED TEXT]\nCannot coerce the result to a single JSON object",
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

async def run():
    try:
        final_state = await graph.ainvoke(initial_state)
        print("Success:", final_state.get('status'))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run())

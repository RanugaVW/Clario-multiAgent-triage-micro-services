import asyncio
from app.graph.state import TicketState
from app.graph.cache_check_node import cache_check_node
from app.tools.rag_tool import add_precedent

def test_caching():
    # 1. Add a ticket to the precedent memory
    ticket_id = "test-12345"
    issue = "I am getting a 404 error when I try to log in to my account page."
    resolution = "We have fixed the 404 error on the login page. Please clear your cache and try again."
    
    print("Adding precedent...")
    add_precedent(ticket_id, issue, resolution, "technical")
    
    # 2. Run cache_check_node with an identical issue
    state: TicketState = {
        "ticket_id": "incoming-001",
        "raw_text": issue,
    }
    
    print("Checking cache...")
    result = cache_check_node(state)
    
    print(f"Cache hit: {result.get('cache_hit')}")
    print(f"Source ID: {result.get('cache_source_ticket_id')}")
    print(f"Routing Decision: {result.get('routing_decision')}")
    if result.get('agent_drafts'):
        print(f"Draft: {result.get('agent_drafts').get('technical')}")

if __name__ == "__main__":
    test_caching()

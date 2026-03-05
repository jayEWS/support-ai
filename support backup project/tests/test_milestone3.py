import httpx
import asyncio
import json
from app.core.database import db_manager

async def test_milestone3_flow():
    # 1. Ensure we have an available agent
    agent_id = "agent_john_demo"
    print(f"🚀 Setting up availability for {agent_id}...")
    db_manager.update_agent_presence(agent_id, "available", active_chat_count=0)
    
    # 2. Finalize a session to create a ticket
    print("🚀 Finalizing session for 'customer@example.com'...")
    url = "http://127.0.0.1:8001/api/close-session"
    payload = {"user_id": "customer@example.com", "option": 1}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=30.0)
            print(f"✅ Finalize Response: {resp.json()}")
            
            print("\n💡 Waiting for Routing Service to process the queue (up to 35s)...")
            # The routing service runs every 30s
            for i in range(10):
                await asyncio.sleep(5)
                # Check if ticket is assigned
                tickets = db_manager.get_all_tickets(filter_type='assigned')
                for t in tickets:
                    if t['user_id'] == "customer@example.com" and t['assigned_to'] == agent_id:
                        print(f"✅ SUCCESS: Ticket #{t['id']} automatically assigned to {agent_id}!")
                        print(f"✅ SLA Due At: {t['due_at']}")
                        return
                print(f"   ... still waiting ({ (i+1)*5 }s)")
            
            print("❌ Timeout: Ticket was not assigned automatically.")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_milestone3_flow())

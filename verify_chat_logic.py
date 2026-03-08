import asyncio
from app.core.database import db_manager
from app.services.chat_service import ChatService
from app.models.models import Message, Ticket

async def verify_close_chat_logic():
    print("🧪 Verifying End Chat Logic...")
    from app.services.rag_service import RAGService
    rag_svc = RAGService()
    chat_service = ChatService(rag_service=rag_svc)
    user_id = "test_user_123"
    
    # 1. Setup: Create some test messages
    db_manager.save_whatsapp_message(user_id, "inbound", "Hello, I need help.")
    db_manager.save_whatsapp_message(user_id, "outbound", "I can help with that.")
    
    initial_msgs = db_manager.get_messages(user_id)
    print(f"Initial messages for {user_id}: {len(initial_msgs)}")
    
    # 2. Test "Resolved" (option='close')
    print("\n[Test 1] Closing as RESOLVED...")
    res = await chat_service.close_chat(user_id, option="close")
    print(f"Result: {res}")
    
    after_close_msgs = db_manager.get_messages(user_id)
    print(f"Messages after Resolved: {len(after_close_msgs)} (Expected: 0)")
    
    # 3. Test "Create Ticket" (option='ticket')
    print("\n[Test 2] Closing as CREATE TICKET...")
    db_manager.save_whatsapp_message(user_id, "inbound", "Still need help.")
    res = await chat_service.close_chat(user_id, option="ticket")
    print(f"Result: {res}")
    
    after_ticket_msgs = db_manager.get_messages(user_id)
    print(f"Messages after Ticket: {len(after_ticket_msgs)} (Expected: 0)")
    
    if res.get("ticket_id"):
        print(f"✅ Ticket created with ID: {res['ticket_id']}")
    else:
        print("❌ FAILED: Ticket was not created!")

if __name__ == "__main__":
    asyncio.run(verify_close_chat_logic())

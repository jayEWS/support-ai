import asyncio
import os
import json
from unittest.mock import MagicMock
from fastapi import Request, BackgroundTasks
from starlette.datastructures import Headers

# Mocking app.state
class MockAppState:
    def __init__(self):
        self.customer_service = MagicMock()
        self.chat_service = MagicMock()
        self.intent_service = MagicMock()
        self.escalation_service = MagicMock()
        self.rag_service = MagicMock()
        self.llm_service = MagicMock()

async def test_whatsapp_flow():
    # Setup environment
    os.environ["WHATSAPP_TEST_MODE"] = "True"
    
    from main import app, whatsapp_webhook
    from app.core.config import settings
    
    # Mock services
    app.state.customer_service = MagicMock()
    app.state.customer_service.get_or_register_customer = MagicMock(
        return_value=asyncio.Future()
    )
    from app.schemas.schemas import CustomerInfo
    app.state.customer_service.get_or_register_customer.return_value.set_result(
        CustomerInfo(identifier="6281229009543", name="Test User", is_new=False)
    )
    
    app.state.chat_service = MagicMock()
    app.state.chat_service._get_user_state.return_value = {'state': 'complete'}
    app.state.chat_service._handle_onboarding.return_value = None
    app.state.chat_service.get_user_language.return_value = 'en'
    
    app.state.intent_service = MagicMock()
    classification = MagicMock()
    classification.intent = "info" # Use a string that is not CRITICAL/ESCALATION
    app.state.intent_service.classify = MagicMock(return_value=asyncio.Future())
    app.state.intent_service.classify.return_value.set_result(classification)
    
    app.state.rag_service = MagicMock()
    rag_res = MagicMock()
    rag_res.confidence = 0.9
    rag_res.answer = "This is a mock answer from RAG."
    app.state.rag_service.query = MagicMock(return_value=asyncio.Future())
    app.state.rag_service.query.return_value.set_result(rag_res)

    # Mock payload from Meta
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": { "display_phone_number": "12345", "phone_number_id": "12345" },
                    "contacts": [{ "profile": { "name": "Test User" }, "wa_id": "6281229009543" }],
                    "messages": [{
                        "from": "6281229009543",
                        "id": "wamid.HBgMNjI4MTIyOTAwOTU0MxUCABEYEkJERDg3REVGQkM0QzRDMEY0OAA=",
                        "timestamp": "1600000000",
                        "type": "text",
                        "text": { "body": "Hello bot" }
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    # Construct a real Request object
    scope = {
        "type": "http",
        "method": "POST",
        "headers": Headers({"content-type": "application/json"}).raw,
    }
    
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload).encode()}

    request = Request(scope, receive)
    background_tasks = BackgroundTasks()
    
    print("Simulating inbound WhatsApp message...")
    try:
        response = await whatsapp_webhook(request, background_tasks)
        print(f"Response: {json.dumps(response, indent=2)}")
    except Exception as e:
        print(f"Error during simulation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_whatsapp_flow())

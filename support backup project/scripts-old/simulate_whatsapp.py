import httpx
import asyncio
import json

async def simulate_incoming_whatsapp(message_text: str, phone_number: str = "6281229009543"):
    url = "http://127.0.0.1:8001/webhook/whatsapp"
    
    # This matches the Bird Conversations API webhook payload structure
    payload = {
        "message": {
            "type": "text",
            "content": {
                "text": message_text
            }
        },
        "contact": {
            "msisdn": phone_number,
            "id": "mock_contact_id_123"
        },
        "tenantId": "demo_tenant_001"
    }
    
    print(f"🚀 Simulating incoming WhatsApp from {phone_number}: '{message_text}'")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"✅ Webhook Response: {resp.status_code} - {resp.json()}")
            print("\n💡 Now check your server terminal logs to see the AI processing and the [MOCK SEND] response!")
        except Exception as e:
            print(f"❌ Error: {e}. Is your server running on http://127.0.0.1:8001?")

if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "How do I process a refund in POS?"
    asyncio.run(simulate_incoming_whatsapp(msg))

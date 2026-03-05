import httpx
import asyncio
import json
import sys

async def simulate_bird_webhook(msg_type, content, phone_number="628123456789"):
    url = "http://127.0.0.1:8001/webhook/whatsapp"
    
    payload = {
        "message": {
            "type": msg_type,
            "content": content
        },
        "contact": {
            "msisdn": phone_number,
            "id": f"mock_id_{phone_number}"
        },
        "workspaceId": "demo_workspace_001"
    }
    
    # Bird v2 often sends a list
    payload_list = [payload]
    
    print(f"🚀 Testing {msg_type} from {phone_number}...")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload_list)
            print(f"✅ Status: {resp.status_code}")
            print(f"✅ Response: {resp.json()}")
        except Exception as e:
            print(f"❌ Error: {e}. Ensure server is running at {url}")

async def run_tests():
    phone = "+628123456789"
    # 1. Test Text
    await simulate_bird_webhook("text", {"text": {"text": "Hello, I need help!"}}, phone_number=phone)
    
    # 2. Test Image
    await simulate_bird_webhook("image", {
        "image": {
            "url": "https://example.com/photo.jpg",
            "caption": "Check this out"
        }
    }, phone_number=phone)
    
    # 3. Test Audio
    await simulate_bird_webhook("audio", {
        "audio": {
            "url": "https://example.com/voice.ogg"
        }
    }, phone_number=phone)

if __name__ == "__main__":
    asyncio.run(run_tests())

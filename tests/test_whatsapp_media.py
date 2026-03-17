"""
WhatsApp Meta Cloud API Webhook Test
Tests inbound message processing using the official Meta webhook format.
"""
import httpx
import asyncio
import json
import time


async def simulate_meta_webhook(msg_type: str, msg_content: dict, phone_number: str = "628123456789"):
    """Simulate a Meta WhatsApp Cloud API webhook payload."""
    url = "http://127.0.0.1:8001/webhook/whatsapp"
    
    message_id = f"wamid.test_{int(time.time() * 1000)}"
    
    # Build the message object based on type
    message = {
        "from": phone_number.lstrip("+"),
        "id": message_id,
        "timestamp": str(int(time.time())),
        "type": msg_type,
    }
    message.update(msg_content)
    
    # Meta webhook payload format (v21.0)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": "test_phone_id"
                    },
                    "contacts": [{
                        "profile": {"name": "Test Customer"},
                        "wa_id": phone_number.lstrip("+")
                    }],
                    "messages": [message]
                },
                "field": "messages"
            }]
        }]
    }
    
    print(f"🚀 Testing {msg_type} from {phone_number}...")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=30.0)
            print(f"  Status: {resp.status_code}")
            data = resp.json()
            if data.get("response"):
                print(f"  AI Response: {data['response'][:100]}...")
            elif data.get("reason"):
                print(f"  Filtered: {data['reason']}")
            else:
                print(f"  Response: {json.dumps(data, indent=2)[:200]}")
        except Exception as e:
            print(f"  ❌ Error: {e}. Ensure server is running at {url}")
    
    # Small delay between messages to avoid duplicate detection
    await asyncio.sleep(1)


async def run_tests():
    phone = "+628123456789"
    print("=" * 60)
    print("WhatsApp Meta Cloud API — Webhook Tests")
    print("=" * 60)
    
    # 1. Text Message
    await simulate_meta_webhook("text", {
        "text": {"body": "Hello, I need help with my POS!"}
    }, phone_number=phone)
    
    # 2. Image Message
    await simulate_meta_webhook("image", {
        "image": {
            "id": "media_img_12345",
            "mime_type": "image/jpeg",
            "caption": "Check this error on screen"
        }
    }, phone_number=phone)
    
    # 3. Audio Message
    await simulate_meta_webhook("audio", {
        "audio": {
            "id": "media_audio_67890",
            "mime_type": "audio/ogg"
        }
    }, phone_number=phone)
    
    # 4. Document Message
    await simulate_meta_webhook("document", {
        "document": {
            "id": "media_doc_11111",
            "filename": "error_log.pdf",
            "mime_type": "application/pdf",
            "caption": "Here is my error log"
        }
    }, phone_number=phone)
    
    # 5. Location Message
    await simulate_meta_webhook("location", {
        "location": {
            "latitude": 1.3521,
            "longitude": 103.8198,
            "name": "Bugis Junction"
        }
    }, phone_number=phone)
    
    # 6. Interactive Button Reply
    await simulate_meta_webhook("interactive", {
        "interactive": {
            "type": "button_reply",
            "button_reply": {
                "id": "btn_yes",
                "title": "Yes, create ticket"
            }
        }
    }, phone_number=phone)
    
    print("\n" + "=" * 60)
    print("✅ All webhook tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())

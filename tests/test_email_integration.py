import httpx
import asyncio
import json

async def test_email_webhook():
    url = "http://127.0.0.1:8001/webhook/email"
    
    # Simulate Mailgun-style form data
    payload = {
        "sender": "customer@example.com",
        "subject": "Question about POS checkout",
        "body-plain": "How do I process a checkout in the Fast Food module?"
    }
    
    print(f"🚀 Testing email webhook from {payload['sender']}...")
    
    async with httpx.AsyncClient() as client:
        try:
            # We'll use data= for form-encoded or json= for json
            resp = await client.post(url, data=payload)
            print(f"✅ Status: {resp.status_code}")
            print(f"✅ Response: {resp.json()}")
            
            print("\n💡 Checking database for user creation and message storage...")
            await asyncio.sleep(2) # Wait for background task
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_email_webhook())

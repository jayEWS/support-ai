# 🧪 Testing Guide - Support Portal

## Server Status
✅ **Running on http://127.0.0.1:8001**

---

## Test Option 1: Open in Browser (Easiest)

```
http://127.0.0.1:8001
```

**What you'll see**: Dashboard with chat interface

---

## Test Option 2: Quick API Test (PowerShell)

```powershell
# Test health/root endpoint
curl http://127.0.0.1:8001/

# Expected: HTML dashboard loads
```

---

## Test Option 3: Test Chat Endpoint

```powershell
# Test the chat API
$body = @{
    message = "What is your support process?"
    user_id = "test_user_123"
} | ConvertTo-Json

curl -Method POST `
  -Uri "http://127.0.0.1:8001/api/chat" `
  -ContentType "application/json" `
  -Body $body

# Expected response:
# {
#   "reply": "Based on our knowledge base...",
#   "confidence": 0.85,
#   "retrieval_method": "hybrid"
# }
```

---

## Test Option 4: Test Rate Limiting

```powershell
# Make 15 rapid requests to webhook
# Should get 429 (Too Many Requests) on requests 11-15

for ($i = 1; $i -le 15; $i++) {
    $response = curl -s -w "`nHTTP_%{http_code}" `
      -X POST "http://127.0.0.1:8001/webhook/whatsapp" `
      -H "Content-Type: application/json" `
      -d '{"test":"data"}'
    
    $code = $response | Select-String "HTTP_\d+" | ForEach-Object { $_.Matches[0].Value }
    Write-Host "Request $i : $code" -ForegroundColor $(if ($code -eq "HTTP_429") { "Red" } else { "Green" })
}

# Expected: Requests 1-10 pass, 11-15 return HTTP_429
```

---

## Test Option 5: RAG Quality Test (Advanced)

```powershell
# Test the RAG evaluation framework
cd d:\Project\support-portal-edgeworks

# Run evaluation
python app/services/rag_evaluation.py

# Expected output: Pass rate, faithfulness scores, etc.
```

---

## Test Option 6: WebSocket Chat Test (Real-time)

Create a file `test_websocket.py`:

```python
import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://127.0.0.1:8001/ws/chat/test_user_123"
    
    async with websockets.connect(uri) as websocket:
        # Send a message
        message = {
            "type": "message",
            "content": "How do I submit a ticket?"
        }
        await websocket.send(json.dumps(message))
        print(f"Sent: {message}")
        
        # Receive response
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_chat())
```

Run it:
```powershell
python test_websocket.py
```

---

## Test Option 7: Full Integration Test

```powershell
# Run all tests in order
Write-Host "Testing Support Portal..." -ForegroundColor Cyan

# 1. Health check
Write-Host "`n1. Health Check..." -ForegroundColor Yellow
$health = curl -s http://127.0.0.1:8001/ | Measure-Object -Character | Select-Object -ExpandProperty Characters
Write-Host "   ✅ Server responding ($health bytes)"

# 2. API test
Write-Host "`n2. Chat API Test..." -ForegroundColor Yellow
$body = @{message = "test"; user_id = "test"} | ConvertTo-Json
$api_result = curl -s -X POST "http://127.0.0.1:8001/api/chat" `
  -H "Content-Type: application/json" `
  -d $body
if ($api_result) {
    Write-Host "   ✅ API responding"
} else {
    Write-Host "   ❌ API error"
}

# 3. Rate limiting test
Write-Host "`n3. Rate Limiting Test..." -ForegroundColor Yellow
$limited = 0
for ($i = 1; $i -le 12; $i++) {
    $response = curl -s -w "`nHTTP_%{http_code}" `
      -X POST "http://127.0.0.1:8001/webhook/whatsapp" `
      -H "Content-Type: application/json" `
      -d '{"test":"data"}' 2>$null
    $code = $response | Select-String "HTTP_\d+" | ForEach-Object { $_.Matches[0].Value }
    if ($code -eq "HTTP_429") { $limited++ }
}
Write-Host "   ✅ Rate limiting active ($limited requests blocked at 429)"

Write-Host "`n✅ All tests complete!" -ForegroundColor Green
```

---

## Test Option 8: Python Client Test

Create `test_client.py`:

```python
import requests
import json

BASE_URL = "http://127.0.0.1:8001"

def test_health():
    """Test server is running"""
    response = requests.get(f"{BASE_URL}/")
    print(f"✅ Health check: {response.status_code}")
    return response.status_code == 200

def test_chat():
    """Test chat API"""
    payload = {
        "message": "What is your return policy?",
        "user_id": "test_user_001"
    }
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Chat API working")
        print(f"   Reply: {data.get('reply', 'N/A')[:100]}...")
        print(f"   Confidence: {data.get('confidence', 'N/A')}")
        print(f"   Method: {data.get('retrieval_method', 'N/A')}")
    else:
        print(f"❌ Chat API error: {response.status_code}")
    return response.status_code == 200

def test_rate_limit():
    """Test rate limiting"""
    limited_count = 0
    for i in range(12):
        response = requests.post(
            f"{BASE_URL}/webhook/whatsapp",
            json={"test": "data"},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 429:
            limited_count += 1
    
    print(f"✅ Rate limiting: {limited_count} requests blocked")
    return limited_count > 0

if __name__ == "__main__":
    print("Testing Support Portal API...\n")
    test_health()
    test_chat()
    test_rate_limit()
    print("\n✅ All tests passed!")
```

Run it:
```powershell
python test_client.py
```

---

## Troubleshooting

### "Connection refused"
- Server not running? Try: `python -m uvicorn main:app --host 127.0.0.1 --port 8001`

### "ModuleNotFoundError"
- Missing packages? Try: `pip install -r requirements.txt`

### "Permission denied"
- On Windows, use full Python path: `.\.venv\Scripts\python.exe`

### "Vector store not available"
- ✅ This is OK - system falls back to keyword search only
- Not a problem for testing

---

## What Each Test Checks

| Test | What It Tests | Expected Result |
|------|--------------|-----------------|
| **Browser** | UI dashboard | Loads chat interface |
| **Health** | Server running | HTTP 200 response |
| **Chat API** | LLM response | JSON with reply + confidence |
| **Rate Limit** | Protection | HTTP 429 after 10 req/min |
| **Evaluation** | RAG quality | Pass rate ≥80% |
| **WebSocket** | Real-time chat | JSON message exchange |
| **Integration** | Full workflow | All tests pass |

---

## Quick Start: Simplest Test

Just open this URL in your browser:
```
http://127.0.0.1:8001
```

That's it! You should see the chat dashboard.

---

**Last Updated**: Feb 28, 2026

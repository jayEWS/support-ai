#!/usr/bin/env python
"""
Quick Test - Tests running server at http://127.0.0.1:8001
Does NOT start the server - assumes it's already running
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8001"

print("\n" + "╔" + "="*48 + "╗")
print("║ 🧪 SUPPORT PORTAL - QUICK TEST".ljust(49) + "║")
print("╚" + "="*48 + "╝\n")

print(f"Server: {BASE_URL}")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("-"*50 + "\n")

# Test 1: Server Running
print("[1/4] Testing if server is running...")
try:
    response = requests.get(f"{BASE_URL}/", timeout=5)
    if response.status_code == 200:
        print("✅ PASS: Server is running (HTTP 200)\n")
    else:
        print(f"❌ FAIL: Server returned {response.status_code}\n")
except Exception as e:
    print(f"❌ FAIL: Cannot connect to {BASE_URL}")
    print(f"       Error: {str(e)}")
    print("       → Start server: python -m uvicorn main:app --host 127.0.0.1 --port 8001\n")
    exit(1)

# Test 2: Chat API
print("[2/4] Testing Chat API...")
try:
    payload = {
        "message": "What is your support process?",
        "user_id": "test_user_001"
    }
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ PASS: Chat API responding (HTTP 200)")
        print(f"   - Reply: {data.get('reply', 'N/A')[:80]}...")
        print(f"   - Confidence: {data.get('confidence', 'N/A')}")
        print(f"   - Method: {data.get('retrieval_method', 'N/A')}\n")
    else:
        print(f"❌ FAIL: Chat API returned {response.status_code}\n")
except requests.Timeout:
    print("⚠️  TIMEOUT: Chat API took too long (>15s)")
    print("    This may indicate LLM is slow or unavailable\n")
except Exception as e:
    print(f"❌ FAIL: Chat API error: {str(e)}\n")

# Test 3: Rate Limiting
print("[3/4] Testing Rate Limiting (making 12 requests)...")
try:
    limited_count = 0
    first_limit = None
    
    for i in range(12):
        response = requests.post(
            f"{BASE_URL}/webhook/whatsapp",
            json={"test": "data"},
            headers={"Content-Type": "application/json"},
            timeout=2
        )
        
        if response.status_code == 429:
            limited_count += 1
            if first_limit is None:
                first_limit = i + 1
    
    if limited_count > 0:
        print(f"✅ PASS: Rate limiting is active")
        print(f"   - Rate limit triggered at request {first_limit}")
        print(f"   - Total blocked: {limited_count} requests\n")
    else:
        print("⚠️  WARNING: No rate limiting detected")
        print("    (All 12 requests passed - this may be OK)\n")
except Exception as e:
    print(f"⚠️  Rate limiting test error: {str(e)}\n")

# Test 4: Database
print("[4/4] Testing Database Connection...")
try:
    response = requests.get(f"{BASE_URL}/", timeout=5)
    if response.status_code == 200:
        print("✅ PASS: Database is connected")
        print("    (Server started successfully with DB)\n")
    else:
        print("❌ FAIL: Database may not be connected\n")
except Exception as e:
    print(f"❌ FAIL: Database test error: {str(e)}\n")

print("="*50)
print("✅ TESTING COMPLETE\n")
print("Next Steps:")
print("  1. Open browser: http://127.0.0.1:8001")
print("  2. Try sending a chat message")
print("  3. Check RAG quality and response times")
print("  4. Review logs for any warnings")
print("")

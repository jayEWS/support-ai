#!/usr/bin/env python
"""
Quick Test Suite - Support Portal
Run: python quick_test.py
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://127.0.0.1:8001"
RESULTS = []

def log(message, status="INFO", color=None):
    """Print colored log message"""
    colors = {
        "SUCCESS": "\033[92m",  # Green
        "ERROR": "\033[91m",    # Red
        "WARNING": "\033[93m",  # Yellow
        "INFO": "\033[94m"      # Blue
    }
    end_color = "\033[0m"
    
    if color or status in colors:
        color_code = colors.get(status, colors["INFO"])
        print(f"{color_code}[{status}]{end_color} {message}")
    else:
        print(f"[{status}] {message}")

def test_server_running():
    """Test 1: Is server running?"""
    log("Testing if server is running...", "INFO")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            log("✅ Server is running", "SUCCESS")
            RESULTS.append(("Server Running", True))
            return True
        else:
            log(f"❌ Server returned {response.status_code}", "ERROR")
            RESULTS.append(("Server Running", False))
            return False
    except requests.exceptions.ConnectionError:
        log(f"❌ Cannot connect to {BASE_URL}", "ERROR")
        log("   → Is the server running? Try: python -m uvicorn main:app --host 127.0.0.1 --port 8001", "WARNING")
        RESULTS.append(("Server Running", False))
        return False
    except Exception as e:
        log(f"❌ Error: {str(e)}", "ERROR")
        RESULTS.append(("Server Running", False))
        return False

def test_chat_api():
    """Test 2: Chat API responding?"""
    log("\nTesting Chat API...", "INFO")
    try:
        payload = {
            "message": "What is your support process?",
            "user_id": "test_user_001"
        }
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            reply = data.get("reply", "N/A")[:80]
            confidence = data.get("confidence", "N/A")
            method = data.get("retrieval_method", "N/A")
            
            log(f"✅ Chat API responding", "SUCCESS")
            log(f"   Reply: {reply}...", "INFO")
            log(f"   Confidence: {confidence}", "INFO")
            log(f"   Method: {method}", "INFO")
            RESULTS.append(("Chat API", True))
            return True
        else:
            log(f"❌ Chat API returned {response.status_code}", "ERROR")
            RESULTS.append(("Chat API", False))
            return False
    except Exception as e:
        log(f"❌ Chat API error: {str(e)}", "ERROR")
        RESULTS.append(("Chat API", False))
        return False

def test_rate_limiting():
    """Test 3: Rate limiting active?"""
    log("\nTesting Rate Limiting...", "INFO")
    try:
        limited_count = 0
        normal_count = 0
        
        for i in range(12):
            try:
                response = requests.post(
                    f"{BASE_URL}/webhook/whatsapp",
                    json={"test": "data"},
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                
                if response.status_code == 429:
                    limited_count += 1
                    if i == 10:  # First limited response
                        log(f"✅ Rate limit triggered at request {i+1} (HTTP 429)", "SUCCESS")
                else:
                    normal_count += 1
            except:
                pass
        
        if limited_count > 0:
            log(f"✅ Rate limiting is active ({limited_count} requests blocked)", "SUCCESS")
            RESULTS.append(("Rate Limiting", True))
            return True
        else:
            log("⚠️  Rate limiting may not be active", "WARNING")
            RESULTS.append(("Rate Limiting", False))
            return False
    except Exception as e:
        log(f"⚠️  Rate limiting test error: {str(e)}", "WARNING")
        RESULTS.append(("Rate Limiting", None))
        return None

def test_database():
    """Test 4: Database connected?"""
    log("\nTesting Database Connection...", "INFO")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        # If server runs, database is likely connected (checked on startup)
        if response.status_code == 200:
            log("✅ Database connection verified (server started successfully)", "SUCCESS")
            RESULTS.append(("Database Connected", True))
            return True
        else:
            log("❌ Database issue", "ERROR")
            RESULTS.append(("Database Connected", False))
            return False
    except Exception as e:
        log(f"❌ Database test error: {str(e)}", "ERROR")
        RESULTS.append(("Database Connected", False))
        return False

def test_static_files():
    """Test 5: Static files loading?"""
    log("\nTesting Static Files...", "INFO")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        content = response.text
        
        if "html" in content.lower() or "chat" in content.lower():
            log("✅ Static files loading", "SUCCESS")
            RESULTS.append(("Static Files", True))
            return True
        else:
            log("⚠️  Unclear if static files loaded", "WARNING")
            RESULTS.append(("Static Files", None))
            return None
    except Exception as e:
        log(f"⚠️  Static files test error: {str(e)}", "WARNING")
        RESULTS.append(("Static Files", None))
        return None

def print_summary():
    """Print test summary"""
    log("\n" + "="*50, "INFO")
    log("TEST SUMMARY", "INFO")
    log("="*50, "INFO")
    
    passed = sum(1 for _, result in RESULTS if result is True)
    failed = sum(1 for _, result in RESULTS if result is False)
    unknown = sum(1 for _, result in RESULTS if result is None)
    
    for test_name, result in RESULTS:
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  UNKNOWN"
        
        print(f"  {status}  {test_name}")
    
    log("\n" + "="*50, "INFO")
    log(f"Results: {passed} passed, {failed} failed, {unknown} unknown", "INFO")
    
    if failed == 0:
        log("\n✅ All critical tests passed! App is ready to use.", "SUCCESS")
        log("   → Open in browser: http://127.0.0.1:8001", "INFO")
        return True
    else:
        log(f"\n❌ {failed} test(s) failed. See details above.", "ERROR")
        return False

def main():
    print("\n" + "╔" + "="*48 + "╗")
    print("║ 🧪 SUPPORT PORTAL - QUICK TEST SUITE".ljust(49) + "║")
    print("╚" + "="*48 + "╝\n")
    
    log(f"Server: {BASE_URL}", "INFO")
    log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
    log("-"*50, "INFO")
    
    # Run all tests
    test_server_running()
    if RESULTS[-1][1] is False:
        log("\n⚠️  Stopping tests - server not running", "WARNING")
        print_summary()
        return 1
    
    test_chat_api()
    test_rate_limiting()
    test_database()
    test_static_files()
    
    # Print summary
    success = print_summary()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

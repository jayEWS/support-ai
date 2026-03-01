#!/usr/bin/env python3
"""
Complete magic link flow test with verification.
"""

import sys
import os
import time
import subprocess
import requests
import re
from pathlib import Path

def test_complete_flow():
    """Test complete magic link flow including verification"""
    
    # Set environment variables
    env = os.environ.copy()
    env['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:8001')
    # DATABASE_URL must be set in environment or .env file - never hardcode credentials here
    
    # Start server
    print("Starting server...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", 
         "--host", "0.0.0.0", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True
    )
    
    # Wait for server to start
    time.sleep(4)
    
    if server_process.poll() is not None:
        print("❌ Server failed to start")
        return
    
    print("✓ Server running")
    
    # Step 1: Request magic link
    email = "verify-test@example.com"
    print(f"\n1. Requesting magic link for {email}...")
    
    response = requests.post(
        "http://localhost:8001/api/auth/magic-link/request",
        json={"email": email},
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"❌ Failed: {response.status_code}")
        server_process.terminate()
        return
    
    print("✓ Magic link requested")
    
    # Wait a moment for logging
    time.sleep(2)
    
    # Step 2: Get logs to extract token
    print("\n2. Extracting token from logs...")
    server_process.terminate()
    
    try:
        stdout, stderr = server_process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()
        stdout, stderr = server_process.communicate()
    
    # Extract token from logs
    match = re.search(r'token=([^&\s"]+)', stderr)
    if not match:
        print("❌ Could not extract token from logs")
        print("Logs:")
        print(stderr[-500:])
        return
    
    token = match.group(1)
    print(f"✓ Token extracted: {token[:20]}...")
    
    # Restart server for verification test
    print("\n3. Restarting server for verification...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", 
         "--host", "0.0.0.0", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True
    )
    
    time.sleep(3)
    print("✓ Server restarted")
    
    # Step 3: Verify magic link
    print(f"\n4. Verifying magic link with token...")
    verify_url = f"http://localhost:8001/api/auth/magic-link/verify?token={token}&email={email}"
    
    try:
        response = requests.get(verify_url, timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Verification successful!")
            print(f"\n   Access Token: {data['access_token'][:30]}...")
            print(f"   Token Type: {data['token_type']}")
            print(f"   User Email: {data['email']}")
            print(f"   User Role: {data['role']}")
            print(f"   User Name: {data.get('name', 'N/A')}")
            print("\n✅ COMPLETE MAGIC LINK FLOW WORKING!")
        else:
            print(f"❌ Verification failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Cleanup
    server_process.terminate()
    try:
        server_process.communicate(timeout=5)
    except:
        server_process.kill()

if __name__ == "__main__":
    test_complete_flow()

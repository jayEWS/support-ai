#!/usr/bin/env python3
"""
Test script to diagnose server crash issue.
Tests various scenarios to isolate the problem.
"""

import sys
import os
import time
import subprocess
import requests
import json
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_simple_get():
    """Test if server can handle a simple GET request"""
    print("\n" + "="*60)
    print("TEST 1: Simple GET request to /health")
    print("="*60)
    
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        print(f"✓ GET /health succeeded with status {response.status_code}")
        print(f"  Response: {response.text}")
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"✗ GET /health failed: Connection error")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"✗ GET /health failed: {type(e).__name__}")
        print(f"  Error: {e}")
        return False

def test_magic_link_request():
    """Test POST request to magic link endpoint"""
    print("\n" + "="*60)
    print("TEST 2: POST request to /api/auth/magic-link/request")
    print("="*60)
    
    try:
        data = {"email": "test@example.com"}
        response = requests.post(
            "http://localhost:8001/api/auth/magic-link/request",
            json=data,
            timeout=10
        )
        print(f"✓ POST succeeded with status {response.status_code}")
        print(f"  Response: {response.json()}")
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"✗ POST failed: Connection error (server crashed?)")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"✗ POST failed: {type(e).__name__}")
        print(f"  Error: {e}")
        return False

def test_imports():
    """Test if all modules can be imported"""
    print("\n" + "="*60)
    print("TEST 0: Testing imports")
    print("="*60)
    
    try:
        print("Importing FastAPI...")
        from fastapi import FastAPI
        print("  ✓ FastAPI imported")
        
        print("Importing uvicorn...")
        import uvicorn
        print("  ✓ uvicorn imported")
        
        print("Importing app.core modules...")
        from app.core.config import settings
        from app.core.database import DatabaseManager
        print("  ✓ app.core modules imported")
        
        print("Importing app.utils.email_utils...")
        from app.utils.email_utils import send_magic_link_email
        print("  ✓ app.utils.email_utils imported")
        
        print("Importing main app...")
        import main
        print("  ✓ main app imported")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {type(e).__name__}")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_server_test():
    """Start server and run tests"""
    print("\n" + "="*70)
    print("STARTING SERVER DIAGNOSTIC TEST")
    print("="*70)
    
    # Test imports first
    if not test_imports():
        print("\n❌ Import test failed - cannot proceed")
        return
    
    print("\n" + "-"*70)
    print("Starting server in background...")
    print("-"*70)
    
    # Set environment variables
    env = os.environ.copy()
    env['BASE_URL'] = 'http://localhost:8001'
    
    # Start server
    try:
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", 
             "--host", "0.0.0.0", "--port", "8001"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        print(f"✓ Server process started (PID: {server_process.pid})")
        
        # Wait for server to start
        print("Waiting 3 seconds for server to initialize...")
        time.sleep(3)
        
        # Check if process is still running
        poll_result = server_process.poll()
        if poll_result is not None:
            print(f"✗ Server exited immediately with code: {poll_result}")
            stdout, stderr = server_process.communicate()
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            return
        
        print("✓ Server is running")
        
        # Run tests
        test_results = []
        test_results.append(("GET /health", test_simple_get()))
        
        # Small delay between requests
        time.sleep(1)
        
        # Check if server is still running before next test
        poll_result = server_process.poll()
        if poll_result is not None:
            print(f"\n⚠️  Server crashed after GET test (exit code: {poll_result})")
        else:
            test_results.append(("POST /api/auth/magic-link/request", test_magic_link_request()))
        
        # Check if server is still running
        poll_result = server_process.poll()
        if poll_result is not None:
            print(f"\n⚠️  Server crashed during tests (exit code: {poll_result})")
        
        # Terminate server
        print("\n" + "-"*70)
        print("Stopping server...")
        server_process.terminate()
        
        try:
            stdout, stderr = server_process.communicate(timeout=5)
            if stdout:
                print("Server STDOUT:")
                print(stdout)
            if stderr:
                print("Server STDERR:")
                print(stderr)
        except subprocess.TimeoutExpired:
            server_process.kill()
            print("Server did not stop gracefully, killed.")
        
        # Print results
        print("\n" + "="*70)
        print("TEST RESULTS SUMMARY")
        print("="*70)
        for test_name, result in test_results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {test_name}")
        
    except Exception as e:
        print(f"✗ Server startup failed: {type(e).__name__}")
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_server_test()

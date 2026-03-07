import asyncio
import aiohttp
import time
import statistics
from datetime import datetime

BASE_URL = "https://support-edgeworks.duckdns.org"
CONCURRENT_USERS = 20  # Adjusted for live test to avoid immediate IP blocking
TOTAL_REQUESTS = 100

async def chat_request(session, user_id, request_id):
    start = time.time()
    payload = {
        "message": "My printer is not working, can you help?",
        "user_id": f"stress_test_user_{user_id}",
        "language": "en"
    }
    try:
        async with session.post(f"{BASE_URL}/api/chat", json=payload) as response:
            content = await response.json()
            duration = time.time() - start
            status = response.status
            return {
                "id": request_id,
                "status": status,
                "duration": duration,
                "success": status == 200,
                "confidence": content.get("confidence", 0)
            }
    except Exception as e:
        return {
            "id": request_id,
            "status": "error",
            "duration": time.time() - start,
            "success": False,
            "error": str(e)
        }

async def run_stress_test():
    print(f"🚀 Starting Stress Test: {CONCURRENT_USERS} concurrent users, {TOTAL_REQUESTS} total requests")
    print(f"Target: {BASE_URL}")
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(TOTAL_REQUESTS):
            user_id = i % CONCURRENT_USERS
            tasks.append(chat_request(session, user_id, i))
        
        # Run in batches to simulate concurrency
        results = await asyncio.gather(*tasks)
    
    total_duration = time.time() - start_time
    
    # Analysis
    successes = [r for r in results if r['success']]
    failures = [r for r in results if not r['success']]
    durations = [r['duration'] for r in successes]
    
    print("\n📊 STRESS TEST RESULTS")
    print("=======================")
    print(f"Total Time:       {total_duration:.2f}s")
    print(f"Requests/Sec:     {TOTAL_REQUESTS / total_duration:.2f} RPS")
    print(f"Success Rate:     {len(successes)}/{TOTAL_REQUESTS} ({len(successes)/TOTAL_REQUESTS*100:.1f}%)")
    print(f"Failures:         {len(failures)}")
    
    if durations:
        print(f"Avg Latency:      {statistics.mean(durations):.2f}s")
        print(f"P95 Latency:      {statistics.quantiles(durations, n=20)[18]:.2f}s") # 95th percentile
        print(f"Max Latency:      {max(durations):.2f}s")
    
    if failures:
        print("\n❌ Errors:")
        for f in failures[:5]:
            print(f"  - Status {f.get('status')}: {f.get('error', 'Unknown')}")

if __name__ == "__main__":
    # Wait for server to boot
    print("Waiting 5s for server warmup...")
    time.sleep(5)
    asyncio.run(run_stress_test())
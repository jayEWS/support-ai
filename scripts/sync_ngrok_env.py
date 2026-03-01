import os
import re
import json
import time
import requests
from pathlib import Path

def update_env_file(new_url):
    env_path = Path("d:/Project/support-portal-edgeworks/.env")
    if not env_path.exists():
        print(f"Error: .env not found at {env_path}")
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Update BASE_URL
    content = re.sub(r"\bBASE_URL=.*", f"BASE_URL={new_url}", content)
    
    # Update GOOGLE_REDIRECT_URI
    content = re.sub(r"\bGOOGLE_REDIRECT_URI=.*", f"GOOGLE_REDIRECT_URI={new_url}/api/auth/google/callback", content)

    # Update ALLOWED_ORIGINS
    # Need to find existing ALLOWED_ORIGINS and append/update it
    match = re.search(r'ALLOWED_ORIGINS=\[(.*)\]', content)
    if match:
        origins_str = match.group(1)
        # Clean up and parse existing origins
        origins = [o.strip().strip('"').strip("'") for o in origins_str.split(",") if o.strip()]
        
        # Add new Ngrok URL if not already present
        if new_url not in origins:
            origins.append(new_url)
        
        # Convert back to JSON-like string format
        new_origins_str = ", ".join([f'"{o}"' for o in origins])
        content = re.sub(r'ALLOWED_ORIGINS=\[.*\]', f'ALLOWED_ORIGINS=[{new_origins_str}]', content)

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Successfully updated .env with URL: {new_url}")
    return True

def get_ngrok_url():
    try:
        # Wait for ngrok to initialize (up to 30 seconds)
        for _ in range(30):
            try:
                resp = requests.get("http://localhost:4040/api/tunnels", timeout=2)
                if resp.status_code == 200:
                    tunnels = resp.json().get("tunnels", [])
                    for tunnel in tunnels:
                        if tunnel.get("proto") == "https":
                            return tunnel.get("public_url")
            except:
                pass
            time.sleep(1)
    except Exception as e:
        print(f"Error fetching ngrok URL: {e}")
    return None

if __name__ == "__main__":
    print("🔍 Fetching Ngrok URL...")
    url = get_ngrok_url()
    if url:
        print(f"🚀 Found Ngrok URL: {url}")
        update_env_file(url)
    else:
        print("❌ Could not find active Ngrok tunnel. Make sure Ngrok is running on port 8001.")

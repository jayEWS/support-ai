import requests
from dotenv import load_dotenv
import os

load_dotenv(override=True)

def setup_bird_v2_webhook(target_url: str):
    api_key = os.getenv("BIRD_API_KEY")
    workspace_id = "4932e6f4-906c-49fb-989f-ed4185e84e57"
    
    print(f"🔧 Configuring Bird v2 Webhook...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 1. List existing webhooks to avoid duplicates
    url = f"https://api.bird.com/workspaces/{workspace_id}/webhooks"
    
    try:
        print("➡️ Checking existing webhooks...")
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            webhooks = resp.json().get('results', [])
            for wh in webhooks:
                if target_url in wh.get('url', ''):
                    print(f"✅ Webhook already exists: {wh['id']}")
                    return
        
        # 2. Create new webhook
        print(f"🆕 Creating new webhook for {target_url}...")
        payload = {
            "url": target_url,
            "events": ["message.created"]
        }
        create_resp = requests.post(url, json=payload, headers=headers)
        
        if create_resp.status_code in [200, 201]:
            print(f"🎉 SUCCESS! Webhook created: {create_resp.json().get('id')}")
        else:
            print(f"❌ Failed to create webhook: {create_resp.status_code} - {create_resp.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    target = "https://support-edgeworks.duckdns.org/webhook/whatsapp"
    setup_bird_v2_webhook(target)

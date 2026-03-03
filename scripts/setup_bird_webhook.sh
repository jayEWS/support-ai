#!/bin/bash
# Setup Bird Webhook Subscription for WhatsApp
# This script creates a webhook subscription on Bird to forward incoming messages to our server

BIRD_API_KEY="Wvlws7uy245OKt0OJGF8RvwcJ3l8PpdFP6Sh"
BIRD_WORKSPACE_ID="4932e6f4-906c-49fb-989f-ed4185e84e57"
BIRD_CHANNEL_ID="5b2cf580-2b8e-5d03-876f-79dd611c0fb8"
WEBHOOK_URL="https://support-edgeworks.duckdns.org/webhook/whatsapp"

echo "=== Step 1: Check existing webhook subscriptions ==="
EXISTING=$(curl -s -X GET \
  "https://api.bird.com/workspaces/${BIRD_WORKSPACE_ID}/channels/${BIRD_CHANNEL_ID}/webhook-subscriptions" \
  -H "Authorization: Bearer ${BIRD_API_KEY}" \
  -H "Content-Type: application/json")

echo "$EXISTING" | python3 -m json.tool 2>/dev/null || echo "$EXISTING"

echo ""
echo "=== Step 2: Create webhook subscription ==="
RESULT=$(curl -s -X POST \
  "https://api.bird.com/workspaces/${BIRD_WORKSPACE_ID}/channels/${BIRD_CHANNEL_ID}/webhook-subscriptions" \
  -H "Authorization: Bearer ${BIRD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "'"${WEBHOOK_URL}"'",
    "events": ["message.created", "message.updated"],
    "signingKey": "",
    "status": "enabled"
  }')

echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"

echo ""
echo "=== Step 3: Verify webhook subscriptions ==="
VERIFY=$(curl -s -X GET \
  "https://api.bird.com/workspaces/${BIRD_WORKSPACE_ID}/channels/${BIRD_CHANNEL_ID}/webhook-subscriptions" \
  -H "Authorization: Bearer ${BIRD_API_KEY}" \
  -H "Content-Type: application/json")

echo "$VERIFY" | python3 -m json.tool 2>/dev/null || echo "$VERIFY"

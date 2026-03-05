#!/bin/bash
# Test WhatsApp webhook with a realistic Bird payload
curl -s -X POST https://support-edgeworks.duckdns.org/webhook/whatsapp \
  -H 'Content-Type: application/json' \
  -d '{"message":{"id":"test_msg_123","content":{"text":"halo test dari whatsapp"}},"contact":{"msisdn":"+6281229009543"}}'
echo ""
echo "--- Logs ---"
sudo docker logs support-ai --tail 20 2>&1

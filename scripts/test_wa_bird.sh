#!/bin/bash
# Test WhatsApp webhook with actual Bird Conversations API format (message.created event)
echo "=== Testing WhatsApp webhook with Bird format ==="

curl -s -X POST https://support-edgeworks.duckdns.org/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message.created",
    "contact": {
      "id": "a621095fa44947a28b441cfdf85cb802",
      "href": "https://rest.messagebird.com/1/contacts/a621095fa44947a28b441cfdf85cb802",
      "msisdn": 6281229009543,
      "firstName": "Jay",
      "lastName": "",
      "customDetails": {},
      "createdDatetime": "2026-02-27T09:19:00Z",
      "updatedDatetime": "2026-03-03T15:00:00Z"
    },
    "conversation": {
      "id": "2e15efafec384e1c82e9842075e87beb",
      "contactId": "a621095fa44947a28b441cfdf85cb802",
      "status": "active",
      "createdDatetime": "2026-03-03T15:00:00Z",
      "lastReceivedDatetime": "2026-03-03T15:00:00Z"
    },
    "message": {
      "id": "test_bird_msg_001",
      "conversationId": "2e15efafec384e1c82e9842075e87beb",
      "channelId": "5b2cf580-2b8e-5d03-876f-79dd611c0fb8",
      "platform": "whatsapp",
      "to": "+6281229009543",
      "from": "+6281229009543",
      "direction": "received",
      "status": "received",
      "type": "text",
      "content": {
        "text": "halo, saya perlu bantuan untuk closing v5"
      },
      "createdDatetime": "2026-03-03T15:00:00Z",
      "updatedDatetime": "2026-03-03T15:00:00Z"
    }
  }'

echo ""
echo ""
echo "=== Checking logs ==="
sudo docker logs support-ai --tail 20 2>&1

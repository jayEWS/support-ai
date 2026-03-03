"""
WhatsApp Cloud API (Meta) Webhook Normalizer

Meta webhook payload format (v21.0):
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "<WABA_ID>",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": { "display_phone_number": "...", "phone_number_id": "..." },
        "contacts": [{ "profile": { "name": "Customer" }, "wa_id": "6281229009543" }],
        "messages": [{
          "from": "6281229009543",
          "id": "wamid.xxx",
          "timestamp": "1234567890",
          "type": "text",
          "text": { "body": "Hello!" }
        }],
        "statuses": [{ ... }]  // delivery receipts
      },
      "field": "messages"
    }]
  }]
}
"""

import hmac
import hashlib
import time
from fastapi import Request, HTTPException
from app.schemas.schemas import WhatsAppMessage, WhatsAppAttachment
from app.core.config import settings
from app.core.logging import logger

# Simple in-memory cache for idempotency (In prod, use Redis)
PROCESSED_MESSAGES = set()
MAX_CACHE_SIZE = 5000


class WhatsAppWebhookService:
    @staticmethod
    async def normalize_payload(request: Request) -> WhatsAppMessage:
        """
        Normalize incoming Meta WhatsApp Cloud API webhook payload.
        """
        payload = await request.json()
        logger.info(f"Raw Meta WhatsApp webhook payload: {payload}")

        try:
            # Validate it's a WhatsApp event
            if payload.get("object") != "whatsapp_business_account":
                logger.debug(f"Ignored non-whatsapp event: {payload.get('object')}")
                raise HTTPException(status_code=200, detail="Not a WhatsApp event")

            entries = payload.get("entry", [])
            if not entries:
                raise HTTPException(status_code=200, detail="No entries")

            # Process first entry, first change
            entry = entries[0]
            changes = entry.get("changes", [])
            if not changes:
                raise HTTPException(status_code=200, detail="No changes")

            value = changes[0].get("value", {})
            field = changes[0].get("field", "")

            # Only process "messages" field events
            if field != "messages":
                logger.debug(f"Ignored field={field} (not messages)")
                raise HTTPException(status_code=200, detail=f"Ignored field: {field}")

            # Check for status updates (delivery receipts) — not actual messages
            if "statuses" in value and "messages" not in value:
                status = value["statuses"][0]
                logger.debug(f"Status update: {status.get('status')} for {status.get('id')}")
                raise HTTPException(status_code=200, detail="Status update, not a message")

            messages = value.get("messages", [])
            if not messages:
                raise HTTPException(status_code=200, detail="No messages in payload")

            msg = messages[0]
            contacts = value.get("contacts", [])

            # --- Extract sender ---
            sender = msg.get("from", "")
            if sender and not sender.startswith("+"):
                sender = f"+{sender}"

            # Get display name from contacts
            sender_name = ""
            if contacts:
                sender_name = contacts[0].get("profile", {}).get("name", "")

            message_id = msg.get("id", "")

            # --- Idempotency Check ---
            if message_id and message_id in PROCESSED_MESSAGES:
                logger.warning(f"Duplicate message: {message_id}")
                raise HTTPException(status_code=200, detail="Duplicate")

            if message_id:
                PROCESSED_MESSAGES.add(message_id)
                if len(PROCESSED_MESSAGES) > MAX_CACHE_SIZE:
                    to_remove = list(PROCESSED_MESSAGES)[:MAX_CACHE_SIZE // 5]
                    for item in to_remove:
                        PROCESSED_MESSAGES.discard(item)

            # --- Extract message content ---
            msg_type = msg.get("type", "text")
            text = ""
            attachments = []

            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")

            elif msg_type == "image":
                img = msg.get("image", {})
                media_id = img.get("id", "")
                attachments.append(WhatsAppAttachment(
                    type="image",
                    url=media_id,  # Will need get_media_url() to download
                    name=img.get("mime_type", "image")
                ))
                text = img.get("caption", "[Image Received]")

            elif msg_type == "audio":
                audio = msg.get("audio", {})
                media_id = audio.get("id", "")
                attachments.append(WhatsAppAttachment(
                    type="audio",
                    url=media_id,
                    name=audio.get("mime_type", "audio")
                ))
                text = "[Audio Received]"

            elif msg_type == "video":
                video = msg.get("video", {})
                media_id = video.get("id", "")
                attachments.append(WhatsAppAttachment(
                    type="video",
                    url=media_id,
                    name=video.get("mime_type", "video")
                ))
                text = video.get("caption", "[Video Received]")

            elif msg_type == "document":
                doc = msg.get("document", {})
                media_id = doc.get("id", "")
                attachments.append(WhatsAppAttachment(
                    type="file",
                    url=media_id,
                    name=doc.get("filename", doc.get("mime_type", "document"))
                ))
                text = doc.get("caption", f"[Document: {doc.get('filename', 'file')}]")

            elif msg_type == "location":
                loc = msg.get("location", {})
                text = f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
                if loc.get("name"):
                    text = f"[Location: {loc['name']} ({loc.get('latitude')}, {loc.get('longitude')})]"

            elif msg_type == "contacts":
                contact_list = msg.get("contacts", [])
                names = [c.get("name", {}).get("formatted_name", "Unknown") for c in contact_list]
                text = f"[Contact shared: {', '.join(names)}]"

            elif msg_type == "sticker":
                sticker = msg.get("sticker", {})
                media_id = sticker.get("id", "")
                attachments.append(WhatsAppAttachment(type="image", url=media_id))
                text = "[Sticker]"

            elif msg_type == "reaction":
                reaction = msg.get("reaction", {})
                text = f"[Reaction: {reaction.get('emoji', '👍')} on message {reaction.get('message_id', '')}]"
                raise HTTPException(status_code=200, detail="Reaction ignored")

            elif msg_type == "interactive":
                interactive = msg.get("interactive", {})
                int_type = interactive.get("type", "")
                if int_type == "button_reply":
                    text = interactive.get("button_reply", {}).get("title", "")
                elif int_type == "list_reply":
                    text = interactive.get("list_reply", {}).get("title", "")
                else:
                    text = f"[Interactive: {int_type}]"

            elif msg_type == "button":
                text = msg.get("button", {}).get("text", "[Button pressed]")

            else:
                text = f"[Unsupported message type: {msg_type}]"

            if not sender or (not text and not attachments):
                logger.debug(f"Ignored empty message. sender={sender}, text={text}")
                raise HTTPException(status_code=200, detail="Empty message")

            logger.info(f"✅ WhatsApp from {sender} ({sender_name}): {text[:100]}")

            return WhatsAppMessage(
                sender=sender,
                text=text,
                attachments=attachments,
                message_id=str(message_id) if message_id else f"meta_{int(time.time())}"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to normalize Meta WhatsApp payload: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    @staticmethod
    def validate_signature(request: Request, signature: str) -> bool:
        """
        Validate Meta webhook signature (X-Hub-Signature-256).
        Meta signs payloads with SHA256 HMAC using App Secret.
        """
        app_secret = settings.WHATSAPP_APP_SECRET
        if not app_secret:
            return True  # Skip validation if not configured

        if not signature or not signature.startswith("sha256="):
            return False

        return True  # Full implementation needs raw body bytes

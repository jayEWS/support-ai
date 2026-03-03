from fastapi import Request, HTTPException
from app.schemas.schemas import WhatsAppMessage, WhatsAppAttachment
from app.core.logging import logger
import time

# Simple in-memory cache for idempotency (In prod, use Redis)
PROCESSED_MESSAGES = set()
# Keep cache bounded
MAX_CACHE_SIZE = 5000

class WhatsAppWebhookService:
    @staticmethod
    async def normalize_payload(request: Request) -> WhatsAppMessage:
        """
        Normalize incoming Bird Conversations API webhook payload.
        
        Bird sends `message.created` events with this structure:
        {
          "type": "message.created",
          "contact": {"id": "...", "msisdn": 316123456789, "firstName": "..." },
          "conversation": { ... },
          "message": {
            "id": "...", "conversationId": "...", "channelId": "...",
            "type": "text", "content": {"text": "Hello!"},
            "direction": "received",  // "sent" for outbound
            "status": "received",
            "from": "+6281229009543",
            ...
          }
        }
        """
        payload = await request.json()
        logger.info(f"Raw Bird webhook payload: {payload}")
        
        try:
            if isinstance(payload, list):
                event = payload[0]
            else:
                event = payload

            msg_obj = event.get('message', {})
            contact_obj = event.get('contact', {})
            
            # --- Filter out outbound messages (our own replies echoed back) ---
            direction = msg_obj.get('direction', 'received')
            if direction == 'sent':
                logger.info(f"Ignoring outbound message echo (direction=sent): {msg_obj.get('id')}")
                raise HTTPException(status_code=200, detail="Outbound echo ignored")

            # --- Extract sender ---
            # Bird sends msisdn as integer (e.g., 6281229009543) or string
            msisdn = contact_obj.get('msisdn')
            if msisdn:
                msisdn_str = str(msisdn)
                # Ensure it has + prefix
                if not msisdn_str.startswith('+'):
                    msisdn_str = f"+{msisdn_str}"
            else:
                # Fallback: try message.from field or contact.id
                msisdn_str = msg_obj.get('from') or contact_obj.get('id') or ''
                if msisdn_str and not msisdn_str.startswith('+'):
                    msisdn_str = f"+{msisdn_str}"
            
            message_id = msg_obj.get('id', '')

            # --- Idempotency Check ---
            if message_id and message_id in PROCESSED_MESSAGES:
                logger.warning(f"Duplicate message received: {message_id}")
                raise HTTPException(status_code=200, detail="Duplicate")
            
            if message_id:
                PROCESSED_MESSAGES.add(message_id)
                # Prevent unbounded growth
                if len(PROCESSED_MESSAGES) > MAX_CACHE_SIZE:
                    # Remove oldest ~20% entries
                    to_remove = list(PROCESSED_MESSAGES)[:MAX_CACHE_SIZE // 5]
                    for item in to_remove:
                        PROCESSED_MESSAGES.discard(item)
            
            # --- Extract message content ---
            content = msg_obj.get('content', {})
            msg_type = msg_obj.get('type', 'text')
            text = ""
            attachments = []

            if msg_type == 'text' or 'text' in content:
                text_field = content.get('text', '')
                if isinstance(text_field, dict):
                    text = text_field.get('text', '') or text_field.get('body', '')
                else:
                    text = str(text_field)
            
            if msg_type == 'image' or 'image' in content:
                img = content.get('image', {})
                attachments.append(WhatsAppAttachment(type='image', url=img.get('url', '')))
                text = text or img.get('caption', '[Image Received]')
            elif msg_type == 'audio' or 'audio' in content:
                audio = content.get('audio', {})
                attachments.append(WhatsAppAttachment(type='audio', url=audio.get('url', '')))
                text = text or '[Audio Received]'
            elif msg_type == 'video' or 'video' in content:
                video = content.get('video', {})
                attachments.append(WhatsAppAttachment(type='video', url=video.get('url', '')))
                text = text or video.get('caption', '[Video Received]')
            elif msg_type == 'file' or 'file' in content or 'document' in content:
                file_obj = content.get('file') or content.get('document', {})
                attachments.append(WhatsAppAttachment(type='file', url=file_obj.get('url', ''), name=file_obj.get('name')))
                text = text or file_obj.get('caption', '[File Received]')
            elif msg_type == 'location' or 'location' in content:
                loc = content.get('location', {})
                text = text or f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"

            if not msisdn_str or (not text and not attachments):
                logger.debug(f"Ignored empty/malformed message. sender={msisdn_str}, text={text}")
                raise HTTPException(status_code=200, detail="Empty message ignored")

            logger.info(f"Normalized WhatsApp message from {msisdn_str}: {text[:100]}")
            
            return WhatsAppMessage(
                sender=msisdn_str,
                text=text,
                attachments=attachments,
                message_id=str(message_id) if message_id else f"bird_{int(time.time())}"
            )
        except HTTPException:
            raise  # Re-raise HTTP exceptions as-is
        except Exception as e:
            logger.error(f"Failed to normalize WhatsApp payload: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    @staticmethod
    def validate_signature(request: Request, signature: str):
        # Implementation of signature validation
        return True

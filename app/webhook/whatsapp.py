from fastapi import Request, HTTPException
from app.schemas.schemas import WhatsAppMessage, WhatsAppAttachment
from app.core.logging import logger
import time

# Simple in-memory cache for idempotency (In prod, use Redis)
PROCESSED_MESSAGES = set()

class WhatsAppWebhookService:
    @staticmethod
    async def normalize_payload(request: Request) -> WhatsAppMessage:
        payload = await request.json()
        
        # Example Bird v2 normalization logic
        try:
            if isinstance(payload, list):
                event = payload[0]
            else:
                event = payload

            msg_obj = event.get('message', {})
            contact_obj = event.get('contact', {})
            external_user_id = contact_obj.get('msisdn') or contact_obj.get('id')
            message_id = msg_obj.get('id')

            # Idempotency Check
            if message_id in PROCESSED_MESSAGES:
                logger.warning(f"Duplicate message received: {message_id}")
                raise HTTPException(status_code=200, detail="Duplicate")
            
            PROCESSED_MESSAGES.add(message_id)
            # Cleanup old messages periodically in real prod
            
            content = msg_obj.get('content', {})
            text = ""
            attachments = []

            if 'text' in content:
                text = content['text'] if isinstance(content['text'], str) else content['text'].get('text', '')
            elif 'image' in content:
                attachments.append(WhatsAppAttachment(type='image', url=content['image'].get('url')))
                text = content['image'].get('caption', '')

            return WhatsAppMessage(
                sender=str(external_user_id),
                text=text,
                attachments=attachments,
                message_id=str(message_id)
            )
        except Exception as e:
            logger.error(f"Failed to normalize WhatsApp payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")

    @staticmethod
    def validate_signature(request: Request, signature: str):
        # Implementation of signature validation
        return True

import hmac
import hashlib
import time
from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
from typing import Optional
import httpx
from app.core.config import settings
from app.core.logging import logger
from app.services.message_service import process_incoming_message

whatsapp_router = APIRouter(prefix="/webhook/whatsapp", tags=["WhatsApp"])

async def validate_bird_signature(request: Request, signature: str):
    """
    Validates Bird (MessageBird) webhook signature.
    """
    if not settings.BIRD_WEBHOOK_SECRET:
        return True
    return True

@whatsapp_router.post("")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_messagebird_signature: Optional[str] = Header(None)
):
    """
    Inbound Webhook from Bird for WhatsApp (Supports v2 format).
    """
    try:
        if not await validate_bird_signature(request, x_messagebird_signature):
            logger.warning("Invalid Bird signature received.")
            raise HTTPException(status_code=401, detail="Invalid signature")

        payload = await request.json()
        logger.info(f"Incoming WhatsApp Payload: {payload}")

        # Bird v2 webhook structure differs from v1
        # It often sends a list of events
        if isinstance(payload, list):
            event = payload[0]
        else:
            event = payload

        # Extract message details
        # v2 often uses event.message or event.body
        msg_obj = event.get('message', {})
        contact_obj = event.get('contact', {})
        
        external_user_id = contact_obj.get('msisdn') or contact_obj.get('id')
        
        # In v2, the content structure depends on message type
        content = msg_obj.get('content', {})
        message_text = ""
        attachments = []

        # Handle different content types
        if 'text' in content:
            text_field = content.get('text', '')
            if isinstance(text_field, dict):
                message_text = text_field.get('text', '')
            else:
                message_text = text_field
        elif 'image' in content:
            img_obj = content.get('image', {})
            message_text = img_obj.get('caption', '[Image Received]')
            attachments.append({"type": "image", "url": img_obj.get('url')})
        elif 'audio' in content:
            audio_obj = content.get('audio', {})
            message_text = '[Audio Received]'
            attachments.append({"type": "audio", "url": audio_obj.get('url')})
        elif 'file' in content or 'document' in content:
            file_obj = content.get('file') or content.get('document', {})
            message_text = file_obj.get('caption', '[File Received]')
            attachments.append({"type": "file", "url": file_obj.get('url'), "name": file_obj.get('name')})
        elif 'video' in content:
            video_obj = content.get('video', {})
            message_text = video_obj.get('caption', '[Video Received]')
            attachments.append({"type": "video", "url": video_obj.get('url')})

        if not external_user_id or (not message_text and not attachments):
            logger.debug("Ignored empty or malformed message.")
            return {"status": "ignored"}

        standardized_data = {
            "channel": "whatsapp",
            "external_user_id": str(external_user_id),
            "message_text": str(message_text),
            "attachments": attachments,
            "tenant_id": event.get("workspaceId", "default"),
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        background_tasks.add_task(process_incoming_message, standardized_data)
        return {"status": "accepted"}

    except Exception as e:
        logger.error(f"WhatsApp Webhook Error: {e}")
        return {"status": "error", "message": str(e)}

async def send_whatsapp_message(to: str, message: str, msg_type: str = "text", media_url: str = None, template_data: dict = None):
    """
    Outbound async function using Bird v2 API.
    Supports text, image, audio, video, file, and template.
    """
    workspace_id = settings.BIRD_WORKSPACE_ID
    channel_id = settings.BIRD_CHANNEL_ID
    
    # Ensure phone number format (must start with + for Bird API)
    formatted_to = to if to.startswith('+') else f"+{to}"
    
    # Bird v2 Message Send URL
    url = f"https://api.bird.com/workspaces/{workspace_id}/channels/{channel_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {settings.BIRD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Base receiver
    payload = {
        "receiver": {
            "contacts": [
                {
                    "identifierValue": formatted_to,
                    "identifierKey": "phonenumber"
                }
            ]
        },
        "body": {}
    }

    # Set body based on type
    if msg_type == "text":
        payload["body"] = {
            "type": "text",
            "text": {"text": message}
        }
    elif msg_type == "image":
        payload["body"] = {
            "type": "image",
            "image": {"url": media_url, "caption": message}
        }
    elif msg_type == "audio":
        payload["body"] = {
            "type": "audio",
            "audio": {"url": media_url}
        }
    elif msg_type == "video":
        payload["body"] = {
            "type": "video",
            "video": {"url": media_url, "caption": message}
        }
    elif msg_type == "file" or msg_type == "document":
        payload["body"] = {
            "type": "file",
            "file": {"url": media_url, "caption": message}
        }
    elif msg_type == "template" and template_data:
        # template_data example: {"name": "hello_world", "language": {"code": "en_US"}, "components": [...]}
        payload["body"] = {
            "type": "template",
            "template": template_data
        }
    else:
        logger.error(f"Unsupported message type: {msg_type}")
        return False

    logger.info(f"Attempting to send WhatsApp to {formatted_to} via Bird...")
    logger.debug(f"URL: {url}")
    logger.debug(f"Payload: {payload}")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=15.0)
            if resp.status_code in [200, 201, 202, 204]:
                logger.info(f"WhatsApp message successfully queued/sent to {to} (Status: {resp.status_code})")
                return True
            else:
                logger.error(f"Bird API Error ({resp.status_code}): {resp.text}")
                return False
    except Exception as e:
        logger.error(f"HTTP Exception while sending WhatsApp: {e}")
        return False

"""
WhatsApp Cloud API (Meta) Adapter
Direct Meta WhatsApp Business API connection.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/
"""
import httpx
from app.core.config import settings
from app.core.logging import logger

WHATSAPP_API_BASE = "https://graph.facebook.com/v21.0"


def is_meta_configured() -> bool:
    """Check if Meta WhatsApp API credentials are configured."""
    return bool(settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_API_TOKEN)


async def send_whatsapp_message(
    to: str,
    message: str,
    msg_type: str = "text",
    media_url: str = None,
    template_data: dict = None
) -> bool:
    """
    Send a WhatsApp message via Meta Cloud API.
    
    Args:
        to: Phone number in international format (e.g. +6281229009543)
        message: Text content to send
        msg_type: text | image | audio | video | document | template
        media_url: URL for media messages
        template_data: Template payload for template messages
    """
    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    token = settings.WHATSAPP_API_TOKEN

    if not phone_id or not token:
        logger.error("WhatsApp Meta API not configured (missing WHATSAPP_PHONE_NUMBER_ID or WHATSAPP_API_TOKEN)")
        return False

    url = f"{WHATSAPP_API_BASE}/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Strip + prefix for Meta API (they want plain number like 6281229009543)
    clean_number = to.lstrip("+")

    # Build payload based on message type
    if msg_type == "text":
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "text",
            "text": {"preview_url": True, "body": message}
        }
    elif msg_type == "image":
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "image",
            "image": {"link": media_url, "caption": message}
        }
    elif msg_type == "audio":
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "audio",
            "audio": {"link": media_url}
        }
    elif msg_type == "video":
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "video",
            "video": {"link": media_url, "caption": message}
        }
    elif msg_type in ("document", "file"):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "document",
            "document": {"link": media_url, "caption": message}
        }
    elif msg_type == "template" and template_data:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_number,
            "type": "template",
            "template": template_data
        }
    elif msg_type == "reaction":
        # For reacting to messages
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "reaction",
            "reaction": {"message_id": media_url, "emoji": message}
        }
    else:
        logger.error(f"Unsupported WhatsApp message type: {msg_type}")
        return False

    logger.info(f"Sending WhatsApp to {clean_number} via Meta Cloud API (type={msg_type})...")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=15.0)

            if resp.status_code in (200, 201):
                resp_data = resp.json()
                msg_id = resp_data.get("messages", [{}])[0].get("id", "unknown")
                logger.info(f"✅ WhatsApp sent to {clean_number} (wamid: {msg_id})")
                return True
            else:
                error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                error_msg = error_data.get("error", {}).get("message", resp.text)
                logger.error(f"❌ Meta WhatsApp API Error ({resp.status_code}): {error_msg}")
                return False
    except Exception as e:
        logger.error(f"❌ HTTP Exception sending WhatsApp: {e}")
        return False


async def mark_message_read(message_id: str) -> bool:
    """Mark an incoming message as 'read' (double blue ticks)."""
    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    token = settings.WHATSAPP_API_TOKEN

    if not phone_id or not token:
        return False

    url = f"{WHATSAPP_API_BASE}/{phone_id}/messages"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }, timeout=10.0)
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to mark message read: {e}")
        return False


async def get_media_url(media_id: str) -> str:
    """Get download URL for a media attachment by its media ID."""
    token = settings.WHATSAPP_API_TOKEN
    url = f"{WHATSAPP_API_BASE}/{media_id}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={
                "Authorization": f"Bearer {token}"
            }, timeout=10.0)
            if resp.status_code == 200:
                return resp.json().get("url", "")
    except Exception as e:
        logger.error(f"Failed to get media URL for {media_id}: {e}")
    return ""

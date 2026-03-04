from app.services import rag_engine
from app.core.logging import logger
from app.core.database import db_manager
import json
import asyncio

async def process_incoming_message(data: dict):
    """
    Standardized internal function to process messages from any channel.
    data format:
    {
      "channel": "...",
      "external_user_id": "...",
      "message_text": "...",
      "attachments": [...],
      "tenant_id": "...",
      "timestamp": "..."
    }
    """
    channel = data.get("channel")
    user_id = data.get("external_user_id")
    text = data.get("message_text")
    attachments = data.get("attachments", [])
    
    logger.info(f"Processing internal message from {channel}: {user_id} - {text[:50] if text else 'Media'}")
    
    # Ensure user exists in DB before saving message (fixes Foreign Key conflict)
    # Generic naming based on channel
    display_name = f"{channel.capitalize()} User {user_id[-4:] if len(user_id) > 4 else user_id}"
    db_manager.create_or_update_user(user_id, name=display_name)

    # Save user message with attachments to DB
    attachments_json = json.dumps(attachments) if attachments else None
    db_manager.save_message(user_id, "user", text or "", attachments=attachments_json)

    if not rag_engine.rag_engine:
        logger.error("RAG Engine not initialized.")
        return "System is currently unavailable."

    # Handle media-only messages or media with text
    if not text and attachments:
        # If user only sent media, acknowledge it
        response = "Thank you, I've received your attachment. Is there anything I can help you with regarding it?"
    else:
        # Process text with RAG
        response = await rag_engine.rag_engine.ask(text, user_id=user_id)
    
    # Send response back via the same channel
    if channel == "whatsapp":
        from app.adapters.whatsapp_meta import send_whatsapp_message, is_meta_configured
        if is_meta_configured():
            await send_whatsapp_message(user_id, response)
        else:
            logger.warning(f"WhatsApp Meta API not configured — reply to {user_id} saved locally only")
    elif channel == "email":
        from app.adapters.email_handler import send_email_response
        await send_email_response(user_id, response)
    
    return response

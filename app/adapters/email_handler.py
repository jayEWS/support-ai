import time
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from app.core.config import settings
from app.core.logging import logger
import httpx

email_router = APIRouter(prefix="/webhook/email", tags=["Email"])


async def _process_email_message(sender: str, subject: str, body: str, full_text: str):
    """Process an email message through the AI pipeline and send response."""
    try:
        from app.core.database import db_manager
        from app.services.rag_service import RAGService
        
        # Save the inbound email as a message
        email_user_id = f"email_{sender.replace('@', '_at_').replace('.', '_')}"
        db_manager.save_message(email_user_id, "user", full_text)
        
        # Query RAG for AI response
        rag_service = RAGService()
        rag_res = await rag_service.query(full_text, language="en")
        ai_response = rag_res.answer
        
        # Save the AI response
        db_manager.save_message(email_user_id, "bot", ai_response)
        
        # Send email reply
        await send_email_response(sender, ai_response, subject=f"Re: {subject}")
        
        logger.info(f"Email processed for {sender}: subject='{subject}', response_len={len(ai_response)}")
    except Exception as e:
        logger.error(f"Error processing email from {sender}: {e}", exc_info=True)


@email_router.post("")
async def email_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Generic Email Webhook (Supports standard formats from Mailgun/SendGrid/etc.)
    """
    try:
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            payload = await request.json()
        else:
            # Handle form-data (common in Mailgun)
            form_data = await request.form()
            payload = dict(form_data)

        logger.info(f"Incoming Email Webhook: {payload}")

        # Normalize data (Mapping common fields)
        # Mailgun: 'sender', 'subject', 'body-plain'
        # SendGrid: 'from', 'subject', 'text'
        sender = payload.get('sender') or payload.get('from')
        subject = payload.get('subject', '(No Subject)')
        body = payload.get('body-plain') or payload.get('text') or payload.get('body', '')

        if not sender or not body:
            logger.warning("Email webhook received with missing sender or body.")
            return {"status": "ignored"}

        # Combine subject and body for RAG context
        full_text = f"Subject: {subject}\n\n{body}"

        # Process through AI pipeline in background
        background_tasks.add_task(_process_email_message, sender, subject, body, full_text)
        return {"status": "accepted"}

    except Exception as e:
        logger.error(f"Email Webhook Error: {e}")
        return {"status": "error", "message": str(e)}

async def send_email_response(to_email: str, message: str, subject: str = "Re: Support Inquiry"):
    """
    Outbound email sending.
    Supports Mailgun API by default, or logs if no API key.
    """
    if not settings.MAILGUN_API_KEY or settings.MAILGUN_API_KEY == "your_mailgun_key":
        logger.info(f" [MOCK EMAIL SEND] To: {to_email} | Message: {message[:100]}...")
        return True

    # Example Mailgun implementation
    domain = settings.MAILGUN_DOMAIN
    url = f"https://api.mailgun.net/v3/{domain}/messages"
    
    auth = ("api", settings.MAILGUN_API_KEY)
    data = {
        "from": f"Support AI <support@{domain}>",
        "to": [to_email],
        "subject": subject,
        "text": message
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, auth=auth, data=data, timeout=10.0)
            if resp.status_code == 200:
                logger.info(f"Email response sent to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

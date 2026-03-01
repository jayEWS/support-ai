import time
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from app.core.config import settings
from app.core.logging import logger
from app.services.message_service import process_incoming_message
import httpx

email_router = APIRouter(prefix="/webhook/email", tags=["Email"])

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

        standardized_data = {
            "channel": "email",
            "external_user_id": str(sender),
            "message_text": full_text,
            "attachments": [], # TODO: Add attachment support for email
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

        background_tasks.add_task(process_incoming_message, standardized_data)
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

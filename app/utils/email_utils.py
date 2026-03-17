"""Email utilities for sending transactional emails - Multiple Provider Support"""

import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from app.core.logging import logger
from typing import Optional

# ============ EMAIL PROVIDER: GMAIL SMTP ============
async def send_via_gmail(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send email via Gmail SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = settings.EMAIL_FROM_ADDRESS or 'noreply@support.local'
        msg['To'] = to_email
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Use SMTP with Gmail
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.GMAIL_EMAIL, settings.GMAIL_PASSWORD)
            server.sendmail(msg['From'], to_email, msg.as_string())
        
        logger.info(f"Email sent via Gmail to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Gmail email failed: {str(e)}")
        return False

# ============ EMAIL PROVIDER: SENDGRID ============
async def send_via_sendgrid(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send email via SendGrid API"""
    try:
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email}],
                    "subject": subject
                }
            ],
            "from": {"email": settings.EMAIL_FROM_ADDRESS or "noreply@support.local"},
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body}
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent via SendGrid to {to_email}")
                return True
            else:
                logger.error(f"SendGrid error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"SendGrid email failed: {str(e)}")
        return False

# ============ EMAIL PROVIDER: MAILGUN ============
async def send_via_mailgun(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    """Send email via Mailgun API"""
    try:
        domain = settings.MAILGUN_DOMAIN
        if not domain:
            logger.error("MAILGUN_DOMAIN not configured")
            return False
        
        url = f"https://api.mailgun.net/v3/{domain}/messages"
        auth = ("api", settings.MAILGUN_API_KEY)
        
        data = {
            "from": settings.EMAIL_FROM_ADDRESS or f"noreply@{domain}",
            "to": to_email,
            "subject": subject,
            "text": text_body,
            "html": html_body
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, auth=auth)
            if response.status_code == 200:
                logger.info(f"Email sent via Mailgun to {to_email}")
                return True
            else:
                logger.error(f"Mailgun error: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        logger.error(f"Mailgun email failed: {str(e)}")
        return False

# ============ MOCK EMAIL FOR DEVELOPMENT ============
def send_mock_email(to_email: str, subject: str) -> bool:
    """Send email in mock mode (logging only)"""
    logger.info(f"[MOCK EMAIL] Email sent to {to_email}")
    logger.info(f"[MOCK EMAIL] Subject: {subject}")
    return True

# ============ MAIN EMAIL FUNCTION ============
async def send_magic_link_email(to_email: str, magic_link: str, app_name: str = "Support Portal") -> bool:
    """
    Send a magic link authentication email using configured provider.
    
    Supports: Gmail SMTP, SendGrid, Mailgun, or Mock mode
    
    Args:
        to_email: Recipient email address
        magic_link: Full URL to the magic link
        app_name: Application name for email content
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    
    # Email content
    subject = f"{app_name} - Sign in with Magic Link"
    
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1e40af;">Sign in to {app_name}</h2>
                
                <p>You requested a magic link to sign in. Click the button below to authenticate:</p>
                
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{magic_link}" 
                       style="background-color: #1e40af; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Sign in with Magic Link
                    </a>
                </div>
                
                <p><strong>Or copy and paste this link:</strong></p>
                <p style="word-break: break-all; background-color: #f5f5f5; padding: 10px; border-radius: 3px;">
                    {magic_link}
                </p>
                
                <p style="color: #666; font-size: 12px;">
                    Time to expiry: 15 minutes for security.
                    Never share this link with anyone.
                </p>
            </div>
        </body>
    </html>
    """
    
    text_body = f"""
Sign in to {app_name}

You requested a magic link to sign in. Visit the link below to authenticate:

{magic_link}

This link expires in 15 minutes for security.
Never share this link with anyone.
    """
    
    # Try to send via configured provider
    email_provider = settings.EMAIL_PROVIDER.lower() if settings.EMAIL_PROVIDER else "mock"
    
    if email_provider == "gmail":
        if not settings.GMAIL_EMAIL or not settings.GMAIL_PASSWORD:
            logger.warning("Gmail not configured, falling back to mock mode")
            return send_mock_email(to_email, subject)
        return await send_via_gmail(to_email, subject, html_body, text_body)
    
    elif email_provider == "sendgrid":
        if not settings.SENDGRID_API_KEY:
            logger.warning("SendGrid not configured, falling back to mock mode")
            return send_mock_email(to_email, subject)
        return await send_via_sendgrid(to_email, subject, html_body, text_body)
    
    elif email_provider == "mailgun":
        if not settings.MAILGUN_API_KEY or not settings.MAILGUN_DOMAIN:
            logger.warning("Mailgun not configured, falling back to mock mode")
            return send_mock_email(to_email, subject)
        return await send_via_mailgun(to_email, subject, html_body, text_body)
    
    else:
        # Default to mock mode
        return send_mock_email(to_email, subject)


async def send_welcome_email(to_email: str, user_name: str = None) -> bool:
    """Send welcome email to new user"""
    try:
        subject = "Welcome to Support Portal!"
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Welcome to Support Portal!</h2>
                <p>Hello {user_name or 'there'},</p>
                <p>Thank you for signing up. You can now access the support portal.</p>
            </body>
        </html>
        """
        text_body = f"Welcome to Support Portal!\n\nHello {user_name or 'there'},\n\nThank you for signing up."
        
        # Try configured provider
        email_provider = settings.EMAIL_PROVIDER.lower() if settings.EMAIL_PROVIDER else "mock"
        if email_provider == "gmail":
            return await send_via_gmail(to_email, subject, html_body, text_body)
        elif email_provider == "sendgrid":
            return await send_via_sendgrid(to_email, subject, html_body, text_body)
        elif email_provider == "mailgun":
            return await send_via_mailgun(to_email, subject, html_body, text_body)
        return send_mock_email(to_email, subject)
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        return False


async def send_chat_transcript(to_email: str, customer_name: str, transcript: str, 
                                ticket_id: int = None, app_name: str = "Edgeworks Support") -> bool:
    """
    Send chat transcript to customer's email after chat session ends.
    
    Args:
        to_email: Customer's email address
        customer_name: Customer's display name
        transcript: Full chat transcript text
        ticket_id: Optional ticket ID if one was created
        app_name: Application name for branding
    
    Returns:
        bool: True if sent successfully
    """
    try:
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        ticket_section = ""
        if ticket_id:
            ticket_section = f"""
                <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 12px; margin: 16px 0;">
                    <p style="margin: 0; font-weight: bold; color: #92400e;">📝 Ticket #{ticket_id} Created</p>
                    <p style="margin: 4px 0 0 0; color: #78350f; font-size: 13px;">Our team will follow up with you shortly.</p>
                </div>
            """
        
        # Convert transcript to HTML-safe format
        import html
        transcript_html = html.escape(transcript).replace('\n', '<br>')
        
        subject = f"{app_name} - Chat Transcript"
        if ticket_id:
            subject += f" (Ticket #{ticket_id})"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f9fafb;">
                <div style="max-width: 640px; margin: 0 auto; padding: 20px;">
                    <div style="background-color: #1e40af; color: white; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
                        <h2 style="margin: 0; font-size: 20px;">💬 Chat Transcript</h2>
                        <p style="margin: 8px 0 0 0; opacity: 0.8; font-size: 13px;">{app_name} &bull; {timestamp}</p>
                    </div>
                    
                    <div style="background-color: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none;">
                        <p style="margin: 0 0 16px 0;">Hello {customer_name or 'there'},</p>
                        <p style="margin: 0 0 16px 0;">Thank you for contacting us. Below is a transcript of your chat session for your records.</p>
                        
                        {ticket_section}
                        
                        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 16px 0; font-size: 13px; max-height: 500px; overflow-y: auto;">
                            <p style="font-weight: bold; color: #475569; margin: 0 0 12px 0; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">Conversation:</p>
                            {transcript_html}
                        </div>
                        
                        <p style="color: #6b7280; font-size: 12px; margin: 16px 0 0 0; border-top: 1px solid #e5e7eb; padding-top: 16px;">
                            This is an automated message from {app_name}. Please do not reply to this email.<br>
                            If you need further assistance, please visit our support portal.
                        </p>
                    </div>
                    
                    <div style="text-align: center; padding: 16px; color: #9ca3af; font-size: 11px;">
                        ⚡ Powered by {app_name}
                    </div>
                </div>
            </body>
        </html>
        """
        
        text_body = f"""Chat Transcript - {app_name}
Date: {timestamp}

Hello {customer_name or 'there'},

Thank you for contacting us. Below is your chat transcript:

{'Ticket #' + str(ticket_id) + ' has been created.' if ticket_id else ''}

--- TRANSCRIPT ---
{transcript}
--- END ---

This is an automated message. Please do not reply.
"""
        
        # Try to send via configured provider
        email_provider = settings.EMAIL_PROVIDER.lower() if settings.EMAIL_PROVIDER else "mock"
        
        if email_provider == "gmail":
            if not settings.GMAIL_EMAIL or not settings.GMAIL_PASSWORD:
                logger.warning("Gmail not configured for transcript, falling back to mock mode")
                return send_mock_email(to_email, subject)
            return await send_via_gmail(to_email, subject, html_body, text_body)
        
        elif email_provider == "sendgrid":
            if not getattr(settings, 'SENDGRID_API_KEY', ''):
                return send_mock_email(to_email, subject)
            return await send_via_sendgrid(to_email, subject, html_body, text_body)
        
        elif email_provider == "mailgun":
            if not settings.MAILGUN_API_KEY or not settings.MAILGUN_DOMAIN:
                return send_mock_email(to_email, subject)
            return await send_via_mailgun(to_email, subject, html_body, text_body)
        
        else:
            return send_mock_email(to_email, subject)
            
    except Exception as e:
        logger.error(f"Failed to send chat transcript to {to_email}: {e}")
        return False
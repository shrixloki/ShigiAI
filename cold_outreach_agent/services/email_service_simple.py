"""Simple email service using SMTP only (no Google dependencies)."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from ..config.settings import settings


class EmailService:
    """Handles email sending via SMTP."""
    
    def __init__(self):
        pass
    
    def send_email(self, to_email: str, subject: str, body: str) -> tuple[bool, str]:
        """
        Send a plain-text email via SMTP.
        Returns (success: bool, message: str)
        """
        try:
            message = MIMEText(body, "plain")
            message["to"] = to_email
            message["from"] = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
            message["subject"] = subject
            
            context = ssl.create_default_context()
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SENDER_EMAIL, to_email, message.as_string())
            
            return True, "sent"
        except Exception as e:
            return False, str(e)
    
    def check_for_reply(self, from_email: str) -> Optional[dict]:
        """SMTP doesn't support inbox reading."""
        return None
    
    def get_recent_replies(self, hours: int = 24) -> list[str]:
        """SMTP doesn't support inbox reading."""
        return []

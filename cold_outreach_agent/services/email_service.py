"""Email service supporting Gmail API and SMTP."""

import base64
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import settings


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly"
]


class EmailService:
    """Handles email sending and inbox checking."""
    
    def __init__(self):
        self._gmail_service = None
    
    def _get_gmail_service(self):
        """Get authenticated Gmail API service."""
        if self._gmail_service:
            return self._gmail_service
        
        creds = None
        token_path = Path(settings.GMAIL_TOKEN_PATH)
        
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GOOGLE_CREDENTIALS_PATH, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        
        self._gmail_service = build("gmail", "v1", credentials=creds)
        return self._gmail_service
    
    def send_email(self, to_email: str, subject: str, body: str) -> tuple[bool, str]:
        """
        Send a plain-text email.
        Returns (success: bool, message: str)
        """
        if settings.EMAIL_METHOD == "gmail_api":
            return self._send_via_gmail_api(to_email, subject, body)
        else:
            return self._send_via_smtp(to_email, subject, body)
    
    def _send_via_gmail_api(self, to_email: str, subject: str, body: str) -> tuple[bool, str]:
        """Send email using Gmail API."""
        try:
            service = self._get_gmail_service()
            
            message = MIMEText(body, "plain")
            message["to"] = to_email
            message["from"] = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
            message["subject"] = subject
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            service.users().messages().send(
                userId="me",
                body={"raw": raw}
            ).execute()
            
            return True, "sent"
        except Exception as e:
            return False, str(e)
    
    def _send_via_smtp(self, to_email: str, subject: str, body: str) -> tuple[bool, str]:
        """Send email using SMTP."""
        try:
            message = MIMEText(body, "plain")
            message["to"] = to_email
            message["from"] = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
            message["subject"] = subject
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SENDER_EMAIL, to_email, message.as_string())
            
            return True, "sent"
        except Exception as e:
            return False, str(e)
    
    def check_for_reply(self, from_email: str) -> Optional[dict]:
        """
        Check if we received a reply from a specific email address.
        Returns the reply message dict if found, None otherwise.
        """
        if settings.EMAIL_METHOD != "gmail_api":
            # SMTP doesn't support inbox reading
            return None
        
        try:
            service = self._get_gmail_service()
            
            # Search for emails from this address
            query = f"from:{from_email} is:inbox"
            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=5
            ).execute()
            
            messages = results.get("messages", [])
            
            if messages:
                # Get the most recent message
                msg = service.users().messages().get(
                    userId="me",
                    id=messages[0]["id"],
                    format="metadata"
                ).execute()
                
                return {
                    "id": msg["id"],
                    "snippet": msg.get("snippet", ""),
                    "from": from_email
                }
            
            return None
        except Exception:
            return None
    
    def get_recent_replies(self, hours: int = 24) -> list[str]:
        """
        Get list of email addresses that replied in the last N hours.
        Returns list of email addresses.
        """
        if settings.EMAIL_METHOD != "gmail_api":
            return []
        
        try:
            service = self._get_gmail_service()
            
            # Search for recent inbox messages
            query = f"is:inbox newer_than:{hours}h"
            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=50
            ).execute()
            
            messages = results.get("messages", [])
            reply_emails = []
            
            for msg_ref in messages:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_ref["id"],
                    format="metadata",
                    metadataHeaders=["From"]
                ).execute()
                
                headers = msg.get("payload", {}).get("headers", [])
                for header in headers:
                    if header["name"] == "From":
                        # Extract email from "Name <email>" format
                        from_value = header["value"]
                        if "<" in from_value:
                            email = from_value.split("<")[1].rstrip(">")
                        else:
                            email = from_value
                        reply_emails.append(email.lower())
                        break
            
            return list(set(reply_emails))
        except Exception:
            return []

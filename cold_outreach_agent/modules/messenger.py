"""
Messenger Module - Sends initial emails to APPROVED leads only.

CRITICAL SAFETY RULES:
1. Only sends to leads with review_status='approved'
2. Only sends to leads with outreach_status='not_sent'
3. Respects daily rate limits
4. Max 1 initial email per lead
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..config.settings import settings
from .logger import action_logger
from ..services.db_service import DatabaseService
from ..services.email_service_simple import EmailService


class MessengerModule:
    """
    Sends initial outreach emails to APPROVED leads only.
    NO EMAILS ARE SENT WITHOUT HUMAN APPROVAL.
    """
    
    def __init__(self):
        self.db = DatabaseService()
        self.email_service = EmailService()
        self.templates_dir = settings.TEMPLATES_DIR / "initial"
    
    def send_all_pending(self) -> dict:
        """
        Send initial emails to all APPROVED leads with outreach_status='not_sent'.
        Respects daily rate limit.
        
        Returns:
            {sent: int, skipped: int, errors: int, rate_limited: bool}
        """
        # Check rate limit
        sent_today = self.db.get_emails_sent_today_sync()
        remaining = settings.MAX_EMAILS_PER_DAY - sent_today
        
        if remaining <= 0:
            action_logger.warning(f"Daily rate limit reached ({settings.MAX_EMAILS_PER_DAY})")
            return {"sent": 0, "skipped": 0, "errors": 0, "rate_limited": True}
        
        # CRITICAL: Only get APPROVED leads
        leads = self.db.get_approved_leads_for_outreach_sync()
        
        if not leads:
            action_logger.info("No approved leads ready for outreach")
            return {"sent": 0, "skipped": 0, "errors": 0, "rate_limited": False}
        
        sent = 0
        skipped = 0
        errors = 0
        
        action_logger.info(f"Processing {len(leads)} approved leads for initial outreach")
        
        for lead in leads:
            if sent >= remaining:
                action_logger.info(f"Rate limit reached, {len(leads) - sent - skipped - errors} leads remaining")
                break
            
            result = self.send_initial_email(lead)
            
            if result == "sent":
                sent += 1
            elif result == "skipped":
                skipped += 1
            else:
                errors += 1
        
        action_logger.log_action(
            lead_id=None,
            module_name="messenger",
            action="send_batch",
            result="success",
            details={"sent": sent, "skipped": skipped, "errors": errors}
        )
        
        return {"sent": sent, "skipped": skipped, "errors": errors, "rate_limited": False}
    
    def send_initial_email(self, lead: dict) -> str:
        """
        Send initial email to a single lead.
        
        SAFETY CHECKS:
        1. Lead must have review_status='approved'
        2. Lead must have outreach_status='not_sent'
        3. Lead must have valid email
        
        Returns: "sent", "skipped", or "error"
        """
        lead_id = lead.get("lead_id")
        email = lead.get("email")
        review_status = lead.get("review_status")
        outreach_status = lead.get("outreach_status")
        
        # CRITICAL SAFETY CHECK: Must be approved
        if review_status != "approved":
            action_logger.log_action(
                lead_id=lead_id,
                module_name="messenger",
                action="send_initial",
                result="blocked",
                details={"reason": f"Lead not approved (status: {review_status})"}
            )
            return "skipped"
        
        # Safety check: Must not have been sent
        if outreach_status != "not_sent":
            action_logger.log_action(
                lead_id=lead_id,
                module_name="messenger",
                action="send_initial",
                result="skipped",
                details={"reason": f"Already processed (status: {outreach_status})"}
            )
            return "skipped"
        
        # Safety check: Must have email
        if not email:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="messenger",
                action="send_initial",
                result="skipped",
                details={"reason": "No email address"}
            )
            return "skipped"
        
        # Get tag for personalization
        tag = lead.get("tag") or "unknown"
        
        # Load and personalize template
        subject, body = self._build_email(lead, tag)
        
        if not subject or not body:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="messenger",
                action="send_initial",
                result="error",
                details={"reason": "Template load failed"}
            )
            return "error"
        
        # Send email
        success, message = self.email_service.send_email(email, subject, body)
        
        if success:
            # Update lead status
            self.db.update_lead_sync(lead_id, {
                "outreach_status": "sent_initial",
                "last_contacted": datetime.now().isoformat()
            })
            
            action_logger.log_action(
                lead_id=lead_id,
                module_name="messenger",
                action="send_initial",
                result="success",
                details={"to": email, "tag": tag}
            )
            return "sent"
        else:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="messenger",
                action="send_initial",
                result="error",
                details={"error": message}
            )
            return "error"
    
    def _build_email(self, lead: dict, tag: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Build personalized email from template.
        Returns (subject, body) or (None, None) on failure.
        """
        template_file = self.templates_dir / "default.txt"
        
        if not template_file.exists():
            return None, None
        
        try:
            content = template_file.read_text(encoding="utf-8")
        except Exception:
            return None, None
        
        # Split subject and body (first line is subject)
        lines = content.strip().split("\n", 1)
        if len(lines) < 2:
            return None, None
        
        subject_template = lines[0].replace("Subject: ", "").strip()
        body_template = lines[1].strip()
        
        # Get observation line based on tag
        observation = self._get_observation_for_tag(tag)
        
        # Personalize
        business_name = lead.get("business_name", "your business")
        
        subject = subject_template.replace("{{business_name}}", business_name)
        body = body_template.replace("{{business_name}}", business_name)
        body = body.replace("{{observation}}", observation)
        body = body.replace("{{sender_name}}", settings.SENDER_NAME)
        
        return subject, body
    
    def _get_observation_for_tag(self, tag: str) -> str:
        """Get a factual observation line for email personalization."""
        observations = {
            "no_website": "I noticed your business doesn't have a website yet",
            "outdated_site": "I took a look at your current website and noticed it might benefit from a refresh",
            "no_cta": "I checked out your online presence and noticed there's an opportunity to make it easier for customers to take action",
            "unknown": "I came across your business and wanted to reach out"
        }
        return observations.get(tag, observations["unknown"])

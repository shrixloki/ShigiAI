"""
Follow-Up Module - Sends one follow-up email after delay.

CRITICAL: Only sends to APPROVED leads with outreach_status='sent_initial'.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..config.settings import settings
from .logger import action_logger
from ..services.db_service import DatabaseService
from ..services.email_service_simple import EmailService


class FollowUpModule:
    """
    Sends follow-up emails to APPROVED leads only.
    Max 1 follow-up per lead.
    """
    
    def __init__(self):
        self.db = DatabaseService()
        self.email_service = EmailService()
        self.templates_dir = settings.TEMPLATES_DIR / "followup"
    
    def send_all_followups(self) -> dict:
        """
        Send follow-ups to eligible APPROVED leads.
        Eligible: review_status='approved', outreach_status='sent_initial', delay passed.
        
        Returns:
            {sent: int, skipped: int, errors: int, rate_limited: bool}
        """
        # Check rate limit
        sent_today = self.db.get_emails_sent_today_sync()
        remaining = settings.MAX_EMAILS_PER_DAY - sent_today
        
        if remaining <= 0:
            action_logger.warning(f"Daily rate limit reached ({settings.MAX_EMAILS_PER_DAY})")
            return {"sent": 0, "skipped": 0, "errors": 0, "rate_limited": True}
        
        leads = self.db.get_leads_for_followup_sync(settings.FOLLOWUP_DELAY_DAYS)
        sent = 0
        skipped = 0
        errors = 0
        
        for lead in leads:
            if sent >= remaining:
                action_logger.info("Rate limit reached, stopping follow-ups")
                break
            
            result = self.send_followup_email(lead)
            
            if result == "sent":
                sent += 1
            elif result == "skipped":
                skipped += 1
            else:
                errors += 1
        
        action_logger.log_action(
            lead_id=None,
            module_name="followup",
            action="send_batch",
            result="success",
            details={"sent": sent, "skipped": skipped, "errors": errors}
        )
        
        return {"sent": sent, "skipped": skipped, "errors": errors, "rate_limited": False}
    
    def send_followup_email(self, lead: dict) -> str:
        """
        Send follow-up email to a single lead.
        
        SAFETY CHECKS:
        1. Lead must have review_status='approved'
        2. Lead must have outreach_status='sent_initial'
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
                module_name="followup",
                action="send_followup",
                result="blocked",
                details={"reason": f"Lead not approved (status: {review_status})"}
            )
            return "skipped"
        
        # Safety check: Must have received initial email
        if outreach_status != "sent_initial":
            action_logger.log_action(
                lead_id=lead_id,
                module_name="followup",
                action="send_followup",
                result="skipped",
                details={"reason": f"Wrong outreach status: {outreach_status}"}
            )
            return "skipped"
        
        # Safety check: Must have email
        if not email:
            return "skipped"
        
        # Check for reply before sending
        try:
            reply = self.email_service.check_for_reply(email)
            if reply:
                self.db.update_lead_sync(lead_id, {"outreach_status": "replied"})
                action_logger.log_action(
                    lead_id=lead_id,
                    module_name="followup",
                    action="send_followup",
                    result="skipped",
                    details={"reason": "Reply detected, marking as replied"}
                )
                return "skipped"
        except Exception as e:
            action_logger.warning(f"Reply check failed for {lead_id}: {e}")
        
        # Load and personalize template
        subject, body = self._build_followup(lead)
        
        if not subject or not body:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="followup",
                action="send_followup",
                result="error",
                details={"reason": "Template load failed"}
            )
            return "error"
        
        # Send email
        success, message = self.email_service.send_email(email, subject, body)
        
        if success:
            self.db.update_lead_sync(lead_id, {
                "outreach_status": "sent_followup",
                "last_contacted": datetime.now().isoformat()
            })
            
            action_logger.log_action(
                lead_id=lead_id,
                module_name="followup",
                action="send_followup",
                result="success",
                details={"to": email}
            )
            return "sent"
        else:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="followup",
                action="send_followup",
                result="error",
                details={"error": message}
            )
            return "error"
    
    def _build_followup(self, lead: dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Build personalized follow-up email from template.
        Returns (subject, body) or (None, None) on failure.
        """
        template_file = self.templates_dir / "default.txt"
        
        if not template_file.exists():
            return None, None
        
        try:
            content = template_file.read_text(encoding="utf-8")
        except Exception:
            return None, None
        
        lines = content.strip().split("\n", 1)
        if len(lines) < 2:
            return None, None
        
        subject_template = lines[0].replace("Subject: ", "").strip()
        body_template = lines[1].strip()
        
        business_name = lead.get("business_name", "your business")
        
        subject = subject_template.replace("{{business_name}}", business_name)
        body = body_template.replace("{{business_name}}", business_name)
        body = body.replace("{{sender_name}}", settings.SENDER_NAME)
        
        return subject, body

"""
Reply Detector Module - Polls inbox and stops automation on reply.

Immediately stops outreach for any lead that responds.
"""

from .logger import action_logger
from ..services.db_service import DatabaseService
from ..services.email_service_simple import EmailService


class ReplyDetectorModule:
    """Detects replies and immediately stops automation for those leads."""
    
    def __init__(self):
        self.db = DatabaseService()
        self.email_service = EmailService()
    
    def check_all_replies(self) -> dict:
        """
        Check for replies from all active leads.
        Updates outreach_status to 'replied' for any lead that responded.
        
        Returns:
            {replies_found: int, checked: int}
        """
        # Get all leads that might receive replies (sent initial or followup)
        all_leads = self.db.get_all_leads_sync()
        active_leads = [
            lead for lead in all_leads
            if lead.get("outreach_status") in ("sent_initial", "sent_followup")
        ]
        
        if not active_leads:
            action_logger.info("No active leads to check for replies")
            return {"replies_found": 0, "checked": 0}
        
        # Get recent reply emails in batch
        try:
            reply_emails = self.email_service.get_recent_replies(hours=48)
            reply_emails_set = set(email.lower() for email in reply_emails)
        except Exception as e:
            action_logger.warning(f"Failed to fetch replies: {e}")
            return {"replies_found": 0, "checked": 0}
        
        replies_found = 0
        
        for lead in active_leads:
            lead_email = lead.get("email", "").lower()
            lead_id = lead.get("lead_id")
            
            if lead_email and lead_email in reply_emails_set:
                # Reply detected - stop all automation
                self._mark_as_replied(lead_id, lead_email)
                replies_found += 1
        
        if replies_found > 0:
            action_logger.log_action(
                lead_id=None,
                module_name="reply_detector",
                action="check_batch",
                result="success",
                details={
                    "replies_found": replies_found,
                    "checked": len(active_leads)
                }
            )
        
        return {"replies_found": replies_found, "checked": len(active_leads)}
    
    def check_single_lead(self, lead_id: str) -> bool:
        """
        Check for reply from a specific lead.
        Returns True if reply found.
        """
        lead = self.db.get_lead_by_id_sync(lead_id)
        
        if not lead:
            return False
        
        email = lead.get("email")
        if not email:
            return False
        
        try:
            reply = self.email_service.check_for_reply(email)
            
            if reply:
                self._mark_as_replied(lead_id, email)
                return True
        except Exception as e:
            action_logger.warning(f"Reply check failed for {lead_id}: {e}")
        
        return False
    
    def _mark_as_replied(self, lead_id: str, email: str):
        """Mark a lead as replied and log the action."""
        try:
            self.db.update_lead_sync(lead_id, {
                "outreach_status": "replied",
                "notes": "Reply detected - automation stopped"
            })
            
            action_logger.log_action(
                lead_id=lead_id,
                module_name="reply_detector",
                action="detect_reply",
                result="success",
                details={"email": email, "action_taken": "automation_stopped"}
            )
        except Exception as e:
            action_logger.log_action(
                lead_id=lead_id,
                module_name="reply_detector",
                action="detect_reply",
                result="error",
                details={"error": str(e)}
            )

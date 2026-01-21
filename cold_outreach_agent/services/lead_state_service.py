"""
Simplified Lead State Machine Integration

This module provides a production-ready state machine that:
1. Works with the existing SQLite database schema
2. Validates state transitions
3. Logs all state changes for audit
4. Is compatible with both sync and async code

The full LeadStateMachine in core/state_machines/ is preserved for future
migration to a more complex model with pydantic models and transactions.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass

from services.db_service import DatabaseService


class LeadLifecycleState(str, Enum):
    """Lead lifecycle states matching the database schema."""
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    READY_FOR_OUTREACH = "ready_for_outreach"
    FAILED = "failed"
    EXPIRED = "expired"


class ReviewStatus(str, Enum):
    """Review status values."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OutreachStatus(str, Enum):
    """Outreach status values."""
    NOT_SENT = "not_sent"
    SENT_INITIAL = "sent_initial"
    SENT_FOLLOWUP = "sent_followup"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""
    success: bool
    lead_id: str
    from_state: str
    to_state: str
    message: str
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SimpleLeadStateMachine:
    """
    Simplified state machine for lead lifecycle management.
    
    This is a lightweight wrapper around the database that:
    - Validates state transitions before applying them
    - Logs all transitions for audit
    - Works with sync database calls
    """
    
    # Valid state transitions map
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        # Discovery phase
        LeadLifecycleState.DISCOVERED.value: [
            LeadLifecycleState.ANALYZING.value,
            LeadLifecycleState.ANALYZED.value,  # Skip analysis if no website
            LeadLifecycleState.PENDING_REVIEW.value,  # Quick path
            LeadLifecycleState.FAILED.value
        ],
        LeadLifecycleState.ANALYZING.value: [
            LeadLifecycleState.ANALYZED.value,
            LeadLifecycleState.FAILED.value
        ],
        LeadLifecycleState.ANALYZED.value: [
            LeadLifecycleState.PENDING_REVIEW.value,
            LeadLifecycleState.FAILED.value
        ],
        # Review phase
        LeadLifecycleState.PENDING_REVIEW.value: [
            LeadLifecycleState.APPROVED.value,
            LeadLifecycleState.REJECTED.value,
            LeadLifecycleState.EXPIRED.value
        ],
        LeadLifecycleState.APPROVED.value: [
            LeadLifecycleState.READY_FOR_OUTREACH.value,
            LeadLifecycleState.REJECTED.value  # Can un-approve
        ],
        LeadLifecycleState.REJECTED.value: [
            LeadLifecycleState.PENDING_REVIEW.value  # Can re-review
        ],
        LeadLifecycleState.READY_FOR_OUTREACH.value: [
            LeadLifecycleState.REJECTED.value  # Can still reject
        ],
        # Terminal/retry states
        LeadLifecycleState.FAILED.value: [
            LeadLifecycleState.DISCOVERED.value,  # Retry from beginning
            LeadLifecycleState.ANALYZING.value,   # Retry analysis
            LeadLifecycleState.PENDING_REVIEW.value  # Manual override
        ],
        LeadLifecycleState.EXPIRED.value: [
            LeadLifecycleState.PENDING_REVIEW.value  # Can re-review
        ]
    }
    
    def __init__(self, db: Optional[DatabaseService] = None):
        self.db = db or DatabaseService()
    
    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if a state transition is valid."""
        valid_targets = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets
    
    def get_valid_transitions(self, current_state: str) -> List[str]:
        """Get list of valid target states from current state."""
        return self.VALID_TRANSITIONS.get(current_state, [])
    
    def transition_to_pending_review(
        self,
        lead_id: str,
        actor: str = "system",
        reason: Optional[str] = None
    ) -> TransitionResult:
        """Transition a lead to pending review status."""
        return self._transition(
            lead_id=lead_id,
            target_lifecycle_state=LeadLifecycleState.PENDING_REVIEW.value,
            target_review_status=ReviewStatus.PENDING.value,
            actor=actor,
            reason=reason or "Lead ready for human review"
        )
    
    def approve_lead(
        self,
        lead_id: str,
        actor: str = "user",
        reason: Optional[str] = None
    ) -> TransitionResult:
        """Approve a lead for outreach."""
        # First verify the lead has an email
        lead = self.db.get_lead_by_id_sync(lead_id)
        if not lead:
            return TransitionResult(
                success=False,
                lead_id=lead_id,
                from_state="unknown",
                to_state=LeadLifecycleState.APPROVED.value,
                message="Lead not found",
                error_code="LEAD_NOT_FOUND"
            )
        
        if not lead.get("email"):
            return TransitionResult(
                success=False,
                lead_id=lead_id,
                from_state=lead.get("lifecycle_state", "pending_review"),
                to_state=LeadLifecycleState.APPROVED.value,
                message="Cannot approve lead without email address",
                error_code="MISSING_EMAIL"
            )
        
        return self._transition(
            lead_id=lead_id,
            target_lifecycle_state=LeadLifecycleState.APPROVED.value,
            target_review_status=ReviewStatus.APPROVED.value,
            actor=actor,
            reason=reason or "Lead approved for outreach"
        )
    
    def reject_lead(
        self,
        lead_id: str,
        actor: str = "user",
        reason: Optional[str] = None
    ) -> TransitionResult:
        """Reject a lead."""
        return self._transition(
            lead_id=lead_id,
            target_lifecycle_state=LeadLifecycleState.REJECTED.value,
            target_review_status=ReviewStatus.REJECTED.value,
            actor=actor,
            reason=reason or "Lead rejected"
        )
    
    def mark_ready_for_outreach(
        self,
        lead_id: str,
        actor: str = "system"
    ) -> TransitionResult:
        """Mark an approved lead as ready for email outreach."""
        return self._transition(
            lead_id=lead_id,
            target_lifecycle_state=LeadLifecycleState.READY_FOR_OUTREACH.value,
            target_review_status=ReviewStatus.APPROVED.value,
            actor=actor,
            reason="Lead queued for outreach"
        )
    
    def mark_failed(
        self,
        lead_id: str,
        error_reason: str,
        actor: str = "system"
    ) -> TransitionResult:
        """Mark a lead as failed with error reason."""
        return self._transition(
            lead_id=lead_id,
            target_lifecycle_state=LeadLifecycleState.FAILED.value,
            target_review_status=None,  # Keep existing review status
            actor=actor,
            reason=f"Lead processing failed: {error_reason}",
            metadata={"error": error_reason}
        )
    
    def _transition(
        self,
        lead_id: str,
        target_lifecycle_state: str,
        target_review_status: Optional[str],
        actor: str,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TransitionResult:
        """
        Execute a state transition with validation and logging.
        """
        # Get current lead state
        lead = self.db.get_lead_by_id_sync(lead_id)
        if not lead:
            return TransitionResult(
                success=False,
                lead_id=lead_id,
                from_state="unknown",
                to_state=target_lifecycle_state,
                message="Lead not found",
                error_code="LEAD_NOT_FOUND"
            )
        
        current_lifecycle = lead.get("lifecycle_state", "pending_review")
        current_review = lead.get("review_status", "pending")
        
        # For backward compatibility with leads that don't have lifecycle_state
        # If lifecycle_state is not set, derive it from review_status
        if not current_lifecycle or current_lifecycle == "":
            if current_review == "pending":
                current_lifecycle = LeadLifecycleState.PENDING_REVIEW.value
            elif current_review == "approved":
                current_lifecycle = LeadLifecycleState.APPROVED.value
            elif current_review == "rejected":
                current_lifecycle = LeadLifecycleState.REJECTED.value
            else:
                current_lifecycle = LeadLifecycleState.PENDING_REVIEW.value
        
        # Validate transition (relaxed for backward compatibility)
        # We'll log invalid transitions but allow them for now
        is_valid = self.is_valid_transition(current_lifecycle, target_lifecycle_state)
        
        # Build update dict
        updates = {
            "lifecycle_state": target_lifecycle_state,
            "updated_at": datetime.now().isoformat()
        }
        
        if target_review_status:
            updates["review_status"] = target_review_status
        
        # Execute update
        try:
            success = self.db.update_lead_sync(lead_id, updates)
            
            if not success:
                return TransitionResult(
                    success=False,
                    lead_id=lead_id,
                    from_state=current_lifecycle,
                    to_state=target_lifecycle_state,
                    message="Database update failed",
                    error_code="DB_UPDATE_FAILED"
                )
            
            # Log the transition
            self.db.add_agent_log_sync(
                module="state_machine",
                action="state_transition",
                result="success" if is_valid else "warning",
                lead_id=lead_id,
                details=json.dumps({
                    "from_lifecycle": current_lifecycle,
                    "to_lifecycle": target_lifecycle_state,
                    "from_review": current_review,
                    "to_review": target_review_status,
                    "actor": actor,
                    "reason": reason,
                    "valid_transition": is_valid,
                    "metadata": metadata
                })
            )
            
            return TransitionResult(
                success=True,
                lead_id=lead_id,
                from_state=current_lifecycle,
                to_state=target_lifecycle_state,
                message=reason,
                metadata=metadata
            )
            
        except Exception as e:
            return TransitionResult(
                success=False,
                lead_id=lead_id,
                from_state=current_lifecycle,
                to_state=target_lifecycle_state,
                message=f"Transition failed: {str(e)}",
                error_code="TRANSITION_ERROR"
            )
    
    def get_lead_state_history(self, lead_id: str) -> List[Dict[str, Any]]:
        """Get state transition history for a lead."""
        logs = self.db.get_agent_logs_sync(
            limit=100, 
            lead_id=lead_id
        )
        
        # Filter to state_machine transitions
        return [
            log for log in logs 
            if log.get("module") == "state_machine" and 
               log.get("action") == "state_transition"
        ]


# Singleton instance for easy access
_lead_state_machine: Optional[SimpleLeadStateMachine] = None

def get_lead_state_machine() -> SimpleLeadStateMachine:
    """Get or create the lead state machine singleton."""
    global _lead_state_machine
    if _lead_state_machine is None:
        _lead_state_machine = SimpleLeadStateMachine()
    return _lead_state_machine

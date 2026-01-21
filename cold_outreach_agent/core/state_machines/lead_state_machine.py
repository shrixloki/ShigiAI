"""Lead lifecycle state machine with proper validation and transitions."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from ..models.lead import Lead, LeadState, ReviewStatus
from ..models.common import OperationResult, StateTransition, EntityType
from ..exceptions import InvalidStateTransitionError, LeadNotFoundError


class LeadStateMachine:
    """Manages lead state transitions with validation and audit logging."""
    
    def __init__(self, db_service, audit_service):
        self.db = db_service
        self.audit = audit_service
    
    async def transition_state(
        self,
        lead_id: UUID,
        target_state: LeadState,
        actor: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OperationResult[Lead]:
        """
        Transition lead to target state with validation and audit logging.
        
        Args:
            lead_id: Lead identifier
            target_state: Target state to transition to
            actor: Who is performing the transition
            reason: Optional reason for the transition
            metadata: Additional metadata for the transition
            
        Returns:
            OperationResult with updated lead or error
        """
        try:
            # Get current lead
            lead = await self.db.get_lead_by_id(lead_id)
            if not lead:
                return OperationResult.error_result(
                    error=f"Lead {lead_id} not found",
                    error_code="LEAD_NOT_FOUND"
                )
            
            current_state = lead.lifecycle_state
            
            # Validate transition
            if not self._is_valid_transition(current_state, target_state):
                return OperationResult.error_result(
                    error=f"Invalid transition from {current_state} to {target_state}",
                    error_code="INVALID_TRANSITION"
                )
            
            # Perform pre-transition validation
            validation_result = await self._validate_transition(lead, target_state, metadata)
            if not validation_result.success:
                return validation_result
            
            # Execute transition atomically
            async with self.db.transaction():
                # Update lead state
                old_values = {"lifecycle_state": current_state}
                new_values = {"lifecycle_state": target_state, "updated_at": datetime.now()}
                
                # Apply any side effects
                side_effects = await self._apply_side_effects(lead, target_state, metadata)
                new_values.update(side_effects)
                
                # Update in database
                updated_lead = await self.db.update_lead(lead_id, new_values)
                
                # Log state transition
                await self._log_state_transition(
                    lead_id=lead_id,
                    from_state=current_state,
                    to_state=target_state,
                    actor=actor,
                    reason=reason,
                    metadata=metadata
                )
                
                # Log audit entry
                await self.audit.log_action(
                    entity_type=EntityType.LEAD,
                    entity_id=lead_id,
                    action="state_transition",
                    actor=actor,
                    old_values=old_values,
                    new_values=new_values,
                    metadata={
                        "reason": reason,
                        "transition_metadata": metadata
                    }
                )
            
            return OperationResult.success_result(
                data=updated_lead,
                metadata={"transition": f"{current_state} -> {target_state}"}
            )
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"State transition failed: {str(e)}",
                error_code="TRANSITION_ERROR"
            )
    
    def _is_valid_transition(self, current_state: LeadState, target_state: LeadState) -> bool:
        """Check if state transition is valid."""
        valid_transitions = {
            LeadState.DISCOVERED: [
                LeadState.ANALYZING,
                LeadState.FAILED
            ],
            LeadState.ANALYZING: [
                LeadState.ANALYZED,
                LeadState.FAILED
            ],
            LeadState.ANALYZED: [
                LeadState.PENDING_REVIEW,
                LeadState.FAILED
            ],
            LeadState.PENDING_REVIEW: [
                LeadState.APPROVED,
                LeadState.REJECTED,
                LeadState.EXPIRED
            ],
            LeadState.APPROVED: [
                LeadState.READY_FOR_OUTREACH,
                LeadState.REJECTED  # Can be rejected after approval
            ],
            LeadState.REJECTED: [
                LeadState.PENDING_REVIEW  # Can be re-reviewed
            ],
            LeadState.READY_FOR_OUTREACH: [
                LeadState.REJECTED  # Can be rejected even when ready
            ],
            LeadState.FAILED: [
                LeadState.DISCOVERED,  # Can retry from beginning
                LeadState.ANALYZING,   # Can retry analysis
                LeadState.ANALYZED     # Can retry review
            ],
            LeadState.EXPIRED: [
                LeadState.PENDING_REVIEW  # Can be re-reviewed
            ]
        }
        
        return target_state in valid_transitions.get(current_state, [])
    
    async def _validate_transition(
        self,
        lead: Lead,
        target_state: LeadState,
        metadata: Optional[Dict[str, Any]]
    ) -> OperationResult[None]:
        """Validate specific transition requirements."""
        
        # Validate transition to READY_FOR_OUTREACH
        if target_state == LeadState.READY_FOR_OUTREACH:
            if not lead.email:
                return OperationResult.error_result(
                    error="Cannot transition to READY_FOR_OUTREACH without email",
                    error_code="MISSING_EMAIL"
                )
            
            if lead.review_status != ReviewStatus.APPROVED:
                return OperationResult.error_result(
                    error="Cannot transition to READY_FOR_OUTREACH without approval",
                    error_code="NOT_APPROVED"
                )
        
        # Validate transition to APPROVED
        if target_state == LeadState.APPROVED:
            if lead.lifecycle_state != LeadState.PENDING_REVIEW:
                return OperationResult.error_result(
                    error="Can only approve leads in PENDING_REVIEW state",
                    error_code="INVALID_APPROVAL_STATE"
                )
        
        return OperationResult.success_result()
    
    async def _apply_side_effects(
        self,
        lead: Lead,
        target_state: LeadState,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply side effects for state transitions."""
        side_effects = {}
        
        # Update review status when transitioning to approved/rejected
        if target_state == LeadState.APPROVED:
            side_effects["review_status"] = ReviewStatus.APPROVED
        elif target_state == LeadState.REJECTED:
            side_effects["review_status"] = ReviewStatus.REJECTED
        elif target_state == LeadState.EXPIRED:
            side_effects["review_status"] = ReviewStatus.EXPIRED
        
        # Update version for optimistic locking
        side_effects["version"] = lead.version + 1
        
        return side_effects
    
    async def _log_state_transition(
        self,
        lead_id: UUID,
        from_state: LeadState,
        to_state: LeadState,
        actor: str,
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ):
        """Log state transition for audit trail."""
        transition = StateTransition(
            entity_id=lead_id,
            entity_type=EntityType.LEAD,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            reason=reason,
            metadata=metadata or {}
        )
        
        await self.db.save_state_transition(transition)
    
    async def approve_lead(
        self,
        lead_id: UUID,
        actor: str,
        reason: Optional[str] = None
    ) -> OperationResult[Lead]:
        """Approve a lead for outreach."""
        return await self.transition_state(
            lead_id=lead_id,
            target_state=LeadState.APPROVED,
            actor=actor,
            reason=reason or "Lead approved for outreach"
        )
    
    async def reject_lead(
        self,
        lead_id: UUID,
        actor: str,
        reason: Optional[str] = None
    ) -> OperationResult[Lead]:
        """Reject a lead."""
        return await self.transition_state(
            lead_id=lead_id,
            target_state=LeadState.REJECTED,
            actor=actor,
            reason=reason or "Lead rejected"
        )
    
    async def mark_ready_for_outreach(
        self,
        lead_id: UUID,
        actor: str = "system"
    ) -> OperationResult[Lead]:
        """Mark approved lead as ready for outreach."""
        return await self.transition_state(
            lead_id=lead_id,
            target_state=LeadState.READY_FOR_OUTREACH,
            actor=actor,
            reason="Lead ready for email outreach"
        )
    
    async def mark_analysis_complete(
        self,
        lead_id: UUID,
        analysis_results: Dict[str, Any],
        actor: str = "system"
    ) -> OperationResult[Lead]:
        """Mark lead analysis as complete."""
        return await self.transition_state(
            lead_id=lead_id,
            target_state=LeadState.ANALYZED,
            actor=actor,
            reason="Website analysis completed",
            metadata={"analysis_results": analysis_results}
        )
    
    async def mark_failed(
        self,
        lead_id: UUID,
        error_reason: str,
        actor: str = "system"
    ) -> OperationResult[Lead]:
        """Mark lead as failed with error reason."""
        return await self.transition_state(
            lead_id=lead_id,
            target_state=LeadState.FAILED,
            actor=actor,
            reason=f"Lead processing failed: {error_reason}",
            metadata={"error": error_reason}
        )
    
    async def get_leads_by_state(self, state: LeadState) -> list[Lead]:
        """Get all leads in a specific state."""
        return await self.db.get_leads_by_state(state)
    
    async def get_leads_ready_for_outreach(self) -> list[Lead]:
        """Get all leads ready for email outreach."""
        return await self.db.get_leads_by_state(LeadState.READY_FOR_OUTREACH)
    
    async def get_pending_review_leads(self) -> list[Lead]:
        """Get all leads pending human review."""
        return await self.db.get_leads_by_state(LeadState.PENDING_REVIEW)
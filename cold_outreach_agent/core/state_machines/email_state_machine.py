"""Email campaign state machine with delivery tracking and retry logic."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from ..models.email import EmailCampaign, EmailState, CampaignType
from ..models.common import OperationResult, StateTransition, EntityType
from ..exceptions import InvalidStateTransitionError, EmailCampaignNotFoundError


class EmailStateMachine:
    """Manages email campaign state transitions with delivery tracking."""
    
    def __init__(self, db_service, audit_service):
        self.db = db_service
        self.audit = audit_service
        self.max_retry_attempts = 3
        self.retry_delays = [300, 900, 3600]  # 5min, 15min, 1hour
    
    async def transition_state(
        self,
        campaign_id: UUID,
        target_state: EmailState,
        actor: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OperationResult[EmailCampaign]:
        """
        Transition email campaign to target state with validation.
        
        Args:
            campaign_id: Email campaign identifier
            target_state: Target state to transition to
            actor: Who is performing the transition
            reason: Optional reason for the transition
            metadata: Additional metadata (delivery info, errors, etc.)
            
        Returns:
            OperationResult with updated campaign or error
        """
        try:
            # Get current campaign
            campaign = await self.db.get_email_campaign_by_id(campaign_id)
            if not campaign:
                return OperationResult.error_result(
                    error=f"Email campaign {campaign_id} not found",
                    error_code="CAMPAIGN_NOT_FOUND"
                )
            
            current_state = campaign.email_state
            
            # Validate transition
            if not self._is_valid_transition(current_state, target_state):
                return OperationResult.error_result(
                    error=f"Invalid transition from {current_state} to {target_state}",
                    error_code="INVALID_TRANSITION"
                )
            
            # Execute transition atomically
            async with self.db.transaction():
                # Prepare update data
                old_values = {"email_state": current_state}
                new_values = {
                    "email_state": target_state,
                    "updated_at": datetime.now()
                }
                
                # Apply state-specific side effects
                side_effects = await self._apply_side_effects(
                    campaign, target_state, metadata
                )
                new_values.update(side_effects)
                
                # Update in database
                updated_campaign = await self.db.update_email_campaign(
                    campaign_id, new_values
                )
                
                # Log state transition
                await self._log_state_transition(
                    campaign_id=campaign_id,
                    from_state=current_state,
                    to_state=target_state,
                    actor=actor,
                    reason=reason,
                    metadata=metadata
                )
                
                # Log audit entry
                await self.audit.log_action(
                    entity_type=EntityType.EMAIL_CAMPAIGN,
                    entity_id=campaign_id,
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
                data=updated_campaign,
                metadata={"transition": f"{current_state} -> {target_state}"}
            )
            
        except Exception as e:
            return OperationResult.error_result(
                error=f"Email state transition failed: {str(e)}",
                error_code="TRANSITION_ERROR"
            )
    
    def _is_valid_transition(self, current_state: EmailState, target_state: EmailState) -> bool:
        """Check if email state transition is valid."""
        valid_transitions = {
            EmailState.QUEUED: [
                EmailState.SENDING,
                EmailState.CANCELLED,
                EmailState.FAILED
            ],
            EmailState.SENDING: [
                EmailState.SENT,
                EmailState.FAILED
            ],
            EmailState.SENT: [
                EmailState.DELIVERED,
                EmailState.BOUNCED,
                EmailState.FAILED
            ],
            EmailState.DELIVERED: [
                EmailState.OPENED,
                EmailState.REPLIED
            ],
            EmailState.OPENED: [
                EmailState.CLICKED,
                EmailState.REPLIED
            ],
            EmailState.CLICKED: [
                EmailState.REPLIED
            ],
            EmailState.REPLIED: [],  # Terminal state
            EmailState.BOUNCED: [],  # Terminal state
            EmailState.FAILED: [
                EmailState.QUEUED  # Can retry
            ],
            EmailState.CANCELLED: []  # Terminal state
        }
        
        return target_state in valid_transitions.get(current_state, [])
    
    async def _apply_side_effects(
        self,
        campaign: EmailCampaign,
        target_state: EmailState,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply side effects for email state transitions."""
        side_effects = {}
        now = datetime.now()
        
        # Update timestamps based on state
        if target_state == EmailState.QUEUED:
            side_effects["queued_at"] = now
        elif target_state == EmailState.SENT:
            side_effects["sent_at"] = now
            # Extract message ID from metadata
            if metadata and "message_id" in metadata:
                side_effects["message_id"] = metadata["message_id"]
        elif target_state == EmailState.DELIVERED:
            side_effects["delivered_at"] = now
        elif target_state == EmailState.OPENED:
            side_effects["opened_at"] = now
        elif target_state == EmailState.CLICKED:
            side_effects["clicked_at"] = now
        elif target_state == EmailState.REPLIED:
            side_effects["replied_at"] = now
        
        # Handle error states
        if target_state == EmailState.FAILED:
            side_effects["error_count"] = campaign.error_count + 1
            if metadata and "error" in metadata:
                side_effects["last_error"] = metadata["error"]
            
            # Set retry time if not exceeded max attempts
            if campaign.error_count < self.max_retry_attempts:
                retry_delay = self.retry_delays[min(campaign.error_count, len(self.retry_delays) - 1)]
                side_effects["retry_after"] = now + timedelta(seconds=retry_delay)
        
        # Handle provider response metadata
        if metadata and "provider_response" in metadata:
            side_effects["provider_response"] = metadata["provider_response"]
        
        if metadata and "delivery_metadata" in metadata:
            side_effects["delivery_metadata"] = metadata["delivery_metadata"]
        
        return side_effects
    
    async def _log_state_transition(
        self,
        campaign_id: UUID,
        from_state: EmailState,
        to_state: EmailState,
        actor: str,
        reason: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ):
        """Log email state transition for audit trail."""
        transition = StateTransition(
            entity_id=campaign_id,
            entity_type=EntityType.EMAIL_CAMPAIGN,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            reason=reason,
            metadata=metadata or {}
        )
        
        await self.db.save_state_transition(transition)
    
    async def mark_sending(
        self,
        campaign_id: UUID,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as currently being sent."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.SENDING,
            actor=actor,
            reason="Email sending initiated"
        )
    
    async def mark_sent(
        self,
        campaign_id: UUID,
        message_id: str,
        provider_response: Dict[str, Any] = None,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as successfully sent."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.SENT,
            actor=actor,
            reason="Email sent successfully",
            metadata={
                "message_id": message_id,
                "provider_response": provider_response or {}
            }
        )
    
    async def mark_delivered(
        self,
        campaign_id: UUID,
        delivery_metadata: Dict[str, Any] = None,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as delivered."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.DELIVERED,
            actor=actor,
            reason="Email delivered",
            metadata={"delivery_metadata": delivery_metadata or {}}
        )
    
    async def mark_opened(
        self,
        campaign_id: UUID,
        open_metadata: Dict[str, Any] = None,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as opened by recipient."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.OPENED,
            actor=actor,
            reason="Email opened by recipient",
            metadata={"open_metadata": open_metadata or {}}
        )
    
    async def mark_replied(
        self,
        campaign_id: UUID,
        reply_metadata: Dict[str, Any] = None,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as replied to by recipient."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.REPLIED,
            actor=actor,
            reason="Recipient replied to email",
            metadata={"reply_metadata": reply_metadata or {}}
        )
    
    async def mark_bounced(
        self,
        campaign_id: UUID,
        bounce_reason: str,
        bounce_metadata: Dict[str, Any] = None,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as bounced."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.BOUNCED,
            actor=actor,
            reason=f"Email bounced: {bounce_reason}",
            metadata={
                "bounce_reason": bounce_reason,
                "bounce_metadata": bounce_metadata or {}
            }
        )
    
    async def mark_failed(
        self,
        campaign_id: UUID,
        error_message: str,
        error_metadata: Dict[str, Any] = None,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Mark email as failed with error details."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.FAILED,
            actor=actor,
            reason=f"Email failed: {error_message}",
            metadata={
                "error": error_message,
                "error_metadata": error_metadata or {}
            }
        )
    
    async def cancel_email(
        self,
        campaign_id: UUID,
        reason: str,
        actor: str
    ) -> OperationResult[EmailCampaign]:
        """Cancel a queued email."""
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.CANCELLED,
            actor=actor,
            reason=f"Email cancelled: {reason}"
        )
    
    async def retry_failed_email(
        self,
        campaign_id: UUID,
        actor: str = "system"
    ) -> OperationResult[EmailCampaign]:
        """Retry a failed email if retry conditions are met."""
        campaign = await self.db.get_email_campaign_by_id(campaign_id)
        if not campaign:
            return OperationResult.error_result(
                error=f"Email campaign {campaign_id} not found",
                error_code="CAMPAIGN_NOT_FOUND"
            )
        
        # Check if retry is allowed
        if campaign.email_state != EmailState.FAILED:
            return OperationResult.error_result(
                error="Can only retry failed emails",
                error_code="INVALID_RETRY_STATE"
            )
        
        if campaign.error_count >= self.max_retry_attempts:
            return OperationResult.error_result(
                error="Maximum retry attempts exceeded",
                error_code="MAX_RETRIES_EXCEEDED"
            )
        
        if campaign.retry_after and campaign.retry_after > datetime.now():
            return OperationResult.error_result(
                error="Retry delay not yet elapsed",
                error_code="RETRY_TOO_SOON"
            )
        
        return await self.transition_state(
            campaign_id=campaign_id,
            target_state=EmailState.QUEUED,
            actor=actor,
            reason=f"Retrying failed email (attempt {campaign.error_count + 1})"
        )
    
    async def get_campaigns_by_state(self, state: EmailState) -> list[EmailCampaign]:
        """Get all email campaigns in a specific state."""
        return await self.db.get_email_campaigns_by_state(state)
    
    async def get_queued_campaigns(self) -> list[EmailCampaign]:
        """Get all queued email campaigns ready to send."""
        return await self.db.get_email_campaigns_by_state(EmailState.QUEUED)
    
    async def get_failed_campaigns_for_retry(self) -> list[EmailCampaign]:
        """Get failed campaigns that are eligible for retry."""
        failed_campaigns = await self.db.get_email_campaigns_by_state(EmailState.FAILED)
        
        eligible_for_retry = []
        now = datetime.now()
        
        for campaign in failed_campaigns:
            if (campaign.error_count < self.max_retry_attempts and
                (campaign.retry_after is None or campaign.retry_after <= now)):
                eligible_for_retry.append(campaign)
        
        return eligible_for_retry
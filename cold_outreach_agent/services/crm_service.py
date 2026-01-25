"""CRM service for reply handling, conversations, and opportunity tracking."""

import asyncio
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from ..core.models.crm import (
    EmailReply, ReplyClassification, ConversationThread, ConversationStatus,
    InternalNote, NoteType, Opportunity, OpportunityStage, LeadStatusTransition,
    ReplyClassifyRequest, OpportunityCreate, OpportunityUpdate, NoteCreate
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class CRMError(ColdOutreachAgentError):
    """CRM operation failed."""
    pass


class CRMService:
    """
    Lightweight CRM service for reply handling and opportunity tracking.
    
    Features:
    - Reply detection and classification
    - Conversation threading
    - Internal notes
    - Lead status transitions based on replies
    - Opportunity pipeline view
    """
    
    # Keywords for reply classification
    POSITIVE_KEYWORDS = [
        r'interested', r'tell me more', r'sounds good', r'let\'?s talk',
        r'schedule a call', r'when can we', r'send more info', r'pricing',
        r'how much', r'quote', r'proposal', r'yes', r'absolutely',
        r'great', r'perfect', r'looking forward'
    ]
    
    NEGATIVE_KEYWORDS = [
        r'not interested', r'no thank', r'remove me', r'unsubscribe',
        r'stop emailing', r'don\'?t contact', r'not looking', r'already have',
        r'no need', r'not for us', r'pass', r'decline', r'not at this time'
    ]
    
    OUT_OF_OFFICE_KEYWORDS = [
        r'out of office', r'ooo', r'vacation', r'away from', r'limited access',
        r'automatic reply', r'auto-reply', r'will respond when', r'returning on'
    ]
    
    WRONG_PERSON_KEYWORDS = [
        r'wrong person', r'no longer with', r'left the company', r'different department',
        r'not me', r'not my area', r'try contacting'
    ]
    
    def __init__(self, db_service):
        self.db = db_service
        self._threads: Dict[UUID, ConversationThread] = {}
        self._replies: Dict[UUID, EmailReply] = {}
        self._notes: Dict[UUID, InternalNote] = {}
        self._opportunities: Dict[UUID, Opportunity] = {}
        self._status_transitions: List[LeadStatusTransition] = []
    
    async def process_reply(self, lead_id: UUID, campaign_id: UUID,
                            from_email: str, from_name: Optional[str],
                            subject: str, body_text: str,
                            body_html: Optional[str] = None,
                            message_id: Optional[str] = None,
                            in_reply_to: Optional[str] = None) -> EmailReply:
        """
        Process an incoming email reply.
        
        Args:
            lead_id: Lead who replied
            campaign_id: Campaign the reply is for
            from_email: Sender's email
            from_name: Sender's name
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body (optional)
            message_id: Email message ID
            in_reply_to: Message ID being replied to
        
        Returns:
            Processed EmailReply with classification
        """
        # Find or create conversation thread
        thread = await self._get_or_create_thread(lead_id, subject)
        
        # Classify the reply
        classification, confidence = self._classify_reply(body_text)
        
        # Create reply record
        reply = EmailReply(
            lead_id=lead_id,
            email_campaign_id=campaign_id,
            thread_id=thread.id,
            from_email=from_email,
            from_name=from_name,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            message_id=message_id,
            in_reply_to=in_reply_to,
            classification=classification,
            classification_confidence=confidence,
            classification_model="keyword_v1"
        )
        
        self._replies[reply.id] = reply
        
        # Update thread
        thread.reply_count += 1
        thread.message_count += 1
        thread.last_reply_at = datetime.now()
        thread.last_message_at = datetime.now()
        thread.overall_sentiment = classification
        
        # Update thread status based on classification
        if classification == ReplyClassification.POSITIVE:
            thread.status = ConversationStatus.ACTIVE
        elif classification == ReplyClassification.NEGATIVE:
            thread.status = ConversationStatus.CLOSED_LOST
        elif classification == ReplyClassification.OUT_OF_OFFICE:
            thread.status = ConversationStatus.AWAITING_REPLY
        
        # Trigger lead status transition
        await self._transition_lead_status(lead_id, classification, reply.id)
        
        action_logger.log_action(
            lead_id=str(lead_id),
            module_name="crm",
            action="process_reply",
            result="success",
            details={
                "classification": classification.value if hasattr(classification, 'value') else classification,
                "confidence": float(confidence),
                "thread_id": str(thread.id)
            }
        )
        
        return reply
    
    def _classify_reply(self, body_text: str) -> tuple[ReplyClassification, Decimal]:
        """
        Classify a reply based on content analysis.
        
        Returns:
            Tuple of (classification, confidence)
        """
        text_lower = body_text.lower()
        
        # Check for out of office first (high priority)
        for pattern in self.OUT_OF_OFFICE_KEYWORDS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return ReplyClassification.OUT_OF_OFFICE, Decimal("0.9")
        
        # Check for wrong person
        for pattern in self.WRONG_PERSON_KEYWORDS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return ReplyClassification.WRONG_PERSON, Decimal("0.85")
        
        # Check for unsubscribe
        if re.search(r'unsubscribe|remove me|stop email', text_lower, re.IGNORECASE):
            return ReplyClassification.UNSUBSCRIBE, Decimal("0.95")
        
        # Count positive and negative signals
        positive_count = sum(
            1 for p in self.POSITIVE_KEYWORDS 
            if re.search(p, text_lower, re.IGNORECASE)
        )
        negative_count = sum(
            1 for p in self.NEGATIVE_KEYWORDS 
            if re.search(p, text_lower, re.IGNORECASE)
        )
        
        # Determine classification based on signal counts
        if positive_count > 0 and positive_count > negative_count:
            confidence = min(Decimal("0.5") + Decimal(str(positive_count * 0.1)), Decimal("0.9"))
            return ReplyClassification.POSITIVE, confidence
        
        if negative_count > 0 and negative_count >= positive_count:
            confidence = min(Decimal("0.5") + Decimal(str(negative_count * 0.1)), Decimal("0.9"))
            return ReplyClassification.NEGATIVE, confidence
        
        # Check for questions (neutral)
        if '?' in body_text:
            return ReplyClassification.NEUTRAL, Decimal("0.6")
        
        # Default to neutral with low confidence
        return ReplyClassification.NEUTRAL, Decimal("0.4")
    
    async def _get_or_create_thread(self, lead_id: UUID, subject: str) -> ConversationThread:
        """Get existing thread or create new one."""
        # Look for existing thread with same subject
        for thread in self._threads.values():
            if thread.lead_id == lead_id:
                # Normalize subjects for comparison
                normalized_existing = re.sub(r'^(re:|fwd:)\s*', '', thread.subject.lower())
                normalized_new = re.sub(r'^(re:|fwd:)\s*', '', subject.lower())
                if normalized_existing == normalized_new:
                    return thread
        
        # Create new thread
        thread = ConversationThread(
            lead_id=lead_id,
            subject=subject,
            status=ConversationStatus.ACTIVE
        )
        self._threads[thread.id] = thread
        return thread
    
    async def _transition_lead_status(self, lead_id: UUID, 
                                       classification: ReplyClassification,
                                       reply_id: UUID):
        """Transition lead status based on reply classification."""
        status_map = {
            ReplyClassification.POSITIVE: ("pending", "interested", "Positive reply received"),
            ReplyClassification.NEGATIVE: ("pending", "rejected", "Declined via reply"),
            ReplyClassification.UNSUBSCRIBE: ("approved", "unsubscribed", "Unsubscribe request"),
        }
        
        if classification in status_map:
            from_status, to_status, reason = status_map[classification]
            
            transition = LeadStatusTransition(
                lead_id=lead_id,
                trigger_reply_id=reply_id,
                from_status=from_status,
                to_status=to_status,
                transition_reason=reason,
                is_automatic=True
            )
            self._status_transitions.append(transition)
            
            # Update lead in database
            try:
                await self.db.update_lead(lead_id, {"outreach_status": to_status})
            except Exception as e:
                action_logger.warning(f"Failed to update lead status: {e}")
    
    async def reclassify_reply(self, request: ReplyClassifyRequest) -> EmailReply:
        """
        Manually reclassify a reply.
        
        Args:
            request: Reclassification request
        
        Returns:
            Updated EmailReply
        """
        reply = self._replies.get(request.reply_id)
        if not reply:
            raise CRMError(f"Reply {request.reply_id} not found")
        
        old_classification = reply.classification
        reply.classification = request.classification
        reply.is_manually_classified = True
        reply.classification_confidence = Decimal("1.0")
        
        # Re-trigger status transition if classification changed
        if old_classification != request.classification:
            await self._transition_lead_status(
                reply.lead_id, 
                request.classification, 
                reply.id
            )
        
        action_logger.log_action(
            lead_id=str(reply.lead_id),
            module_name="crm",
            action="reclassify_reply",
            result="success",
            details={
                "old": old_classification.value if hasattr(old_classification, 'value') else old_classification,
                "new": request.classification.value if hasattr(request.classification, 'value') else request.classification,
                "actor": request.actor
            }
        )
        
        return reply
    
    async def add_note(self, request: NoteCreate) -> InternalNote:
        """
        Add an internal note to a lead.
        
        Args:
            request: Note creation request
        
        Returns:
            Created InternalNote
        """
        note = InternalNote(
            lead_id=request.lead_id,
            thread_id=request.thread_id,
            note_type=request.note_type,
            content=request.content,
            is_pinned=request.is_pinned,
            created_by=request.created_by
        )
        
        self._notes[note.id] = note
        
        action_logger.log_action(
            lead_id=str(request.lead_id),
            module_name="crm",
            action="add_note",
            result="success",
            details={"note_type": request.note_type.value if hasattr(request.note_type, 'value') else request.note_type}
        )
        
        return note
    
    async def get_lead_notes(self, lead_id: UUID) -> List[InternalNote]:
        """Get all notes for a lead."""
        notes = [n for n in self._notes.values() if n.lead_id == lead_id]
        return sorted(notes, key=lambda n: n.created_at, reverse=True)
    
    async def update_note(self, note_id: UUID, content: str) -> Optional[InternalNote]:
        """Update a note's content."""
        note = self._notes.get(note_id)
        if note:
            note.content = content
            note.updated_at = datetime.now()
        return note
    
    async def delete_note(self, note_id: UUID) -> bool:
        """Delete a note."""
        if note_id in self._notes:
            del self._notes[note_id]
            return True
        return False
    
    async def create_opportunity(self, request: OpportunityCreate) -> Opportunity:
        """
        Create a new opportunity/deal.
        
        Args:
            request: Opportunity creation request
        
        Returns:
            Created Opportunity
        """
        opportunity = Opportunity(
            lead_id=request.lead_id,
            name=request.name,
            description=request.description,
            estimated_value=request.estimated_value,
            expected_close_date=request.expected_close_date,
            owner=request.owner,
            created_by=request.created_by
        )
        
        # Calculate weighted value
        if opportunity.estimated_value:
            opportunity.weighted_value = opportunity.calculate_weighted_value()
        
        self._opportunities[opportunity.id] = opportunity
        
        action_logger.log_action(
            lead_id=str(request.lead_id),
            module_name="crm",
            action="create_opportunity",
            result="success",
            details={
                "name": request.name,
                "value": float(request.estimated_value) if request.estimated_value else None
            }
        )
        
        return opportunity
    
    async def update_opportunity(self, opportunity_id: UUID, 
                                  update: OpportunityUpdate) -> Optional[Opportunity]:
        """Update an existing opportunity."""
        opportunity = self._opportunities.get(opportunity_id)
        if not opportunity:
            return None
        
        # Track stage change
        old_stage = opportunity.stage
        
        if update.name is not None:
            opportunity.name = update.name
        if update.description is not None:
            opportunity.description = update.description
        if update.stage is not None:
            opportunity.previous_stage = opportunity.stage
            opportunity.stage = update.stage
            opportunity.stage_changed_at = datetime.now()
            
            # Set close date if closing
            if update.stage in [OpportunityStage.CLOSED_WON, OpportunityStage.CLOSED_LOST]:
                opportunity.closed_at = datetime.now()
        
        if update.estimated_value is not None:
            opportunity.estimated_value = update.estimated_value
        if update.probability is not None:
            opportunity.probability = update.probability
        if update.expected_close_date is not None:
            opportunity.expected_close_date = update.expected_close_date
        if update.owner is not None:
            opportunity.owner = update.owner
        if update.closed_reason is not None:
            opportunity.closed_reason = update.closed_reason
        
        # Recalculate weighted value
        opportunity.weighted_value = opportunity.calculate_weighted_value()
        opportunity.updated_at = datetime.now()
        
        action_logger.log_action(
            lead_id=str(opportunity.lead_id),
            module_name="crm",
            action="update_opportunity",
            result="success",
            details={
                "old_stage": old_stage.value if hasattr(old_stage, 'value') else old_stage,
                "new_stage": opportunity.stage.value if hasattr(opportunity.stage, 'value') else opportunity.stage
            }
        )
        
        return opportunity
    
    async def get_opportunity(self, opportunity_id: UUID) -> Optional[Opportunity]:
        """Get an opportunity by ID."""
        return self._opportunities.get(opportunity_id)
    
    async def get_lead_opportunities(self, lead_id: UUID) -> List[Opportunity]:
        """Get all opportunities for a lead."""
        return [o for o in self._opportunities.values() if o.lead_id == lead_id]
    
    async def get_pipeline_view(self) -> Dict[str, List[Opportunity]]:
        """Get opportunities grouped by stage."""
        pipeline: Dict[str, List[Opportunity]] = {
            stage.value: [] for stage in OpportunityStage
        }
        
        for opp in self._opportunities.values():
            stage_value = opp.stage.value if hasattr(opp.stage, 'value') else opp.stage
            if stage_value in pipeline:
                pipeline[stage_value].append(opp)
        
        return pipeline
    
    async def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        opportunities = list(self._opportunities.values())
        
        if not opportunities:
            return {
                "total_opportunities": 0,
                "total_value": 0,
                "weighted_value": 0,
                "by_stage": {}
            }
        
        total_value = sum(
            float(o.estimated_value) for o in opportunities 
            if o.estimated_value and not o.is_closed()
        )
        weighted_value = sum(
            float(o.weighted_value) for o in opportunities 
            if o.weighted_value and not o.is_closed()
        )
        
        by_stage = {}
        for stage in OpportunityStage:
            stage_opps = [o for o in opportunities if o.stage == stage]
            by_stage[stage.value] = {
                "count": len(stage_opps),
                "value": sum(float(o.estimated_value or 0) for o in stage_opps)
            }
        
        return {
            "total_opportunities": len(opportunities),
            "active_opportunities": sum(1 for o in opportunities if not o.is_closed()),
            "total_value": total_value,
            "weighted_value": weighted_value,
            "won_count": sum(1 for o in opportunities if o.stage == OpportunityStage.CLOSED_WON),
            "lost_count": sum(1 for o in opportunities if o.stage == OpportunityStage.CLOSED_LOST),
            "by_stage": by_stage
        }
    
    async def get_conversation_thread(self, thread_id: UUID) -> Optional[ConversationThread]:
        """Get a conversation thread by ID."""
        return self._threads.get(thread_id)
    
    async def get_lead_threads(self, lead_id: UUID) -> List[ConversationThread]:
        """Get all conversation threads for a lead."""
        threads = [t for t in self._threads.values() if t.lead_id == lead_id]
        return sorted(threads, key=lambda t: t.updated_at, reverse=True)
    
    async def get_thread_replies(self, thread_id: UUID) -> List[EmailReply]:
        """Get all replies in a thread."""
        replies = [r for r in self._replies.values() if r.thread_id == thread_id]
        return sorted(replies, key=lambda r: r.received_at)
    
    async def update_thread_status(self, thread_id: UUID, 
                                    status: ConversationStatus) -> Optional[ConversationThread]:
        """Update a thread's status."""
        thread = self._threads.get(thread_id)
        if thread:
            thread.status = status
            thread.updated_at = datetime.now()
        return thread
    
    async def set_follow_up_reminder(self, thread_id: UUID, 
                                      follow_up_at: datetime) -> Optional[ConversationThread]:
        """Set a follow-up reminder for a thread."""
        thread = self._threads.get(thread_id)
        if thread:
            thread.follow_up_at = follow_up_at
            thread.status = ConversationStatus.FOLLOW_UP_NEEDED
            thread.updated_at = datetime.now()
        return thread
    
    async def assign_thread(self, thread_id: UUID, 
                            user_id: str) -> Optional[ConversationThread]:
        """Assign a thread to a user."""
        thread = self._threads.get(thread_id)
        if thread:
            thread.assigned_to = user_id
            thread.assigned_at = datetime.now()
            thread.updated_at = datetime.now()
        return thread
    
    async def get_pending_follow_ups(self) -> List[ConversationThread]:
        """Get threads with pending follow-ups."""
        now = datetime.now()
        return [
            t for t in self._threads.values()
            if t.follow_up_at and t.follow_up_at <= now
            and t.status == ConversationStatus.FOLLOW_UP_NEEDED
        ]
    
    async def get_unread_replies(self) -> List[EmailReply]:
        """Get all unread replies."""
        return [r for r in self._replies.values() if not r.is_processed]
    
    async def mark_reply_processed(self, reply_id: UUID) -> Optional[EmailReply]:
        """Mark a reply as processed."""
        reply = self._replies.get(reply_id)
        if reply:
            reply.is_processed = True
            reply.processed_at = datetime.now()
        return reply

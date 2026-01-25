"""CRM and reply handling models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReplyClassification(str, Enum):
    """Classification of email replies."""
    POSITIVE = "positive"  # Interested
    NEGATIVE = "negative"  # Not interested
    NEUTRAL = "neutral"    # Questions, info requests
    OUT_OF_OFFICE = "out_of_office"
    WRONG_PERSON = "wrong_person"
    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    AUTO_REPLY = "auto_reply"
    UNKNOWN = "unknown"


class ConversationStatus(str, Enum):
    """Status of a conversation thread."""
    ACTIVE = "active"
    AWAITING_REPLY = "awaiting_reply"
    FOLLOW_UP_NEEDED = "follow_up_needed"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    ON_HOLD = "on_hold"


class OpportunityStage(str, Enum):
    """Pipeline stages for opportunities."""
    LEAD = "lead"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class NoteType(str, Enum):
    """Types of internal notes."""
    GENERAL = "general"
    CALL = "call"
    MEETING = "meeting"
    FOLLOW_UP = "follow_up"
    RESEARCH = "research"
    OBJECTION = "objection"
    ACTION_ITEM = "action_item"


class EmailReply(BaseModel):
    """Individual email reply record."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    email_campaign_id: UUID = Field(...)
    thread_id: UUID = Field(...)
    
    # Email content
    from_email: str = Field(..., max_length=255)
    from_name: Optional[str] = Field(None, max_length=200)
    subject: str = Field(..., max_length=500)
    body_text: str = Field(...)
    body_html: Optional[str] = None
    
    # Reply metadata
    received_at: datetime = Field(default_factory=datetime.now)
    message_id: Optional[str] = Field(None, max_length=255)
    in_reply_to: Optional[str] = Field(None, max_length=255)
    
    # Classification
    classification: ReplyClassification = Field(default=ReplyClassification.UNKNOWN)
    classification_confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    classification_model: Optional[str] = Field(None, max_length=50)
    is_manually_classified: bool = Field(default=False)
    
    # Sentiment (optional)
    sentiment_score: Optional[Decimal] = Field(None, ge=-1, le=1)  # -1 negative, 1 positive
    
    # Processing
    is_processed: bool = Field(default=False)
    processed_at: Optional[datetime] = None
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class ConversationThread(BaseModel):
    """Email conversation thread."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    
    # Thread info
    subject: str = Field(..., max_length=500)
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    
    # Messages
    message_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)
    last_message_at: Optional[datetime] = None
    last_reply_at: Optional[datetime] = None
    
    # Classification
    overall_sentiment: Optional[ReplyClassification] = None
    
    # Assignment
    assigned_to: Optional[str] = Field(None, max_length=100)
    assigned_at: Optional[datetime] = None
    
    # Reminders
    follow_up_at: Optional[datetime] = None
    
    # Audit
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class InternalNote(BaseModel):
    """Internal note on a lead or conversation."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    thread_id: Optional[UUID] = None
    
    # Note content
    note_type: NoteType = Field(default=NoteType.GENERAL)
    content: str = Field(..., min_length=1, max_length=5000)
    
    # Metadata
    is_pinned: bool = Field(default=False)
    is_private: bool = Field(default=False)  # Only visible to creator
    
    # Mentions (user IDs)
    mentions: List[str] = Field(default_factory=list)
    
    # Audit
    created_by: str = Field(..., max_length=100)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class Opportunity(BaseModel):
    """Sales opportunity/deal tracker."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    
    # Opportunity details
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    
    # Pipeline
    stage: OpportunityStage = Field(default=OpportunityStage.LEAD)
    previous_stage: Optional[OpportunityStage] = None
    stage_changed_at: Optional[datetime] = None
    
    # Value
    estimated_value: Optional[Decimal] = Field(None, ge=0)
    currency: str = Field(default="USD", max_length=3)
    probability: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    weighted_value: Optional[Decimal] = Field(None, ge=0)  # value * probability
    
    # Timeline
    expected_close_date: Optional[datetime] = None
    
    # Assignment
    owner: Optional[str] = Field(None, max_length=100)
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    
    # Win/Loss tracking
    closed_at: Optional[datetime] = None
    closed_reason: Optional[str] = Field(None, max_length=500)
    competitor: Optional[str] = Field(None, max_length=200)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    
    def is_closed(self) -> bool:
        """Check if opportunity is closed."""
        return self.stage in [OpportunityStage.CLOSED_WON, OpportunityStage.CLOSED_LOST]
    
    def calculate_weighted_value(self) -> Optional[Decimal]:
        """Calculate probability-weighted value."""
        if self.estimated_value:
            return self.estimated_value * self.probability
        return None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class LeadStatusTransition(BaseModel):
    """Record of lead status changes based on replies."""
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    trigger_reply_id: Optional[UUID] = None
    
    from_status: str = Field(..., max_length=50)
    to_status: str = Field(..., max_length=50)
    transition_reason: str = Field(..., max_length=500)
    
    is_automatic: bool = Field(default=True)
    actor: str = Field(default="system", max_length=100)
    
    transitioned_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class ReplyClassifyRequest(BaseModel):
    """Request to classify an email reply."""
    reply_id: UUID = Field(...)
    classification: ReplyClassification = Field(...)
    actor: str = Field(..., max_length=100)


class OpportunityCreate(BaseModel):
    """Create a new opportunity."""
    lead_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    estimated_value: Optional[Decimal] = Field(None, ge=0)
    expected_close_date: Optional[datetime] = None
    owner: Optional[str] = Field(None, max_length=100)
    created_by: str = Field(default="system", max_length=100)


class OpportunityUpdate(BaseModel):
    """Update an existing opportunity."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    stage: Optional[OpportunityStage] = None
    estimated_value: Optional[Decimal] = Field(None, ge=0)
    probability: Optional[Decimal] = Field(None, ge=0, le=1)
    expected_close_date: Optional[datetime] = None
    owner: Optional[str] = Field(None, max_length=100)
    closed_reason: Optional[str] = Field(None, max_length=500)


class NoteCreate(BaseModel):
    """Create an internal note."""
    lead_id: UUID = Field(...)
    thread_id: Optional[UUID] = None
    note_type: NoteType = Field(default=NoteType.GENERAL)
    content: str = Field(..., min_length=1, max_length=5000)
    is_pinned: bool = Field(default=False)
    created_by: str = Field(..., max_length=100)

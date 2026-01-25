"""Campaign intelligence models for multi-step email sequences."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SequenceStepType(str, Enum):
    """Types of sequence steps."""
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"
    BREAK_UP = "break_up"
    RE_ENGAGEMENT = "re_engagement"


class ConditionType(str, Enum):
    """Conditional branching types."""
    NO_REPLY = "no_reply"
    REPLIED = "replied"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    TIME_ELAPSED = "time_elapsed"


class SequenceStatus(str, Enum):
    """Status of an email sequence."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class LeadSequenceStatus(str, Enum):
    """Status of a lead within a sequence."""
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    PAUSED = "paused"
    REPLY_RECEIVED = "reply_received"
    COMPLETED = "completed"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    REMOVED = "removed"


class ConditionBranch(BaseModel):
    """Conditional branch definition."""
    condition: ConditionType
    wait_time_hours: Optional[int] = Field(None, ge=0)
    next_step_index: Optional[int] = None  # None means end sequence
    action: Optional[str] = Field(None, max_length=100)  # e.g., "pause", "notify"


class SequenceStep(BaseModel):
    """Individual step in an email sequence."""
    index: int = Field(..., ge=0)
    step_type: SequenceStepType
    
    # Timing
    delay_hours: int = Field(default=24, ge=0)  # Delay from previous step
    send_window_start: Optional[int] = Field(None, ge=0, le=23)  # Hour of day (UTC)
    send_window_end: Optional[int] = Field(None, ge=0, le=23)
    skip_weekends: bool = Field(default=True)
    
    # Content
    template_id: str = Field(..., max_length=100)
    subject_override: Optional[str] = Field(None, max_length=255)
    
    # Personalization tokens
    personalization_tokens: List[str] = Field(default_factory=list)
    
    # Conditional branches
    conditions: List[ConditionBranch] = Field(default_factory=list)
    
    # Metadata
    notes: str = Field(default="", max_length=500)


class EmailSequence(BaseModel):
    """Multi-step email sequence definition."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    
    # Status
    status: SequenceStatus = Field(default=SequenceStatus.ACTIVE)
    
    # Steps
    steps: List[SequenceStep] = Field(default_factory=list)
    
    # Settings
    auto_pause_on_reply: bool = Field(default=True)
    auto_pause_on_bounce: bool = Field(default=True)
    continue_on_open: bool = Field(default=True)
    max_leads_per_day: int = Field(default=50, ge=1)
    
    # Targeting
    target_lead_filter: Dict[str, Any] = Field(default_factory=dict)
    exclude_tags: List[str] = Field(default_factory=list)
    
    # Performance tracking
    total_enrolled: int = Field(default=0, ge=0)
    total_completed: int = Field(default=0, ge=0)
    total_replied: int = Field(default=0, ge=0)
    total_bounced: int = Field(default=0, ge=0)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    version: int = Field(default=1)
    
    def get_step_count(self) -> int:
        """Get total number of steps."""
        return len(self.steps)
    
    def get_next_step(self, current_index: int) -> Optional[SequenceStep]:
        """Get the next step in the sequence."""
        next_index = current_index + 1
        if next_index < len(self.steps):
            return self.steps[next_index]
        return None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class LeadSequenceEnrollment(BaseModel):
    """Tracks a lead's progress through a sequence."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    sequence_id: UUID = Field(...)
    
    # Progress
    current_step_index: int = Field(default=0, ge=0)
    status: LeadSequenceStatus = Field(default=LeadSequenceStatus.ENROLLED)
    
    # Timing
    enrolled_at: datetime = Field(default_factory=datetime.now)
    next_step_scheduled: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Response tracking
    total_emails_sent: int = Field(default=0, ge=0)
    total_opens: int = Field(default=0, ge=0)
    total_clicks: int = Field(default=0, ge=0)
    last_email_sent_at: Optional[datetime] = None
    last_open_at: Optional[datetime] = None
    last_click_at: Optional[datetime] = None
    
    # Reply handling
    reply_received_at: Optional[datetime] = None
    reply_email_id: Optional[UUID] = None
    
    # Exit tracking
    exit_reason: Optional[str] = Field(None, max_length=500)
    exit_step_index: Optional[int] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def is_active(self) -> bool:
        """Check if enrollment is active."""
        return self.status in [
            LeadSequenceStatus.ENROLLED,
            LeadSequenceStatus.IN_PROGRESS,
            LeadSequenceStatus.WAITING
        ]
    
    def should_pause_on_reply(self) -> bool:
        """Check if sequence should pause on reply."""
        return self.status in [
            LeadSequenceStatus.ENROLLED,
            LeadSequenceStatus.IN_PROGRESS,
            LeadSequenceStatus.WAITING
        ]
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class PersonalizationToken(BaseModel):
    """Token for email personalization from enrichment data."""
    name: str = Field(..., max_length=50)  # e.g., "company_tech_stack"
    source: str = Field(..., max_length=50)  # e.g., "enrichment", "lead", "custom"
    path: str = Field(..., max_length=200)  # e.g., "enrichment.tech_stack[0].name"
    default_value: Optional[str] = Field(None, max_length=500)
    transform: Optional[str] = Field(None, max_length=100)  # e.g., "title_case", "lowercase"


class SequenceCreate(BaseModel):
    """Create a new email sequence."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    steps: List[SequenceStep] = Field(default_factory=list)
    auto_pause_on_reply: bool = Field(default=True)
    max_leads_per_day: int = Field(default=50, ge=1)
    created_by: str = Field(default="system", max_length=100)


class SequenceUpdate(BaseModel):
    """Update an existing sequence."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[SequenceStatus] = None
    steps: Optional[List[SequenceStep]] = None
    auto_pause_on_reply: Optional[bool] = None
    max_leads_per_day: Optional[int] = Field(None, ge=1)


class EnrollLeadRequest(BaseModel):
    """Request to enroll a lead in a sequence."""
    lead_id: UUID = Field(...)
    sequence_id: UUID = Field(...)
    skip_to_step: Optional[int] = Field(None, ge=0)
    schedule_delay_hours: Optional[int] = Field(None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

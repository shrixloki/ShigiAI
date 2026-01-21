"""Email campaign domain model with state tracking."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EmailState(str, Enum):
    """Email delivery states."""
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CampaignType(str, Enum):
    """Types of email campaigns."""
    INITIAL = "initial"
    FOLLOWUP_1 = "followup_1"
    FOLLOWUP_2 = "followup_2"
    FOLLOWUP_3 = "followup_3"
    CUSTOM = "custom"


class EmailCampaign(BaseModel):
    """Production-grade email campaign model."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    
    # Campaign details
    campaign_type: CampaignType = Field(...)
    template_id: Optional[str] = Field(None, max_length=100)
    
    # Email content
    subject: str = Field(..., min_length=1, max_length=255)
    body_text: str = Field(..., min_length=1)
    body_html: Optional[str] = None
    
    # Recipients
    to_email: str = Field(..., max_length=255)
    to_name: Optional[str] = Field(None, max_length=255)
    from_email: str = Field(..., max_length=255)
    from_name: str = Field(..., max_length=255)
    
    # State tracking
    email_state: EmailState = Field(default=EmailState.QUEUED)
    
    # Delivery tracking
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    
    # Error tracking
    error_count: int = Field(default=0)
    last_error: Optional[str] = Field(None, max_length=1000)
    retry_after: Optional[datetime] = None
    
    # Delivery metadata
    message_id: Optional[str] = Field(None, max_length=255)
    provider_response: Dict[str, Any] = Field(default_factory=dict)
    delivery_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit fields
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def can_transition_to(self, target_state: EmailState) -> bool:
        """Check if transition to target state is valid."""
        valid_transitions = {
            EmailState.QUEUED: [EmailState.SENDING, EmailState.CANCELLED, EmailState.FAILED],
            EmailState.SENDING: [EmailState.SENT, EmailState.FAILED],
            EmailState.SENT: [EmailState.DELIVERED, EmailState.BOUNCED, EmailState.FAILED],
            EmailState.DELIVERED: [EmailState.OPENED, EmailState.REPLIED],
            EmailState.OPENED: [EmailState.CLICKED, EmailState.REPLIED],
            EmailState.CLICKED: [EmailState.REPLIED],
            EmailState.REPLIED: [],  # Terminal state
            EmailState.BOUNCED: [],  # Terminal state
            EmailState.FAILED: [EmailState.QUEUED],  # Can retry
            EmailState.CANCELLED: []  # Terminal state
        }
        
        return target_state in valid_transitions.get(self.email_state, [])
    
    def is_terminal_state(self) -> bool:
        """Check if email is in a terminal state."""
        terminal_states = {
            EmailState.REPLIED,
            EmailState.BOUNCED,
            EmailState.CANCELLED
        }
        return self.email_state in terminal_states
    
    def can_retry(self) -> bool:
        """Check if email can be retried."""
        return (
            self.email_state == EmailState.FAILED and
            self.error_count < 3 and
            (self.retry_after is None or self.retry_after <= datetime.now())
        )
    
    def get_delivery_duration(self) -> Optional[float]:
        """Get delivery duration in seconds."""
        if self.queued_at and self.delivered_at:
            return (self.delivered_at - self.queued_at).total_seconds()
        return None
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class EmailCampaignCreate(BaseModel):
    """Model for creating new email campaigns."""
    lead_id: UUID = Field(...)
    campaign_type: CampaignType = Field(...)
    template_id: Optional[str] = Field(None, max_length=100)
    subject: str = Field(..., min_length=1, max_length=255)
    body_text: str = Field(..., min_length=1)
    body_html: Optional[str] = None
    to_email: str = Field(..., max_length=255)
    to_name: Optional[str] = Field(None, max_length=255)
    from_email: str = Field(..., max_length=255)
    from_name: str = Field(..., max_length=255)


class EmailCampaignUpdate(BaseModel):
    """Model for updating email campaigns."""
    email_state: Optional[EmailState] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    error_count: Optional[int] = None
    last_error: Optional[str] = Field(None, max_length=1000)
    retry_after: Optional[datetime] = None
    message_id: Optional[str] = Field(None, max_length=255)
    provider_response: Optional[Dict[str, Any]] = None
    delivery_metadata: Optional[Dict[str, Any]] = None


class EmailFilter(BaseModel):
    """Model for filtering email campaigns."""
    lead_id: Optional[UUID] = None
    campaign_type: Optional[CampaignType] = None
    email_state: Optional[EmailState] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    has_errors: Optional[bool] = None
    can_retry: Optional[bool] = None
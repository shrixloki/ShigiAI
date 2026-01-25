"""Compliance and risk control models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UnsubscribeSource(str, Enum):
    """Source of unsubscribe request."""
    EMAIL_LINK = "email_link"
    REPLY = "reply"
    MANUAL = "manual"
    API = "api"
    IMPORT = "import"


class DoNotContactReason(str, Enum):
    """Reason for do-not-contact designation."""
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    LEGAL_REQUEST = "legal_request"
    COMPETITOR = "competitor"
    BAD_DATA = "bad_data"
    INTERNAL_POLICY = "internal_policy"
    OTHER = "other"


class SpamRiskLevel(str, Enum):
    """Spam risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DomainWarmupStage(str, Enum):
    """Domain warmup stages."""
    COLD = "cold"
    WARMING = "warming"
    WARM = "warm"
    HOT = "hot"


class UnsubscribeRecord(BaseModel):
    """Record of unsubscribe request."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Contact info
    email: str = Field(..., max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    lead_id: Optional[UUID] = None
    
    # Unsubscribe details
    source: UnsubscribeSource
    campaign_id: Optional[UUID] = None
    email_id: Optional[UUID] = None
    
    # Confirmation
    confirmation_sent: bool = Field(default=False)
    confirmation_sent_at: Optional[datetime] = None
    
    # Audit
    unsubscribed_at: datetime = Field(default_factory=datetime.now)
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class DoNotContactEntry(BaseModel):
    """Do-not-contact registry entry."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Contact info (at least one required)
    email: Optional[str] = Field(None, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    company_name: Optional[str] = Field(None, max_length=255)
    
    # Classification
    reason: DoNotContactReason
    reason_detail: Optional[str] = Field(None, max_length=1000)
    
    # Source
    source_lead_id: Optional[UUID] = None
    source_campaign_id: Optional[UUID] = None
    source_reference: Optional[str] = Field(None, max_length=255)
    
    # Validity
    is_permanent: bool = Field(default=True)
    expires_at: Optional[datetime] = None
    
    # Status
    is_active: bool = Field(default=True)
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = Field(None, max_length=100)
    deactivation_reason: Optional[str] = Field(None, max_length=500)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    
    def is_valid(self) -> bool:
        """Check if entry is currently valid."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True
    
    def matches_email(self, email: str) -> bool:
        """Check if email matches this entry."""
        email = email.lower()
        if self.email and self.email.lower() == email:
            return True
        if self.domain:
            email_domain = email.split('@')[-1] if '@' in email else ''
            if email_domain.lower() == self.domain.lower():
                return True
        return False
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class SpamRiskAssessment(BaseModel):
    """Spam risk assessment for sending."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Context
    sender_email: str = Field(..., max_length=255)
    sender_domain: str = Field(..., max_length=255)
    
    # Risk scores
    overall_risk: SpamRiskLevel
    content_risk_score: Decimal = Field(..., ge=0, le=1)
    volume_risk_score: Decimal = Field(..., ge=0, le=1)
    reputation_risk_score: Decimal = Field(..., ge=0, le=1)
    engagement_risk_score: Decimal = Field(..., ge=0, le=1)
    
    # Risk factors
    risk_factors: List[str] = Field(default_factory=list)
    mitigation_suggestions: List[str] = Field(default_factory=list)
    
    # Metrics used for calculation
    metrics: Dict[str, Any] = Field(default_factory=dict)
    
    # Assessment timing
    assessed_at: datetime = Field(default_factory=datetime.now)
    valid_until: datetime = Field(...)
    
    def is_valid(self) -> bool:
        """Check if assessment is still valid."""
        return datetime.now() < self.valid_until
    
    def should_pause_sending(self) -> bool:
        """Check if sending should be paused."""
        return self.overall_risk in [SpamRiskLevel.HIGH, SpamRiskLevel.CRITICAL]
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class DomainWarmupStatus(BaseModel):
    """Domain warmup tracking."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    domain: str = Field(..., max_length=255)
    
    # Warmup stage
    stage: DomainWarmupStage = Field(default=DomainWarmupStage.COLD)
    warmup_started_at: Optional[datetime] = None
    stage_started_at: Optional[datetime] = None
    
    # Daily limits based on stage
    current_daily_limit: int = Field(default=10, ge=0)
    target_daily_limit: int = Field(default=100, ge=0)
    
    # Tracking
    total_emails_sent: int = Field(default=0, ge=0)
    emails_sent_today: int = Field(default=0, ge=0)
    last_email_sent_at: Optional[datetime] = None
    
    # Reputation metrics
    bounce_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    spam_complaint_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    open_rate: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    
    # Health
    is_healthy: bool = Field(default=True)
    health_issues: List[str] = Field(default_factory=list)
    last_health_check: Optional[datetime] = None
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def can_send(self) -> bool:
        """Check if domain can send more emails today."""
        return self.is_healthy and self.emails_sent_today < self.current_daily_limit
    
    def get_remaining_today(self) -> int:
        """Get remaining emails allowed today."""
        return max(0, self.current_daily_limit - self.emails_sent_today)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class CoolingOffPeriod(BaseModel):
    """Cooling-off period between contacts."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Target
    lead_id: Optional[UUID] = None
    domain: Optional[str] = Field(None, max_length=255)
    
    # Period
    started_at: datetime = Field(default_factory=datetime.now)
    ends_at: datetime = Field(...)
    duration_hours: int = Field(..., ge=1)
    
    # Reason
    reason: str = Field(..., max_length=500)
    triggered_by: str = Field(default="system", max_length=100)
    
    # Status
    is_active: bool = Field(default=True)
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = Field(None, max_length=100)
    
    def is_in_effect(self) -> bool:
        """Check if cooling-off period is currently active."""
        if not self.is_active:
            return False
        return datetime.now() < self.ends_at
    
    def get_remaining_hours(self) -> int:
        """Get remaining hours in cooling-off period."""
        if not self.is_in_effect():
            return 0
        remaining = (self.ends_at - datetime.now()).total_seconds() / 3600
        return max(0, int(remaining))
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class ComplianceCheck(BaseModel):
    """Pre-send compliance check result."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    email: str = Field(..., max_length=255)
    
    # Check results
    is_compliant: bool = Field(default=True)
    checks_performed: List[str] = Field(default_factory=list)
    failed_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Blocking reasons
    is_unsubscribed: bool = Field(default=False)
    is_do_not_contact: bool = Field(default=False)
    is_in_cooling_off: bool = Field(default=False)
    is_domain_blocked: bool = Field(default=False)
    daily_limit_reached: bool = Field(default=False)
    
    # Risk assessment
    spam_risk: Optional[SpamRiskLevel] = None
    
    # Timing
    checked_at: datetime = Field(default_factory=datetime.now)
    
    def can_send(self) -> bool:
        """Check if email can be sent."""
        return (
            self.is_compliant and
            not self.is_unsubscribed and
            not self.is_do_not_contact and
            not self.is_in_cooling_off and
            not self.is_domain_blocked and
            not self.daily_limit_reached
        )
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class AddToDoNotContactRequest(BaseModel):
    """Request to add entry to do-not-contact list."""
    email: Optional[str] = Field(None, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    reason: DoNotContactReason
    reason_detail: Optional[str] = Field(None, max_length=1000)
    is_permanent: bool = Field(default=True)
    expires_at: Optional[datetime] = None


class RemoveFromDoNotContactRequest(BaseModel):
    """Request to remove entry from do-not-contact list."""
    entry_id: UUID = Field(...)
    reason: str = Field(..., min_length=10, max_length=500)


class StartCoolingOffRequest(BaseModel):
    """Request to start cooling-off period."""
    lead_id: Optional[UUID] = None
    domain: Optional[str] = Field(None, max_length=255)
    duration_hours: int = Field(..., ge=1, le=720)  # Max 30 days
    reason: str = Field(..., max_length=500)

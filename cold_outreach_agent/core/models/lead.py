"""Lead domain model with proper state management."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class LeadState(str, Enum):
    """Lead lifecycle states."""
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
    """Human review status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DiscoverySource(str, Enum):
    """Source of lead discovery."""
    GOOGLE_MAPS = "google_maps"
    MANUAL_IMPORT = "manual_import"
    CSV_IMPORT = "csv_import"
    API_IMPORT = "api_import"
    REFERRAL = "referral"


class Lead(BaseModel):
    """Production-grade lead model with full state tracking."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Business information
    business_name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    location: str = Field(..., min_length=1, max_length=255)
    
    # Contact information
    maps_url: Optional[str] = Field(None, max_length=1000)
    website_url: Optional[str] = Field(None, max_length=1000)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    
    # Discovery metadata
    discovery_source: DiscoverySource = Field(...)
    discovery_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    discovery_metadata: Dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=datetime.now)
    
    # State tracking
    lifecycle_state: LeadState = Field(default=LeadState.DISCOVERED)
    review_status: ReviewStatus = Field(default=ReviewStatus.PENDING)
    
    # Classification
    tag: Optional[str] = Field(None, max_length=50)
    quality_score: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Audit fields
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: int = Field(default=1)
    
    # Notes and metadata
    notes: str = Field(default="", max_length=2000)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v
    
    @validator('website_url')
    def validate_website_url(cls, v):
        """Normalize website URL."""
        if not v:
            return v
        if not v.startswith(('http://', 'https://')):
            return f'https://{v}'
        return v
    
    def can_transition_to(self, target_state: LeadState) -> bool:
        """Check if transition to target state is valid."""
        valid_transitions = {
            LeadState.DISCOVERED: [LeadState.ANALYZING, LeadState.FAILED],
            LeadState.ANALYZING: [LeadState.ANALYZED, LeadState.FAILED],
            LeadState.ANALYZED: [LeadState.PENDING_REVIEW, LeadState.FAILED],
            LeadState.PENDING_REVIEW: [LeadState.APPROVED, LeadState.REJECTED, LeadState.EXPIRED],
            LeadState.APPROVED: [LeadState.READY_FOR_OUTREACH],
            LeadState.REJECTED: [],  # Terminal state
            LeadState.READY_FOR_OUTREACH: [],  # Managed by email system
            LeadState.FAILED: [LeadState.DISCOVERED],  # Can retry
            LeadState.EXPIRED: [LeadState.PENDING_REVIEW]  # Can re-review
        }
        
        return target_state in valid_transitions.get(self.lifecycle_state, [])
    
    def is_ready_for_outreach(self) -> bool:
        """Check if lead is ready for email outreach."""
        return (
            self.lifecycle_state == LeadState.APPROVED and
            self.review_status == ReviewStatus.APPROVED and
            self.email is not None and
            self.email != ""
        )
    
    def get_display_name(self) -> str:
        """Get human-readable display name."""
        return f"{self.business_name} ({self.location})"
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class LeadCreate(BaseModel):
    """Model for creating new leads."""
    business_name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    location: str = Field(..., min_length=1, max_length=255)
    maps_url: Optional[str] = Field(None, max_length=1000)
    website_url: Optional[str] = Field(None, max_length=1000)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    discovery_source: DiscoverySource = Field(...)
    discovery_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    discovery_metadata: Dict[str, Any] = Field(default_factory=dict)
    tag: Optional[str] = Field(None, max_length=50)
    notes: str = Field(default="", max_length=2000)


class LeadUpdate(BaseModel):
    """Model for updating existing leads."""
    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, min_length=1, max_length=255)
    website_url: Optional[str] = Field(None, max_length=1000)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    tag: Optional[str] = Field(None, max_length=50)
    quality_score: Optional[Decimal] = Field(None, ge=0, le=1)
    notes: Optional[str] = Field(None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None


class LeadFilter(BaseModel):
    """Model for filtering leads."""
    lifecycle_state: Optional[LeadState] = None
    review_status: Optional[ReviewStatus] = None
    discovery_source: Optional[DiscoverySource] = None
    category: Optional[str] = None
    tag: Optional[str] = None
    has_email: Optional[bool] = None
    has_website: Optional[bool] = None
    min_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
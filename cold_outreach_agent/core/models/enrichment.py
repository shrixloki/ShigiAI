"""Lead enrichment domain models with state tracking and confidence scoring."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class EnrichmentState(str, Enum):
    """Enrichment pipeline states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    STALE = "stale"


class EnrichmentSource(str, Enum):
    """Source of enrichment data."""
    WEBSITE_CRAWL = "website_crawl"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    GITHUB = "github"
    MANUAL = "manual"
    API = "api"


class BusinessMaturity(str, Enum):
    """Business maturity stage classification."""
    IDEA = "idea"
    MVP = "mvp"
    EARLY_STAGE = "early_stage"
    SCALING = "scaling"
    MATURE = "mature"
    ENTERPRISE = "enterprise"
    UNKNOWN = "unknown"


class CompanySize(str, Enum):
    """Estimated company size."""
    SOLO = "1"
    SMALL = "2-10"
    MEDIUM = "11-50"
    LARGE = "51-200"
    ENTERPRISE = "201-1000"
    CORPORATION = "1000+"
    UNKNOWN = "unknown"


class TechStackCategory(str, Enum):
    """Technology stack categories."""
    FRONTEND = "frontend"
    BACKEND = "backend"
    CMS = "cms"
    ECOMMERCE = "ecommerce"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    HOSTING = "hosting"
    PAYMENT = "payment"
    OTHER = "other"


class TechStackItem(BaseModel):
    """Individual technology detection."""
    name: str = Field(..., max_length=100)
    category: TechStackCategory
    version: Optional[str] = Field(None, max_length=50)
    confidence: Decimal = Field(default=Decimal("0.8"), ge=0, le=1)
    detected_at: datetime = Field(default_factory=datetime.now)
    source_url: Optional[str] = Field(None, max_length=1000)


class HiringSignal(BaseModel):
    """Detected hiring/careers signal."""
    role_type: str = Field(..., max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    seniority: Optional[str] = Field(None, max_length=50)
    detected_at: datetime = Field(default_factory=datetime.now)
    source_url: str = Field(..., max_length=1000)
    is_active: bool = Field(default=True)


class ContactIntentSignal(BaseModel):
    """Detected contact intent signals."""
    signal_type: str = Field(..., max_length=100)  # form, cta, chat, phone, etc.
    description: str = Field(..., max_length=500)
    location_on_page: Optional[str] = Field(None, max_length=200)
    source_url: str = Field(..., max_length=1000)
    detected_at: datetime = Field(default_factory=datetime.now)


class SocialPresence(BaseModel):
    """Social media presence data."""
    platform: str = Field(..., max_length=50)  # linkedin, twitter, github, etc.
    profile_url: Optional[str] = Field(None, max_length=1000)
    handle: Optional[str] = Field(None, max_length=100)
    follower_count: Optional[int] = Field(None, ge=0)
    is_verified: bool = Field(default=False)
    last_activity: Optional[datetime] = None
    activity_score: Optional[Decimal] = Field(None, ge=0, le=1)
    detected_at: datetime = Field(default_factory=datetime.now)


class DecisionMaker(BaseModel):
    """Extracted decision-maker information."""
    name: Optional[str] = Field(None, max_length=200)
    title: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    linkedin_url: Optional[str] = Field(None, max_length=1000)
    confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    source: EnrichmentSource
    detected_at: datetime = Field(default_factory=datetime.now)


class LeadEnrichment(BaseModel):
    """Full lead enrichment data with state tracking."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    
    # State tracking
    enrichment_state: EnrichmentState = Field(default=EnrichmentState.PENDING)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.now)
    
    # Retry handling
    attempt_count: int = Field(default=0, ge=0)
    last_error: Optional[str] = Field(None, max_length=1000)
    retry_after: Optional[datetime] = None
    
    # Tech Stack Detection
    tech_stack: List[TechStackItem] = Field(default_factory=list)
    tech_stack_score: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Hiring/Career Signals
    hiring_signals: List[HiringSignal] = Field(default_factory=list)
    is_hiring: bool = Field(default=False)
    hiring_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Contact Intent
    contact_signals: List[ContactIntentSignal] = Field(default_factory=list)
    has_contact_form: bool = Field(default=False)
    has_live_chat: bool = Field(default=False)
    contact_intent_score: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Social Presence
    social_presences: List[SocialPresence] = Field(default_factory=list)
    social_score: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Business Classification
    business_maturity: BusinessMaturity = Field(default=BusinessMaturity.UNKNOWN)
    company_size: CompanySize = Field(default=CompanySize.UNKNOWN)
    maturity_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Decision Makers
    decision_makers: List[DecisionMaker] = Field(default_factory=list)
    primary_contact: Optional[DecisionMaker] = None
    
    # Overall Enrichment Score
    enrichment_confidence: Decimal = Field(default=Decimal("0.0"), ge=0, le=1)
    data_freshness_score: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Metadata
    enrichment_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    version: int = Field(default=1)
    
    def is_stale(self, max_age_days: int = 30) -> bool:
        """Check if enrichment data is stale."""
        if not self.completed_at:
            return True
        age = (datetime.now() - self.completed_at).days
        return age > max_age_days
    
    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if enrichment can be retried."""
        if self.enrichment_state not in [EnrichmentState.FAILED, EnrichmentState.PARTIAL]:
            return False
        if self.attempt_count >= max_retries:
            return False
        if self.retry_after and self.retry_after > datetime.now():
            return False
        return True
    
    def get_enrichment_summary(self) -> Dict[str, Any]:
        """Get summary of enrichment data for display."""
        return {
            "state": self.enrichment_state.value,
            "tech_count": len(self.tech_stack),
            "is_hiring": self.is_hiring,
            "hiring_roles": [h.role_type for h in self.hiring_signals[:3]],
            "social_platforms": [s.platform for s in self.social_presences],
            "business_maturity": self.business_maturity.value,
            "company_size": self.company_size.value,
            "decision_makers_count": len(self.decision_makers),
            "confidence": float(self.enrichment_confidence),
            "is_stale": self.is_stale()
        }
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class EnrichmentCreate(BaseModel):
    """Model for initiating lead enrichment."""
    lead_id: UUID = Field(...)
    sources: List[EnrichmentSource] = Field(
        default=[EnrichmentSource.WEBSITE_CRAWL]
    )
    priority: int = Field(default=5, ge=1, le=10)


class EnrichmentUpdate(BaseModel):
    """Model for updating enrichment data."""
    enrichment_state: Optional[EnrichmentState] = None
    tech_stack: Optional[List[TechStackItem]] = None
    hiring_signals: Optional[List[HiringSignal]] = None
    contact_signals: Optional[List[ContactIntentSignal]] = None
    social_presences: Optional[List[SocialPresence]] = None
    decision_makers: Optional[List[DecisionMaker]] = None
    business_maturity: Optional[BusinessMaturity] = None
    company_size: Optional[CompanySize] = None
    enrichment_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    last_error: Optional[str] = Field(None, max_length=1000)

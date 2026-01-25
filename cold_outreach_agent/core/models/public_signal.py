"""Public signal - Looking for Developer system models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class RoleType(str, Enum):
    """Types of developer roles sought."""
    FULL_STACK = "full_stack"
    FRONTEND = "frontend"
    BACKEND = "backend"
    MOBILE = "mobile"
    DEVOPS = "devops"
    DATA_ENGINEER = "data_engineer"
    ML_ENGINEER = "ml_engineer"
    WEB_DESIGNER = "web_designer"
    UI_UX = "ui_ux"
    WORDPRESS = "wordpress"
    SHOPIFY = "shopify"
    CUSTOM = "custom"


class EngagementType(str, Enum):
    """Types of engagement."""
    PROJECT = "project"          # One-time project
    RETAINER = "retainer"        # Ongoing monthly
    FULL_TIME = "full_time"      # Full-time hire
    PART_TIME = "part_time"      # Part-time
    CONTRACT = "contract"        # Fixed-term contract
    FREELANCE = "freelance"      # Freelance/gig


class BudgetRange(str, Enum):
    """Budget ranges for projects."""
    UNDER_1K = "under_1k"
    K1_5K = "1k_5k"
    K5_10K = "5k_10k"
    K10_25K = "10k_25k"
    K25_50K = "25k_50k"
    K50_100K = "50k_100k"
    ABOVE_100K = "100k_plus"
    NEGOTIABLE = "negotiable"


class ProfileStatus(str, Enum):
    """Status of business profile."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class ApprovalDecision(str, Enum):
    """Approval workflow decisions."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


class BusinessProfile(BaseModel):
    """Public business profile for developer matching."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: Optional[UUID] = None  # Link to existing lead if applicable
    
    # Business information
    business_name: str = Field(..., min_length=2, max_length=200)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    website_url: Optional[str] = Field(None, max_length=1000)
    location: str = Field(..., min_length=2, max_length=200)
    timezone: Optional[str] = Field(None, max_length=50)
    
    # Contact information
    contact_name: str = Field(..., min_length=2, max_length=200)
    contact_email: str = Field(..., max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    preferred_contact_method: str = Field(default="email", max_length=20)
    
    # Looking for Developer toggle
    is_looking_for_developer: bool = Field(default=True)
    looking_since: Optional[datetime] = None
    
    # Requirements (when looking for developer)
    role_types: List[RoleType] = Field(default_factory=list)
    custom_role_description: Optional[str] = Field(None, max_length=500)
    
    budget_range: Optional[BudgetRange] = None
    budget_notes: Optional[str] = Field(None, max_length=500)
    
    engagement_type: Optional[EngagementType] = None
    expected_duration: Optional[str] = Field(None, max_length=100)
    
    # Project details
    project_description: Optional[str] = Field(None, max_length=5000)
    required_skills: List[str] = Field(default_factory=list)
    preferred_technologies: List[str] = Field(default_factory=list)
    
    # Availability
    start_date_preference: Optional[str] = Field(None, max_length=100)  # e.g., "ASAP", "Q1 2024"
    urgency_level: int = Field(default=3, ge=1, le=5)  # 1-5 scale
    
    # Status and approval
    status: ProfileStatus = Field(default=ProfileStatus.DRAFT)
    is_featured: bool = Field(default=False)
    is_searchable: bool = Field(default=True)  # Appears in directory
    
    # Approval tracking
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = Field(None, max_length=100)
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    
    # Engagement tracking
    view_count: int = Field(default=0, ge=0)
    inquiry_count: int = Field(default=0, ge=0)
    last_viewed_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None  # Profile listing expiration
    
    @validator('contact_email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()
    
    def is_active(self) -> bool:
        """Check if profile is currently active and searchable."""
        if self.status != ProfileStatus.APPROVED:
            return False
        if not self.is_looking_for_developer:
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True
    
    def get_public_summary(self) -> Dict[str, Any]:
        """Get public-safe profile summary."""
        return {
            "id": str(self.id),
            "business_name": self.business_name,
            "industry": self.industry,
            "location": self.location,
            "role_types": [r.value if hasattr(r, 'value') else r for r in self.role_types],
            "budget_range": self.budget_range.value if self.budget_range else None,
            "engagement_type": self.engagement_type.value if self.engagement_type else None,
            "required_skills": self.required_skills[:5],  # Limit for preview
            "urgency_level": self.urgency_level,
            "is_featured": self.is_featured,
            "created_at": self.created_at.isoformat()
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: float(v)
        }


class DeveloperInquiry(BaseModel):
    """Inbound inquiry from a developer."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID = Field(...)  # Business profile being contacted
    
    # Developer info
    developer_name: str = Field(..., min_length=2, max_length=200)
    developer_email: str = Field(..., max_length=255)
    developer_phone: Optional[str] = Field(None, max_length=50)
    developer_website: Optional[str] = Field(None, max_length=1000)
    developer_linkedin: Optional[str] = Field(None, max_length=500)
    developer_github: Optional[str] = Field(None, max_length=500)
    
    # Inquiry content
    message: str = Field(..., min_length=20, max_length=5000)
    proposed_rate: Optional[str] = Field(None, max_length=100)
    availability: Optional[str] = Field(None, max_length=200)
    
    # Skills and experience
    relevant_skills: List[str] = Field(default_factory=list)
    years_experience: Optional[int] = Field(None, ge=0, le=50)
    portfolio_links: List[str] = Field(default_factory=list)
    
    # Status
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = None
    is_replied: bool = Field(default=False)
    replied_at: Optional[datetime] = None
    is_archived: bool = Field(default=False)
    
    # Lead capture
    captured_as_lead: bool = Field(default=False)
    captured_lead_id: Optional[UUID] = None
    
    # Audit
    submitted_at: datetime = Field(default_factory=datetime.now)
    source_ip: Optional[str] = Field(None, max_length=45)
    source_referrer: Optional[str] = Field(None, max_length=1000)
    
    @validator('developer_email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class ProfileApprovalRecord(BaseModel):
    """Record of profile approval decision."""
    
    id: UUID = Field(default_factory=uuid4)
    profile_id: UUID = Field(...)
    
    decision: ApprovalDecision
    reason: Optional[str] = Field(None, max_length=1000)
    changes_requested: Optional[List[str]] = None
    
    decided_by: str = Field(..., max_length=100)
    decided_at: datetime = Field(default_factory=datetime.now)
    
    previous_status: ProfileStatus
    new_status: ProfileStatus
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class DirectorySearchFilters(BaseModel):
    """Filters for searching the public directory."""
    
    # Text search
    query: Optional[str] = Field(None, max_length=200)
    
    # Filters
    role_types: Optional[List[RoleType]] = None
    budget_ranges: Optional[List[BudgetRange]] = None
    engagement_types: Optional[List[EngagementType]] = None
    industries: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    
    # Urgency
    min_urgency: Optional[int] = Field(None, ge=1, le=5)
    
    # Sorting
    sort_by: str = Field(default="created_at", max_length=50)
    sort_order: str = Field(default="desc", max_length=10)
    
    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    
    # Flags
    featured_only: bool = Field(default=False)


class DirectoryEntry(BaseModel):
    """Public directory entry (profile summary for listing)."""
    
    id: UUID
    business_name: str
    industry: Optional[str]
    location: str
    role_types: List[str]
    budget_range: Optional[str]
    engagement_type: Optional[str]
    required_skills: List[str]
    urgency_level: int
    is_featured: bool
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class ProfileCreateRequest(BaseModel):
    """Request to create a business profile."""
    business_name: str = Field(..., min_length=2, max_length=200)
    industry: Optional[str] = Field(None, max_length=100)
    website_url: Optional[str] = Field(None, max_length=1000)
    location: str = Field(..., min_length=2, max_length=200)
    contact_name: str = Field(..., min_length=2, max_length=200)
    contact_email: str = Field(..., max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    role_types: List[RoleType] = Field(default_factory=list)
    budget_range: Optional[BudgetRange] = None
    engagement_type: Optional[EngagementType] = None
    project_description: Optional[str] = Field(None, max_length=5000)
    required_skills: List[str] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    """Request to update a business profile."""
    is_looking_for_developer: Optional[bool] = None
    role_types: Optional[List[RoleType]] = None
    budget_range: Optional[BudgetRange] = None
    engagement_type: Optional[EngagementType] = None
    project_description: Optional[str] = Field(None, max_length=5000)
    required_skills: Optional[List[str]] = None
    urgency_level: Optional[int] = Field(None, ge=1, le=5)
    is_searchable: Optional[bool] = None


class SendInquiryRequest(BaseModel):
    """Request to send an inquiry to a business."""
    profile_id: UUID = Field(...)
    developer_name: str = Field(..., min_length=2, max_length=200)
    developer_email: str = Field(..., max_length=255)
    message: str = Field(..., min_length=20, max_length=5000)
    relevant_skills: List[str] = Field(default_factory=list)
    portfolio_links: List[str] = Field(default_factory=list)

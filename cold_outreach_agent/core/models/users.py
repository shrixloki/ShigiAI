"""Multi-user role system and access control models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "admin"           # Full system access
    REVIEWER = "reviewer"     # Can review and approve leads
    SENDER = "sender"         # Can send emails, view leads
    VIEWER = "viewer"         # Read-only access


class Permission(str, Enum):
    """Granular permissions."""
    # Lead permissions
    LEAD_VIEW = "lead:view"
    LEAD_CREATE = "lead:create"
    LEAD_UPDATE = "lead:update"
    LEAD_DELETE = "lead:delete"
    LEAD_APPROVE = "lead:approve"
    LEAD_REJECT = "lead:reject"
    LEAD_ASSIGN = "lead:assign"
    
    # Email permissions
    EMAIL_VIEW = "email:view"
    EMAIL_SEND = "email:send"
    EMAIL_TEMPLATE_EDIT = "email:template_edit"
    
    # Campaign permissions
    CAMPAIGN_VIEW = "campaign:view"
    CAMPAIGN_CREATE = "campaign:create"
    CAMPAIGN_UPDATE = "campaign:update"
    CAMPAIGN_DELETE = "campaign:delete"
    
    # Discovery permissions
    DISCOVERY_START = "discovery:start"
    DISCOVERY_STOP = "discovery:stop"
    
    # System permissions
    SYSTEM_VIEW = "system:view"
    SYSTEM_CONFIG = "system:config"
    SYSTEM_EXPORT = "system:export"
    SYSTEM_IMPORT = "system:import"
    
    # User permissions
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # Analytics permissions
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"


# Role to permission mapping
ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: list(Permission),  # All permissions
    
    UserRole.REVIEWER: [
        Permission.LEAD_VIEW, Permission.LEAD_APPROVE, Permission.LEAD_REJECT,
        Permission.EMAIL_VIEW, Permission.CAMPAIGN_VIEW,
        Permission.SYSTEM_VIEW, Permission.ANALYTICS_VIEW
    ],
    
    UserRole.SENDER: [
        Permission.LEAD_VIEW, Permission.EMAIL_VIEW, Permission.EMAIL_SEND,
        Permission.CAMPAIGN_VIEW, Permission.SYSTEM_VIEW, Permission.ANALYTICS_VIEW
    ],
    
    UserRole.VIEWER: [
        Permission.LEAD_VIEW, Permission.EMAIL_VIEW, Permission.CAMPAIGN_VIEW,
        Permission.SYSTEM_VIEW, Permission.ANALYTICS_VIEW
    ]
}


class User(BaseModel):
    """User account model."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    
    # Auth (password hash, not plaintext)
    password_hash: str = Field(..., max_length=255)
    
    # Role
    role: UserRole = Field(default=UserRole.VIEWER)
    custom_permissions: List[Permission] = Field(default_factory=list)
    
    # Status
    is_active: bool = Field(default=True)
    is_email_verified: bool = Field(default=False)
    
    # Session management
    last_login_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    current_session_id: Optional[str] = Field(None, max_length=255)
    
    # Settings
    preferences: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = Field(default="UTC", max_length=50)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = Field(None, max_length=100)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        # Custom permissions override
        if permission in self.custom_permissions:
            return True
        # Role-based permissions
        role_permissions = ROLE_PERMISSIONS.get(self.role, [])
        return permission in role_permissions
    
    def get_all_permissions(self) -> List[Permission]:
        """Get all permissions for this user."""
        role_permissions = set(ROLE_PERMISSIONS.get(self.role, []))
        custom_permissions = set(self.custom_permissions)
        return list(role_permissions | custom_permissions)
    
    @validator('email')
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


class LeadAssignment(BaseModel):
    """Lead assignment to user."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    lead_id: UUID = Field(...)
    user_id: UUID = Field(...)
    
    # Assignment details
    assigned_by: UUID = Field(...)
    assigned_at: datetime = Field(default_factory=datetime.now)
    
    # Status
    is_active: bool = Field(default=True)
    unassigned_at: Optional[datetime] = None
    unassigned_by: Optional[UUID] = None
    
    # Notes
    assignment_reason: Optional[str] = Field(None, max_length=500)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class ApprovalDelegation(BaseModel):
    """Delegation of approval authority."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Delegation
    delegator_id: UUID = Field(...)  # User delegating authority
    delegate_id: UUID = Field(...)   # User receiving authority
    
    # Scope
    permissions_delegated: List[Permission] = Field(default_factory=list)
    
    # Time limits
    valid_from: datetime = Field(default_factory=datetime.now)
    valid_until: Optional[datetime] = None
    
    # Status
    is_active: bool = Field(default=True)
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = Field(None, max_length=500)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """Check if delegation is currently valid."""
        if not self.is_active:
            return False
        now = datetime.now()
        if self.valid_from > now:
            return False
        if self.valid_until and self.valid_until < now:
            return False
        return True
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class UserActivityLog(BaseModel):
    """Log of user activities for audit."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID = Field(...)
    
    # Activity details
    action: str = Field(..., max_length=100)
    entity_type: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[UUID] = None
    
    # Request context
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)
    session_id: Optional[str] = Field(None, max_length=255)
    
    # Details
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamp
    occurred_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class UserSession(BaseModel):
    """Active user session."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID = Field(...)
    
    # Session data
    session_token: str = Field(..., max_length=512)
    refresh_token: Optional[str] = Field(None, max_length=512)
    
    # Context
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = Field(None, max_length=500)
    device_info: Optional[Dict[str, Any]] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(...)
    last_activity_at: datetime = Field(default_factory=datetime.now)
    
    # Status
    is_active: bool = Field(default=True)
    revoked_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now() > self.expires_at
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class UserCreate(BaseModel):
    """Create new user request."""
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = Field(default=UserRole.VIEWER)


class UserUpdate(BaseModel):
    """Update user request."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[UserRole] = None
    custom_permissions: Optional[List[Permission]] = None
    is_active: Optional[bool] = None
    preferences: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = Field(None, max_length=50)


class AssignLeadRequest(BaseModel):
    """Request to assign lead to user."""
    lead_id: UUID = Field(...)
    user_id: UUID = Field(...)
    reason: Optional[str] = Field(None, max_length=500)


class DelegateApprovalRequest(BaseModel):
    """Request to delegate approval authority."""
    delegate_id: UUID = Field(...)
    permissions: List[Permission] = Field(...)
    valid_until: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=500)

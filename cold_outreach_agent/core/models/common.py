"""Common models and utilities used across the application."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Generic, TypeVar, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


T = TypeVar('T')


class EntityType(str, Enum):
    """Types of entities in the system."""
    LEAD = "lead"
    EMAIL_CAMPAIGN = "email_campaign"
    AUDIT_LOG = "audit_log"
    STATE_TRANSITION = "state_transition"
    SYSTEM_CONFIG = "system_config"


class OperationResult(BaseModel, Generic[T]):
    """Standard result wrapper for operations."""
    
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def success_result(
        cls, 
        data: Optional[T] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'OperationResult[T]':
        """Create a successful operation result."""
        return cls(
            success=True,
            data=data,
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(
        cls,
        error: str,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'OperationResult[T]':
        """Create an error operation result."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            metadata=metadata or {}
        )


class PaginationParams(BaseModel):
    """Pagination parameters for list operations."""
    
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        pagination: PaginationParams
    ) -> 'PaginatedResponse[T]':
        """Create paginated response from items and pagination params."""
        total_pages = (total + pagination.page_size - 1) // pagination.page_size
        
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_previous=pagination.page > 1
        )


class AuditLog(BaseModel):
    """Audit log entry for tracking all system actions."""
    
    id: UUID = Field(default_factory=uuid4)
    entity_type: EntityType
    entity_id: Optional[UUID] = None
    action: str = Field(..., max_length=100)
    actor: str = Field(..., max_length=100)  # user, system, api_key, etc.
    
    # Change tracking
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    
    # Context
    metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[UUID] = None
    request_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Timestamp
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class StateTransition(BaseModel):
    """State transition record for audit trail."""
    
    id: UUID = Field(default_factory=uuid4)
    entity_id: UUID
    entity_type: EntityType
    from_state: str = Field(..., max_length=50)
    to_state: str = Field(..., max_length=50)
    actor: str = Field(..., max_length=100)
    reason: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class SystemHealth(BaseModel):
    """System health status."""
    
    is_healthy: bool
    status: str  # healthy, degraded, unhealthy
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    last_check: datetime = Field(default_factory=datetime.now)
    uptime_seconds: Optional[float] = None
    
    def add_check(self, name: str, passed: bool, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a health check result."""
        self.checks[name] = {
            "passed": passed,
            "message": message,
            "metadata": metadata or {},
            "checked_at": datetime.now().isoformat()
        }
        
        # Update overall health
        if not passed and self.is_healthy:
            self.is_healthy = False
            self.status = "unhealthy"


class RateLimitStatus(BaseModel):
    """Rate limiting status."""
    
    limit_type: str  # daily, hourly, per_minute
    current_count: int
    max_count: int
    window_start: datetime
    window_end: datetime
    remaining: int
    reset_at: datetime
    
    @property
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.current_count >= self.max_count
    
    @property
    def utilization_percent(self) -> float:
        """Get utilization as percentage."""
        if self.max_count == 0:
            return 100.0
        return (self.current_count / self.max_count) * 100.0


class ConfigurationItem(BaseModel):
    """Configuration item with validation."""
    
    key: str = Field(..., max_length=100)
    value: Any
    value_type: str  # string, integer, boolean, json
    description: Optional[str] = Field(None, max_length=500)
    is_required: bool = False
    is_sensitive: bool = False  # For passwords, API keys, etc.
    validation_pattern: Optional[str] = None  # Regex pattern for validation
    default_value: Optional[Any] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def get_display_value(self) -> str:
        """Get value for display (masks sensitive values)."""
        if self.is_sensitive and self.value:
            return "***MASKED***"
        return str(self.value)


class BackgroundTask(BaseModel):
    """Background task tracking."""
    
    id: UUID = Field(default_factory=uuid4)
    task_type: str = Field(..., max_length=100)
    status: str = Field(default="queued")  # queued, running, completed, failed, cancelled
    
    # Task details
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # Progress tracking
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    progress_message: Optional[str] = None
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Retry logic
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    retry_after: Optional[datetime] = None
    
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in ["completed", "failed", "cancelled"]
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status == "failed" and
            self.retry_count < self.max_retries and
            (self.retry_after is None or self.retry_after <= datetime.now())
        )
    
    def get_duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class EmailDeliveryStatus(BaseModel):
    """Email delivery status tracking."""
    
    message_id: str
    provider: str  # smtp, gmail_api, etc.
    status: str  # queued, sending, sent, delivered, bounced, failed
    
    # Timestamps
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    # Tracking
    tracking_events: List[Dict[str, Any]] = Field(default_factory=list)
    provider_response: Dict[str, Any] = Field(default_factory=dict)
    
    # Error handling
    error_count: int = Field(default=0)
    last_error: Optional[str] = None
    
    def add_tracking_event(self, event_type: str, timestamp: datetime, metadata: Optional[Dict[str, Any]] = None):
        """Add a tracking event."""
        self.tracking_events.append({
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {}
        })
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ValidationError(BaseModel):
    """Validation error details."""
    
    field: str
    message: str
    code: str
    value: Optional[Any] = None
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ValidationResult(BaseModel):
    """Validation result with detailed errors."""
    
    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list)
    
    def add_error(self, field: str, message: str, code: str, value: Optional[Any] = None):
        """Add a validation error."""
        self.errors.append(ValidationError(
            field=field,
            message=message,
            code=code,
            value=value
        ))
        self.is_valid = False
    
    def add_warning(self, field: str, message: str, code: str, value: Optional[Any] = None):
        """Add a validation warning."""
        self.warnings.append(ValidationError(
            field=field,
            message=message,
            code=code,
            value=value
        ))
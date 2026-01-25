"""Sync and integration models for Google Sheets and external APIs."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SyncDirection(str, Enum):
    """Direction of sync."""
    IMPORT = "import"      # External -> System
    EXPORT = "export"      # System -> External
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    """Status of sync job."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    LOCAL_WINS = "local_wins"      # System data takes priority
    REMOTE_WINS = "remote_wins"    # External data takes priority
    NEWEST_WINS = "newest_wins"    # Most recent update wins
    MANUAL = "manual"              # Require manual resolution
    MERGE = "merge"                # Attempt to merge changes


class SyncSource(str, Enum):
    """External sync sources."""
    GOOGLE_SHEETS = "google_sheets"
    CSV_FILE = "csv_file"
    REST_API = "rest_api"
    WEBHOOK = "webhook"


class FieldMapping(BaseModel):
    """Mapping between external and internal fields."""
    external_field: str = Field(..., max_length=100)
    internal_field: str = Field(..., max_length=100)
    transform: Optional[str] = Field(None, max_length=100)  # e.g., "lowercase", "date_parse"
    default_value: Optional[str] = Field(None, max_length=500)
    is_required: bool = Field(default=False)


class SyncConfiguration(BaseModel):
    """Configuration for a sync connection."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    
    # Source configuration
    source: SyncSource
    source_config: Dict[str, Any] = Field(default_factory=dict)
    # For Google Sheets: {"spreadsheet_id": "", "sheet_name": "", "range": ""}
    # For CSV: {"file_path": ""}
    # For REST API: {"url": "", "method": "", "headers": {}}
    
    # Sync settings
    direction: SyncDirection = Field(default=SyncDirection.IMPORT)
    conflict_resolution: ConflictResolution = Field(default=ConflictResolution.NEWEST_WINS)
    
    # Field mappings
    field_mappings: List[FieldMapping] = Field(default_factory=list)
    
    # Unique key for matching records
    unique_key_fields: List[str] = Field(default_factory=list)  # e.g., ["email", "business_name"]
    
    # Scheduling
    is_scheduled: bool = Field(default=False)
    schedule_cron: Optional[str] = Field(None, max_length=100)  # Cron expression
    next_scheduled_run: Optional[datetime] = None
    
    # Status
    is_active: bool = Field(default=True)
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[SyncStatus] = None
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class SyncJob(BaseModel):
    """Individual sync job execution."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    config_id: UUID = Field(...)
    
    # Status
    status: SyncStatus = Field(default=SyncStatus.PENDING)
    
    # Progress
    total_records: int = Field(default=0, ge=0)
    processed_records: int = Field(default=0, ge=0)
    created_records: int = Field(default=0, ge=0)
    updated_records: int = Field(default=0, ge=0)
    skipped_records: int = Field(default=0, ge=0)
    failed_records: int = Field(default=0, ge=0)
    
    # Conflicts
    conflicts_detected: int = Field(default=0, ge=0)
    conflicts_resolved: int = Field(default=0, ge=0)
    conflicts_pending: int = Field(default=0, ge=0)
    
    # Errors
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Triggered by
    triggered_by: str = Field(default="system", max_length=100)
    trigger_type: str = Field(default="manual", max_length=50)  # manual, scheduled, webhook
    
    def get_progress_percentage(self) -> float:
        """Get sync progress as percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100
    
    def get_summary(self) -> Dict[str, Any]:
        """Get job summary."""
        return {
            "status": self.status.value if hasattr(self.status, 'value') else self.status,
            "progress": self.get_progress_percentage(),
            "total": self.total_records,
            "created": self.created_records,
            "updated": self.updated_records,
            "skipped": self.skipped_records,
            "failed": self.failed_records,
            "conflicts": self.conflicts_pending,
            "errors_count": len(self.errors)
        }
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class SyncConflict(BaseModel):
    """Detected sync conflict requiring resolution."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    job_id: UUID = Field(...)
    
    # Record info
    record_type: str = Field(..., max_length=50)  # e.g., "lead"
    record_id: Optional[UUID] = None
    unique_key: Dict[str, Any] = Field(default_factory=dict)
    
    # Conflicting values
    local_values: Dict[str, Any] = Field(default_factory=dict)
    remote_values: Dict[str, Any] = Field(default_factory=dict)
    conflicting_fields: List[str] = Field(default_factory=list)
    
    # Timestamps
    local_updated_at: Optional[datetime] = None
    remote_updated_at: Optional[datetime] = None
    
    # Resolution
    is_resolved: bool = Field(default=False)
    resolution: Optional[str] = Field(None, max_length=50)  # "local", "remote", "merged", "skipped"
    resolved_values: Optional[Dict[str, Any]] = None
    resolved_by: Optional[str] = Field(None, max_length=100)
    resolved_at: Optional[datetime] = None
    
    # Audit
    detected_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class WebhookConfig(BaseModel):
    """Webhook configuration for external notifications."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    
    # Endpoint
    url: str = Field(..., max_length=2000)
    method: str = Field(default="POST", max_length=10)
    headers: Dict[str, str] = Field(default_factory=dict)
    
    # Authentication
    auth_type: Optional[str] = Field(None, max_length=50)  # none, basic, bearer, custom
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    
    # Events to trigger on
    events: List[str] = Field(default_factory=list)  # e.g., ["lead.created", "email.replied"]
    
    # Payload template (uses Jinja2 or similar)
    payload_template: Optional[str] = Field(None, max_length=10000)
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=1, le=3600)
    
    # Status
    is_active: bool = Field(default=True)
    last_triggered_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    consecutive_failures: int = Field(default=0, ge=0)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", max_length=100)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class WebhookDelivery(BaseModel):
    """Record of webhook delivery attempt."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    webhook_id: UUID = Field(...)
    
    # Event
    event_type: str = Field(..., max_length=100)
    event_id: Optional[UUID] = None
    
    # Request
    request_url: str = Field(..., max_length=2000)
    request_headers: Dict[str, str] = Field(default_factory=dict)
    request_body: Optional[str] = Field(None)
    
    # Response
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    response_body: Optional[str] = Field(None, max_length=10000)
    
    # Status
    is_success: bool = Field(default=False)
    attempt_number: int = Field(default=1, ge=1)
    error_message: Optional[str] = Field(None, max_length=1000)
    
    # Timing
    triggered_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class APIKey(BaseModel):
    """API key for REST API access."""
    
    # Identity
    id: UUID = Field(default_factory=uuid4)
    
    # Key info
    name: str = Field(..., min_length=1, max_length=100)
    key_prefix: str = Field(..., max_length=8)  # First 8 chars for identification
    key_hash: str = Field(..., max_length=255)  # Hashed full key
    
    # Permissions
    scopes: List[str] = Field(default_factory=list)  # e.g., ["leads:read", "leads:write"]
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_per_day: int = Field(default=10000, ge=1)
    
    # Status
    is_active: bool = Field(default=True)
    expires_at: Optional[datetime] = None
    
    # Usage tracking
    last_used_at: Optional[datetime] = None
    total_requests: int = Field(default=0, ge=0)
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(..., max_length=100)
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = Field(None, max_length=100)
    
    def is_valid(self) -> bool:
        """Check if API key is currently valid."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class GoogleSheetsConfig(BaseModel):
    """Google Sheets specific configuration."""
    spreadsheet_id: str = Field(..., max_length=200)
    sheet_name: str = Field(..., max_length=100)
    range: str = Field(default="A:Z", max_length=50)
    header_row: int = Field(default=1, ge=1)
    data_start_row: int = Field(default=2, ge=1)


class CSVImportConfig(BaseModel):
    """CSV import configuration."""
    delimiter: str = Field(default=",", max_length=5)
    encoding: str = Field(default="utf-8", max_length=20)
    has_header: bool = Field(default=True)
    skip_rows: int = Field(default=0, ge=0)


class CreateSyncConfigRequest(BaseModel):
    """Request to create a sync configuration."""
    name: str = Field(..., min_length=1, max_length=100)
    source: SyncSource
    source_config: Dict[str, Any] = Field(default_factory=dict)
    direction: SyncDirection = Field(default=SyncDirection.IMPORT)
    conflict_resolution: ConflictResolution = Field(default=ConflictResolution.NEWEST_WINS)
    field_mappings: List[FieldMapping] = Field(default_factory=list)
    unique_key_fields: List[str] = Field(default_factory=list)


class TriggerSyncRequest(BaseModel):
    """Request to trigger a sync job."""
    config_id: UUID = Field(...)
    force_full_sync: bool = Field(default=False)


class ResolveConflictRequest(BaseModel):
    """Request to resolve a sync conflict."""
    conflict_id: UUID = Field(...)
    resolution: str = Field(..., max_length=50)  # "local", "remote", "merged"
    merged_values: Optional[Dict[str, Any]] = None


class CreateAPIKeyRequest(BaseModel):
    """Request to create an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=60, ge=1)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)

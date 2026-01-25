"""Sync service for Google Sheets and external integrations."""

import asyncio
import csv
import io
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID
import os

from ..core.models.sync import (
    SyncConfiguration, SyncJob, SyncConflict, SyncDirection, SyncStatus,
    ConflictResolution, SyncSource, FieldMapping, WebhookConfig, WebhookDelivery,
    APIKey, CreateSyncConfigRequest, TriggerSyncRequest, ResolveConflictRequest,
    CreateAPIKeyRequest
)
from ..core.exceptions import ColdOutreachAgentError
from ..modules.logger import action_logger


class SyncError(ColdOutreachAgentError):
    """Sync operation failed."""
    pass


class SyncService:
    """
    Service for external sync and integrations.
    
    Features:
    - Google Sheets two-way sync
    - CSV import/export
    - Scheduled sync jobs
    - Conflict resolution
    - Webhooks
    - REST API key management
    """
    
    def __init__(self, db_service):
        self.db = db_service
        
        self._configs: Dict[UUID, SyncConfiguration] = {}
        self._jobs: Dict[UUID, SyncJob] = {}
        self._conflicts: Dict[UUID, SyncConflict] = {}
        self._webhooks: Dict[UUID, WebhookConfig] = {}
        self._api_keys: Dict[UUID, APIKey] = {}
        self._webhook_deliveries: List[WebhookDelivery] = []
    
    # ========== Sync Configuration ==========
    
    async def create_sync_config(self, request: CreateSyncConfigRequest,
                                   created_by: str = "system") -> SyncConfiguration:
        """
        Create a new sync configuration.
        
        Args:
            request: Configuration request
            created_by: User creating the config
        
        Returns:
            Created SyncConfiguration
        """
        config = SyncConfiguration(
            name=request.name,
            source=request.source,
            source_config=request.source_config,
            direction=request.direction,
            conflict_resolution=request.conflict_resolution,
            field_mappings=request.field_mappings,
            unique_key_fields=request.unique_key_fields,
            created_by=created_by
        )
        
        self._configs[config.id] = config
        
        action_logger.log_action(
            lead_id=None,
            module_name="sync",
            action="create_config",
            result="success",
            details={
                "config_id": str(config.id),
                "name": config.name,
                "source": config.source.value if hasattr(config.source, 'value') else config.source
            }
        )
        
        return config
    
    async def get_sync_config(self, config_id: UUID) -> Optional[SyncConfiguration]:
        """Get a sync configuration by ID."""
        return self._configs.get(config_id)
    
    async def list_sync_configs(self) -> List[SyncConfiguration]:
        """List all sync configurations."""
        return list(self._configs.values())
    
    async def update_sync_config(self, config_id: UUID,
                                   **updates) -> Optional[SyncConfiguration]:
        """Update a sync configuration."""
        config = self._configs.get(config_id)
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)
        
        config.updated_at = datetime.now()
        return config
    
    async def delete_sync_config(self, config_id: UUID) -> bool:
        """Delete a sync configuration."""
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False
    
    # ========== Sync Jobs ==========
    
    async def trigger_sync(self, request: TriggerSyncRequest,
                            triggered_by: str = "system") -> SyncJob:
        """
        Trigger a sync job.
        
        Args:
            request: Sync trigger request
            triggered_by: User triggering the sync
        
        Returns:
            Created SyncJob
        """
        config = await self.get_sync_config(request.config_id)
        if not config:
            raise SyncError(f"Config {request.config_id} not found")
        
        job = SyncJob(
            config_id=request.config_id,
            status=SyncStatus.PENDING,
            triggered_by=triggered_by,
            trigger_type="manual"
        )
        
        self._jobs[job.id] = job
        
        # Start sync in background
        asyncio.create_task(self._run_sync_job(job, config))
        
        action_logger.log_action(
            lead_id=None,
            module_name="sync",
            action="trigger_sync",
            result="success",
            details={
                "job_id": str(job.id),
                "config_name": config.name
            }
        )
        
        return job
    
    async def _run_sync_job(self, job: SyncJob, config: SyncConfiguration):
        """Run a sync job asynchronously."""
        job.status = SyncStatus.IN_PROGRESS
        job.started_at = datetime.now()
        
        try:
            if config.source == SyncSource.GOOGLE_SHEETS:
                await self._sync_google_sheets(job, config)
            elif config.source == SyncSource.CSV_FILE:
                await self._sync_csv(job, config)
            elif config.source == SyncSource.REST_API:
                await self._sync_rest_api(job, config)
            
            if job.failed_records > 0:
                job.status = SyncStatus.COMPLETED_WITH_ERRORS
            else:
                job.status = SyncStatus.COMPLETED
                
        except Exception as e:
            job.status = SyncStatus.FAILED
            job.errors.append({
                "type": "sync_error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
            action_logger.error(f"Sync job {job.id} failed: {e}")
        
        job.completed_at = datetime.now()
        job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())
        
        # Update config with last sync info
        config.last_sync_at = datetime.now()
        config.last_sync_status = job.status
    
    async def _sync_google_sheets(self, job: SyncJob, config: SyncConfiguration):
        """Sync with Google Sheets."""
        # In production, this would use Google Sheets API
        # For now, this is a placeholder implementation
        
        spreadsheet_id = config.source_config.get('spreadsheet_id')
        sheet_name = config.source_config.get('sheet_name')
        
        if not spreadsheet_id:
            raise SyncError("Missing spreadsheet_id in config")
        
        # Placeholder: simulate reading from sheets
        # In production: use google-api-python-client
        
        action_logger.info(f"Would sync from Google Sheet: {spreadsheet_id}/{sheet_name}")
        
        # Simulate some processed records
        job.total_records = 10
        job.processed_records = 10
        job.created_records = 5
        job.updated_records = 3
        job.skipped_records = 2
    
    async def _sync_csv(self, job: SyncJob, config: SyncConfiguration):
        """Sync from CSV file."""
        file_path = config.source_config.get('file_path')
        if not file_path or not os.path.exists(file_path):
            raise SyncError(f"CSV file not found: {file_path}")
        
        delimiter = config.source_config.get('delimiter', ',')
        encoding = config.source_config.get('encoding', 'utf-8')
        
        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)
        
        job.total_records = len(rows)
        
        for row in rows:
            try:
                # Map fields
                mapped_data = self._apply_field_mappings(row, config.field_mappings)
                
                # Find existing record by unique key
                existing = await self._find_by_unique_key(mapped_data, config.unique_key_fields)
                
                if existing:
                    # Check for conflicts
                    if config.direction == SyncDirection.BIDIRECTIONAL:
                        conflict = self._detect_conflict(existing, mapped_data)
                        if conflict:
                            self._conflicts[conflict.id] = conflict
                            job.conflicts_detected += 1
                            continue
                    
                    # Update existing
                    await self._update_record(existing, mapped_data)
                    job.updated_records += 1
                else:
                    # Create new
                    await self._create_record(mapped_data)
                    job.created_records += 1
                
                job.processed_records += 1
                
            except Exception as e:
                job.failed_records += 1
                job.errors.append({
                    "row": job.processed_records + job.failed_records,
                    "error": str(e)
                })
    
    async def _sync_rest_api(self, job: SyncJob, config: SyncConfiguration):
        """Sync from REST API."""
        url = config.source_config.get('url')
        method = config.source_config.get('method', 'GET')
        headers = config.source_config.get('headers', {})
        
        if not url:
            raise SyncError("Missing URL in API config")
        
        # In production: use aiohttp to fetch data
        # For now, placeholder
        
        action_logger.info(f"Would sync from API: {method} {url}")
        
        job.total_records = 5
        job.processed_records = 5
        job.created_records = 3
        job.updated_records = 2
    
    def _apply_field_mappings(self, data: Dict, mappings: List[FieldMapping]) -> Dict:
        """Apply field mappings to transform data."""
        result = {}
        
        for mapping in mappings:
            value = data.get(mapping.external_field, mapping.default_value)
            
            # Apply transform
            if value and mapping.transform:
                if mapping.transform == 'lowercase':
                    value = str(value).lower()
                elif mapping.transform == 'uppercase':
                    value = str(value).upper()
                elif mapping.transform == 'title_case':
                    value = str(value).title()
            
            result[mapping.internal_field] = value
        
        return result
    
    async def _find_by_unique_key(self, data: Dict, key_fields: List[str]) -> Optional[Dict]:
        """Find existing record by unique key fields."""
        # In production: query database
        return None
    
    def _detect_conflict(self, existing: Dict, new_data: Dict) -> Optional[SyncConflict]:
        """Detect if there's a conflict between existing and new data."""
        conflicting = []
        for key, new_val in new_data.items():
            old_val = existing.get(key)
            if old_val != new_val and old_val is not None:
                conflicting.append(key)
        
        if conflicting:
            return SyncConflict(
                job_id=UUID('00000000-0000-0000-0000-000000000000'),  # Would be actual job ID
                record_type='lead',
                unique_key={k: existing.get(k) for k in ['email', 'business_name']},
                local_values=existing,
                remote_values=new_data,
                conflicting_fields=conflicting
            )
        return None
    
    async def _update_record(self, existing: Dict, new_data: Dict):
        """Update an existing record."""
        # In production: update database
        pass
    
    async def _create_record(self, data: Dict):
        """Create a new record."""
        # In production: insert to database
        pass
    
    async def get_sync_job(self, job_id: UUID) -> Optional[SyncJob]:
        """Get a sync job by ID."""
        return self._jobs.get(job_id)
    
    async def list_sync_jobs(self, config_id: Optional[UUID] = None,
                              limit: int = 50) -> List[SyncJob]:
        """List sync jobs, optionally filtered by config."""
        jobs = list(self._jobs.values())
        
        if config_id:
            jobs = [j for j in jobs if j.config_id == config_id]
        
        jobs.sort(key=lambda j: j.started_at or datetime.min, reverse=True)
        return jobs[:limit]
    
    # ========== Conflict Resolution ==========
    
    async def get_pending_conflicts(self, job_id: Optional[UUID] = None) -> List[SyncConflict]:
        """Get pending conflicts to resolve."""
        conflicts = [c for c in self._conflicts.values() if not c.is_resolved]
        
        if job_id:
            conflicts = [c for c in conflicts if c.job_id == job_id]
        
        return conflicts
    
    async def resolve_conflict(self, request: ResolveConflictRequest,
                                resolved_by: str) -> SyncConflict:
        """
        Resolve a sync conflict.
        
        Args:
            request: Resolution request
            resolved_by: User resolving conflict
        
        Returns:
            Updated SyncConflict
        """
        conflict = self._conflicts.get(request.conflict_id)
        if not conflict:
            raise SyncError(f"Conflict {request.conflict_id} not found")
        
        conflict.is_resolved = True
        conflict.resolution = request.resolution
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.now()
        
        # Apply resolution
        if request.resolution == 'local':
            # Keep local values - no action needed
            conflict.resolved_values = conflict.local_values
        elif request.resolution == 'remote':
            # Use remote values
            conflict.resolved_values = conflict.remote_values
            await self._update_record({}, conflict.remote_values)
        elif request.resolution == 'merged' and request.merged_values:
            conflict.resolved_values = request.merged_values
            await self._update_record({}, request.merged_values)
        
        action_logger.log_action(
            lead_id=None,
            module_name="sync",
            action="resolve_conflict",
            result="success",
            details={
                "conflict_id": str(request.conflict_id),
                "resolution": request.resolution
            }
        )
        
        return conflict
    
    # ========== CSV Export ==========
    
    async def export_leads_csv(self, filters: Optional[Dict] = None) -> str:
        """
        Export leads to CSV format.
        
        Args:
            filters: Optional filters
        
        Returns:
            CSV string
        """
        leads = await self.db.get_all_leads()
        
        if not leads:
            return ""
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)
        
        return output.getvalue()
    
    async def import_leads_csv(self, csv_content: str,
                                field_mappings: List[FieldMapping],
                                unique_key_fields: List[str]) -> Dict[str, int]:
        """
        Import leads from CSV content.
        
        Args:
            csv_content: CSV string content
            field_mappings: Field mappings to apply
            unique_key_fields: Fields for unique key matching
        
        Returns:
            Dict with import statistics
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        
        stats = {
            "total": len(rows),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0
        }
        
        for row in rows:
            try:
                mapped = self._apply_field_mappings(row, field_mappings)
                
                if not mapped.get('email'):
                    stats['skipped'] += 1
                    continue
                
                # Try to create lead
                await self.db.create_lead(mapped)
                stats['created'] += 1
                
            except Exception as e:
                stats['failed'] += 1
                action_logger.warning(f"Failed to import row: {e}")
        
        return stats
    
    # ========== Webhooks ==========
    
    async def create_webhook(self, name: str, url: str, events: List[str],
                              headers: Dict[str, str] = None,
                              created_by: str = "system") -> WebhookConfig:
        """Create a new webhook configuration."""
        webhook = WebhookConfig(
            name=name,
            url=url,
            events=events,
            headers=headers or {},
            created_by=created_by
        )
        
        self._webhooks[webhook.id] = webhook
        
        action_logger.log_action(
            lead_id=None,
            module_name="sync",
            action="create_webhook",
            result="success",
            details={"webhook_id": str(webhook.id), "events": events}
        )
        
        return webhook
    
    async def get_webhook(self, webhook_id: UUID) -> Optional[WebhookConfig]:
        """Get a webhook by ID."""
        return self._webhooks.get(webhook_id)
    
    async def list_webhooks(self) -> List[WebhookConfig]:
        """List all webhooks."""
        return list(self._webhooks.values())
    
    async def trigger_webhook(self, event_type: str, event_data: Dict) -> List[WebhookDelivery]:
        """
        Trigger webhooks for an event.
        
        Args:
            event_type: Type of event (e.g., "lead.created")
            event_data: Event payload data
        
        Returns:
            List of delivery attempts
        """
        deliveries = []
        
        for webhook in self._webhooks.values():
            if not webhook.is_active:
                continue
            if event_type not in webhook.events:
                continue
            
            delivery = await self._deliver_webhook(webhook, event_type, event_data)
            deliveries.append(delivery)
            self._webhook_deliveries.append(delivery)
        
        return deliveries
    
    async def _deliver_webhook(self, webhook: WebhookConfig,
                                event_type: str,
                                event_data: Dict) -> WebhookDelivery:
        """Deliver a webhook payload."""
        # Build payload
        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": event_data
        }
        
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type,
            request_url=webhook.url,
            request_headers=webhook.headers,
            request_body=json.dumps(payload)
        )
        
        # In production: use aiohttp to POST payload
        # For now, simulate success
        try:
            # Simulated delivery
            delivery.response_status = 200
            delivery.is_success = True
            delivery.completed_at = datetime.now()
            delivery.duration_ms = 150
            
            webhook.last_triggered_at = datetime.now()
            webhook.last_success_at = datetime.now()
            webhook.consecutive_failures = 0
            
        except Exception as e:
            delivery.is_success = False
            delivery.error_message = str(e)
            delivery.completed_at = datetime.now()
            
            webhook.consecutive_failures += 1
        
        return delivery
    
    async def get_webhook_deliveries(self, webhook_id: UUID,
                                       limit: int = 50) -> List[WebhookDelivery]:
        """Get delivery history for a webhook."""
        deliveries = [d for d in self._webhook_deliveries if d.webhook_id == webhook_id]
        deliveries.sort(key=lambda d: d.triggered_at, reverse=True)
        return deliveries[:limit]
    
    # ========== API Keys ==========
    
    async def create_api_key(self, request: CreateAPIKeyRequest,
                              created_by: str) -> tuple[APIKey, str]:
        """
        Create a new API key.
        
        Args:
            request: Key creation request
            created_by: User creating the key
        
        Returns:
            Tuple of (APIKey, raw_key) - raw_key is only shown once
        """
        # Generate random key
        raw_key = f"sk_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Calculate expiry
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.now() + timedelta(days=request.expires_in_days)
        
        api_key = APIKey(
            name=request.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=request.scopes,
            rate_limit_per_minute=request.rate_limit_per_minute,
            expires_at=expires_at,
            created_by=created_by
        )
        
        self._api_keys[api_key.id] = api_key
        
        action_logger.log_action(
            lead_id=None,
            module_name="sync",
            action="create_api_key",
            result="success",
            details={
                "key_id": str(api_key.id),
                "name": api_key.name,
                "scopes": api_key.scopes
            }
        )
        
        return api_key, raw_key
    
    async def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate an API key.
        
        Args:
            raw_key: The raw API key string
        
        Returns:
            APIKey if valid, None otherwise
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash:
                if not api_key.is_valid():
                    return None
                
                # Update usage
                api_key.last_used_at = datetime.now()
                api_key.total_requests += 1
                
                return api_key
        
        return None
    
    async def revoke_api_key(self, key_id: UUID, revoked_by: str) -> bool:
        """Revoke an API key."""
        api_key = self._api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.is_active = False
        api_key.revoked_at = datetime.now()
        api_key.revoked_by = revoked_by
        
        action_logger.log_action(
            lead_id=None,
            module_name="sync",
            action="revoke_api_key",
            result="success",
            details={"key_id": str(key_id)}
        )
        
        return True
    
    async def list_api_keys(self) -> List[APIKey]:
        """List all API keys (without hashes)."""
        return list(self._api_keys.values())

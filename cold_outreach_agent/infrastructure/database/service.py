"""Production-grade database service with proper transactions and indexing."""

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

import aiosqlite

from ...core.models.lead import Lead, LeadCreate, LeadUpdate, LeadFilter, LeadState, ReviewStatus
from ...core.models.email import EmailCampaign, EmailCampaignCreate, EmailCampaignUpdate, EmailFilter, EmailState
from ...core.models.campaign import EmailSequence, LeadSequenceEnrollment, SequenceStatus, LeadSequenceStatus
from ...core.models.common import AuditLog, StateTransition, PaginationParams, PaginatedResponse
from ...core.exceptions import DatabaseError, LeadNotFoundError, EmailCampaignNotFoundError
from .migrations import MigrationManager


class ProductionDatabaseService:
    """Production-grade database service with proper error handling and transactions."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.migration_manager = MigrationManager(db_path)
        self._connection_pool = None
    
    async def initialize(self):
        """Initialize database with migrations and indexes."""
        try:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Run migrations
            await self.migration_manager.migrate()
            
            # Create indexes for performance
            await self._create_indexes()
            
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {str(e)}")
    
    async def _create_indexes(self):
        """Create database indexes for performance."""
        indexes = [
            # Lead indexes
            "CREATE INDEX IF NOT EXISTS idx_leads_lifecycle_state ON leads(lifecycle_state)",
            "CREATE INDEX IF NOT EXISTS idx_leads_review_status ON leads(review_status)",
            "CREATE INDEX IF NOT EXISTS idx_leads_discovery_source ON leads(discovery_source)",
            "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)",
            "CREATE INDEX IF NOT EXISTS idx_leads_maps_url ON leads(maps_url)",
            "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_leads_business_location ON leads(business_name, location)",
            
            # Email campaign indexes
            "CREATE INDEX IF NOT EXISTS idx_email_campaigns_lead_id ON email_campaigns(lead_id)",
            "CREATE INDEX IF NOT EXISTS idx_email_campaigns_state ON email_campaigns(email_state)",
            "CREATE INDEX IF NOT EXISTS idx_email_campaigns_type ON email_campaigns(campaign_type)",
            "CREATE INDEX IF NOT EXISTS idx_email_campaigns_created_at ON email_campaigns(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_email_campaigns_retry ON email_campaigns(email_state, retry_after)",
            
            # Audit log indexes
            "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor)",
            "CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)",
            
            # State transition indexes
            "CREATE INDEX IF NOT EXISTS idx_state_transitions_entity ON state_transitions(entity_type, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_state_transitions_created_at ON state_transitions(created_at)"
        ]
        
        async with aiosqlite.connect(self.db_path) as db:
            for index_sql in indexes:
                await db.execute(index_sql)
            await db.commit()
    
    @asynccontextmanager
    async def transaction(self):
        """Async context manager for database transactions."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("BEGIN")
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    
    # Lead Operations
    async def create_lead(self, lead_data: LeadCreate) -> Lead:
        """Create a new lead with proper validation."""
        try:
            lead = Lead(
                id=uuid4(),
                **lead_data.dict(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            async with self.transaction() as db:
                # Check for duplicates
                if await self._lead_exists_by_business_location(
                    db, lead.business_name, lead.location
                ):
                    raise DatabaseError(
                        f"Lead already exists: {lead.business_name} in {lead.location}",
                        error_code="DUPLICATE_LEAD"
                    )
                
                # Insert lead
                await db.execute("""
                    INSERT INTO leads (
                        id, business_name, category, location, maps_url, website_url,
                        email, phone, discovery_source, discovery_confidence,
                        discovery_metadata, discovered_at, lifecycle_state, review_status,
                        tag, quality_score, created_at, updated_at, version, notes, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(lead.id), lead.business_name, lead.category, lead.location,
                    lead.maps_url, lead.website_url, lead.email, lead.phone,
                    lead.discovery_source, float(lead.discovery_confidence) if lead.discovery_confidence else None,
                    json.dumps(lead.discovery_metadata), lead.discovered_at.isoformat(),
                    lead.lifecycle_state, lead.review_status, lead.tag,
                    float(lead.quality_score) if lead.quality_score else None,
                    lead.created_at.isoformat(), lead.updated_at.isoformat(),
                    lead.version, lead.notes, json.dumps(lead.metadata)
                ))
            
            return lead
            
        except Exception as e:
            if isinstance(e, DatabaseError):
                raise
            raise DatabaseError(f"Failed to create lead: {str(e)}")
    
    async def get_lead_by_id(self, lead_id: UUID) -> Optional[Lead]:
        """Get lead by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM leads WHERE id = ?",
                    (str(lead_id),)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return self._row_to_lead(row)
                
        except Exception as e:
            raise DatabaseError(f"Failed to get lead {lead_id}: {str(e)}")
    
    async def update_lead(self, lead_id: UUID, updates: LeadUpdate) -> Lead:
        """Update lead with optimistic locking."""
        try:
            async with self.transaction() as db:
                # Get current lead for version check
                current_lead = await self.get_lead_by_id(lead_id)
                if not current_lead:
                    raise LeadNotFoundError(f"Lead {lead_id} not found")
                
                # Prepare update data
                update_data = updates.dict(exclude_unset=True)
                update_data["updated_at"] = datetime.now()
                update_data["version"] = current_lead.version + 1
                
                # Build dynamic update query
                set_clauses = []
                values = []
                
                for field, value in update_data.items():
                    if field in ["metadata", "discovery_metadata"] and value is not None:
                        value = json.dumps(value)
                    elif field in ["discovery_confidence", "quality_score"] and value is not None:
                        value = float(value)
                    elif isinstance(value, datetime):
                        value = value.isoformat()
                    
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
                
                values.append(str(lead_id))
                values.append(current_lead.version)  # For optimistic locking
                
                # Execute update with version check
                cursor = await db.execute(f"""
                    UPDATE leads 
                    SET {', '.join(set_clauses)}
                    WHERE id = ? AND version = ?
                """, values)
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        "Lead update failed - concurrent modification detected",
                        error_code="CONCURRENT_MODIFICATION"
                    )
                
                # Return updated lead
                return await self.get_lead_by_id(lead_id)
                
        except Exception as e:
            if isinstance(e, (DatabaseError, LeadNotFoundError)):
                raise
            raise DatabaseError(f"Failed to update lead {lead_id}: {str(e)}")
    
    async def get_leads(
        self, 
        filters: Optional[LeadFilter] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResponse[Lead]:
        """Get leads with filtering and pagination."""
        try:
            # Build WHERE clause
            where_conditions = []
            params = []
            
            if filters:
                if filters.lifecycle_state:
                    where_conditions.append("lifecycle_state = ?")
                    params.append(filters.lifecycle_state)
                
                if filters.review_status:
                    where_conditions.append("review_status = ?")
                    params.append(filters.review_status)
                
                if filters.discovery_source:
                    where_conditions.append("discovery_source = ?")
                    params.append(filters.discovery_source)
                
                if filters.category:
                    where_conditions.append("category = ?")
                    params.append(filters.category)
                
                if filters.tag:
                    where_conditions.append("tag = ?")
                    params.append(filters.tag)
                
                if filters.has_email is not None:
                    if filters.has_email:
                        where_conditions.append("email IS NOT NULL AND email != ''")
                    else:
                        where_conditions.append("(email IS NULL OR email = '')")
                
                if filters.has_website is not None:
                    if filters.has_website:
                        where_conditions.append("website_url IS NOT NULL AND website_url != ''")
                    else:
                        where_conditions.append("(website_url IS NULL OR website_url = '')")
                
                if filters.min_confidence:
                    where_conditions.append("discovery_confidence >= ?")
                    params.append(float(filters.min_confidence))
                
                if filters.created_after:
                    where_conditions.append("created_at >= ?")
                    params.append(filters.created_after.isoformat())
                
                if filters.created_before:
                    where_conditions.append("created_at <= ?")
                    params.append(filters.created_before.isoformat())
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Get total count
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(f"SELECT COUNT(*) FROM leads {where_clause}", params)
                total = (await cursor.fetchone())[0]
                
                # Get paginated results
                pagination = pagination or PaginationParams()
                
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(f"""
                    SELECT * FROM leads {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, params + [pagination.page_size, pagination.offset])
                
                rows = await cursor.fetchall()
                leads = [self._row_to_lead(row) for row in rows]
                
                return PaginatedResponse.create(leads, total, pagination)
                
        except Exception as e:
            raise DatabaseError(f"Failed to get leads: {str(e)}")
    
    async def get_leads_by_state(self, state: LeadState) -> List[Lead]:
        """Get all leads in a specific lifecycle state."""
        filters = LeadFilter(lifecycle_state=state)
        result = await self.get_leads(filters)
        return result.items
    
    # Email Campaign Operations
    async def create_email_campaign(self, campaign_data: EmailCampaignCreate) -> EmailCampaign:
        """Create a new email campaign."""
        try:
            campaign = EmailCampaign(
                id=uuid4(),
                **campaign_data.dict(),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            async with self.transaction() as db:
                await db.execute("""
                    INSERT INTO email_campaigns (
                        id, lead_id, campaign_type, template_id, subject, body_text, body_html,
                        to_email, to_name, from_email, from_name, email_state, queued_at,
                        error_count, provider_response, delivery_metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(campaign.id), str(campaign.lead_id), campaign.campaign_type,
                    campaign.template_id, campaign.subject, campaign.body_text, campaign.body_html,
                    campaign.to_email, campaign.to_name, campaign.from_email, campaign.from_name,
                    campaign.email_state, campaign.queued_at.isoformat() if campaign.queued_at else None,
                    campaign.error_count, json.dumps(campaign.provider_response),
                    json.dumps(campaign.delivery_metadata), campaign.created_at.isoformat(),
                    campaign.updated_at.isoformat()
                ))
            
            return campaign
            
        except Exception as e:
            raise DatabaseError(f"Failed to create email campaign: {str(e)}")
    
    async def get_email_campaign_by_id(self, campaign_id: UUID) -> Optional[EmailCampaign]:
        """Get email campaign by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM email_campaigns WHERE id = ?",
                    (str(campaign_id),)
                )
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return self._row_to_email_campaign(row)
                
        except Exception as e:
            raise DatabaseError(f"Failed to get email campaign {campaign_id}: {str(e)}")
    
    async def update_email_campaign(
        self, 
        campaign_id: UUID, 
        updates: Dict[str, Any]
    ) -> EmailCampaign:
        """Update email campaign."""
        try:
            async with self.transaction() as db:
                # Prepare update data
                update_data = updates.copy()
                update_data["updated_at"] = datetime.now()
                
                # Build dynamic update query
                set_clauses = []
                values = []
                
                for field, value in update_data.items():
                    if field in ["provider_response", "delivery_metadata"] and value is not None:
                        value = json.dumps(value)
                    elif isinstance(value, datetime):
                        value = value.isoformat()
                    
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
                
                values.append(str(campaign_id))
                
                # Execute update
                await db.execute(f"""
                    UPDATE email_campaigns 
                    SET {', '.join(set_clauses)}
                    WHERE id = ?
                """, values)
                
                # Return updated campaign
                return await self.get_email_campaign_by_id(campaign_id)
                
        except Exception as e:
            raise DatabaseError(f"Failed to update email campaign {campaign_id}: {str(e)}")
    
    async def get_email_campaigns_by_state(self, state: EmailState) -> List[EmailCampaign]:
        """Get all email campaigns in a specific state."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM email_campaigns WHERE email_state = ? ORDER BY created_at ASC",
                    (state,)
                )
                rows = await cursor.fetchall()
                
                return [self._row_to_email_campaign(row) for row in rows]
                
        except Exception as e:
            raise DatabaseError(f"Failed to get email campaigns by state {state}: {str(e)}")
    
    # Audit and State Transition Operations
    async def save_audit_log(self, audit_log: AuditLog):
        """Save audit log entry."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO audit_log (
                        id, entity_type, entity_id, action, actor, old_values, new_values,
                        metadata, session_id, request_id, ip_address, user_agent, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(audit_log.id), audit_log.entity_type, 
                    str(audit_log.entity_id) if audit_log.entity_id else None,
                    audit_log.action, audit_log.actor,
                    json.dumps(audit_log.old_values) if audit_log.old_values else None,
                    json.dumps(audit_log.new_values) if audit_log.new_values else None,
                    json.dumps(audit_log.metadata), 
                    str(audit_log.session_id) if audit_log.session_id else None,
                    str(audit_log.request_id) if audit_log.request_id else None,
                    audit_log.ip_address, audit_log.user_agent,
                    audit_log.created_at.isoformat()
                ))
                await db.commit()
                
        except Exception as e:
            raise DatabaseError(f"Failed to save audit log: {str(e)}")
    
    async def save_state_transition(self, transition: StateTransition):
        """Save state transition record."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO state_transitions (
                        id, entity_id, entity_type, from_state, to_state, actor, reason, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(transition.id), str(transition.entity_id), transition.entity_type,
                    transition.from_state, transition.to_state, transition.actor,
                    transition.reason, json.dumps(transition.metadata),
                    transition.created_at.isoformat()
                ))
                await db.commit()
                
        except Exception as e:
            raise DatabaseError(f"Failed to save state transition: {str(e)}")
    
    # Helper Methods
    async def _lead_exists_by_business_location(
        self, 
        db: aiosqlite.Connection, 
        business_name: str, 
        location: str
    ) -> bool:
        """Check if lead exists by business name and location."""
        cursor = await db.execute(
            "SELECT 1 FROM leads WHERE LOWER(business_name) = ? AND LOWER(location) = ?",
            (business_name.lower(), location.lower())
        )
        return await cursor.fetchone() is not None
    
    def _row_to_lead(self, row: aiosqlite.Row) -> Lead:
        """Convert database row to Lead model."""
        return Lead(
            id=UUID(row["id"]),
            business_name=row["business_name"],
            category=row["category"],
            location=row["location"],
            maps_url=row["maps_url"],
            website_url=row["website_url"],
            email=row["email"],
            phone=row["phone"],
            discovery_source=row["discovery_source"],
            discovery_confidence=row["discovery_confidence"],
            discovery_metadata=json.loads(row["discovery_metadata"]) if row["discovery_metadata"] else {},
            discovered_at=datetime.fromisoformat(row["discovered_at"]),
            lifecycle_state=row["lifecycle_state"],
            review_status=row["review_status"],
            tag=row["tag"],
            quality_score=row["quality_score"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            version=row["version"],
            notes=row["notes"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )
    
    async def get_email_campaigns_sent_in_period(self, start_time: datetime, end_time: datetime) -> List[EmailCampaign]:
        """Get email campaigns sent in a specific time period."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM email_campaigns 
                    WHERE email_state = 'sent' 
                    AND sent_at BETWEEN ? AND ?
                    ORDER BY sent_at DESC
                """, (start_time.isoformat(), end_time.isoformat()))
                
                rows = await cursor.fetchall()
                return [self._row_to_email_campaign(row) for row in rows]
                
        except Exception as e:
            raise DatabaseError(f"Failed to get email campaigns sent in period: {str(e)}")
    
    async def get_leads_by_business_location(self, business_name: str, location: str) -> List[Lead]:
        """Get leads by business name and location (for duplicate checking)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM leads 
                    WHERE LOWER(business_name) = ? AND LOWER(location) = ?
                """, (business_name.lower(), location.lower()))
                
                rows = await cursor.fetchall()
                return [self._row_to_lead(row) for row in rows]
                
        except Exception as e:
            raise DatabaseError(f"Failed to get leads by business/location: {str(e)}")
    
    async def update_lead_state(self, lead_id: UUID, new_state: Dict[str, Any]) -> Lead:
        """Update lead state with proper validation."""
        try:
            async with self.transaction() as db:
                # Get current lead for version check
                current_lead = await self.get_lead_by_id(lead_id)
                if not current_lead:
                    raise LeadNotFoundError(f"Lead {lead_id} not found")
                
                # Prepare update data
                update_data = new_state.copy()
                update_data["updated_at"] = datetime.now()
                update_data["version"] = current_lead.version + 1
                
                # Build dynamic update query
                set_clauses = []
                values = []
                
                for field, value in update_data.items():
                    if field in ["metadata", "discovery_metadata"] and value is not None:
                        value = json.dumps(value)
                    elif field in ["discovery_confidence", "quality_score"] and value is not None:
                        value = float(value)
                    elif isinstance(value, datetime):
                        value = value.isoformat()
                    
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
                
                values.append(str(lead_id))
                values.append(current_lead.version)  # For optimistic locking
                
                # Execute update with version check
                cursor = await db.execute(f"""
                    UPDATE leads 
                    SET {', '.join(set_clauses)}
                    WHERE id = ? AND version = ?
                """, values)
                
                if cursor.rowcount == 0:
                    raise DatabaseError(
                        "Lead update failed - concurrent modification detected",
                        error_code="CONCURRENT_MODIFICATION"
                    )
                
                # Return updated lead
                return await self.get_lead_by_id(lead_id)
                
        except Exception as e:
            if isinstance(e, (DatabaseError, LeadNotFoundError)):
                raise
            raise DatabaseError(f"Failed to update lead state {lead_id}: {str(e)}")
    
    async def get_audit_logs(
        self, 
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit logs with filtering."""
        try:
            where_conditions = []
            params = []
            
            if entity_type:
                where_conditions.append("entity_type = ?")
                params.append(entity_type)
            
            if entity_id:
                where_conditions.append("entity_id = ?")
                params.append(str(entity_id))
            
            if action:
                where_conditions.append("action = ?")
                params.append(action)
            
            if actor:
                where_conditions.append("actor = ?")
                params.append(actor)
            
            if start_time:
                where_conditions.append("created_at >= ?")
                params.append(start_time.isoformat())
            
            if end_time:
                where_conditions.append("created_at <= ?")
                params.append(end_time.isoformat())
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(f"""
                    SELECT * FROM audit_log {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ?
                """, params + [limit])
                
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            raise DatabaseError(f"Failed to get audit logs: {str(e)}")
    
    async def cleanup_old_data(self, retention_days: int = 90):
        """Clean up old data based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            async with self.transaction() as db:
                # Clean up old audit logs
                await db.execute(
                    "DELETE FROM audit_log WHERE created_at < ?",
                    (cutoff_date.isoformat(),)
                )
                
                # Clean up old state transitions
                await db.execute(
                    "DELETE FROM state_transitions WHERE created_at < ?",
                    (cutoff_date.isoformat(),)
                )
                
                # Clean up old failed email campaigns (keep successful ones)
                await db.execute("""
                    DELETE FROM email_campaigns 
                    WHERE email_state IN ('failed', 'cancelled') 
                    AND created_at < ?
                """, (cutoff_date.isoformat(),))
                
                # Vacuum database to reclaim space
                await db.execute("VACUUM")
                
        except Exception as e:
            raise DatabaseError(f"Failed to cleanup old data: {str(e)}")
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring."""
        try:
            stats = {}
            
            async with aiosqlite.connect(self.db_path) as db:
                # Get table counts
                tables = ['leads', 'email_campaigns', 'audit_log', 'state_transitions']
                
                for table in tables:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                    count = (await cursor.fetchone())[0]
                    stats[f"{table}_count"] = count
                
                # Get database size
                cursor = await db.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                size = (await cursor.fetchone())[0]
                stats["database_size_bytes"] = size
                
                # Get recent activity
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM leads 
                    WHERE created_at >= datetime('now', '-24 hours')
                """)
                stats["leads_created_24h"] = (await cursor.fetchone())[0]
                
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM email_campaigns 
                    WHERE created_at >= datetime('now', '-24 hours')
                """)
                stats["emails_sent_24h"] = (await cursor.fetchone())[0]
                
                return stats
                
        except Exception as e:
            raise DatabaseError(f"Failed to get database statistics: {str(e)}")
            
    def _row_to_email_campaign(self, row: aiosqlite.Row) -> EmailCampaign:
        """Convert database row to EmailCampaign model."""
        return EmailCampaign(
            id=UUID(row["id"]),
            lead_id=UUID(row["lead_id"]),
            campaign_type=row["campaign_type"],
            template_id=row["template_id"],
            subject=row["subject"],
            body_text=row["body_text"],
            body_html=row["body_html"],
            to_email=row["to_email"],
            to_name=row["to_name"],
            from_email=row["from_email"],
            from_name=row["from_name"],
            email_state=row["email_state"],
            queued_at=datetime.fromisoformat(row["queued_at"]) if row["queued_at"] else None,
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
            delivered_at=datetime.fromisoformat(row["delivered_at"]) if row["delivered_at"] else None,
            opened_at=datetime.fromisoformat(row["opened_at"]) if row["opened_at"] else None,
            clicked_at=datetime.fromisoformat(row["clicked_at"]) if row["clicked_at"] else None,
            replied_at=datetime.fromisoformat(row["replied_at"]) if row["replied_at"] else None,
            error_count=row["error_count"],
            last_error=row["last_error"],
            retry_after=datetime.fromisoformat(row["retry_after"]) if row["retry_after"] else None,
            message_id=row["message_id"],
            provider_response=json.loads(row["provider_response"]) if row["provider_response"] else {},
            delivery_metadata=json.loads(row["delivery_metadata"]) if row["delivery_metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"])
        )

    async def get_all_campaigns(self, limit: Optional[int] = None) -> List[EmailCampaign]:
        """Get all email campaigns for analytics."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                query = "SELECT * FROM email_campaigns ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = await db.execute(query)
                rows = await cursor.fetchall()
                return [self._row_to_email_campaign(row) for row in rows]
        except Exception as e:
            raise DatabaseError(f"Failed to get all campaigns: {str(e)}")

    async def get_campaigns_by_range(self, start_date: datetime, end_date: datetime) -> List[EmailCampaign]:
        """Get campaigns within a date range."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM email_campaigns 
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                """, (start_date.isoformat(), end_date.isoformat()))
                rows = await cursor.fetchall()
                return [self._row_to_email_campaign(row) for row in rows]
        except Exception as e:
            raise DatabaseError(f"Failed to get campaigns by range: {str(e)}")

    async def get_all_leads_for_analytics(self) -> List[Lead]:
        """Get all leads for analytics (warning: can be large)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM leads")
                rows = await cursor.fetchall()
                return [self._row_to_lead(row) for row in rows]
        except Exception as e:
            raise DatabaseError(f"Failed to get all leads: {str(e)}")

    # --- Campaign / Sequence Methods ---

    async def create_sequence(self, sequence: EmailSequence) -> EmailSequence:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO email_sequences (
                        id, name, description, status, steps, auto_pause_on_reply,
                        max_leads_per_day, created_by, created_at, updated_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(sequence.id), sequence.name, sequence.description,
                    sequence.status.value if hasattr(sequence.status, 'value') else sequence.status,
                    json.dumps([s.dict() for s in sequence.steps]),
                    sequence.auto_pause_on_reply, sequence.max_leads_per_day,
                    sequence.created_by, sequence.created_at.isoformat(),
                    sequence.updated_at.isoformat(), sequence.version
                ))
                await db.commit()
                return sequence
        except Exception as e:
            raise DatabaseError(f"Failed to create sequence: {str(e)}")

    async def get_sequence(self, sequence_id: UUID) -> Optional[EmailSequence]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM email_sequences WHERE id = ?", (str(sequence_id),))
                row = await cursor.fetchone()
                if not row: return None
                
                steps_data = json.loads(row['steps'])
                # Reconstruct generic Steps (requires importing SequenceStep which we skipped, 
                # but we can pass generic dicts to Pydantic model if structured correctly)
                # For now assume the model handles list of dicts conversion
                
                return EmailSequence(
                    id=UUID(row['id']),
                    name=row['name'],
                    description=row['description'],
                    status=row['status'],  # Pydantic will cast to enum
                    steps=steps_data,
                    auto_pause_on_reply=bool(row['auto_pause_on_reply']),
                    max_leads_per_day=row['max_leads_per_day'],
                    created_by=row['created_by'],
                    total_enrolled=row['total_enrolled'],
                    total_completed=row['total_completed'],
                    total_replied=row['total_replied'],
                    total_bounced=row['total_bounced'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    version=row['version']
                )
        except Exception as e:
            raise DatabaseError(f"Failed to get sequence: {str(e)}")

    async def update_sequence(self, sequence: EmailSequence):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE email_sequences SET
                        name=?, description=?, status=?, steps=?, auto_pause_on_reply=?,
                        max_leads_per_day=?, updated_at=?, version=?,
                        total_enrolled=?, total_completed=?, total_replied=?, total_bounced=?
                    WHERE id=?
                """, (
                    sequence.name, sequence.description,
                    sequence.status.value if hasattr(sequence.status, 'value') else sequence.status,
                    json.dumps([s.dict() for s in sequence.steps]),
                    sequence.auto_pause_on_reply, sequence.max_leads_per_day,
                    sequence.updated_at.isoformat(), sequence.version,
                    sequence.total_enrolled, sequence.total_completed, 
                    sequence.total_replied, sequence.total_bounced,
                    str(sequence.id)
                ))
                await db.commit()
        except Exception as e:
            raise DatabaseError(f"Failed to update sequence: {str(e)}")

    async def create_enrollment(self, enrollment: LeadSequenceEnrollment) -> LeadSequenceEnrollment:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO sequence_enrollments (
                        id, sequence_id, lead_id, status, current_step_index,
                        next_step_scheduled, total_emails_sent, last_email_sent_at,
                        reply_received_at, exit_reason, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(enrollment.id), str(enrollment.sequence_id), str(enrollment.lead_id),
                    enrollment.status.value if hasattr(enrollment.status, 'value') else enrollment.status,
                    enrollment.current_step_index,
                    enrollment.next_step_scheduled.isoformat() if enrollment.next_step_scheduled else None,
                    enrollment.total_emails_sent,
                    enrollment.last_email_sent_at.isoformat() if enrollment.last_email_sent_at else None,
                    enrollment.reply_received_at.isoformat() if enrollment.reply_received_at else None,
                    enrollment.exit_reason,
                    json.dumps(enrollment.metadata),
                    enrollment.created_at.isoformat(),
                    enrollment.updated_at.isoformat()
                ))
                await db.commit()
                return enrollment
        except Exception as e:
            raise DatabaseError(f"Failed to create enrollment: {str(e)}")

    async def update_enrollment(self, enrollment: LeadSequenceEnrollment):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE sequence_enrollments SET
                        status=?, current_step_index=?, next_step_scheduled=?,
                        total_emails_sent=?, last_email_sent_at=?,
                        reply_received_at=?, exit_reason=?, metadata=?, updated_at=?, completed_at=?
                    WHERE id=?
                """, (
                    enrollment.status.value if hasattr(enrollment.status, 'value') else enrollment.status,
                    enrollment.current_step_index,
                    enrollment.next_step_scheduled.isoformat() if enrollment.next_step_scheduled else None,
                    enrollment.total_emails_sent,
                    enrollment.last_email_sent_at.isoformat() if enrollment.last_email_sent_at else None,
                    enrollment.reply_received_at.isoformat() if enrollment.reply_received_at else None,
                    enrollment.exit_reason, json.dumps(enrollment.metadata),
                    enrollment.updated_at.isoformat(),
                    enrollment.completed_at.isoformat() if enrollment.completed_at else None,
                    str(enrollment.id)
                ))
                await db.commit()
        except Exception as e:
            raise DatabaseError(f"Failed to update enrollment: {str(e)}")

    async def get_enrollment(self, enrollment_id: UUID) -> Optional[LeadSequenceEnrollment]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM sequence_enrollments WHERE id = ?", (str(enrollment_id),))
                row = await cursor.fetchone()
                if not row: return None
                return self._row_to_enrollment(row)
        except Exception as e:
            raise DatabaseError(f"Failed to get enrollment: {str(e)}")

    async def get_enrollments(self, sequence_id: Optional[UUID] = None, lead_id: Optional[UUID] = None) -> List[LeadSequenceEnrollment]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                query = "SELECT * FROM sequence_enrollments WHERE 1=1"
                params = []
                if sequence_id:
                    query += " AND sequence_id = ?"
                    params.append(str(sequence_id))
                if lead_id:
                    query += " AND lead_id = ?"
                    params.append(str(lead_id))
                
                cursor = await db.execute(query, tuple(params))
                rows = await cursor.fetchall()
                return [self._row_to_enrollment(row) for row in rows]
        except Exception as e:
            raise DatabaseError(f"Failed to get enrollments: {str(e)}")

    async def get_pending_enrollments(self) -> List[LeadSequenceEnrollment]:
        try:
            now = datetime.now()
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("""
                    SELECT * FROM sequence_enrollments 
                    WHERE status = 'enrolled' 
                    AND next_step_scheduled <= ?
                """, (now.isoformat(),))
                rows = await cursor.fetchall()
                return [self._row_to_enrollment(row) for row in rows]
        except Exception as e:
            raise DatabaseError(f"Failed to get pending enrollments: {str(e)}")
            
    def _row_to_enrollment(self, row) -> LeadSequenceEnrollment:
        return LeadSequenceEnrollment(
            id=UUID(row['id']),
            sequence_id=UUID(row['sequence_id']),
            lead_id=UUID(row['lead_id']),
            status=row['status'],
            current_step_index=row['current_step_index'],
            next_step_scheduled=datetime.fromisoformat(row['next_step_scheduled']) if row['next_step_scheduled'] else None,
            total_emails_sent=row['total_emails_sent'],
            last_email_sent_at=datetime.fromisoformat(row['last_email_sent_at']) if row['last_email_sent_at'] else None,
            reply_received_at=datetime.fromisoformat(row['reply_received_at']) if row['reply_received_at'] else None,
            exit_reason=row['exit_reason'],
            metadata=json.loads(row['metadata']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
        )



"""Database migration management for production system."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import aiosqlite

from ...core.exceptions import DatabaseError


class Migration:
    """Represents a single database migration."""
    
    def __init__(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
    
    def __str__(self):
        return f"Migration {self.version}: {self.name}"


class MigrationManager:
    """Manages database schema migrations."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.migrations = self._get_migrations()
    
    def _get_migrations(self) -> List[Migration]:
        """Define all database migrations."""
        return [
            Migration(
                version=1,
                name="initial_schema",
                up_sql="""
                -- Create leads table
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    business_name TEXT NOT NULL,
                    category TEXT,
                    location TEXT NOT NULL,
                    maps_url TEXT UNIQUE,
                    website_url TEXT,
                    email TEXT,
                    phone TEXT,
                    
                    -- Discovery metadata
                    discovery_source TEXT NOT NULL,
                    discovery_confidence REAL,
                    discovery_metadata TEXT DEFAULT '{}',
                    discovered_at TEXT NOT NULL,
                    
                    -- State tracking
                    lifecycle_state TEXT NOT NULL DEFAULT 'discovered',
                    review_status TEXT NOT NULL DEFAULT 'pending',
                    
                    -- Classification
                    tag TEXT,
                    quality_score REAL,
                    
                    -- Audit fields
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    
                    -- Notes and metadata
                    notes TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                );
                
                -- Create email campaigns table
                CREATE TABLE IF NOT EXISTS email_campaigns (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    campaign_type TEXT NOT NULL,
                    template_id TEXT,
                    
                    -- Email content
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    body_html TEXT,
                    
                    -- Recipients
                    to_email TEXT NOT NULL,
                    to_name TEXT,
                    from_email TEXT NOT NULL,
                    from_name TEXT NOT NULL,
                    
                    -- State tracking
                    email_state TEXT NOT NULL DEFAULT 'queued',
                    
                    -- Delivery tracking
                    queued_at TEXT,
                    sent_at TEXT,
                    delivered_at TEXT,
                    opened_at TEXT,
                    clicked_at TEXT,
                    replied_at TEXT,
                    
                    -- Error tracking
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    retry_after TEXT,
                    
                    -- Delivery metadata
                    message_id TEXT,
                    provider_response TEXT DEFAULT '{}',
                    delivery_metadata TEXT DEFAULT '{}',
                    
                    -- Audit fields
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                );
                
                -- Create audit log table
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    
                    -- Change tracking
                    old_values TEXT,
                    new_values TEXT,
                    metadata TEXT DEFAULT '{}',
                    
                    -- Context
                    session_id TEXT,
                    request_id TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    
                    created_at TEXT NOT NULL
                );
                
                -- Create state transitions table
                CREATE TABLE IF NOT EXISTS state_transitions (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                
                -- Create migration tracking table
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                """,
                down_sql="""
                DROP TABLE IF EXISTS state_transitions;
                DROP TABLE IF EXISTS audit_log;
                DROP TABLE IF EXISTS email_campaigns;
                DROP TABLE IF EXISTS leads;
                DROP TABLE IF EXISTS schema_migrations;
                """
            ),
            
            Migration(
                version=2,
                name="add_performance_indexes",
                up_sql="""
                -- Lead indexes for performance
                CREATE INDEX IF NOT EXISTS idx_leads_lifecycle_state ON leads(lifecycle_state);
                CREATE INDEX IF NOT EXISTS idx_leads_review_status ON leads(review_status);
                CREATE INDEX IF NOT EXISTS idx_leads_discovery_source ON leads(discovery_source);
                CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
                CREATE INDEX IF NOT EXISTS idx_leads_maps_url ON leads(maps_url);
                CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);
                CREATE INDEX IF NOT EXISTS idx_leads_business_location ON leads(business_name, location);
                
                -- Email campaign indexes
                CREATE INDEX IF NOT EXISTS idx_email_campaigns_lead_id ON email_campaigns(lead_id);
                CREATE INDEX IF NOT EXISTS idx_email_campaigns_state ON email_campaigns(email_state);
                CREATE INDEX IF NOT EXISTS idx_email_campaigns_type ON email_campaigns(campaign_type);
                CREATE INDEX IF NOT EXISTS idx_email_campaigns_created_at ON email_campaigns(created_at);
                CREATE INDEX IF NOT EXISTS idx_email_campaigns_retry ON email_campaigns(email_state, retry_after);
                
                -- Audit log indexes
                CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
                CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor);
                CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
                
                -- State transition indexes
                CREATE INDEX IF NOT EXISTS idx_state_transitions_entity ON state_transitions(entity_type, entity_id);
                CREATE INDEX IF NOT EXISTS idx_state_transitions_created_at ON state_transitions(created_at);
                """,
                down_sql="""
                DROP INDEX IF EXISTS idx_leads_lifecycle_state;
                DROP INDEX IF EXISTS idx_leads_review_status;
                DROP INDEX IF EXISTS idx_leads_discovery_source;
                DROP INDEX IF EXISTS idx_leads_email;
                DROP INDEX IF EXISTS idx_leads_maps_url;
                DROP INDEX IF EXISTS idx_leads_created_at;
                DROP INDEX IF EXISTS idx_leads_business_location;
                DROP INDEX IF EXISTS idx_email_campaigns_lead_id;
                DROP INDEX IF EXISTS idx_email_campaigns_state;
                DROP INDEX IF EXISTS idx_email_campaigns_type;
                DROP INDEX IF EXISTS idx_email_campaigns_created_at;
                DROP INDEX IF EXISTS idx_email_campaigns_retry;
                DROP INDEX IF EXISTS idx_audit_log_entity;
                DROP INDEX IF EXISTS idx_audit_log_action;
                DROP INDEX IF EXISTS idx_audit_log_actor;
                DROP INDEX IF EXISTS idx_audit_log_created_at;
                DROP INDEX IF EXISTS idx_state_transitions_entity;
                DROP INDEX IF EXISTS idx_state_transitions_created_at;
                """
            ),
            
            Migration(
                version=3,
                name="add_rate_limiting_table",
                up_sql="""
                -- Create rate limiting table for email sending
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id TEXT PRIMARY KEY,
                    limit_type TEXT NOT NULL, -- 'daily', 'hourly', 'minute'
                    limit_key TEXT NOT NULL, -- identifier (e.g., 'email_sending')
                    count INTEGER NOT NULL DEFAULT 0,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    
                    UNIQUE(limit_type, limit_key, window_start)
                );
                
                CREATE INDEX IF NOT EXISTS idx_rate_limits_type_key ON rate_limits(limit_type, limit_key);
                CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start, window_end);
                """,
                down_sql="""
                DROP TABLE IF EXISTS rate_limits;
                """
            ),
            
            Migration(
                version=4,
                name="add_email_templates_table",
                up_sql="""
                -- Create email templates table
                CREATE TABLE IF NOT EXISTS email_templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    campaign_type TEXT NOT NULL,
                    
                    -- Template content
                    subject_template TEXT NOT NULL,
                    body_text_template TEXT NOT NULL,
                    body_html_template TEXT,
                    
                    -- Template metadata
                    variables TEXT DEFAULT '[]', -- JSON array of required variables
                    is_active BOOLEAN DEFAULT 1,
                    
                    -- Audit fields
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1
                );
                
                CREATE INDEX IF NOT EXISTS idx_email_templates_campaign_type ON email_templates(campaign_type);
                CREATE INDEX IF NOT EXISTS idx_email_templates_active ON email_templates(is_active);
                
                -- Insert default templates
                INSERT OR IGNORE INTO email_templates (
                    id, name, description, campaign_type, subject_template, 
                    body_text_template, variables, created_at, updated_at, created_by
                ) VALUES (
                    'initial_outreach_default',
                    'Initial Outreach - Default',
                    'Default template for initial business outreach',
                    'initial',
                    'Partnership Opportunity with {{business_name}}',
                    'Hi {{business_name}} team,

I hope this email finds you well. I came across {{business_name}} and was impressed by your presence in {{location}}.

I wanted to reach out to discuss a potential partnership opportunity that could benefit your business.

Would you be interested in a brief conversation to explore how we might work together?

Best regards,
{{sender_name}}',
                    '["business_name", "location", "sender_name"]',
                    datetime('now'),
                    datetime('now'),
                    'system'
                );
                """,
                down_sql="""
                DROP TABLE IF EXISTS email_templates;
                """
            ),
            
            Migration(
                version=5,
                name="add_advanced_services_tables",
                up_sql="""
                -- Users and Auth
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_login_at TEXT,
                    email_verified BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
                
                -- Enrichment Data
                CREATE TABLE IF NOT EXISTS enrichment_data (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL UNIQUE,
                    data_source TEXT NOT NULL,
                    enriched_data TEXT NOT NULL, -- JSON
                    confidence_score REAL,
                    enriched_at TEXT NOT NULL,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                );
                
                -- Scoring
                CREATE TABLE IF NOT EXISTS lead_scores (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL UNIQUE,
                    score_type TEXT NOT NULL,
                    score_value REAL NOT NULL,
                    score_breakdown TEXT, -- JSON
                    calculated_at TEXT NOT NULL,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                );
                
                -- Compliance
                CREATE TABLE IF NOT EXISTS do_not_contact (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    domain TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_dnc_email ON do_not_contact(email);
                CREATE INDEX IF NOT EXISTS idx_dnc_domain ON do_not_contact(domain);
                
                -- CRM
                CREATE TABLE IF NOT EXISTS crm_threads (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    subject TEXT,
                    status TEXT,
                    last_message_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                );
                
                CREATE TABLE IF NOT EXISTS crm_opportunities (
                    id TEXT PRIMARY KEY,
                    lead_id TEXT NOT NULL,
                    name TEXT,
                    stage TEXT,
                    value REAL,
                    close_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                );
                
                -- Public Signals
                CREATE TABLE IF NOT EXISTS public_profiles (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    business_name TEXT NOT NULL,
                    slug TEXT UNIQUE,
                    is_active BOOLEAN DEFAULT 0,
                    profile_data TEXT, -- JSON
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                
                -- Sync
                CREATE TABLE IF NOT EXISTS sync_configs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    config_data TEXT NOT NULL, -- JSON
                    is_active BOOLEAN DEFAULT 1,
                    last_sync_at TEXT,
                    created_at TEXT NOT NULL
                );
                
                -- Sequences (Campaigns)
                CREATE TABLE IF NOT EXISTS email_sequences (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    steps TEXT NOT NULL, -- JSON
                    auto_pause_on_reply BOOLEAN DEFAULT 1,
                    max_leads_per_day INTEGER,
                    created_by TEXT,
                    
                    total_enrolled INTEGER DEFAULT 0,
                    total_completed INTEGER DEFAULT 0,
                    total_replied INTEGER DEFAULT 0,
                    total_bounced INTEGER DEFAULT 0,
                    
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER DEFAULT 1
                );
                
                CREATE TABLE IF NOT EXISTS sequence_enrollments (
                    id TEXT PRIMARY KEY,
                    sequence_id TEXT NOT NULL,
                    lead_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_step_index INTEGER DEFAULT 0,
                    next_step_scheduled TEXT,
                    
                    total_emails_sent INTEGER DEFAULT 0,
                    last_email_sent_at TEXT,
                    reply_received_at TEXT,
                    exit_reason TEXT,
                    metadata TEXT DEFAULT '{}',
                    
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    
                    FOREIGN KEY (sequence_id) REFERENCES email_sequences (id),
                    FOREIGN KEY (lead_id) REFERENCES leads (id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_enrollment_sequence__status ON sequence_enrollments(sequence_id, status);
                CREATE INDEX IF NOT EXISTS idx_enrollment_lead ON sequence_enrollments(lead_id);
                """,
                down_sql="""
                DROP TABLE IF EXISTS sequence_enrollments;
                DROP TABLE IF EXISTS email_sequences;
                DROP TABLE IF EXISTS sync_configs;
                DROP TABLE IF EXISTS public_profiles;
                DROP TABLE IF EXISTS crm_opportunities;
                DROP TABLE IF EXISTS crm_threads;
                DROP TABLE IF EXISTS do_not_contact;
                DROP TABLE IF EXISTS lead_scores;
                DROP TABLE IF EXISTS enrichment_data;
                DROP TABLE IF EXISTS user_sessions;
                DROP TABLE IF EXISTS users;
                """

            )
        ]
    
    async def migrate(self):
        """Run all pending migrations."""
        try:
            # Ensure database file exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Create migration tracking table if it doesn't exist
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    )
                """)
                await db.commit()
                
                # Get current version
                current_version = await self._get_current_version(db)
                
                # Apply pending migrations
                pending_migrations = [m for m in self.migrations if m.version > current_version]
                
                for migration in pending_migrations:
                    await self._apply_migration(db, migration)
                
                if pending_migrations:
                    print(f"Applied {len(pending_migrations)} migrations")
                
        except Exception as e:
            raise DatabaseError(f"Migration failed: {str(e)}")
    
    async def _get_current_version(self, db: aiosqlite.Connection) -> int:
        """Get the current database schema version."""
        try:
            cursor = await db.execute("SELECT MAX(version) FROM schema_migrations")
            result = await cursor.fetchone()
            return result[0] if result[0] is not None else 0
        except Exception:
            return 0
    
    async def _apply_migration(self, db: aiosqlite.Connection, migration: Migration):
        """Apply a single migration."""
        try:
            print(f"Applying migration {migration.version}: {migration.name}")
            
            # Execute migration SQL
            await db.executescript(migration.up_sql)
            
            # Record migration as applied
            await db.execute("""
                INSERT INTO schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
            """, (migration.version, migration.name, datetime.now().isoformat()))
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Failed to apply migration {migration.version}: {str(e)}")
    
    async def rollback(self, target_version: int):
        """Rollback to a specific version."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                current_version = await self._get_current_version(db)
                
                if target_version >= current_version:
                    print(f"Already at or below version {target_version}")
                    return
                
                # Get migrations to rollback (in reverse order)
                rollback_migrations = [
                    m for m in reversed(self.migrations) 
                    if target_version < m.version <= current_version
                ]
                
                for migration in rollback_migrations:
                    await self._rollback_migration(db, migration)
                
                print(f"Rolled back {len(rollback_migrations)} migrations")
                
        except Exception as e:
            raise DatabaseError(f"Rollback failed: {str(e)}")
    
    async def _rollback_migration(self, db: aiosqlite.Connection, migration: Migration):
        """Rollback a single migration."""
        try:
            if not migration.down_sql:
                raise DatabaseError(f"No rollback SQL for migration {migration.version}")
            
            print(f"Rolling back migration {migration.version}: {migration.name}")
            
            # Execute rollback SQL
            await db.executescript(migration.down_sql)
            
            # Remove migration record
            await db.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (migration.version,)
            )
            
            await db.commit()
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Failed to rollback migration {migration.version}: {str(e)}")
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                current_version = await self._get_current_version(db)
                
                # Get applied migrations
                cursor = await db.execute("""
                    SELECT version, name, applied_at 
                    FROM schema_migrations 
                    ORDER BY version
                """)
                applied_migrations = await cursor.fetchall()
                
                # Get pending migrations
                pending_migrations = [
                    {"version": m.version, "name": m.name}
                    for m in self.migrations 
                    if m.version > current_version
                ]
                
                return {
                    "current_version": current_version,
                    "latest_version": max(m.version for m in self.migrations),
                    "applied_migrations": [
                        {"version": row[0], "name": row[1], "applied_at": row[2]}
                        for row in applied_migrations
                    ],
                    "pending_migrations": pending_migrations,
                    "total_migrations": len(self.migrations)
                }
                
        except Exception as e:
            raise DatabaseError(f"Failed to get migration status: {str(e)}")
    
    async def validate_schema(self) -> Dict[str, Any]:
        """Validate current database schema."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Check if all expected tables exist
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                existing_tables = {row[0] for row in await cursor.fetchall()}
                
                expected_tables = {
                    'leads', 'email_campaigns', 'audit_log', 
                    'state_transitions', 'schema_migrations',
                    'rate_limits', 'email_templates',
                    'users', 'user_sessions', 'enrichment_data', 'lead_scores',
                    'do_not_contact', 'crm_threads', 'crm_opportunities',
                    'public_profiles', 'sync_configs'
                }
                
                missing_tables = expected_tables - existing_tables
                extra_tables = existing_tables - expected_tables
                
                # Check indexes
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """)
                existing_indexes = {row[0] for row in await cursor.fetchall()}
                
                return {
                    "valid": len(missing_tables) == 0,
                    "existing_tables": list(existing_tables),
                    "missing_tables": list(missing_tables),
                    "extra_tables": list(extra_tables),
                    "existing_indexes": list(existing_indexes),
                    "schema_version": await self._get_current_version(db)
                }
                
        except Exception as e:
            raise DatabaseError(f"Schema validation failed: {str(e)}")
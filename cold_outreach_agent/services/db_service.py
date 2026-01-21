"""Local SQLite database service for lead management with review workflow.

Provides both async (for use in async contexts) and sync methods (for legacy code).
Sync methods use asyncio.run() internally and should only be called from sync contexts.
"""

import aiosqlite
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config.settings import settings


def _run_async(coro):
    """Helper to run async code in sync context, handles nested event loops."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, create new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class DatabaseService:
    """Handles all local database operations with review workflow support (Async)."""
    
    def __init__(self):
        self.db_path = settings.PROJECT_ROOT / "leads.db"
        
    async def init_db(self):
        """Initialize database and create/migrate tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # Main leads table with review workflow
            await db.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    lead_id TEXT PRIMARY KEY,
                    business_name TEXT NOT NULL,
                    category TEXT,
                    location TEXT,
                    maps_url TEXT,
                    website_url TEXT,
                    email TEXT,
                    discovery_source TEXT DEFAULT 'manual',
                    discovery_confidence TEXT DEFAULT 'medium',
                    tag TEXT DEFAULT 'unknown',
                    review_status TEXT DEFAULT 'pending',
                    outreach_status TEXT DEFAULT 'not_sent',
                    discovered_at TEXT,
                    last_contacted TEXT,
                    notes TEXT DEFAULT ''
                )
            """)
            
            # Agent logs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    module TEXT NOT NULL,
                    lead_id TEXT,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    details TEXT
                )
            """)

            # Create Indexes for performance
            await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_review_status ON leads(review_status);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_outreach_status ON leads(outreach_status);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_maps_url ON leads(maps_url);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_leads_discovered_at ON leads(discovered_at);")
            
            # Migration: add new columns if they don't exist
            await self._migrate_schema(db)
            await db.commit()
    
    async def _migrate_schema(self, db):
        """Add new columns to existing tables if needed."""
        async with db.execute("PRAGMA table_info(leads)") as cursor:
            existing_cols = {row[1] for row in await cursor.fetchall()}
        
        migrations = [
            ("maps_url", "TEXT"),
            ("website_url", "TEXT"),
            ("discovery_source", "TEXT DEFAULT 'manual'"),
            ("discovery_confidence", "TEXT DEFAULT 'medium'"),
            ("review_status", "TEXT DEFAULT 'pending'"),
            ("outreach_status", "TEXT DEFAULT 'not_sent'"),
            ("discovered_at", "TEXT"),
            ("lifecycle_state", "TEXT DEFAULT 'pending_review'"),
            ("updated_at", "TEXT"),
        ]
        
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                try:
                    await db.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
                except aiosqlite.OperationalError:
                    pass
        
        # Migrate old 'status' to 'outreach_status' and 'website' to 'website_url'
        if "status" in existing_cols and "outreach_status" not in existing_cols:
            await db.execute("UPDATE leads SET outreach_status = status WHERE outreach_status IS NULL")
        
        if "website" in existing_cols:
            await db.execute("UPDATE leads SET website_url = website WHERE website_url IS NULL OR website_url = ''")
    
    def _row_to_dict(self, row, cursor) -> dict:
        """Convert a row to dictionary."""
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    
    # --- Lead CRUD Operations ---
    
    async def get_all_leads(self) -> List[dict]:
        """Fetch all leads."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM leads ORDER BY discovered_at DESC") as cursor:
                return [dict(row) for row in await cursor.fetchall()]
    
    async def get_lead_by_id(self, lead_id: str) -> Optional[dict]:
        """Get a single lead by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM leads WHERE lead_id = ?", (lead_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_leads_by_review_status(self, review_status: str) -> List[dict]:
        """Get leads filtered by review status (pending/approved/rejected)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM leads WHERE review_status = ? ORDER BY discovered_at DESC"
            async with db.execute(query, (review_status,)) as cursor:
                return [dict(row) for row in await cursor.fetchall()]
    
    async def get_leads_by_outreach_status(self, outreach_status: str) -> List[dict]:
        """Get leads filtered by outreach status."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM leads WHERE outreach_status = ? ORDER BY discovered_at DESC"
            async with db.execute(query, (outreach_status,)) as cursor:
                 return [dict(row) for row in await cursor.fetchall()]
    
    async def get_approved_leads_for_outreach(self) -> List[dict]:
        """Get leads that are approved and ready for initial outreach."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM leads 
                WHERE review_status = 'approved' 
                AND outreach_status = 'not_sent'
                AND email IS NOT NULL AND email != ''
                ORDER BY discovered_at ASC
            """) as cursor:
                return [dict(row) for row in await cursor.fetchall()]
    
    async def get_leads_for_followup(self, delay_days: int) -> List[dict]:
        """Get approved leads eligible for follow-up."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM leads 
                WHERE review_status = 'approved'
                AND outreach_status = 'sent_initial'
                ORDER BY last_contacted ASC
            """) as cursor:
                leads = [dict(row) for row in await cursor.fetchall()]
        
        eligible = []
        now = datetime.now()
        for lead in leads:
            last_contacted_str = lead.get("last_contacted")
            if not last_contacted_str:
                continue
            try:
                # Handle ISO format with potential Z or cleanup
                contact_date = datetime.fromisoformat(last_contacted_str.replace("Z", "+00:00"))
                days_since = (now - contact_date).days
                if days_since >= delay_days:
                    eligible.append(lead)
            except ValueError:
                continue
        
        return eligible
    
    async def get_leads_without_tag(self) -> List[dict]:
        """Get leads that haven't been classified yet."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM leads WHERE tag = '' OR tag IS NULL OR tag = 'unknown'") as cursor:
                return [dict(row) for row in await cursor.fetchall()]
    
    async def add_lead(self, lead_data: dict) -> str:
        """Add a new lead. Returns the lead_id."""
        lead_id = lead_data.get("lead_id") or str(uuid.uuid4())[:8]
        discovered_at = lead_data.get("discovered_at") or datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO leads (
                    lead_id, business_name, category, location, maps_url, website_url,
                    email, discovery_source, discovery_confidence, tag, review_status,
                    outreach_status, discovered_at, last_contacted, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead_id,
                lead_data.get("business_name", ""),
                lead_data.get("category", ""),
                lead_data.get("location", ""),
                lead_data.get("maps_url", ""),
                lead_data.get("website_url", ""),
                lead_data.get("email", ""),
                lead_data.get("discovery_source", "manual"),
                lead_data.get("discovery_confidence", "medium"),
                lead_data.get("tag", "unknown"),
                lead_data.get("review_status", "pending"),
                lead_data.get("outreach_status", "not_sent"),
                discovered_at,
                lead_data.get("last_contacted", ""),
                lead_data.get("notes", "")
            ))
            await db.commit()
        
        return lead_id
    
    async def update_lead(self, lead_id: str, updates: dict) -> bool:
        """Update specific fields for a lead."""
        if not updates:
            return False
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [lead_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                f"UPDATE leads SET {set_clause} WHERE lead_id = ?",
                values
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def approve_lead(self, lead_id: str) -> bool:
        """Approve a lead for outreach."""
        return await self.update_lead(lead_id, {"review_status": "approved"})
    
    async def reject_lead(self, lead_id: str) -> bool:
        """Reject a lead (will not receive outreach)."""
        return await self.update_lead(lead_id, {"review_status": "rejected"})
    
    async def bulk_approve_leads(self, lead_ids: List[str]) -> int:
        """Approve multiple leads. Returns count of updated leads."""
        count = 0
        for lead_id in lead_ids:
            if await self.approve_lead(lead_id):
                count += 1
        return count
    
    async def bulk_reject_leads(self, lead_ids: List[str]) -> int:
        """Reject multiple leads. Returns count of updated leads."""
        count = 0
        for lead_id in lead_ids:
            if await self.reject_lead(lead_id):
                count += 1
        return count
    
    async def clear_all_leads(self) -> int:
        """Delete all leads from the database. Returns count of deleted leads."""
        async with aiosqlite.connect(self.db_path) as db:
            # Get count before deletion
            async with db.execute("SELECT COUNT(*) FROM leads") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            
            # Delete all leads
            await db.execute("DELETE FROM leads")
            await db.commit()
            
        return count
    
    async def lead_exists_by_maps_url(self, maps_url: str) -> bool:
        """Check if a lead with this maps URL already exists."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM leads WHERE maps_url = ?", (maps_url,)) as cursor:
                return await cursor.fetchone() is not None
    
    async def lead_exists_by_email(self, email: str) -> bool:
        """Check if a lead with this email already exists."""
        if not email:
            return False
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM leads WHERE email = ?", (email.lower(),)) as cursor:
                return await cursor.fetchone() is not None
    
    async def lead_exists_by_business_location(self, business_name: str, location: str) -> bool:
        """Check if a lead with same business name and location exists."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM leads WHERE LOWER(business_name) = ? AND LOWER(location) = ?",
                (business_name.lower(), location.lower())
            ) as cursor:
                return await cursor.fetchone() is not None
    
    # --- Statistics ---
    
    async def get_emails_sent_today(self) -> int:
        """Count emails sent today for rate limiting."""
        today = datetime.now().strftime("%Y-%m-%d")
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM leads WHERE last_contacted LIKE ?",
                (f"{today}%",)
            ) as cursor:
                 row = await cursor.fetchone()
                 return row[0] if row else 0
    
    async def get_lead_counts(self) -> dict:
        """Get counts by review and outreach status."""
        async with aiosqlite.connect(self.db_path) as db:
            # Helper to run count query
            async def cnt(query):
                async with db.execute(query) as c:
                    r = await c.fetchone()
                    return r[0] if r else 0

            return {
                "total": await cnt("SELECT COUNT(*) FROM leads"),
                "pending_review": await cnt("SELECT COUNT(*) FROM leads WHERE review_status = 'pending'"),
                "approved": await cnt("SELECT COUNT(*) FROM leads WHERE review_status = 'approved'"),
                "rejected": await cnt("SELECT COUNT(*) FROM leads WHERE review_status = 'rejected'"),
                "sent_initial": await cnt("SELECT COUNT(*) FROM leads WHERE outreach_status = 'sent_initial'"),
                "sent_followup": await cnt("SELECT COUNT(*) FROM leads WHERE outreach_status = 'sent_followup'"),
                "replied": await cnt("SELECT COUNT(*) FROM leads WHERE outreach_status = 'replied'")
            }
    
    # --- Agent Logs ---
    
    async def add_agent_log(self, module: str, action: str, result: str, 
                      lead_id: Optional[str] = None, details: Optional[str] = None):
        """Add an entry to agent_logs table."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO agent_logs (timestamp, module, lead_id, action, result, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    module,
                    lead_id,
                    action,
                    result,
                    details
                ))
                await db.commit()
        except Exception as e:
            # Fallback to print if DB fails, don't crash the log
            print(f"CRITICAL: Failed to write to DB log: {e}")
    
    async def get_agent_logs(self, limit: int = 100, module: Optional[str] = None, 
                       lead_id: Optional[str] = None) -> List[dict]:
        """Get agent logs with optional filtering."""
        query = "SELECT * FROM agent_logs WHERE 1=1"
        params = []
        
        if module:
            query += " AND module = ?"
            params.append(module)
        
        if lead_id:
            query += " AND lead_id = ?"
            params.append(lead_id)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    # =====================================================================
    # SYNCHRONOUS WRAPPERS
    # These methods call the async versions using _run_async()
    # Use these from synchronous code (FastAPI sync endpoints, modules, etc.)
    # =====================================================================
    
    def init_db_sync(self):
        """Sync wrapper for init_db."""
        return _run_async(self.init_db())
    
    def get_all_leads_sync(self) -> List[dict]:
        """Fetch all leads (sync)."""
        return _run_async(self.get_all_leads())
    
    def get_lead_by_id_sync(self, lead_id: str) -> Optional[dict]:
        """Get a single lead by ID (sync)."""
        return _run_async(self.get_lead_by_id(lead_id))
    
    def get_leads_by_review_status_sync(self, review_status: str) -> List[dict]:
        """Get leads filtered by review status (sync)."""
        return _run_async(self.get_leads_by_review_status(review_status))
    
    def get_leads_by_outreach_status_sync(self, outreach_status: str) -> List[dict]:
        """Get leads filtered by outreach status (sync)."""
        return _run_async(self.get_leads_by_outreach_status(outreach_status))
    
    def get_approved_leads_for_outreach_sync(self) -> List[dict]:
        """Get leads that are approved and ready for initial outreach (sync)."""
        return _run_async(self.get_approved_leads_for_outreach())
    
    def get_leads_for_followup_sync(self, delay_days: int) -> List[dict]:
        """Get approved leads eligible for follow-up (sync)."""
        return _run_async(self.get_leads_for_followup(delay_days))
    
    def get_leads_without_tag_sync(self) -> List[dict]:
        """Get leads that haven't been classified yet (sync)."""
        return _run_async(self.get_leads_without_tag())
    
    def add_lead_sync(self, lead_data: dict) -> str:
        """Add a new lead (sync). Returns the lead_id."""
        return _run_async(self.add_lead(lead_data))
    
    def update_lead_sync(self, lead_id: str, updates: dict) -> bool:
        """Update specific fields for a lead (sync)."""
        return _run_async(self.update_lead(lead_id, updates))
    
    def approve_lead_sync(self, lead_id: str) -> bool:
        """Approve a lead for outreach (sync)."""
        return _run_async(self.approve_lead(lead_id))
    
    def reject_lead_sync(self, lead_id: str) -> bool:
        """Reject a lead (sync)."""
        return _run_async(self.reject_lead(lead_id))
    
    def bulk_approve_leads_sync(self, lead_ids: List[str]) -> int:
        """Approve multiple leads (sync). Returns count."""
        return _run_async(self.bulk_approve_leads(lead_ids))
    
    def bulk_reject_leads_sync(self, lead_ids: List[str]) -> int:
        """Reject multiple leads (sync). Returns count."""
        return _run_async(self.bulk_reject_leads(lead_ids))
    
    def clear_all_leads_sync(self) -> int:
        """Delete all leads from the database (sync). Returns count of deleted leads."""
        return _run_async(self.clear_all_leads())
    
    def lead_exists_by_maps_url_sync(self, maps_url: str) -> bool:
        """Check if a lead with this maps URL already exists (sync)."""
        return _run_async(self.lead_exists_by_maps_url(maps_url))
    
    def lead_exists_by_email_sync(self, email: str) -> bool:
        """Check if a lead with this email already exists (sync)."""
        return _run_async(self.lead_exists_by_email(email))
    
    def lead_exists_by_business_location_sync(self, business_name: str, location: str) -> bool:
        """Check if a lead with same business name and location exists (sync)."""
        return _run_async(self.lead_exists_by_business_location(business_name, location))
    
    def get_emails_sent_today_sync(self) -> int:
        """Count emails sent today for rate limiting (sync)."""
        return _run_async(self.get_emails_sent_today())
    
    def get_lead_counts_sync(self) -> dict:
        """Get counts by review and outreach status (sync)."""
        return _run_async(self.get_lead_counts())
    
    def add_agent_log_sync(self, module: str, action: str, result: str,
                           lead_id: Optional[str] = None, details: Optional[str] = None):
        """Add an entry to agent_logs table (sync)."""
        return _run_async(self.add_agent_log(module, action, result, lead_id, details))
    
    def get_agent_logs_sync(self, limit: int = 100, module: Optional[str] = None,
                            lead_id: Optional[str] = None) -> List[dict]:
        """Get agent logs with optional filtering (sync)."""
        return _run_async(self.get_agent_logs(limit, module, lead_id))


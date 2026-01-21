"""
Agent State Machine - Persistent state management with separate discovery and outreach states.

States: idle, discovering, reviewing, outreach_running, paused, stopping, error
Transitions are explicit and logged. Illegal transitions are rejected.
"""

import sqlite3
import threading
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from config.settings import settings


class AgentState(str, Enum):
    IDLE = "idle"
    DISCOVERING = "discovering"
    PAUSED = "paused"
    OUTREACH_RUNNING = "outreach_running"
    STOPPING = "stopping"
    ERROR = "error"


# Legal state transitions - Discovery and Outreach are SEPARATE
VALID_TRANSITIONS = {
    AgentState.IDLE: {AgentState.DISCOVERING, AgentState.OUTREACH_RUNNING},
    AgentState.DISCOVERING: {AgentState.PAUSED, AgentState.STOPPING, AgentState.ERROR, AgentState.IDLE},
    AgentState.OUTREACH_RUNNING: {AgentState.PAUSED, AgentState.STOPPING, AgentState.ERROR, AgentState.IDLE},
    AgentState.PAUSED: {AgentState.DISCOVERING, AgentState.OUTREACH_RUNNING, AgentState.STOPPING, AgentState.IDLE},
    AgentState.STOPPING: {AgentState.IDLE, AgentState.ERROR},
    AgentState.ERROR: {AgentState.IDLE},  # Manual recovery only
}


class AgentStateManager:
    """
    Manages persistent agent state with explicit transitions.
    Thread-safe singleton pattern.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.db_path = settings.PROJECT_ROOT / "leads.db"
        self._init_tables()
        self._initialized = True
    
    def _init_tables(self):
        """Create agent_state and agent_control_log tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state TEXT NOT NULL DEFAULT 'idle',
                    last_transition_time TEXT NOT NULL,
                    reason TEXT,
                    controlled_by TEXT DEFAULT 'system',
                    last_heartbeat TEXT,
                    error_message TEXT,
                    current_task TEXT,
                    discovery_query TEXT,
                    discovery_location TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_control_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    previous_state TEXT NOT NULL,
                    new_state TEXT NOT NULL,
                    controlled_by TEXT NOT NULL,
                    reason TEXT,
                    result TEXT NOT NULL
                )
            """)
            
            # Initialize state row if not exists
            cursor = conn.execute("SELECT COUNT(*) FROM agent_state")
            if cursor.fetchone()[0] == 0:
                conn.execute("""
                    INSERT INTO agent_state (id, state, last_transition_time, controlled_by)
                    VALUES (1, 'idle', ?, 'system')
                """, (datetime.now().isoformat(),))
            
            # Migration: add new columns if needed
            self._migrate_state_table(conn)
            conn.commit()
    
    def _migrate_state_table(self, conn):
        """Add new columns to agent_state if needed."""
        cursor = conn.execute("PRAGMA table_info(agent_state)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        migrations = [
            ("current_task", "TEXT"),
            ("discovery_query", "TEXT"),
            ("discovery_location", "TEXT"),
        ]
        
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE agent_state ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass
    
    def get_state(self) -> dict:
        """Get current agent state from DB (source of truth)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT state, last_transition_time, reason, controlled_by, 
                       last_heartbeat, error_message, current_task,
                       discovery_query, discovery_location
                FROM agent_state WHERE id = 1
            """)
            row = cursor.fetchone()
            
            if not row:
                return {
                    "state": AgentState.IDLE.value,
                    "last_transition_time": None,
                    "reason": None,
                    "controlled_by": "system",
                    "last_heartbeat": None,
                    "error_message": None,
                    "current_task": None,
                    "discovery_query": None,
                    "discovery_location": None
                }
            
            return {
                "state": row[0],
                "last_transition_time": row[1],
                "reason": row[2],
                "controlled_by": row[3],
                "last_heartbeat": row[4],
                "error_message": row[5],
                "current_task": row[6] if len(row) > 6 else None,
                "discovery_query": row[7] if len(row) > 7 else None,
                "discovery_location": row[8] if len(row) > 8 else None
            }
    
    def transition(
        self,
        new_state: AgentState,
        controlled_by: str = "system",
        reason: Optional[str] = None,
        error_message: Optional[str] = None,
        current_task: Optional[str] = None,
        discovery_query: Optional[str] = None,
        discovery_location: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Attempt state transition. Returns (success, message).
        Rejects illegal transitions.
        """
        with self._lock:
            current = self.get_state()
            current_state = AgentState(current["state"])
            
            # Check if transition is valid
            if new_state not in VALID_TRANSITIONS.get(current_state, set()):
                msg = f"Illegal transition: {current_state.value} → {new_state.value}"
                self._log_transition(current_state, new_state, controlled_by, reason, "rejected")
                return False, msg
            
            timestamp = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE agent_state 
                    SET state = ?, last_transition_time = ?, reason = ?, 
                        controlled_by = ?, error_message = ?, current_task = ?,
                        discovery_query = ?, discovery_location = ?
                    WHERE id = 1
                """, (
                    new_state.value, timestamp, reason, controlled_by, error_message,
                    current_task, discovery_query, discovery_location
                ))
                conn.commit()
            
            self._log_transition(current_state, new_state, controlled_by, reason, "success")
            return True, f"Transitioned to {new_state.value}"
    
    def _log_transition(
        self,
        previous: AgentState,
        new: AgentState,
        controlled_by: str,
        reason: Optional[str],
        result: str
    ):
        """Log state transition to audit table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO agent_control_log 
                (timestamp, previous_state, new_state, controlled_by, reason, result)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                previous.value,
                new.value,
                controlled_by,
                reason,
                result
            ))
            conn.commit()
    
    def update_heartbeat(self, current_task: Optional[str] = None):
        """Update heartbeat timestamp (called by running agent)."""
        with sqlite3.connect(self.db_path) as conn:
            if current_task:
                conn.execute("""
                    UPDATE agent_state SET last_heartbeat = ?, current_task = ? WHERE id = 1
                """, (datetime.now().isoformat(), current_task))
            else:
                conn.execute("""
                    UPDATE agent_state SET last_heartbeat = ? WHERE id = 1
                """, (datetime.now().isoformat(),))
            conn.commit()
    
    def set_error(self, error_message: str, controlled_by: str = "system"):
        """Transition to error state with message."""
        return self.transition(
            AgentState.ERROR,
            controlled_by=controlled_by,
            reason="Agent error",
            error_message=error_message
        )
    
    def get_control_logs(self, limit: int = 50) -> list:
        """Get recent control log entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, previous_state, new_state, controlled_by, reason, result
                FROM agent_control_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            return [
                {
                    "timestamp": row[0],
                    "previous_state": row[1],
                    "new_state": row[2],
                    "controlled_by": row[3],
                    "reason": row[4],
                    "result": row[5]
                }
                for row in cursor.fetchall()
            ]
    
    def is_healthy(self, heartbeat_threshold_seconds: int = 30) -> Tuple[bool, str]:
        """
        Check if agent is healthy based on state and heartbeat.
        Returns (healthy, reason).
        """
        state_data = self.get_state()
        state = state_data["state"]
        
        if state == AgentState.ERROR.value:
            return False, f"Agent in error state: {state_data.get('error_message', 'Unknown')}"
        
        if state in (AgentState.DISCOVERING.value, AgentState.OUTREACH_RUNNING.value):
            heartbeat = state_data.get("last_heartbeat")
            if heartbeat:
                try:
                    last_beat = datetime.fromisoformat(heartbeat)
                    seconds_since = (datetime.now() - last_beat).total_seconds()
                    if seconds_since > heartbeat_threshold_seconds:
                        return False, f"Heartbeat stale ({int(seconds_since)}s ago)"
                except ValueError:
                    return False, "Invalid heartbeat timestamp"
            else:
                return False, "No heartbeat recorded"
        
        return True, "OK"
    
    def is_discovering(self) -> bool:
        """Check if agent is currently discovering."""
        return self.get_state()["state"] == AgentState.DISCOVERING.value
    
    def is_outreach_running(self) -> bool:
        """Check if agent is currently running outreach."""
        return self.get_state()["state"] == AgentState.OUTREACH_RUNNING.value
    
    def is_idle(self) -> bool:
        """Check if agent is idle."""
        return self.get_state()["state"] == AgentState.IDLE.value


# Singleton instance
agent_state_manager = AgentStateManager()

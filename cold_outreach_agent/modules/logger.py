"""Centralized logging module for all agent actions."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config.settings import settings


class ActionLogger:
    """Logs all agent actions to file, JSON, and database."""
    
    def __init__(self):
        self.log_dir = settings.LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup file logger
        self._setup_file_logger()
        
        # JSON log file path
        self.json_log_path = self.log_dir / f"actions_{datetime.now().strftime('%Y%m%d')}.json"
        
        # Database service (lazy loaded to avoid circular imports)
        self._db = None
    
    @property
    def db(self):
        """Lazy load database service."""
        if self._db is None:
            from ..services.db_service import DatabaseService
            self._db = DatabaseService()
        return self._db
    
    def _setup_file_logger(self):
        """Configure the file logger."""
        self.logger = logging.getLogger("outreach_agent")
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL))
        
        if not self.logger.handlers:
            # File handler
            log_file = self.log_dir / f"agent_{datetime.now().strftime('%Y%m%d')}.log"
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def log_action(
        self,
        lead_id: Optional[str],
        module_name: str,
        action: str,
        result: str,
        details: Optional[dict] = None
    ):
        """Log an action to file, JSON, and database."""
        timestamp = datetime.now().isoformat()
        
        # Log to file
        msg = f"[{module_name}] lead={lead_id} | action={action} | result={result}"
        if result == "success":
            self.logger.info(msg)
        elif result == "error":
            self.logger.error(msg)
        else:
            self.logger.warning(msg)
        
        # Convert details to string for database
        details_str = json.dumps(details) if details else None
        
        # Log to database
        try:
            self.db.add_agent_log(
                module=module_name,
                action=action,
                result=result,
                lead_id=lead_id,
                details=details_str
            )
        except Exception as e:
            self.logger.error(f"Failed to log to database: {e}")
        
        # Log to JSON file (backup)
        log_entry = {
            "timestamp": timestamp,
            "lead_id": lead_id,
            "module_name": module_name,
            "action": action,
            "result": result,
            "details": details or {}
        }
        self._append_json_log(log_entry)
    
    def _append_json_log(self, entry: dict):
        """Append entry to JSON log file."""
        try:
            logs = []
            if self.json_log_path.exists():
                try:
                    with open(self.json_log_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    logs = []
            
            logs.append(entry)
            
            # Keep only last 1000 entries per day
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            with open(self.json_log_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to write JSON log: {e}")
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)


# Singleton instance
action_logger = ActionLogger()

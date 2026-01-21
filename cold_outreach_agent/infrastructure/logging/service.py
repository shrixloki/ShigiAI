"""Production-grade logging service with structured JSON logging and audit trails."""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from ...core.models.common import AuditLog, EntityType
from ...core.exceptions import ColdOutreachAgentError


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": getattr(record, 'module', None),
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class ProductionLoggingService:
    """Production-grade logging service with audit capabilities."""
    
    def __init__(
        self,
        log_dir: Path,
        log_level: str = "INFO",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        db_service=None
    ):
        self.log_dir = log_dir
        self.log_level = getattr(logging, log_level.upper())
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.db_service = db_service
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup loggers
        self._setup_loggers()
        
        # Session tracking
        self.session_id = uuid4()
        
    def _setup_loggers(self):
        """Setup structured loggers for different components."""
        
        # Main application logger
        self.app_logger = self._create_logger(
            "cold_outreach_agent",
            self.log_dir / "application.log"
        )
        
        # API logger
        self.api_logger = self._create_logger(
            "cold_outreach_agent.api",
            self.log_dir / "api.log"
        )
        
        # Scraping logger
        self.scraping_logger = self._create_logger(
            "cold_outreach_agent.scraping",
            self.log_dir / "scraping.log"
        )
        
        # Email logger
        self.email_logger = self._create_logger(
            "cold_outreach_agent.email",
            self.log_dir / "email.log"
        )
        
        # Database logger
        self.database_logger = self._create_logger(
            "cold_outreach_agent.database",
            self.log_dir / "database.log"
        )
        
        # Audit logger (separate from audit database)
        self.audit_logger = self._create_logger(
            "cold_outreach_agent.audit",
            self.log_dir / "audit.log"
        )
        
        # Error logger (all errors)
        self.error_logger = self._create_logger(
            "cold_outreach_agent.errors",
            self.log_dir / "errors.log",
            level=logging.ERROR
        )
    
    def _create_logger(
        self,
        name: str,
        log_file: Path,
        level: Optional[int] = None
    ) -> logging.Logger:
        """Create a structured logger with file rotation."""
        
        logger = logging.getLogger(name)
        logger.setLevel(level or self.log_level)
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
        
        # Console handler for development
        if self.log_level <= logging.DEBUG:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(StructuredFormatter())
            logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
        
        return logger
    
    def log_application_event(
        self,
        message: str,
        level: str = "INFO",
        component: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """Log application event with structured data."""
        
        extra = {
            "component": component,
            "operation": operation,
            "session_id": str(self.session_id),
            **kwargs
        }
        
        log_level = getattr(logging, level.upper())
        self.app_logger.log(log_level, message, extra=extra)
    
    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None,
        **kwargs
    ):
        """Log API request with timing and metadata."""
        
        extra = {
            "request_method": method,
            "request_path": path,
            "response_status": status_code,
            "duration_ms": duration_ms,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "request_id": request_id,
            "session_id": str(self.session_id),
            **kwargs
        }
        
        level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 else logging.INFO
        self.api_logger.log(level, f"{method} {path} - {status_code} ({duration_ms:.2f}ms)", extra=extra)
    
    def log_scraping_operation(
        self,
        operation: str,
        query: Optional[str] = None,
        location: Optional[str] = None,
        results_count: Optional[int] = None,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs
    ):
        """Log scraping operation with results and performance data."""
        
        extra = {
            "operation": operation,
            "query": query,
            "location": location,
            "results_count": results_count,
            "duration_ms": duration_ms,
            "success": success,
            "error_message": error_message,
            "session_id": str(self.session_id),
            **kwargs
        }
        
        level = logging.ERROR if not success else logging.INFO
        message = f"Scraping {operation}"
        if query and location:
            message += f" - {query} in {location}"
        if results_count is not None:
            message += f" - {results_count} results"
        if error_message:
            message += f" - Error: {error_message}"
        
        self.scraping_logger.log(level, message, extra=extra)
    
    def log_email_operation(
        self,
        operation: str,
        campaign_id: Optional[UUID] = None,
        lead_id: Optional[UUID] = None,
        to_email: Optional[str] = None,
        provider: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs
    ):
        """Log email operation with delivery tracking."""
        
        extra = {
            "operation": operation,
            "campaign_id": str(campaign_id) if campaign_id else None,
            "lead_id": str(lead_id) if lead_id else None,
            "to_email": to_email,
            "provider": provider,
            "success": success,
            "error_message": error_message,
            "session_id": str(self.session_id),
            **kwargs
        }
        
        level = logging.ERROR if not success else logging.INFO
        message = f"Email {operation}"
        if to_email:
            message += f" to {to_email}"
        if provider:
            message += f" via {provider}"
        if error_message:
            message += f" - Error: {error_message}"
        
        self.email_logger.log(level, message, extra=extra)
    
    def log_database_operation(
        self,
        operation: str,
        table: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs
    ):
        """Log database operation with performance metrics."""
        
        extra = {
            "operation": operation,
            "table": table,
            "entity_id": str(entity_id) if entity_id else None,
            "duration_ms": duration_ms,
            "success": success,
            "error_message": error_message,
            "session_id": str(self.session_id),
            **kwargs
        }
        
        level = logging.ERROR if not success else logging.DEBUG
        message = f"Database {operation}"
        if table:
            message += f" on {table}"
        if duration_ms:
            message += f" ({duration_ms:.2f}ms)"
        if error_message:
            message += f" - Error: {error_message}"
        
        self.database_logger.log(level, message, extra=extra)
    
    def log_error(
        self,
        error: Exception,
        component: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Log error with full context and stack trace."""
        
        extra = {
            "component": component,
            "operation": operation,
            "error_type": type(error).__name__,
            "context": context or {},
            "session_id": str(self.session_id),
            **kwargs
        }
        
        # Add structured error info for our custom exceptions
        if isinstance(error, ColdOutreachAgentError):
            extra.update({
                "error_code": error.error_code,
                "error_context": error.context,
                "error_cause": str(error.cause) if error.cause else None
            })
        
        message = f"Error in {component or 'unknown'}"
        if operation:
            message += f" during {operation}"
        message += f": {str(error)}"
        
        self.error_logger.error(message, exc_info=True, extra=extra)
        
        # Also log to main application logger
        self.app_logger.error(message, exc_info=True, extra=extra)
    
    async def log_audit_event(
        self,
        entity_type: EntityType,
        entity_id: Optional[UUID],
        action: str,
        actor: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log audit event to both file and database."""
        
        audit_log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata or {},
            session_id=self.session_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Log to file
        extra = {
            "audit_id": str(audit_log.id),
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "action": action,
            "actor": actor,
            "old_values": old_values,
            "new_values": new_values,
            "metadata": metadata,
            "session_id": str(self.session_id),
            "request_id": str(request_id) if request_id else None,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        self.audit_logger.info(f"Audit: {action} on {entity_type} by {actor}", extra=extra)
        
        # Save to database if available
        if self.db_service:
            try:
                await self.db_service.save_audit_log(audit_log)
            except Exception as e:
                self.log_error(e, component="audit", operation="save_to_database")
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics and health info."""
        
        stats = {
            "session_id": str(self.session_id),
            "log_directory": str(self.log_dir),
            "log_level": logging.getLevelName(self.log_level),
            "loggers": {},
            "log_files": []
        }
        
        # Logger statistics
        for logger_name in [
            "cold_outreach_agent",
            "cold_outreach_agent.api",
            "cold_outreach_agent.scraping",
            "cold_outreach_agent.email",
            "cold_outreach_agent.database",
            "cold_outreach_agent.audit",
            "cold_outreach_agent.errors"
        ]:
            logger = logging.getLogger(logger_name)
            stats["loggers"][logger_name] = {
                "level": logging.getLevelName(logger.level),
                "handlers": len(logger.handlers),
                "disabled": logger.disabled
            }
        
        # Log file statistics
        for log_file in self.log_dir.glob("*.log*"):
            try:
                file_stat = log_file.stat()
                stats["log_files"].append({
                    "name": log_file.name,
                    "size_bytes": file_stat.st_size,
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                })
            except Exception:
                pass
        
        return stats
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files."""
        
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
        cleaned_files = []
        
        for log_file in self.log_dir.glob("*.log.*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_files.append(str(log_file))
            except Exception as e:
                self.log_error(e, component="logging", operation="cleanup_old_logs")
        
        if cleaned_files:
            self.log_application_event(
                f"Cleaned up {len(cleaned_files)} old log files",
                component="logging",
                operation="cleanup",
                cleaned_files=cleaned_files
            )
        
        return cleaned_files
    
    async def log_action(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[UUID] = None,
        request_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an action to the audit trail (alias for log_audit_event)."""
        await self.log_audit_event(
            entity_type=EntityType(entity_type),
            entity_id=entity_id,
            action=action,
            actor=actor,
            old_values=old_values,
            new_values=new_values,
            metadata=metadata,
            request_id=request_id or session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_state_transition(
        self,
        entity_type: str,
        entity_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a state transition."""
        try:
            transition_data = {
                "timestamp": datetime.now().isoformat(),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "from_state": from_state,
                "to_state": to_state,
                "actor": actor,
                "reason": reason,
                "metadata": metadata or {},
                "session_id": str(self.session_id)
            }
            
            self.audit_logger.info(json.dumps({
                "event_type": "state_transition",
                **transition_data
            }))
            
        except Exception as e:
            self.log_error(e, component="audit", operation="log_state_transition")
    
    def search_logs(
        self,
        query: str,
        log_file: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Search logs with filters."""
        
        results = []
        log_files = [self.log_dir / log_file] if log_file else list(self.log_dir.glob("*.log"))
        
        for file_path in log_files:
            if not file_path.exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if len(results) >= max_results:
                            break
                        
                        try:
                            log_entry = json.loads(line.strip())
                            
                            # Time filter
                            if start_time or end_time:
                                log_time = datetime.fromisoformat(log_entry.get('timestamp', ''))
                                if start_time and log_time < start_time:
                                    continue
                                if end_time and log_time > end_time:
                                    continue
                            
                            # Text search
                            if query.lower() in line.lower():
                                log_entry['_file'] = file_path.name
                                log_entry['_line'] = line_num
                                results.append(log_entry)
                        
                        except (json.JSONDecodeError, ValueError):
                            # Skip non-JSON lines
                            continue
            
            except Exception as e:
                self.log_error(e, component="logging", operation="search_logs")
        
        return results
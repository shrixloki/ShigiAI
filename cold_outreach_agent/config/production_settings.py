"""Production-grade configuration management with validation and environment support."""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from dotenv import load_dotenv

from ..core.exceptions import ConfigurationError, MissingConfigurationError, InvalidConfigurationError


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: Path = field(default_factory=lambda: Path("data/cold_outreach.db"))
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    backup_retention_days: int = 30
    connection_timeout: int = 30
    
    def __post_init__(self):
        # Ensure database directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class EmailConfig:
    """Email configuration."""
    # Provider settings
    primary_provider: str = "smtp"
    fallback_providers: List[str] = field(default_factory=lambda: ["smtp"])
    
    # SMTP settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_timeout: int = 60
    
    # Gmail API settings
    gmail_credentials_path: Optional[str] = None
    gmail_token_path: Optional[str] = None
    gmail_scopes: List[str] = field(default_factory=lambda: ["https://www.googleapis.com/auth/gmail.send"])
    
    # Sender information
    sender_name: str = ""
    sender_email: str = ""
    
    # Rate limiting
    max_emails_per_day: int = 20
    max_emails_per_hour: int = 5
    max_emails_per_minute: int = 1
    
    # Retry settings
    max_retry_attempts: int = 3
    retry_delays: List[int] = field(default_factory=lambda: [300, 900, 3600])  # 5min, 15min, 1hour
    
    # Template settings
    templates_dir: Optional[Path] = None
    default_template: str = "initial_outreach"
    
    def validate(self) -> List[str]:
        """Validate email configuration."""
        errors = []
        
        if not self.sender_email:
            errors.append("sender_email is required")
        
        if not self.sender_name:
            errors.append("sender_name is required")
        
        if self.primary_provider == "smtp":
            if not self.smtp_username:
                errors.append("smtp_username is required for SMTP provider")
            if not self.smtp_password:
                errors.append("smtp_password is required for SMTP provider")
        
        if self.primary_provider == "gmail_api":
            if not self.gmail_credentials_path:
                errors.append("gmail_credentials_path is required for Gmail API provider")
        
        if self.max_emails_per_day <= 0:
            errors.append("max_emails_per_day must be positive")
        
        if self.max_emails_per_hour <= 0:
            errors.append("max_emails_per_hour must be positive")
        
        return errors


@dataclass
class ScrapingConfig:
    """Web scraping configuration."""
    # Browser settings
    headless: bool = True
    browser_timeout: int = 60000
    page_timeout: int = 30000
    element_timeout: int = 15000
    
    # Anti-detection
    use_anti_detection: bool = True
    rotate_user_agents: bool = True
    random_delays: bool = True
    min_delay: float = 1.0
    max_delay: float = 3.0
    
    # Retry settings
    max_retry_attempts: int = 3
    retry_delay: float = 5.0
    
    # Rate limiting
    max_requests_per_minute: int = 10
    max_concurrent_sessions: int = 2
    
    # Fallback settings
    use_fallback_data: bool = True
    fallback_sample_size: int = 5
    
    # Performance
    max_results_per_session: int = 100
    max_scroll_attempts: int = 30
    
    def validate(self) -> List[str]:
        """Validate scraping configuration."""
        errors = []
        
        if self.browser_timeout <= 0:
            errors.append("browser_timeout must be positive")
        
        if self.max_retry_attempts < 0:
            errors.append("max_retry_attempts must be non-negative")
        
        if self.min_delay < 0 or self.max_delay < 0:
            errors.append("delay values must be non-negative")
        
        if self.min_delay > self.max_delay:
            errors.append("min_delay cannot be greater than max_delay")
        
        return errors


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    retention_days: int = 30
    
    # Structured logging
    use_json_format: bool = True
    include_request_id: bool = True
    
    # Component-specific logging
    log_api_requests: bool = True
    log_database_queries: bool = False  # Only in debug mode
    log_email_content: bool = False  # Security: don't log email content by default
    
    def __post_init__(self):
        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> List[str]:
        """Validate logging configuration."""
        errors = []
        
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            errors.append(f"log_level must be one of: {', '.join(valid_levels)}")
        
        if self.max_file_size <= 0:
            errors.append("max_file_size must be positive")
        
        if self.backup_count < 0:
            errors.append("backup_count must be non-negative")
        
        return errors


@dataclass
class SecurityConfig:
    """Security configuration."""
    # API security
    enable_cors: bool = True
    allowed_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:8082",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ])
    api_rate_limit: int = 100  # requests per minute
    
    # Data protection
    encrypt_sensitive_data: bool = False  # Future feature
    audit_all_actions: bool = True
    
    # Session management
    session_timeout_minutes: int = 60
    max_concurrent_sessions: int = 5
    
    def validate(self) -> List[str]:
        """Validate security configuration."""
        errors = []
        
        if self.api_rate_limit <= 0:
            errors.append("api_rate_limit must be positive")
        
        if self.session_timeout_minutes <= 0:
            errors.append("session_timeout_minutes must be positive")
        
        return errors


@dataclass
class SystemConfig:
    """System-wide configuration."""
    # Environment
    environment: str = "development"  # development, staging, production
    debug: bool = False
    
    # Performance
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300
    
    # Health checks
    health_check_interval: int = 60  # seconds
    enable_metrics: bool = True
    
    # Maintenance
    auto_cleanup_enabled: bool = True
    cleanup_interval_hours: int = 24
    
    def validate(self) -> List[str]:
        """Validate system configuration."""
        errors = []
        
        valid_environments = ["development", "staging", "production"]
        if self.environment not in valid_environments:
            errors.append(f"environment must be one of: {', '.join(valid_environments)}")
        
        if self.max_concurrent_tasks <= 0:
            errors.append("max_concurrent_tasks must be positive")
        
        return errors


class ProductionSettings:
    """Production-grade settings manager."""
    
    def __init__(self, env_file: Optional[Path] = None):
        self.project_root = Path(__file__).parent.parent
        self.env_file = env_file or self.project_root / ".env"
        
        # Load environment variables
        if self.env_file.exists():
            load_dotenv(self.env_file)
        
        # Initialize configuration sections
        self.database = self._load_database_config()
        self.email = self._load_email_config()
        self.scraping = self._load_scraping_config()
        self.logging = self._load_logging_config()
        self.security = self._load_security_config()
        self.system = self._load_system_config()
    
    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration from environment."""
        return DatabaseConfig(
            path=Path(os.getenv("DATABASE_PATH", "data/cold_outreach.db")),
            backup_enabled=self._get_bool("DATABASE_BACKUP_ENABLED", True),
            backup_interval_hours=self._get_int("DATABASE_BACKUP_INTERVAL_HOURS", 24),
            backup_retention_days=self._get_int("DATABASE_BACKUP_RETENTION_DAYS", 30),
            connection_timeout=self._get_int("DATABASE_CONNECTION_TIMEOUT", 30)
        )
    
    def _load_email_config(self) -> EmailConfig:
        """Load email configuration from environment."""
        return EmailConfig(
            primary_provider=os.getenv("EMAIL_PRIMARY_PROVIDER", "smtp"),
            fallback_providers=self._get_list("EMAIL_FALLBACK_PROVIDERS", ["smtp"]),
            
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=self._get_int("SMTP_PORT", 587),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=self._get_bool("SMTP_USE_TLS", True),
            smtp_timeout=self._get_int("SMTP_TIMEOUT", 60),
            
            gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH"),
            gmail_token_path=os.getenv("GMAIL_TOKEN_PATH"),
            
            sender_name=os.getenv("SENDER_NAME", ""),
            sender_email=os.getenv("SENDER_EMAIL", ""),
            
            max_emails_per_day=self._get_int("MAX_EMAILS_PER_DAY", 20),
            max_emails_per_hour=self._get_int("MAX_EMAILS_PER_HOUR", 5),
            max_emails_per_minute=self._get_int("MAX_EMAILS_PER_MINUTE", 1),
            
            max_retry_attempts=self._get_int("EMAIL_MAX_RETRY_ATTEMPTS", 3),
            retry_delays=self._get_int_list("EMAIL_RETRY_DELAYS", [300, 900, 3600]),
            
            templates_dir=Path(os.getenv("EMAIL_TEMPLATES_DIR", "templates")) if os.getenv("EMAIL_TEMPLATES_DIR") else None,
            default_template=os.getenv("EMAIL_DEFAULT_TEMPLATE", "initial_outreach")
        )
    
    def _load_scraping_config(self) -> ScrapingConfig:
        """Load scraping configuration from environment."""
        return ScrapingConfig(
            headless=self._get_bool("SCRAPING_HEADLESS", True),
            browser_timeout=self._get_int("SCRAPING_BROWSER_TIMEOUT", 60000),
            page_timeout=self._get_int("SCRAPING_PAGE_TIMEOUT", 30000),
            element_timeout=self._get_int("SCRAPING_ELEMENT_TIMEOUT", 15000),
            
            use_anti_detection=self._get_bool("SCRAPING_USE_ANTI_DETECTION", True),
            rotate_user_agents=self._get_bool("SCRAPING_ROTATE_USER_AGENTS", True),
            random_delays=self._get_bool("SCRAPING_RANDOM_DELAYS", True),
            min_delay=self._get_float("SCRAPING_MIN_DELAY", 1.0),
            max_delay=self._get_float("SCRAPING_MAX_DELAY", 3.0),
            
            max_retry_attempts=self._get_int("SCRAPING_MAX_RETRY_ATTEMPTS", 3),
            retry_delay=self._get_float("SCRAPING_RETRY_DELAY", 5.0),
            
            max_requests_per_minute=self._get_int("SCRAPING_MAX_REQUESTS_PER_MINUTE", 10),
            max_concurrent_sessions=self._get_int("SCRAPING_MAX_CONCURRENT_SESSIONS", 2),
            
            use_fallback_data=self._get_bool("SCRAPING_USE_FALLBACK_DATA", True),
            fallback_sample_size=self._get_int("SCRAPING_FALLBACK_SAMPLE_SIZE", 5),
            
            max_results_per_session=self._get_int("SCRAPING_MAX_RESULTS_PER_SESSION", 100),
            max_scroll_attempts=self._get_int("SCRAPING_MAX_SCROLL_ATTEMPTS", 30)
        )
    
    def _load_logging_config(self) -> LoggingConfig:
        """Load logging configuration from environment."""
        return LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            log_dir=Path(os.getenv("LOG_DIR", "logs")),
            max_file_size=self._get_int("LOG_MAX_FILE_SIZE", 10 * 1024 * 1024),
            backup_count=self._get_int("LOG_BACKUP_COUNT", 5),
            retention_days=self._get_int("LOG_RETENTION_DAYS", 30),
            
            use_json_format=self._get_bool("LOG_USE_JSON_FORMAT", True),
            include_request_id=self._get_bool("LOG_INCLUDE_REQUEST_ID", True),
            
            log_api_requests=self._get_bool("LOG_API_REQUESTS", True),
            log_database_queries=self._get_bool("LOG_DATABASE_QUERIES", False),
            log_email_content=self._get_bool("LOG_EMAIL_CONTENT", False)
        )
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration from environment."""
        return SecurityConfig(
            enable_cors=self._get_bool("SECURITY_ENABLE_CORS", True),
            allowed_origins=self._get_list("SECURITY_ALLOWED_ORIGINS", ["http://localhost:3000", "http://localhost:5173"]),
            api_rate_limit=self._get_int("SECURITY_API_RATE_LIMIT", 100),
            
            encrypt_sensitive_data=self._get_bool("SECURITY_ENCRYPT_SENSITIVE_DATA", False),
            audit_all_actions=self._get_bool("SECURITY_AUDIT_ALL_ACTIONS", True),
            
            session_timeout_minutes=self._get_int("SECURITY_SESSION_TIMEOUT_MINUTES", 60),
            max_concurrent_sessions=self._get_int("SECURITY_MAX_CONCURRENT_SESSIONS", 5)
        )
    
    def _load_system_config(self) -> SystemConfig:
        """Load system configuration from environment."""
        return SystemConfig(
            environment=os.getenv("ENVIRONMENT", "development"),
            debug=self._get_bool("DEBUG", False),
            
            max_concurrent_tasks=self._get_int("SYSTEM_MAX_CONCURRENT_TASKS", 10),
            task_timeout_seconds=self._get_int("SYSTEM_TASK_TIMEOUT_SECONDS", 300),
            
            health_check_interval=self._get_int("SYSTEM_HEALTH_CHECK_INTERVAL", 60),
            enable_metrics=self._get_bool("SYSTEM_ENABLE_METRICS", True),
            
            auto_cleanup_enabled=self._get_bool("SYSTEM_AUTO_CLEANUP_ENABLED", True),
            cleanup_interval_hours=self._get_int("SYSTEM_CLEANUP_INTERVAL_HOURS", 24)
        )
    
    def _get_bool(self, key: str, default: bool) -> bool:
        """Get boolean value from environment."""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def _get_int(self, key: str, default: int) -> int:
        """Get integer value from environment."""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default
    
    def _get_float(self, key: str, default: float) -> float:
        """Get float value from environment."""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default
    
    def _get_list(self, key: str, default: List[str]) -> List[str]:
        """Get list value from environment (comma-separated)."""
        value = os.getenv(key)
        if not value:
            return default
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def _get_int_list(self, key: str, default: List[int]) -> List[int]:
        """Get list of integers from environment (comma-separated)."""
        value = os.getenv(key)
        if not value:
            return default
        try:
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        except ValueError:
            return default
    
    def validate(self) -> Dict[str, List[str]]:
        """Validate all configuration sections."""
        validation_results = {}
        
        sections = {
            "database": self.database,
            "email": self.email,
            "scraping": self.scraping,
            "logging": self.logging,
            "security": self.security,
            "system": self.system
        }
        
        for section_name, section_config in sections.items():
            if hasattr(section_config, 'validate'):
                errors = section_config.validate()
                if errors:
                    validation_results[section_name] = errors
        
        return validation_results
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation summary with overall status."""
        validation_results = self.validate()
        
        total_errors = sum(len(errors) for errors in validation_results.values())
        
        return {
            "is_valid": total_errors == 0,
            "total_errors": total_errors,
            "sections_with_errors": len(validation_results),
            "errors_by_section": validation_results,
            "environment": self.system.environment,
            "debug_mode": self.system.debug
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary (excluding sensitive data)."""
        return {
            "database": {
                "path": str(self.database.path),
                "backup_enabled": self.database.backup_enabled,
                "backup_interval_hours": self.database.backup_interval_hours
            },
            "email": {
                "primary_provider": self.email.primary_provider,
                "sender_name": self.email.sender_name,
                "sender_email": self.email.sender_email,
                "max_emails_per_day": self.email.max_emails_per_day,
                "max_emails_per_hour": self.email.max_emails_per_hour
            },
            "scraping": {
                "headless": self.scraping.headless,
                "use_anti_detection": self.scraping.use_anti_detection,
                "max_results_per_session": self.scraping.max_results_per_session
            },
            "logging": {
                "level": self.logging.level,
                "log_dir": str(self.logging.log_dir),
                "use_json_format": self.logging.use_json_format
            },
            "security": {
                "enable_cors": self.security.enable_cors,
                "api_rate_limit": self.security.api_rate_limit,
                "audit_all_actions": self.security.audit_all_actions
            },
            "system": {
                "environment": self.system.environment,
                "debug": self.system.debug,
                "max_concurrent_tasks": self.system.max_concurrent_tasks
            }
        }


# Global settings instance
settings = ProductionSettings()
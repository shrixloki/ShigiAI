"""Configuration loader from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings loaded from environment."""
    
    # Project root path
    PROJECT_ROOT: Path = PROJECT_ROOT
    
    # Email Method
    EMAIL_METHOD: str = os.getenv("EMAIL_METHOD", "gmail_api")
    
    # SMTP Settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", os.getenv("SMTP_USERNAME", ""))
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    
    # Gmail API
    GMAIL_TOKEN_PATH: str = os.getenv("GMAIL_TOKEN_PATH", "token.json")
    
    # Sender Info
    SENDER_NAME: str = os.getenv("SENDER_NAME", "")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")
    
    # Rate Limits
    MAX_EMAILS_PER_DAY: int = int(os.getenv("MAX_EMAILS_PER_DAY", "20"))
    FOLLOWUP_DELAY_DAYS: int = int(os.getenv("FOLLOWUP_DELAY_DAYS", "3"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = PROJECT_ROOT / os.getenv("LOG_DIR", "logs")
    
    # Paths
    TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required settings. Returns list of missing fields."""
        errors = []
        if not cls.SENDER_EMAIL:
            errors.append("SENDER_EMAIL")
        if cls.EMAIL_METHOD == "smtp":
            if not cls.SMTP_USER:
                errors.append("SMTP_USER")
            if not cls.SMTP_PASSWORD:
                errors.append("SMTP_PASSWORD")
        return errors


settings = Settings()

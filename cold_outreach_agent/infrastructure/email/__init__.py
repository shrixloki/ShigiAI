"""Email infrastructure with SMTP/Gmail API and retry logic."""

from .service import ProductionEmailService
from .providers import SMTPProvider, GmailAPIProvider
from .templates import EmailTemplateManager

__all__ = [
    "ProductionEmailService",
    "SMTPProvider", 
    "GmailAPIProvider",
    "EmailTemplateManager"
]
"""Database infrastructure with migrations and proper indexing."""

from .service import ProductionDatabaseService
from .migrations import MigrationManager
from .models import DatabaseLead, DatabaseEmailCampaign, DatabaseAuditLog

__all__ = [
    "ProductionDatabaseService",
    "MigrationManager", 
    "DatabaseLead",
    "DatabaseEmailCampaign",
    "DatabaseAuditLog"
]
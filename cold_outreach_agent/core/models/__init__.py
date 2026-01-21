"""Domain models and data structures."""

from .lead import Lead, LeadState, ReviewStatus, DiscoverySource
from .email import EmailCampaign, EmailState, CampaignType
from .common import AuditLog, StateTransition, OperationResult

__all__ = [
    "Lead",
    "LeadState", 
    "ReviewStatus",
    "DiscoverySource",
    "EmailCampaign",
    "EmailState",
    "CampaignType",
    "AuditLog",
    "StateTransition",
    "OperationResult"
]
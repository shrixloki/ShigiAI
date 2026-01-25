"""Domain models and data structures."""

# Core models
from .lead import Lead, LeadState, ReviewStatus, DiscoverySource, LeadCreate, LeadUpdate, LeadFilter
from .email import EmailCampaign, EmailState, CampaignType, EmailCampaignCreate, EmailCampaignUpdate
from .common import AuditLog, StateTransition, OperationResult

# Enrichment models
from .enrichment import (
    LeadEnrichment, EnrichmentState, EnrichmentSource, BusinessMaturity, CompanySize,
    TechStackItem, TechStackCategory, HiringSignal, ContactIntentSignal, 
    SocialPresence, DecisionMaker, EnrichmentCreate, EnrichmentUpdate
)

# Scoring models
from .scoring import (
    LeadScore, ScoreComponent, ScoreCategory, ScoreLevel,
    ScoreExplanation, ScoringRule, ScoringRuleType, ScoreHistory,
    ScoreOverrideRequest, ScoringConfigUpdate
)

# Campaign intelligence models
from .campaign import (
    EmailSequence, SequenceStep, SequenceStepType, SequenceStatus,
    LeadSequenceEnrollment, LeadSequenceStatus, ConditionType, ConditionBranch,
    PersonalizationToken, SequenceCreate, SequenceUpdate, EnrollLeadRequest
)

# CRM models
from .crm import (
    EmailReply, ReplyClassification, ConversationThread, ConversationStatus,
    InternalNote, NoteType, Opportunity, OpportunityStage, LeadStatusTransition,
    ReplyClassifyRequest, OpportunityCreate, OpportunityUpdate, NoteCreate
)

# User and role models
from .users import (
    User, UserRole, Permission, ROLE_PERMISSIONS,
    LeadAssignment, ApprovalDelegation, UserActivityLog, UserSession,
    UserCreate, UserUpdate, AssignLeadRequest, DelegateApprovalRequest
)

# Compliance models
from .compliance import (
    UnsubscribeRecord, UnsubscribeSource, DoNotContactEntry, DoNotContactReason,
    SpamRiskAssessment, SpamRiskLevel, DomainWarmupStatus, DomainWarmupStage,
    CoolingOffPeriod, ComplianceCheck, AddToDoNotContactRequest, 
    RemoveFromDoNotContactRequest, StartCoolingOffRequest
)

# Analytics models
from .analytics import (
    LeadFunnelData, FunnelStage, CampaignPerformance, TemplatePerformance,
    IndustryResponseRate, LocationHeatmapData, TimeSeriesMetric, TimeSeriesDataPoint,
    MetricPeriod, MetricType, ChartType, DashboardWidget, AnalyticsDashboard,
    AnalyticsQuery, AnalyticsExportRequest
)

# Public signal models
from .public_signal import (
    BusinessProfile, ProfileStatus, RoleType, EngagementType, BudgetRange,
    DeveloperInquiry, ProfileApprovalRecord, ApprovalDecision,
    DirectorySearchFilters, DirectoryEntry, ProfileCreateRequest, 
    ProfileUpdateRequest, SendInquiryRequest
)

# Sync models
from .sync import (
    SyncConfiguration, SyncJob, SyncConflict, SyncDirection, SyncStatus,
    ConflictResolution, SyncSource, FieldMapping, WebhookConfig, WebhookDelivery,
    APIKey, GoogleSheetsConfig, CSVImportConfig, CreateSyncConfigRequest,
    TriggerSyncRequest, ResolveConflictRequest, CreateAPIKeyRequest
)

__all__ = [
    # Core
    "Lead", "LeadState", "ReviewStatus", "DiscoverySource", "LeadCreate", "LeadUpdate", "LeadFilter",
    "EmailCampaign", "EmailState", "CampaignType", "EmailCampaignCreate", "EmailCampaignUpdate",
    "AuditLog", "StateTransition", "OperationResult",
    
    # Enrichment
    "LeadEnrichment", "EnrichmentState", "EnrichmentSource", "BusinessMaturity", "CompanySize",
    "TechStackItem", "TechStackCategory", "HiringSignal", "ContactIntentSignal",
    "SocialPresence", "DecisionMaker", "EnrichmentCreate", "EnrichmentUpdate",
    
    # Scoring
    "LeadScore", "ScoreComponent", "ScoreCategory", "ScoreLevel",
    "ScoreExplanation", "ScoringRule", "ScoringRuleType", "ScoreHistory",
    "ScoreOverrideRequest", "ScoringConfigUpdate",
    
    # Campaign
    "EmailSequence", "SequenceStep", "SequenceStepType", "SequenceStatus",
    "LeadSequenceEnrollment", "LeadSequenceStatus", "ConditionType", "ConditionBranch",
    "PersonalizationToken", "SequenceCreate", "SequenceUpdate", "EnrollLeadRequest",
    
    # CRM
    "EmailReply", "ReplyClassification", "ConversationThread", "ConversationStatus",
    "InternalNote", "NoteType", "Opportunity", "OpportunityStage", "LeadStatusTransition",
    "ReplyClassifyRequest", "OpportunityCreate", "OpportunityUpdate", "NoteCreate",
    
    # Users
    "User", "UserRole", "Permission", "ROLE_PERMISSIONS",
    "LeadAssignment", "ApprovalDelegation", "UserActivityLog", "UserSession",
    "UserCreate", "UserUpdate", "AssignLeadRequest", "DelegateApprovalRequest",
    
    # Compliance
    "UnsubscribeRecord", "UnsubscribeSource", "DoNotContactEntry", "DoNotContactReason",
    "SpamRiskAssessment", "SpamRiskLevel", "DomainWarmupStatus", "DomainWarmupStage",
    "CoolingOffPeriod", "ComplianceCheck", "AddToDoNotContactRequest",
    "RemoveFromDoNotContactRequest", "StartCoolingOffRequest",
    
    # Analytics
    "LeadFunnelData", "FunnelStage", "CampaignPerformance", "TemplatePerformance",
    "IndustryResponseRate", "LocationHeatmapData", "TimeSeriesMetric", "TimeSeriesDataPoint",
    "MetricPeriod", "MetricType", "ChartType", "DashboardWidget", "AnalyticsDashboard",
    "AnalyticsQuery", "AnalyticsExportRequest",
    
    # Public Signal
    "BusinessProfile", "ProfileStatus", "RoleType", "EngagementType", "BudgetRange",
    "DeveloperInquiry", "ProfileApprovalRecord", "ApprovalDecision",
    "DirectorySearchFilters", "DirectoryEntry", "ProfileCreateRequest",
    "ProfileUpdateRequest", "SendInquiryRequest",
    
    # Sync
    "SyncConfiguration", "SyncJob", "SyncConflict", "SyncDirection", "SyncStatus",
    "ConflictResolution", "SyncSource", "FieldMapping", "WebhookConfig", "WebhookDelivery",
    "APIKey", "GoogleSheetsConfig", "CSVImportConfig", "CreateSyncConfigRequest",
    "TriggerSyncRequest", "ResolveConflictRequest", "CreateAPIKeyRequest"
]
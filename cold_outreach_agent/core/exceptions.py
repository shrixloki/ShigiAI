"""Production-grade exception hierarchy with proper error codes and context."""

from typing import Optional, Dict, Any
from uuid import UUID


class ColdOutreachAgentError(Exception):
    """Base exception for all cold outreach agent errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.context = context or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None
        }


# Database Exceptions
class DatabaseError(ColdOutreachAgentError):
    """Database operation failed."""
    pass


class LeadNotFoundError(DatabaseError):
    """Lead not found in database."""
    
    def __init__(self, lead_id: UUID, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Lead {lead_id} not found",
            error_code="LEAD_NOT_FOUND",
            context={"lead_id": str(lead_id), **(context or {})}
        )


class EmailCampaignNotFoundError(DatabaseError):
    """Email campaign not found in database."""
    
    def __init__(self, campaign_id: UUID, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Email campaign {campaign_id} not found",
            error_code="EMAIL_CAMPAIGN_NOT_FOUND",
            context={"campaign_id": str(campaign_id), **(context or {})}
        )


class DuplicateLeadError(DatabaseError):
    """Attempt to create duplicate lead."""
    
    def __init__(self, business_name: str, location: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Lead already exists: {business_name} in {location}",
            error_code="DUPLICATE_LEAD",
            context={"business_name": business_name, "location": location, **(context or {})}
        )


class ConcurrentModificationError(DatabaseError):
    """Concurrent modification detected (optimistic locking)."""
    
    def __init__(self, entity_id: UUID, entity_type: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Concurrent modification detected for {entity_type} {entity_id}",
            error_code="CONCURRENT_MODIFICATION",
            context={"entity_id": str(entity_id), "entity_type": entity_type, **(context or {})}
        )


# State Machine Exceptions
class InvalidStateTransitionError(ColdOutreachAgentError):
    """Invalid state transition attempted."""
    
    def __init__(
        self,
        from_state: str,
        to_state: str,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            f"Invalid {entity_type} transition from {from_state} to {to_state}",
            error_code="INVALID_STATE_TRANSITION",
            context={
                "from_state": from_state,
                "to_state": to_state,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id else None,
                **(context or {})
            }
        )


# Scraping Exceptions
class GoogleMapsScrapingError(ColdOutreachAgentError):
    """Google Maps scraping operation failed."""
    pass


class LocationResolutionError(GoogleMapsScrapingError):
    """Failed to resolve location to coordinates."""
    
    def __init__(self, location: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Failed to resolve location: {location}",
            error_code="LOCATION_RESOLUTION_FAILED",
            context={"location": location, **(context or {})}
        )


class AntiDetectionError(GoogleMapsScrapingError):
    """Anti-bot detection triggered."""
    
    def __init__(self, detection_type: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Anti-bot detection triggered: {detection_type}",
            error_code="ANTI_DETECTION_TRIGGERED",
            context={"detection_type": detection_type, **(context or {})}
        )


class WebsiteAnalysisError(ColdOutreachAgentError):
    """Website analysis failed."""
    
    def __init__(self, website_url: str, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Website analysis failed for {website_url}: {reason}",
            error_code="WEBSITE_ANALYSIS_FAILED",
            context={"website_url": website_url, "reason": reason, **(context or {})}
        )


# Email Exceptions
class EmailDeliveryError(ColdOutreachAgentError):
    """Email delivery failed."""
    pass


class RateLimitExceededError(EmailDeliveryError):
    """Email rate limit exceeded."""
    
    def __init__(self, limit_type: str, current_count: int, max_count: int, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"{limit_type} rate limit exceeded: {current_count}/{max_count}",
            error_code="RATE_LIMIT_EXCEEDED",
            context={
                "limit_type": limit_type,
                "current_count": current_count,
                "max_count": max_count,
                **(context or {})
            }
        )


class EmailProviderError(EmailDeliveryError):
    """Email provider operation failed."""
    
    def __init__(self, provider_name: str, operation: str, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Email provider {provider_name} {operation} failed: {reason}",
            error_code="EMAIL_PROVIDER_ERROR",
            context={
                "provider_name": provider_name,
                "operation": operation,
                "reason": reason,
                **(context or {})
            }
        )


class EmailTemplateError(EmailDeliveryError):
    """Email template processing failed."""
    
    def __init__(self, template_id: str, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Email template {template_id} processing failed: {reason}",
            error_code="EMAIL_TEMPLATE_ERROR",
            context={"template_id": template_id, "reason": reason, **(context or {})}
        )


# Configuration Exceptions
class ConfigurationError(ColdOutreachAgentError):
    """Configuration error."""
    pass


class MissingConfigurationError(ConfigurationError):
    """Required configuration missing."""
    
    def __init__(self, config_key: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Required configuration missing: {config_key}",
            error_code="MISSING_CONFIGURATION",
            context={"config_key": config_key, **(context or {})}
        )


class InvalidConfigurationError(ConfigurationError):
    """Invalid configuration value."""
    
    def __init__(self, config_key: str, value: Any, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Invalid configuration for {config_key}: {reason}",
            error_code="INVALID_CONFIGURATION",
            context={"config_key": config_key, "value": str(value), "reason": reason, **(context or {})}
        )


# Business Logic Exceptions
class LeadValidationError(ColdOutreachAgentError):
    """Lead validation failed."""
    
    def __init__(self, lead_id: Optional[UUID], validation_errors: list, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Lead validation failed: {', '.join(validation_errors)}",
            error_code="LEAD_VALIDATION_FAILED",
            context={
                "lead_id": str(lead_id) if lead_id else None,
                "validation_errors": validation_errors,
                **(context or {})
            }
        )


class ApprovalRequiredError(ColdOutreachAgentError):
    """Human approval required for operation."""
    
    def __init__(self, operation: str, entity_id: UUID, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Human approval required for {operation} on {entity_id}",
            error_code="APPROVAL_REQUIRED",
            context={"operation": operation, "entity_id": str(entity_id), **(context or {})}
        )


class OutreachNotAllowedError(ColdOutreachAgentError):
    """Outreach not allowed for lead."""
    
    def __init__(self, lead_id: UUID, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Outreach not allowed for lead {lead_id}: {reason}",
            error_code="OUTREACH_NOT_ALLOWED",
            context={"lead_id": str(lead_id), "reason": reason, **(context or {})}
        )


# System Exceptions
class SystemHealthError(ColdOutreachAgentError):
    """System health check failed."""
    pass


class ResourceExhaustionError(SystemHealthError):
    """System resources exhausted."""
    
    def __init__(self, resource_type: str, current_usage: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Resource exhaustion: {resource_type} usage at {current_usage}",
            error_code="RESOURCE_EXHAUSTION",
            context={"resource_type": resource_type, "current_usage": current_usage, **(context or {})}
        )


class ExternalServiceError(ColdOutreachAgentError):
    """External service unavailable or failed."""
    
    def __init__(self, service_name: str, operation: str, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"External service {service_name} {operation} failed: {reason}",
            error_code="EXTERNAL_SERVICE_ERROR",
            context={"service_name": service_name, "operation": operation, "reason": reason, **(context or {})}
        )


# Desktop Application Exceptions
class DesktopPackagingError(ColdOutreachAgentError):
    """Desktop application packaging failed."""
    
    def __init__(self, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Desktop packaging failed: {reason}",
            error_code="DESKTOP_PACKAGING_ERROR",
            context={"reason": reason, **(context or {})}
        )


class DesktopRuntimeError(ColdOutreachAgentError):
    """Desktop application runtime error."""
    
    def __init__(self, operation: str, reason: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            f"Desktop runtime error during {operation}: {reason}",
            error_code="DESKTOP_RUNTIME_ERROR",
            context={"operation": operation, "reason": reason, **(context or {})}
        )
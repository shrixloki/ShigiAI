"""Production-grade FastAPI server with comprehensive error handling, observability, and security."""

import asyncio
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from pydantic import BaseModel, Field, ValidationError
import uvicorn

from ..config.production_settings import settings
from ..core.exceptions import ColdOutreachAgentError
from ..core.models.common import OperationResult, PaginationParams, EntityType
from ..core.models.lead import Lead, LeadCreate, LeadUpdate, LeadFilter, LeadState, ReviewStatus
from ..core.models.email import EmailCampaign, EmailCampaignCreate, EmailState, CampaignType
from ..infrastructure.database.service import ProductionDatabaseService
from ..infrastructure.logging.service import ProductionLoggingService
from ..infrastructure.email.service import ProductionEmailService
from ..infrastructure.scraping.google_maps_scraper import ProductionGoogleMapsScraperService
from ..core.state_machines.lead_state_machine import LeadStateMachine
from ..core.state_machines.email_state_machine import EmailStateMachine


# Request/Response Models
class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    error_code: str
    details: Optional[Dict[str, Any]] = None
    request_id: str
    timestamp: str


class SuccessResponse(BaseModel):
    """Standard success response model."""
    success: bool = True
    data: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None
    request_id: str
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    environment: str
    checks: Dict[str, Dict[str, Any]]
    uptime_seconds: float


class DiscoveryRequest(BaseModel):
    """Discovery request model."""
    query: str = Field(..., min_length=1, max_length=100, description="Business category to search for")
    location: str = Field(..., min_length=1, max_length=200, description="Location to search in")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum number of results")


class BulkActionRequest(BaseModel):
    """Bulk action request model."""
    lead_ids: List[str] = Field(..., min_items=1, max_items=100)
    reason: Optional[str] = Field(None, max_length=500)


class EmailCampaignRequest(BaseModel):
    """Email campaign creation request."""
    lead_id: str
    campaign_type: CampaignType
    template_id: Optional[str] = None
    custom_subject: Optional[str] = Field(None, max_length=255)
    custom_body: Optional[str] = Field(None, max_length=10000)


# Global services (initialized in lifespan)
db_service: Optional[ProductionDatabaseService] = None
logging_service: Optional[ProductionLoggingService] = None
email_service: Optional[ProductionEmailService] = None
scraping_service: Optional[ProductionGoogleMapsScraperService] = None
lead_state_machine: Optional[LeadStateMachine] = None
email_state_machine: Optional[EmailStateMachine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_service, logging_service, email_service, scraping_service
    global lead_state_machine, email_state_machine
    
    # Startup
    try:
        # Initialize logging service
        logging_service = ProductionLoggingService(
            log_dir=settings.logging.log_dir,
            log_level=settings.logging.level,
            max_file_size=settings.logging.max_file_size,
            backup_count=settings.logging.backup_count
        )
        
        logging_service.log_application_event(
            "Application startup initiated",
            component="server",
            operation="startup"
        )
        
        # Initialize database service
        db_service = ProductionDatabaseService(settings.database.path)
        await db_service.initialize()
        
        # Initialize state machines
        lead_state_machine = LeadStateMachine(db_service, logging_service)
        email_state_machine = EmailStateMachine(db_service, logging_service)
        
        # Initialize email service
        email_config = {
            'primary_provider': settings.email.primary_provider,
            'smtp_host': settings.email.smtp_host,
            'smtp_port': settings.email.smtp_port,
            'smtp_username': settings.email.smtp_username,
            'smtp_password': settings.email.smtp_password,
            'smtp_use_tls': settings.email.smtp_use_tls,
            'sender_name': settings.email.sender_name,
            'sender_email': settings.email.sender_email,
            'max_emails_per_day': settings.email.max_emails_per_day,
            'max_emails_per_hour': settings.email.max_emails_per_hour
        }
        
        email_service = ProductionEmailService(
            db_service=db_service,
            audit_service=logging_service,
            config=email_config
        )
        
        # Initialize scraping service
        scraping_service = ProductionGoogleMapsScraperService()
        
        logging_service.log_application_event(
            "Application startup completed successfully",
            component="server",
            operation="startup"
        )
        
        yield
        
    except Exception as e:
        if logging_service:
            logging_service.log_error(e, component="server", operation="startup")
        raise
    
    # Shutdown
    try:
        if logging_service:
            logging_service.log_application_event(
                "Application shutdown initiated",
                component="server",
                operation="shutdown"
            )
        
        # Cleanup resources
        if scraping_service:
            await scraping_service._cleanup_browser()
        
        if logging_service:
            logging_service.log_application_event(
                "Application shutdown completed",
                component="server",
                operation="shutdown"
            )
    
    except Exception as e:
        if logging_service:
            logging_service.log_error(e, component="server", operation="shutdown")


# Create FastAPI app
app = FastAPI(
    title="Cold Outreach Agent API",
    description="Production-grade cold outreach automation system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.system.debug else None,
    redoc_url="/redoc" if settings.system.debug else None
)

# Add middleware
if settings.security.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
)


# Dependency injection
async def get_request_id(request: Request) -> str:
    """Generate or extract request ID."""
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    return request_id


async def get_db() -> ProductionDatabaseService:
    """Get database service dependency."""
    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service not available"
        )
    return db_service


async def get_logging() -> ProductionLoggingService:
    """Get logging service dependency."""
    if not logging_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Logging service not available"
        )
    return logging_service


# Middleware for request logging and timing
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests with timing and error handling."""
    start_time = time.time()
    request_id = await get_request_id(request)
    
    # Log request start
    if logging_service and settings.logging.log_api_requests:
        logging_service.log_api_request(
            method=request.method,
            path=str(request.url.path),
            status_code=0,  # Will be updated
            duration_ms=0,  # Will be updated
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            request_id=request_id
        )
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log successful request
        if logging_service and settings.logging.log_api_requests:
            logging_service.log_api_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=duration_ms,
                user_agent=request.headers.get("user-agent"),
                ip_address=request.client.host if request.client else None,
                request_id=request_id
            )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log error
        if logging_service:
            logging_service.log_error(
                e,
                component="api",
                operation=f"{request.method} {request.url.path}",
                context={"request_id": request_id, "duration_ms": duration_ms}
            )
        
        # Return error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="Internal server error",
                error_code="INTERNAL_ERROR",
                request_id=request_id,
                timestamp=datetime.now().isoformat()
            ).dict()
        )


# Exception handlers
@app.exception_handler(ColdOutreachAgentError)
async def cold_outreach_exception_handler(request: Request, exc: ColdOutreachAgentError):
    """Handle custom application exceptions."""
    request_id = getattr(request.state, 'request_id', str(uuid4()))
    
    if logging_service:
        logging_service.log_error(
            exc,
            component="api",
            operation=f"{request.method} {request.url.path}",
            context={"request_id": request_id}
        )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error=exc.message,
            error_code=exc.error_code,
            details=exc.context,
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        ).dict()
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    request_id = getattr(request.state, 'request_id', str(uuid4()))
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation error",
            error_code="VALIDATION_ERROR",
            details={"validation_errors": exc.errors()},
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        ).dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler_override(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format."""
    request_id = getattr(request.state, 'request_id', str(uuid4()))
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            error_code="HTTP_ERROR",
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        ).dict()
    )


# Health and system endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint."""
    start_time = time.time()
    checks = {}
    
    # Database health
    try:
        if db_service:
            # Simple database query
            await db_service.get_leads(pagination=PaginationParams(page=1, page_size=1))
            checks["database"] = {"status": "healthy", "message": "Database connection successful"}
        else:
            checks["database"] = {"status": "unhealthy", "message": "Database service not initialized"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "message": str(e)}
    
    # Email service health
    try:
        if email_service:
            provider_status = await email_service.get_provider_status()
            healthy_providers = sum(1 for p in provider_status.values() if p.get("available", False))
            if healthy_providers > 0:
                checks["email"] = {"status": "healthy", "message": f"{healthy_providers} email providers available"}
            else:
                checks["email"] = {"status": "unhealthy", "message": "No email providers available"}
        else:
            checks["email"] = {"status": "unhealthy", "message": "Email service not initialized"}
    except Exception as e:
        checks["email"] = {"status": "unhealthy", "message": str(e)}
    
    # Configuration health
    validation_summary = settings.get_validation_summary()
    if validation_summary["is_valid"]:
        checks["configuration"] = {"status": "healthy", "message": "Configuration valid"}
    else:
        checks["configuration"] = {
            "status": "unhealthy", 
            "message": f"{validation_summary['total_errors']} configuration errors"
        }
    
    # Overall status
    unhealthy_checks = [name for name, check in checks.items() if check["status"] != "healthy"]
    overall_status = "unhealthy" if unhealthy_checks else "healthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        environment=settings.system.environment,
        checks=checks,
        uptime_seconds=time.time() - start_time
    )


@app.get("/system/status")
async def system_status(
    request_id: str = Depends(get_request_id),
    db: ProductionDatabaseService = Depends(get_db)
):
    """Get detailed system status and metrics."""
    
    try:
        # Get lead statistics
        lead_counts = {}
        for state in LeadState:
            leads = await lead_state_machine.get_leads_by_state(state)
            lead_counts[state] = len(leads)
        
        # Get email statistics
        email_stats = await email_service.get_campaign_statistics()
        
        # Get configuration summary
        config_summary = settings.get_validation_summary()
        
        return SuccessResponse(
            data={
                "lead_counts": lead_counts,
                "email_statistics": email_stats,
                "configuration": config_summary,
                "environment": settings.system.environment,
                "debug_mode": settings.system.debug
            },
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        if logging_service:
            logging_service.log_error(e, component="api", operation="system_status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system status"
        )


# Discovery endpoints
@app.post("/api/discovery/start")
async def start_discovery(
    request: DiscoveryRequest,
    request_id: str = Depends(get_request_id),
    db: ProductionDatabaseService = Depends(get_db),
    logger: ProductionLoggingService = Depends(get_logging)
):
    """Start business discovery process."""
    
    try:
        logger.log_application_event(
            f"Discovery started: {request.query} in {request.location}",
            component="api",
            operation="start_discovery",
            query=request.query,
            location=request.location,
            max_results=request.max_results
        )
        
        # Start discovery
        discovery_result = await scraping_service.discover_businesses(
            query=request.query,
            location=request.location,
            max_results=request.max_results
        )
        
        if not discovery_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=discovery_result.error
            )
        
        # Save discovered leads
        saved_leads = []
        for lead_data in discovery_result.data.discovered_leads:
            try:
                lead = await db.create_lead(lead_data)
                saved_leads.append(lead)
                
                # Log audit event
                await logger.log_audit_event(
                    entity_type=EntityType.LEAD,
                    entity_id=lead.id,
                    action="discovered",
                    actor="system",
                    new_values=lead.dict(),
                    request_id=request_id
                )
            
            except Exception as e:
                logger.log_error(e, component="api", operation="save_discovered_lead")
                continue
        
        return SuccessResponse(
            data={
                "discovered_count": len(saved_leads),
                "skipped_count": discovery_result.data.skipped_count,
                "error_count": discovery_result.data.error_count,
                "leads": [lead.dict() for lead in saved_leads[:10]]  # Return first 10 for preview
            },
            metadata={
                "total_discovered": len(discovery_result.data.discovered_leads),
                "total_saved": len(saved_leads),
                "strategy_used": discovery_result.metadata.get("strategy_used")
            },
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error(e, component="api", operation="start_discovery")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Discovery failed"
        )


# Lead management endpoints
@app.get("/api/leads")
async def get_leads(
    lifecycle_state: Optional[LeadState] = None,
    review_status: Optional[ReviewStatus] = None,
    page: int = 1,
    page_size: int = 50,
    request_id: str = Depends(get_request_id),
    db: ProductionDatabaseService = Depends(get_db)
):
    """Get leads with filtering and pagination."""
    
    try:
        filters = LeadFilter(
            lifecycle_state=lifecycle_state,
            review_status=review_status
        )
        
        pagination = PaginationParams(page=page, page_size=page_size)
        result = await db.get_leads(filters, pagination)
        
        return SuccessResponse(
            data={
                "leads": [lead.dict() for lead in result.items],
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                    "has_next": result.has_next,
                    "has_previous": result.has_previous
                }
            },
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        if logging_service:
            logging_service.log_error(e, component="api", operation="get_leads")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get leads"
        )


@app.post("/api/leads/{lead_id}/approve")
async def approve_lead(
    lead_id: str,
    request_id: str = Depends(get_request_id),
    logger: ProductionLoggingService = Depends(get_logging)
):
    """Approve a lead for outreach."""
    
    try:
        from uuid import UUID
        lead_uuid = UUID(lead_id)
        
        result = await lead_state_machine.approve_lead(
            lead_id=lead_uuid,
            actor="user",
            reason="Lead approved via API"
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )
        
        return SuccessResponse(
            data=result.data.dict(),
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid lead ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error(e, component="api", operation="approve_lead")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve lead"
        )


@app.post("/api/leads/bulk-approve")
async def bulk_approve_leads(
    request: BulkActionRequest,
    request_id: str = Depends(get_request_id),
    logger: ProductionLoggingService = Depends(get_logging)
):
    """Approve multiple leads at once."""
    
    try:
        from uuid import UUID
        
        approved_count = 0
        failed_count = 0
        
        for lead_id_str in request.lead_ids:
            try:
                lead_uuid = UUID(lead_id_str)
                result = await lead_state_machine.approve_lead(
                    lead_id=lead_uuid,
                    actor="user",
                    reason=request.reason or "Bulk approval via API"
                )
                
                if result.success:
                    approved_count += 1
                else:
                    failed_count += 1
            
            except Exception as e:
                logger.log_error(e, component="api", operation="bulk_approve_lead")
                failed_count += 1
        
        return SuccessResponse(
            data={
                "approved_count": approved_count,
                "failed_count": failed_count,
                "total_requested": len(request.lead_ids)
            },
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.log_error(e, component="api", operation="bulk_approve_leads")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk approval failed"
        )


# Email campaign endpoints
@app.post("/api/campaigns/create")
async def create_email_campaign(
    request: EmailCampaignRequest,
    request_id: str = Depends(get_request_id),
    db: ProductionDatabaseService = Depends(get_db),
    logger: ProductionLoggingService = Depends(get_logging)
):
    """Create and optionally send an email campaign."""
    
    try:
        from uuid import UUID
        lead_uuid = UUID(request.lead_id)
        
        # Get lead
        lead = await db.get_lead_by_id(lead_uuid)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found"
            )
        
        # Create and send campaign
        result = await email_service.create_and_send_campaign(
            lead=lead,
            campaign_type=request.campaign_type,
            template_id=request.template_id,
            custom_subject=request.custom_subject,
            custom_body=request.custom_body
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )
        
        return SuccessResponse(
            data=result.data.dict(),
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid lead ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error(e, component="api", operation="create_email_campaign")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create email campaign"
        )


@app.post("/api/campaigns/process-queue")
async def process_email_queue(
    request_id: str = Depends(get_request_id),
    logger: ProductionLoggingService = Depends(get_logging)
):
    """Process queued email campaigns."""
    
    try:
        result = await email_service.process_queued_campaigns()
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error
            )
        
        return SuccessResponse(
            data=result.data,
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error(e, component="api", operation="process_email_queue")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process email queue"
        )


if __name__ == "__main__":
    uvicorn.run(
        "cold_outreach_agent.api.production_server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.system.debug,
        log_level=settings.logging.level.lower()
    )
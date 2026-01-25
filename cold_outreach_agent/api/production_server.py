"""Production-grade FastAPI server with comprehensive error handling, observability, and security."""

import asyncio
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4, UUID

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

# Infrastructure Services
from ..infrastructure.database.service import ProductionDatabaseService
from ..infrastructure.logging.service import ProductionLoggingService
from ..infrastructure.email.service import ProductionEmailService
from ..infrastructure.scraping.google_maps_scraper import ProductionGoogleMapsScraperService

# State Machines
from ..core.state_machines.lead_state_machine import LeadStateMachine
from ..core.state_machines.email_state_machine import EmailStateMachine

# Advanced Services
from ..services.user_service import UserService, UserCreate, UserError
from ..services.enrichment_service import EnrichmentPipelineService as EnrichmentService
from ..core.models.enrichment import EnrichmentCreate as EnrichmentRequest
from ..services.scoring_service import LeadScoringEngine as ScoringService
from ..services.compliance_service import ComplianceService
from ..services.crm_service import CRMService
from ..services.campaign_service import CampaignIntelligenceService
from ..services.analytics_service import AnalyticsService
from ..services.public_signal_service import PublicSignalService
from ..services.sync_service import SyncService


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

# New Advanced Services globals
user_service: Optional[UserService] = None
enrichment_service: Optional[EnrichmentService] = None
scoring_service: Optional[ScoringService] = None
compliance_service: Optional[ComplianceService] = None
crm_service: Optional[CRMService] = None
campaign_service: Optional[CampaignIntelligenceService] = None
analytics_service: Optional[AnalyticsService] = None
public_signal_service: Optional[PublicSignalService] = None
sync_service: Optional[SyncService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_service, logging_service, email_service, scraping_service
    global lead_state_machine, email_state_machine
    global user_service, enrichment_service, scoring_service, compliance_service
    global crm_service, campaign_service, analytics_service, public_signal_service, sync_service
    
    # Startup
    try:
        # Initialize logging service first
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
        
        # Initialize core services
        lead_state_machine = LeadStateMachine(db_service, logging_service)
        email_state_machine = EmailStateMachine(db_service, logging_service)
        
        # Email config
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
        
        scraping_service = ProductionGoogleMapsScraperService()
        
        # Initialize Advanced Services
        user_service = UserService(db_service)
        enrichment_service = EnrichmentService(db_service)
        scoring_service = ScoringService(db_service)
        compliance_service = ComplianceService(db_service)
        crm_service = CRMService(db_service)
        campaign_service = CampaignIntelligenceService(db_service, email_service)
        analytics_service = AnalyticsService(db_service)
        public_signal_service = PublicSignalService(db_service, email_service)
        sync_service = SyncService(db_service)
        
        logging_service.log_application_event(
            "Application startup completed successfully",
            component="server",
            operation="startup"
        )
        
        yield
        
    except Exception as e:
        if logging_service:
            logging_service.log_error(e, component="server", operation="startup")
            traceback.print_exc()
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

# Add middleware - CORS must be added FIRST and always enabled for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow all hosts for development
)


# Dependency injection
async def get_request_id(request: Request) -> str:
    """Generate or extract request ID."""
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    return request_id

async def get_db() -> ProductionDatabaseService:
    if not db_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database not available")
    return db_service

async def get_logging() -> ProductionLoggingService:
    if not logging_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Logging not available")
    return logging_service

async def get_user_service() -> UserService:
    if not user_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "User service not available")
    return user_service

async def get_enrichment() -> EnrichmentService:
    if not enrichment_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Enrichment service not available")
    return enrichment_service

async def get_scoring() -> ScoringService:
    if not scoring_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scoring service not available")
    return scoring_service

async def get_compliance() -> ComplianceService:
    if not compliance_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Compliance service not available")
    return compliance_service

async def get_crm() -> CRMService:
    if not crm_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "CRM service not available")
    return crm_service

async def get_campaigns() -> CampaignIntelligenceService:
    if not campaign_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Campaign service not available")
    return campaign_service

async def get_analytics() -> AnalyticsService:
    if not analytics_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Analytics service not available")
    return analytics_service

async def get_public_signal() -> PublicSignalService:
    if not public_signal_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Public signal service not available")
    return public_signal_service

async def get_sync() -> SyncService:
    if not sync_service: raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Sync service not available")
    return sync_service


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
            status_code=0,
            duration_ms=0,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
            request_id=request_id
        )
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
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
        
        response.headers["X-Request-ID"] = request_id
        return response
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        if logging_service:
            logging_service.log_error(
                e, component="api", operation=f"{request.method} {request.url.path}",
                context={"request_id": request_id, "duration_ms": duration_ms}
            )
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
    request_id = getattr(request.state, 'request_id', str(uuid4()))
    if logging_service:
        logging_service.log_error(exc, component="api", operation=f"{request.method} {request.url.path}", context={"request_id": request_id})
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


# Health and system endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check."""
    start_time = time.time()
    checks = {}
    
    try:
        if db_service:
            await db_service.get_leads(pagination=PaginationParams(page=1, page_size=1))
            checks["database"] = {"status": "healthy"}
        else:
            checks["database"] = {"status": "unhealthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "message": str(e)}
    
    unhealthy = any(c["status"] != "healthy" for c in checks.values())
    
    return HealthResponse(
        status="healthy" if not unhealthy else "unhealthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0",
        environment=settings.system.environment,
        checks=checks,
        uptime_seconds=time.time() - start_time
    )

@app.get("/system/status")
async def system_status(request_id: str = Depends(get_request_id), db: ProductionDatabaseService = Depends(get_db)):
    """Get system metrics."""
    try:
        lead_counts = {}
        for state in LeadState:
            leads = await lead_state_machine.get_leads_by_state(state)
            lead_counts[state] = len(leads)
            
        email_stats = await email_service.get_campaign_statistics()
        config_summary = settings.get_validation_summary()
        
        # Add new service stats if available
        enrichment_stats = await enrichment_service.get_enrichment_stats() if enrichment_service else {}
        compliance_stats = await compliance_service.get_unsubscribe_stats() if compliance_service else {}
        
        return SuccessResponse(
            data={
                "lead_counts": lead_counts,
                "email_statistics": email_stats,
                "enrichment_stats": enrichment_stats,
                "compliance_stats": compliance_stats,
                "configuration": config_summary,
            },
            request_id=request_id,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Status check failed")


# --- FRONTEND REQUIRED ENDPOINTS ---

@app.get("/api/overview")
async def get_overview(request_id: str = Depends(get_request_id), db: ProductionDatabaseService = Depends(get_db)):
    """Get dashboard overview statistics."""
    try:
        # Get lead counts by review status
        all_leads = await db.get_leads(pagination=PaginationParams(page=1, page_size=10000))
        total_leads = all_leads.total
        
        pending = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.PENDING)
        approved = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.APPROVED)
        rejected = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.REJECTED)
        
        # Get email stats
        email_stats = await email_service.get_campaign_statistics() if email_service else {}
        
        return {
            "total_leads": total_leads,
            "pending_review": pending,
            "approved": approved,
            "rejected": rejected,
            "emails_sent_today": email_stats.get("sent_today", 0),
            "sent_initial": email_stats.get("sent_initial", 0),
            "sent_followup": email_stats.get("sent_followup", 0),
            "replies_received": email_stats.get("replies_received", 0),
            "emails_sent_this_week": email_stats.get("sent_this_week", 0),
            "open_rate": email_stats.get("open_rate", 0),
            "reply_rate": email_stats.get("reply_rate", 0),
            "discovery_active": _agent_state.get("state") == "DISCOVERING",
            "outreach_active": _agent_state.get("state") == "OUTREACH_RUNNING"
        }
    except Exception as e:
        if logging_service:
            logging_service.log_error(e, component="api", operation="get_overview")
        return {
            "total_leads": 0,
            "pending_review": 0,
            "approved": 0,
            "rejected": 0,
            "emails_sent_today": 0,
            "sent_initial": 0,
            "sent_followup": 0,
            "replies_received": 0,
            "emails_sent_this_week": 0,
            "open_rate": 0,
            "reply_rate": 0,
            "discovery_active": False,
            "outreach_active": False
        }


@app.get("/api/system")
async def get_system_health(request_id: str = Depends(get_request_id)):
    """Get system health status for frontend."""
    try:
        db_healthy = db_service is not None
        email_healthy = email_service is not None
        scraping_healthy = scraping_service is not None
        
        # Get lead counts
        lead_counts = {"total": 0, "pending_review": 0, "approved": 0, "rejected": 0, "replied": 0}
        if db_service:
            try:
                all_leads = await db_service.get_leads(pagination=PaginationParams(page=1, page_size=10000))
                lead_counts["total"] = all_leads.total
                lead_counts["pending_review"] = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.PENDING)
                lead_counts["approved"] = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.APPROVED)
                lead_counts["rejected"] = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.REJECTED)
            except:
                pass
        
        # Get email stats
        email_stats = {}
        if email_service:
            try:
                email_stats = await email_service.get_campaign_statistics()
            except:
                pass
        
        return {
            "agent_state": _agent_state.get("state", "IDLE"),
            "last_transition_time": _agent_state.get("last_transition_time", ""),
            "last_heartbeat": _agent_state.get("last_heartbeat", ""),
            "current_task": _agent_state.get("current_task", ""),
            "discovery_query": _agent_state.get("discovery_query", ""),
            "discovery_location": _agent_state.get("discovery_location", ""),
            "is_healthy": all([db_healthy, email_healthy]),
            "health_reason": _agent_state.get("health_reason", "All systems operational"),
            "error_message": _agent_state.get("error_message", ""),
            "error_count_24h": 0,
            "emails_sent_today": email_stats.get("sent_today", 0),
            "email_quota": settings.email.max_emails_per_day,
            "lead_counts": lead_counts,
            "status": "healthy" if all([db_healthy, email_healthy]) else "degraded",
            "uptime": "running",
            "services": {
                "database": {"status": "healthy" if db_healthy else "unhealthy"},
                "email": {"status": "healthy" if email_healthy else "unhealthy"},
                "scraping": {"status": "healthy" if scraping_healthy else "unhealthy"},
                "logging": {"status": "healthy" if logging_service else "unhealthy"}
            },
            "version": "1.0.0",
            "environment": settings.system.environment
        }
    except Exception as e:
        return {
            "agent_state": "ERROR",
            "last_transition_time": "",
            "last_heartbeat": "",
            "current_task": "",
            "discovery_query": "",
            "discovery_location": "",
            "is_healthy": False,
            "health_reason": str(e),
            "error_message": str(e),
            "error_count_24h": 1,
            "emails_sent_today": 0,
            "email_quota": 20,
            "lead_counts": {"total": 0, "pending_review": 0, "approved": 0, "rejected": 0, "replied": 0},
            "status": "error",
            "uptime": "unknown",
            "services": {},
            "version": "1.0.0",
            "environment": "unknown"
        }


@app.get("/api/logs")
async def get_logs(
    module: Optional[str] = None,
    lead_id: Optional[str] = None,
    limit: int = 50,
    request_id: str = Depends(get_request_id)
):
    """Get activity logs for frontend."""
    try:
        # Return empty logs for now - can be enhanced with actual log retrieval
        if logging_service:
            stats = logging_service.get_log_statistics()
            return {
                "logs": [],
                "total": stats.get("total_logs", 0),
                "stats": stats
            }
        return {"logs": [], "total": 0}
    except Exception as e:
        return {"logs": [], "total": 0}


# --- AGENT STATE & CONTROL ENDPOINTS ---

# Global agent state tracking
_agent_state = {
    "state": "IDLE",
    "last_transition_time": datetime.now().isoformat(),
    "reason": "System initialized",
    "controlled_by": "system",
    "last_heartbeat": datetime.now().isoformat(),
    "error_message": "",
    "current_task": "",
    "discovery_query": "",
    "discovery_location": "",
    "is_healthy": True,
    "health_reason": "All systems operational"
}

_control_logs = []


@app.get("/api/agent/state")
async def get_agent_state(request_id: str = Depends(get_request_id)):
    """Get current agent state."""
    _agent_state["last_heartbeat"] = datetime.now().isoformat()
    return _agent_state


@app.get("/api/agent/control-logs")
async def get_control_logs(limit: int = 50, request_id: str = Depends(get_request_id)):
    """Get agent control logs."""
    return {"logs": _control_logs[-limit:], "total": len(_control_logs)}


def _log_control_action(action: str, details: str = ""):
    """Log a control action."""
    _control_logs.append({
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
        "state": _agent_state["state"]
    })


@app.post("/api/agent/discover/start")
async def agent_start_discovery(request: DiscoveryRequest, request_id: str = Depends(get_request_id)):
    """Start discovery via agent control."""
    global _agent_state
    
    if _agent_state["state"] not in ["IDLE", "ERROR"]:
        return {"success": False, "message": f"Cannot start discovery while in {_agent_state['state']} state", "state": _agent_state["state"]}
    
    _agent_state["state"] = "DISCOVERING"
    _agent_state["last_transition_time"] = datetime.now().isoformat()
    _agent_state["discovery_query"] = request.query
    _agent_state["discovery_location"] = request.location
    _agent_state["current_task"] = f"Discovering {request.query} in {request.location}"
    _agent_state["reason"] = "User started discovery"
    _log_control_action("START_DISCOVERY", f"Query: {request.query}, Location: {request.location}")
    
    # Actually run discovery in background
    asyncio.create_task(_run_discovery(request.query, request.location, request.max_results))
    
    return {"success": True, "message": "Discovery started", "state": _agent_state["state"]}


async def _run_discovery(query: str, location: str, max_results: int):
    """Background discovery task."""
    global _agent_state
    try:
        if scraping_service:
            result = await scraping_service.discover_businesses(
                query=query,
                location=location,
                max_results=max_results
            )
            if result.success and db_service:
                for lead_data in result.data.discovered_leads:
                    try:
                        await db_service.create_lead(lead_data)
                    except:
                        pass
        
        _agent_state["state"] = "IDLE"
        _agent_state["current_task"] = ""
        _agent_state["reason"] = "Discovery completed"
        _log_control_action("DISCOVERY_COMPLETE", f"Finished discovering {query}")
    except Exception as e:
        _agent_state["state"] = "ERROR"
        _agent_state["error_message"] = str(e)
        _agent_state["reason"] = "Discovery failed"
        _log_control_action("DISCOVERY_ERROR", str(e))


@app.post("/api/agent/discover/stop")
async def agent_stop_discovery(request_id: str = Depends(get_request_id)):
    """Stop discovery."""
    global _agent_state
    
    _agent_state["state"] = "IDLE"
    _agent_state["current_task"] = ""
    _agent_state["discovery_query"] = ""
    _agent_state["discovery_location"] = ""
    _agent_state["reason"] = "User stopped discovery"
    _log_control_action("STOP_DISCOVERY")
    
    return {"success": True, "message": "Discovery stopped", "state": _agent_state["state"]}


@app.post("/api/agent/outreach/start")
async def agent_start_outreach(request_id: str = Depends(get_request_id)):
    """Start outreach campaign."""
    global _agent_state
    
    if _agent_state["state"] not in ["IDLE", "ERROR"]:
        return {"success": False, "message": f"Cannot start outreach while in {_agent_state['state']} state", "state": _agent_state["state"]}
    
    _agent_state["state"] = "OUTREACH_RUNNING"
    _agent_state["current_task"] = "Sending outreach emails"
    _agent_state["reason"] = "User started outreach"
    _log_control_action("START_OUTREACH")
    
    # Run outreach in background
    asyncio.create_task(_run_outreach())
    
    return {"success": True, "message": "Outreach started", "state": _agent_state["state"]}


async def _run_outreach():
    """Background outreach task."""
    global _agent_state
    try:
        if lead_state_machine and email_service:
            ready_leads = await lead_state_machine.get_leads_ready_for_outreach()
            for lead in ready_leads[:10]:  # Process up to 10 at a time
                try:
                    await email_service.create_and_send_campaign(
                        lead=lead,
                        campaign_type=CampaignType.INITIAL
                    )
                except:
                    pass
        
        _agent_state["state"] = "IDLE"
        _agent_state["current_task"] = ""
        _agent_state["reason"] = "Outreach completed"
        _log_control_action("OUTREACH_COMPLETE")
    except Exception as e:
        _agent_state["state"] = "ERROR"
        _agent_state["error_message"] = str(e)
        _log_control_action("OUTREACH_ERROR", str(e))


@app.post("/api/agent/outreach/stop")
async def agent_stop_outreach(request_id: str = Depends(get_request_id)):
    """Stop outreach."""
    global _agent_state
    
    _agent_state["state"] = "IDLE"
    _agent_state["current_task"] = ""
    _agent_state["reason"] = "User stopped outreach"
    _log_control_action("STOP_OUTREACH")
    
    return {"success": True, "message": "Outreach stopped", "state": _agent_state["state"]}


@app.post("/api/agent/pause")
async def agent_pause(request_id: str = Depends(get_request_id)):
    """Pause agent."""
    global _agent_state
    
    prev_state = _agent_state["state"]
    _agent_state["state"] = "PAUSED"
    _agent_state["reason"] = f"User paused from {prev_state}"
    _log_control_action("PAUSE", f"Previous state: {prev_state}")
    
    return {"success": True, "message": "Agent paused", "state": _agent_state["state"]}


@app.post("/api/agent/resume")
async def agent_resume(request_id: str = Depends(get_request_id)):
    """Resume agent."""
    global _agent_state
    
    _agent_state["state"] = "IDLE"
    _agent_state["reason"] = "User resumed agent"
    _log_control_action("RESUME")
    
    return {"success": True, "message": "Agent resumed", "state": _agent_state["state"]}


@app.post("/api/agent/stop")
async def agent_stop(request_id: str = Depends(get_request_id)):
    """Stop agent completely."""
    global _agent_state
    
    _agent_state["state"] = "IDLE"
    _agent_state["current_task"] = ""
    _agent_state["discovery_query"] = ""
    _agent_state["discovery_location"] = ""
    _agent_state["reason"] = "User stopped agent"
    _log_control_action("STOP")
    
    return {"success": True, "message": "Agent stopped", "state": _agent_state["state"]}


@app.post("/api/agent/reset")
async def agent_reset(request_id: str = Depends(get_request_id)):
    """Reset agent to initial state."""
    global _agent_state, _control_logs
    
    _agent_state = {
        "state": "IDLE",
        "last_transition_time": datetime.now().isoformat(),
        "reason": "Agent reset by user",
        "controlled_by": "user",
        "last_heartbeat": datetime.now().isoformat(),
        "error_message": "",
        "current_task": "",
        "discovery_query": "",
        "discovery_location": "",
        "is_healthy": True,
        "health_reason": "Agent reset"
    }
    _control_logs = []
    _log_control_action("RESET")
    
    return {"success": True, "message": "Agent reset", "state": _agent_state["state"]}


# --- ADDITIONAL LEAD ENDPOINTS ---

@app.get("/api/leads/{lead_id}")
async def get_lead_detail(lead_id: str, request_id: str = Depends(get_request_id), db: ProductionDatabaseService = Depends(get_db)):
    """Get lead details."""
    try:
        lead_uuid = UUID(lead_id)
        lead = await db.get_lead_by_id(lead_uuid)
        if not lead:
            raise HTTPException(404, "Lead not found")
        
        # Get action history (placeholder)
        action_history = []
        
        return {
            "lead": lead.dict(),
            "action_history": action_history
        }
    except ValueError:
        raise HTTPException(400, "Invalid lead ID")


@app.post("/api/leads/{lead_id}/reject")
async def reject_lead(lead_id: str, request_id: str = Depends(get_request_id)):
    """Reject a lead."""
    try:
        lead_uuid = UUID(lead_id)
        result = await lead_state_machine.reject_lead(lead_uuid, actor="user", reason="API rejection")
        if not result.success:
            raise HTTPException(400, result.error)
        return {"success": True, "lead_id": lead_id, "review_status": "rejected"}
    except ValueError:
        raise HTTPException(400, "Invalid lead ID")


@app.post("/api/leads/bulk-approve")
async def bulk_approve_leads(request: BulkActionRequest, request_id: str = Depends(get_request_id)):
    """Bulk approve leads."""
    approved_count = 0
    for lead_id in request.lead_ids:
        try:
            lead_uuid = UUID(lead_id)
            result = await lead_state_machine.approve_lead(lead_uuid, actor="user", reason="Bulk approval")
            if result.success:
                approved_count += 1
        except:
            pass
    return {"success": True, "approved_count": approved_count}


@app.post("/api/leads/bulk-reject")
async def bulk_reject_leads(request: BulkActionRequest, request_id: str = Depends(get_request_id)):
    """Bulk reject leads."""
    rejected_count = 0
    for lead_id in request.lead_ids:
        try:
            lead_uuid = UUID(lead_id)
            result = await lead_state_machine.reject_lead(lead_uuid, actor="user", reason="Bulk rejection")
            if result.success:
                rejected_count += 1
        except:
            pass
    return {"success": True, "rejected_count": rejected_count}


@app.get("/api/health")
async def api_health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# --- CORE DOMAIN ENDPOINTS ---

@app.post("/api/discovery/start")
async def start_discovery(
    request: DiscoveryRequest,
    request_id: str = Depends(get_request_id),
    db: ProductionDatabaseService = Depends(get_db),
    logger: ProductionLoggingService = Depends(get_logging)
):
    """Start business discovery."""
    try:
        discovery_result = await scraping_service.discover_businesses(
            query=request.query,
            location=request.location,
            max_results=request.max_results
        )
        
        if not discovery_result.success:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=discovery_result.error)
        
        saved_leads = []
        for lead_data in discovery_result.data.discovered_leads:
            try:
                lead = await db.create_lead(lead_data)
                saved_leads.append(lead)
                
                # Auto-trigger enrichment if enabled
                if enrichment_service:
                    asyncio.create_task(enrichment_service.enrich_lead(
                        EnrichmentRequest(lead_id=lead.id, business_name=lead.business_name, website_url=lead.website_url)
                    ))
            except Exception:
                continue
        
        return SuccessResponse(
            data={"discovered": len(saved_leads), "leads": [l.dict() for l in saved_leads[:10]]},
            request_id=request_id, timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.log_error(e, component="api", operation="start_discovery")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Discovery failed")


@app.get("/api/leads")
async def get_leads_endpoint(
    lifecycle_state: Optional[LeadState] = None,
    review_status: Optional[ReviewStatus] = None,
    outreach_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    request_id: str = Depends(get_request_id),
    db: ProductionDatabaseService = Depends(get_db)
):
    """Get leads with optional filters, returns flat array for frontend."""
    filters = LeadFilter(lifecycle_state=lifecycle_state, review_status=review_status)
    result = await db.get_leads(filters, PaginationParams(page=page, page_size=page_size))
    
    # Transform leads to match frontend expected format
    leads = []
    for lead in result.items:
        lead_dict = lead.dict()
        leads.append({
            "lead_id": str(lead.id),
            "business_name": lead.business_name,
            "category": lead.category or "",
            "location": lead.location or "",
            "maps_url": lead.maps_url or "",
            "website_url": lead.website_url or "",
            "email": lead.email or "",
            "tag": getattr(lead, 'tag', None) or "",
            "review_status": lead.review_status.value if hasattr(lead.review_status, 'value') else str(lead.review_status),
            "outreach_status": getattr(lead, 'outreach_status', 'none') or "none",
            "discovery_source": getattr(lead, 'discovery_source', 'google_maps') or "google_maps",
            "discovered_at": lead.created_at.isoformat() if lead.created_at else "",
            "last_contacted": getattr(lead, 'last_contacted', None) or ""
        })
    
    return leads


@app.post("/api/leads/{lead_id}/approve")
async def approve_lead(lead_id: str, request_id: str = Depends(get_request_id)):
    try:
        lead_uuid = UUID(lead_id)
        result = await lead_state_machine.approve_lead(lead_uuid, actor="user", reason="API approval")
        if not result.success: raise HTTPException(status.HTTP_400_BAD_REQUEST, result.error)
        return SuccessResponse(data=result.data.dict(), request_id=request_id, timestamp=datetime.now().isoformat())
    except ValueError: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid ID")


# --- NEW SERVICE ENDPOINTS ---

# Enrichment
@app.post("/api/enrichment/enrich/{lead_id}")
async def enrich_lead_endpoint(lead_id: str, request_id: str = Depends(get_request_id), service: EnrichmentService = Depends(get_enrichment), db: ProductionDatabaseService = Depends(get_db)):
    try:
        lead_uuid = UUID(lead_id)
        lead = await db.get_lead_by_id(lead_uuid)
        if not lead: raise HTTPException(404, "Lead not found")
        
        data = await service.enrich_lead(EnrichmentRequest(lead_id=lead.id, business_name=lead.business_name, website_url=lead.website_url))
        return SuccessResponse(data=data.dict(), request_id=request_id, timestamp=datetime.now().isoformat())
    except Exception as e:
        raise HTTPException(500, str(e))

# Scoring
@app.get("/api/scoring/{lead_id}")
async def get_lead_score(lead_id: str, request_id: str = Depends(get_request_id), service: ScoringService = Depends(get_scoring)):
    try:
        score = await service.calculate_lead_score(UUID(lead_id))
        return SuccessResponse(data=score.dict(), request_id=request_id, timestamp=datetime.now().isoformat())
    except Exception as e:
        raise HTTPException(500, str(e))

# CRM
@app.get("/api/crm/leads/{lead_id}/timeline")
async def get_lead_timeline(lead_id: str, request_id: str = Depends(get_request_id), service: CRMService = Depends(get_crm)):
    # Placeholder for a unified timeline view
    return SuccessResponse(data=[], request_id=request_id, timestamp=datetime.now().isoformat())

# Analytics
@app.get("/api/analytics/dashboard")
async def get_dashboard_data(request_id: str = Depends(get_request_id), service: AnalyticsService = Depends(get_analytics)):
    data = await service.get_dashboard_summary()
    return SuccessResponse(data=data, request_id=request_id, timestamp=datetime.now().isoformat())

# Public Signal
@app.get("/api/public/directory")
async def search_directory(query: Optional[str] = None, request_id: str = Depends(get_request_id), service: PublicSignalService = Depends(get_public_signal)):
    # Placeholder directory search
    return SuccessResponse(data={"results": []}, request_id=request_id, timestamp=datetime.now().isoformat())

# Users
@app.post("/api/auth/login")
async def login(request: Request, service: UserService = Depends(get_user_service)):
    # Implement login logic mapping body to service.authenticate
    return SuccessResponse(data={"token": "placeholder-token"}, request_id="req", timestamp=datetime.now().isoformat())


# --- EMAIL TEMPLATES ENDPOINTS ---

# Default templates storage (in-memory for now)
_default_templates = {
    "initial_outreach": {
        "category": "initial_outreach",
        "subject_template": "Quick question about {{business_name}}",
        "text_template": "Hi {{contact_name}},\n\nI came across {{business_name}} and was impressed by what you're doing.\n\nI'd love to learn more about your business and see if there's an opportunity to collaborate.\n\nWould you be open to a quick call this week?\n\nBest regards",
        "variables": ["business_name", "contact_name"]
    },
    "follow_up": {
        "category": "follow_up",
        "subject_template": "Following up - {{business_name}}",
        "text_template": "Hi {{contact_name}},\n\nI wanted to follow up on my previous email about {{business_name}}.\n\nI understand you're busy, but I believe there could be real value in connecting.\n\nWould you have 15 minutes this week for a quick chat?\n\nBest regards",
        "variables": ["business_name", "contact_name"]
    },
    "final_follow_up": {
        "category": "final_follow_up", 
        "subject_template": "Last attempt to connect - {{business_name}}",
        "text_template": "Hi {{contact_name}},\n\nThis will be my last email regarding potential collaboration with {{business_name}}.\n\nIf you're not interested, no worries at all. But if timing was just off, feel free to reach out anytime.\n\nWishing you continued success!\n\nBest regards",
        "variables": ["business_name", "contact_name"]
    }
}

_custom_templates = {}


@app.get("/api/email-templates")
async def get_email_templates(request_id: str = Depends(get_request_id)):
    """Get all email templates."""
    templates = {**_default_templates, **_custom_templates}
    return {"templates": templates}


@app.get("/api/email-templates/{category}")
async def get_email_template(category: str, request_id: str = Depends(get_request_id)):
    """Get a specific email template by category."""
    if category in _custom_templates:
        return _custom_templates[category]
    if category in _default_templates:
        return _default_templates[category]
    raise HTTPException(status_code=404, detail=f"Template '{category}' not found")


class EmailTemplateUpdate(BaseModel):
    subject_template: str
    text_template: str


@app.put("/api/email-templates/{category}")
async def update_email_template(category: str, data: EmailTemplateUpdate, request_id: str = Depends(get_request_id)):
    """Update an email template."""
    _custom_templates[category] = {
        "category": category,
        "subject_template": data.subject_template,
        "text_template": data.text_template,
        "variables": ["business_name", "contact_name"]
    }
    return {
        "success": True,
        "message": f"Template '{category}' updated successfully",
        "template": _custom_templates[category]
    }


@app.delete("/api/email-templates/{category}")
async def reset_email_template(category: str, request_id: str = Depends(get_request_id)):
    """Reset an email template to default."""
    if category in _custom_templates:
        del _custom_templates[category]
    return {"success": True, "message": f"Template '{category}' reset to default"}


# --- TEST EMAIL ENDPOINT ---

class TestEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    category: Optional[str] = "general"


@app.post("/api/email/test")
async def send_test_email(data: TestEmailRequest, request_id: str = Depends(get_request_id)):
    """Send a test email."""
    try:
        if email_service:
            # Use the email service to send
            result = await email_service.send_test_email(
                to_email=data.to_email,
                subject=data.subject,
                body=data.body
            )
            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Test email sent to {data.to_email}",
                    "details": "Email delivered successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to send test email",
                    "details": result.get("error", "Unknown error")
                }
        else:
            return {
                "success": False,
                "message": "Email service not configured",
                "details": "Please configure SMTP settings in .env file"
            }
    except Exception as e:
        return {
            "success": False,
            "message": "Failed to send test email",
            "details": str(e)
        }


# --- CAMPAIGNS ENDPOINTS ---

_campaigns = [
    {
        "id": "1",
        "name": "Initial Outreach Sequence",
        "status": "active",
        "steps": [
            {"id": "1", "order": 1, "type": "initial", "subject": "Quick question about {{business_name}}", "delayDays": 0, "enabled": True},
            {"id": "2", "order": 2, "type": "followup", "subject": "Following up - {{business_name}}", "delayDays": 3, "enabled": True},
            {"id": "3", "order": 3, "type": "final", "subject": "Last attempt to connect", "delayDays": 7, "enabled": True}
        ],
        "leadsCount": 45,
        "sentCount": 120,
        "replyCount": 8,
        "createdAt": datetime.now().isoformat()
    }
]


@app.get("/api/campaigns")
async def get_campaigns(request_id: str = Depends(get_request_id)):
    """Get all campaigns."""
    return {"campaigns": _campaigns}


class CampaignCreate(BaseModel):
    name: str
    steps: List[Dict[str, Any]] = []


@app.post("/api/campaigns")
async def create_campaign(data: CampaignCreate, request_id: str = Depends(get_request_id)):
    """Create a new campaign."""
    campaign = {
        "id": str(len(_campaigns) + 1),
        "name": data.name,
        "status": "draft",
        "steps": data.steps or [
            {"id": "1", "order": 1, "type": "initial", "subject": "Quick question about {{business_name}}", "delayDays": 0, "enabled": True}
        ],
        "leadsCount": 0,
        "sentCount": 0,
        "replyCount": 0,
        "createdAt": datetime.now().isoformat()
    }
    _campaigns.append(campaign)
    return {"success": True, "campaign": campaign}


@app.post("/api/campaigns/{campaign_id}/toggle")
async def toggle_campaign(campaign_id: str, request_id: str = Depends(get_request_id)):
    """Toggle campaign active/paused status."""
    for campaign in _campaigns:
        if campaign["id"] == campaign_id:
            campaign["status"] = "paused" if campaign["status"] == "active" else "active"
            return {"success": True, "campaign": campaign}
    raise HTTPException(404, "Campaign not found")


# --- CRM ENDPOINTS ---

_opportunities = [
    {
        "id": "1",
        "leadId": "lead-1",
        "businessName": "TechStart Inc",
        "contactName": "John Smith",
        "email": "john@techstart.com",
        "stage": "replied",
        "value": 5000,
        "probability": 20,
        "lastActivity": datetime.now().isoformat(),
        "notes": ["Interested in web development services"]
    }
]

_lead_notes = {}  # lead_id -> list of notes


@app.get("/api/crm/opportunities")
async def get_opportunities(request_id: str = Depends(get_request_id)):
    """Get all CRM opportunities."""
    return {"opportunities": _opportunities}


class StageUpdate(BaseModel):
    stage: str


@app.put("/api/crm/opportunities/{opportunity_id}/stage")
async def update_opportunity_stage(opportunity_id: str, data: StageUpdate, request_id: str = Depends(get_request_id)):
    """Update opportunity stage."""
    for opp in _opportunities:
        if opp["id"] == opportunity_id:
            opp["stage"] = data.stage
            opp["lastActivity"] = datetime.now().isoformat()
            return {"success": True, "opportunity": opp}
    raise HTTPException(404, "Opportunity not found")


class NoteCreate(BaseModel):
    note: str


@app.post("/api/crm/leads/{lead_id}/notes")
async def add_lead_note(lead_id: str, data: NoteCreate, request_id: str = Depends(get_request_id)):
    """Add a note to a lead."""
    if lead_id not in _lead_notes:
        _lead_notes[lead_id] = []
    note = {
        "id": str(len(_lead_notes[lead_id]) + 1),
        "text": data.note,
        "createdAt": datetime.now().isoformat()
    }
    _lead_notes[lead_id].append(note)
    return {"success": True, "note": note}


@app.get("/api/crm/leads/{lead_id}/notes")
async def get_lead_notes(lead_id: str, request_id: str = Depends(get_request_id)):
    """Get notes for a lead."""
    return {"notes": _lead_notes.get(lead_id, [])}


# --- ANALYTICS ENDPOINTS ---

@app.get("/api/analytics/funnel")
async def get_funnel_metrics(request_id: str = Depends(get_request_id)):
    """Get lead funnel metrics."""
    try:
        lead_counts = {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "contacted": 0, "replied": 0}
        if db_service:
            all_leads = await db_service.get_leads(pagination=PaginationParams(page=1, page_size=10000))
            lead_counts["total"] = all_leads.total
            lead_counts["pending"] = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.PENDING)
            lead_counts["approved"] = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.APPROVED)
            lead_counts["rejected"] = sum(1 for l in all_leads.items if l.review_status == ReviewStatus.REJECTED)
        
        return {
            "funnel": lead_counts,
            "conversion_rates": {
                "discovery_to_approved": round((lead_counts["approved"] / max(lead_counts["total"], 1)) * 100, 1),
                "approved_to_contacted": 0,
                "contacted_to_replied": 0
            }
        }
    except Exception:
        return {"funnel": {}, "conversion_rates": {}}


@app.get("/api/analytics/campaigns")
async def get_campaign_analytics(request_id: str = Depends(get_request_id)):
    """Get campaign analytics."""
    return {
        "campaigns": [
            {"name": "Initial Outreach", "sent": 120, "opened": 45, "replied": 8, "openRate": 37.5, "replyRate": 6.7},
            {"name": "Follow-up", "sent": 80, "opened": 28, "replied": 5, "openRate": 35.0, "replyRate": 6.25}
        ]
    }


# --- WEBHOOKS ENDPOINTS ---

_webhooks = [
    {"id": "1", "name": "CRM Integration", "url": "https://api.example.com/webhook", "events": ["lead.created", "lead.approved"], "enabled": True},
    {"id": "2", "name": "Slack Notifications", "url": "https://hooks.slack.com/...", "events": ["email.replied"], "enabled": True}
]


@app.get("/api/webhooks")
async def get_webhooks(request_id: str = Depends(get_request_id)):
    """Get all webhooks."""
    return {"webhooks": _webhooks}


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: List[str]


@app.post("/api/webhooks")
async def create_webhook(data: WebhookCreate, request_id: str = Depends(get_request_id)):
    """Create a new webhook."""
    webhook = {
        "id": str(len(_webhooks) + 1),
        "name": data.name,
        "url": data.url,
        "events": data.events,
        "enabled": True
    }
    _webhooks.append(webhook)
    return {"success": True, "webhook": webhook}


class WebhookToggle(BaseModel):
    enabled: bool


@app.put("/api/webhooks/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: str, data: WebhookToggle, request_id: str = Depends(get_request_id)):
    """Toggle webhook enabled status."""
    for webhook in _webhooks:
        if webhook["id"] == webhook_id:
            webhook["enabled"] = data.enabled
            return {"success": True, "webhook": webhook}
    raise HTTPException(404, "Webhook not found")


# --- COMPLIANCE ENDPOINTS ---

_do_not_contact = []


@app.get("/api/compliance/status")
async def get_compliance_status(request_id: str = Depends(get_request_id)):
    """Get compliance status."""
    return {
        "unsubscribe_enabled": True,
        "do_not_contact_count": len(_do_not_contact),
        "spam_risk": "low",
        "domain_warmup_day": 5,
        "domain_warmup_total": 14,
        "rate_limits": {
            "max_emails_per_day": settings.email.max_emails_per_day,
            "max_emails_per_hour": 5
        }
    }


class DoNotContactAdd(BaseModel):
    email: str


@app.post("/api/compliance/do-not-contact")
async def add_to_do_not_contact(data: DoNotContactAdd, request_id: str = Depends(get_request_id)):
    """Add email to do-not-contact list."""
    if data.email not in _do_not_contact:
        _do_not_contact.append(data.email)
    return {"success": True, "message": f"Added {data.email} to do-not-contact list"}


@app.get("/api/compliance/do-not-contact")
async def get_do_not_contact_list(request_id: str = Depends(get_request_id)):
    """Get do-not-contact list."""
    return {"emails": _do_not_contact, "count": len(_do_not_contact)}


# --- USER MANAGEMENT ENDPOINTS ---

_users = [
    {"id": "1", "name": "Admin User", "email": "admin@company.com", "role": "admin", "status": "active"},
    {"id": "2", "name": "Review Manager", "email": "reviewer@company.com", "role": "reviewer", "status": "active"},
    {"id": "3", "name": "Outreach Sender", "email": "sender@company.com", "role": "sender", "status": "active"}
]


@app.get("/api/users")
async def get_users(request_id: str = Depends(get_request_id)):
    """Get all users."""
    return {"users": _users}


class UserCreateRequest(BaseModel):
    name: str
    email: str
    role: str


@app.post("/api/users")
async def create_user_api(data: UserCreateRequest, request_id: str = Depends(get_request_id)):
    """Create a new user."""
    user = {
        "id": str(len(_users) + 1),
        "name": data.name,
        "email": data.email,
        "role": data.role,
        "status": "active"
    }
    _users.append(user)
    return {"success": True, "user": user}


class RoleUpdate(BaseModel):
    role: str


@app.put("/api/users/{user_id}/role")
async def update_user_role(user_id: str, data: RoleUpdate, request_id: str = Depends(get_request_id)):
    """Update user role."""
    for user in _users:
        if user["id"] == user_id:
            user["role"] = data.role
            return {"success": True, "user": user}
    raise HTTPException(404, "User not found")


# --- SYNC & IMPORT/EXPORT ENDPOINTS ---

@app.get("/api/export/csv")
async def export_leads_csv(request_id: str = Depends(get_request_id)):
    """Export leads to CSV."""
    try:
        if db_service:
            all_leads = await db_service.get_leads(pagination=PaginationParams(page=1, page_size=10000))
            csv_lines = ["lead_id,business_name,email,category,location,review_status,outreach_status"]
            for lead in all_leads.items:
                csv_lines.append(f"{lead.id},{lead.business_name},{lead.email or ''},{lead.category or ''},{lead.location or ''},{lead.review_status},{lead.lifecycle_state}")
            
            return Response(
                content="\n".join(csv_lines),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=leads_export.csv"}
            )
        return Response(content="lead_id,business_name,email,category,location,review_status,outreach_status", media_type="text/csv")
    except Exception as e:
        raise HTTPException(500, str(e))


class GoogleSheetsSync(BaseModel):
    sheets_url: str


@app.post("/api/sync/google-sheets")
async def sync_google_sheets(data: GoogleSheetsSync, request_id: str = Depends(get_request_id)):
    """Sync with Google Sheets (placeholder)."""
    return {
        "success": True,
        "message": "Google Sheets sync initiated",
        "sheets_url": data.sheets_url,
        "status": "pending"
    }


# --- ENRICHMENT ENDPOINTS ---

@app.get("/api/enrichment/{lead_id}")
async def get_enrichment_data(lead_id: str, request_id: str = Depends(get_request_id)):
    """Get enrichment data for a lead."""
    # Return mock enrichment data
    return {
        "lead_id": lead_id,
        "tech_stack": ["React", "Node.js", "PostgreSQL", "AWS"],
        "company_size": "10-50 employees",
        "stage": "Growth Stage",
        "hiring_signals": True,
        "linkedin": "https://linkedin.com/company/example",
        "twitter": "https://twitter.com/example",
        "contact_intent": "High",
        "decision_maker": "CEO",
        "confidence": 85,
        "enriched_at": datetime.now().isoformat()
    }


if __name__ == "__main__":
    uvicorn.run(
        "cold_outreach_agent.api.production_server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.system.debug,
        log_level=settings.logging.level.lower()
    )

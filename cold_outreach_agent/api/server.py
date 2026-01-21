"""
FastAPI server with separate discovery and outreach control endpoints.

CRITICAL: Discovery and Outreach are SEPARATE operations.
NO EMAILS ARE SENT WITHOUT HUMAN APPROVAL.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.db_service import DatabaseService
from services.agent_state import agent_state_manager, AgentState
from services.agent_runner import agent_runner
from config.settings import settings
from api.static_server import setup_static_files

app = FastAPI(title="Cold Outreach Agent API", version="3.0.0")

# CORS for frontend

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static file serving for React dashboard
setup_static_files(app)

db = DatabaseService()
# Initialize the database on startup
db.init_db_sync()


# --- Request/Response Models ---

class ControlResponse(BaseModel):
    success: bool
    message: str
    state: str


class DiscoveryStartRequest(BaseModel):
    query: str
    location: str
    max_results: Optional[int] = 50


class BulkLeadAction(BaseModel):
    lead_ids: List[str]


class TestEmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    category: Optional[str] = "general"


class EmailTemplateUpdate(BaseModel):
    subject_template: str
    text_template: str
    category: Optional[str] = None


class AgentStateResponse(BaseModel):
    state: str
    last_transition_time: Optional[str]
    reason: Optional[str]
    controlled_by: str
    last_heartbeat: Optional[str]
    error_message: Optional[str]
    current_task: Optional[str]
    discovery_query: Optional[str]
    discovery_location: Optional[str]
    is_healthy: bool
    health_reason: str


# --- Discovery Control Endpoints ---

@app.post("/api/agent/discover/start", response_model=ControlResponse)
def start_discovery(request: DiscoveryStartRequest):
    """
    Start map discovery. Finds businesses and creates PENDING leads.
    Only valid from idle state.
    """
    success, message = agent_runner.start_discovery(
        query=request.query,
        location=request.location,
        max_results=request.max_results,
        controlled_by="user"
    )
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


@app.post("/api/agent/discover/stop", response_model=ControlResponse)
def stop_discovery():
    """Stop discovery gracefully."""
    success, message = agent_runner.stop_discovery(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


# --- Outreach Control Endpoints ---

@app.post("/api/agent/outreach/start", response_model=ControlResponse)
def start_outreach():
    """
    Start outreach. Sends emails ONLY to APPROVED leads.
    Only valid from idle state.
    """
    success, message = agent_runner.start_outreach(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


@app.post("/api/agent/outreach/stop", response_model=ControlResponse)
def stop_outreach():
    """Stop outreach gracefully."""
    success, message = agent_runner.stop_outreach(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


# --- Common Agent Control ---

@app.post("/api/agent/pause", response_model=ControlResponse)
def pause_agent():
    """Pause the agent (discovery or outreach)."""
    success, message = agent_runner.pause(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


@app.post("/api/agent/resume", response_model=ControlResponse)
def resume_agent():
    """Resume the agent from paused state."""
    success, message = agent_runner.resume(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


@app.post("/api/agent/stop", response_model=ControlResponse)
def stop_agent():
    """Stop the agent from any running state."""
    success, message = agent_runner.stop(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


@app.post("/api/agent/reset", response_model=ControlResponse)
def reset_agent():
    """Reset agent from error state."""
    success, message = agent_runner.reset_from_error(controlled_by="user")
    state = agent_state_manager.get_state()["state"]
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return ControlResponse(success=success, message=message, state=state)


@app.get("/api/agent/state", response_model=AgentStateResponse)
def get_agent_state():
    """Get current agent state from DB (source of truth)."""
    state_data = agent_state_manager.get_state()
    is_healthy, health_reason = agent_state_manager.is_healthy()
    
    return AgentStateResponse(
        state=state_data["state"],
        last_transition_time=state_data["last_transition_time"],
        reason=state_data["reason"],
        controlled_by=state_data["controlled_by"],
        last_heartbeat=state_data["last_heartbeat"],
        error_message=state_data["error_message"],
        current_task=state_data.get("current_task"),
        discovery_query=state_data.get("discovery_query"),
        discovery_location=state_data.get("discovery_location"),
        is_healthy=is_healthy,
        health_reason=health_reason
    )


@app.get("/api/agent/control-logs")
def get_control_logs(limit: int = Query(50, description="Max results")):
    """Get agent control audit logs."""
    logs = agent_state_manager.get_control_logs(limit=limit)
    return {"logs": logs, "total": len(logs)}


# --- Lead Review Endpoints (CRITICAL) ---

@app.post("/api/leads/{lead_id}/approve")
def approve_lead(lead_id: str):
    """
    Approve a lead for outreach.
    Only approved leads will receive emails.
    """
    lead = db.get_lead_by_id_sync(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    success = db.approve_lead_sync(lead_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve lead")
    
    db.add_agent_log_sync(
        module="review",
        action="approve",
        result="success",
        lead_id=lead_id,
        details="Lead approved by user"
    )
    
    return {"success": True, "message": "Lead approved", "lead_id": lead_id, "review_status": "approved"}


@app.post("/api/leads/{lead_id}/reject")
def reject_lead(lead_id: str):
    """
    Reject a lead. Rejected leads will NOT receive emails.
    """
    lead = db.get_lead_by_id_sync(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    success = db.reject_lead_sync(lead_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reject lead")
    
    db.add_agent_log_sync(
        module="review",
        action="reject",
        result="success",
        lead_id=lead_id,
        details="Lead rejected by user"
    )
    
    return {"success": True, "message": "Lead rejected", "lead_id": lead_id, "review_status": "rejected"}


@app.post("/api/leads/bulk-approve")
def bulk_approve_leads(request: BulkLeadAction):
    """Approve multiple leads at once."""
    count = db.bulk_approve_leads_sync(request.lead_ids)
    
    db.add_agent_log_sync(
        module="review",
        action="bulk_approve",
        result="success",
        details=f"Approved {count} leads"
    )
    
    return {"success": True, "approved_count": count}


@app.post("/api/leads/bulk-reject")
def bulk_reject_leads(request: BulkLeadAction):
    """Reject multiple leads at once."""
    count = db.bulk_reject_leads_sync(request.lead_ids)
    
    db.add_agent_log_sync(
        module="review",
        action="bulk_reject",
        result="success",
        details=f"Rejected {count} leads"
    )
    
    return {"success": True, "rejected_count": count}


@app.delete("/api/leads/clear-all")
def clear_all_leads():
    """Delete all leads from the database. USE WITH CAUTION."""
    count = db.clear_all_leads_sync()
    
    db.add_agent_log_sync(
        module="review",
        action="clear_all",
        result="success",
        details=f"Cleared {count} leads from database"
    )
    
    return {"success": True, "deleted_count": count, "message": f"Deleted {count} leads"}


# --- Lead Read Endpoints ---

@app.get("/api/leads")
def get_leads(
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    outreach_status: Optional[str] = Query(None, description="Filter by outreach status")
):
    """List leads with optional filtering."""
    if review_status:
        leads = db.get_leads_by_review_status_sync(review_status)
    elif outreach_status:
        leads = db.get_leads_by_outreach_status_sync(outreach_status)
    else:
        leads = db.get_all_leads_sync()
    
    return [
        {
            "lead_id": l.get("lead_id"),
            "business_name": l.get("business_name"),
            "category": l.get("category"),
            "location": l.get("location"),
            "maps_url": l.get("maps_url"),
            "website_url": l.get("website_url"),
            "email": l.get("email"),
            "tag": l.get("tag"),
            "review_status": l.get("review_status"),
            "outreach_status": l.get("outreach_status"),
            "discovery_source": l.get("discovery_source"),
            "discovered_at": l.get("discovered_at"),
            "last_contacted": l.get("last_contacted")
        }
        for l in leads
    ]


@app.get("/api/leads/{lead_id}")
def get_lead_detail(lead_id: str):
    """Full lead details with action history."""
    lead = db.get_lead_by_id_sync(lead_id)
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get action history for this lead
    history = db.get_agent_logs_sync(limit=50, lead_id=lead_id)
    
    return {
        "lead": lead,
        "action_history": history
    }


# --- Overview & Stats ---

@app.get("/api/overview")
def get_overview():
    """Dashboard overview stats."""
    counts = db.get_lead_counts_sync()
    sent_today = db.get_emails_sent_today_sync()
    
    return {
        "total_leads": counts["total"],
        "pending_review": counts["pending_review"],
        "approved": counts["approved"],
        "rejected": counts["rejected"],
        "emails_sent_today": sent_today,
        "sent_initial": counts["sent_initial"],
        "sent_followup": counts["sent_followup"],
        "replies_received": counts["replied"]
    }


@app.get("/api/logs")
def get_logs_endpoint(
    module: Optional[str] = Query(None, description="Filter by module"),
    lead_id: Optional[str] = Query(None, description="Filter by lead ID"),
    limit: int = Query(100, description="Max results")
):
    """Get agent logs with filtering."""
    logs = db.get_agent_logs_sync(limit=limit, module=module, lead_id=lead_id)
    return {"logs": logs, "total": len(logs)}


@app.get("/api/system")
def get_system_status():
    """System health and agent status."""
    counts = db.get_lead_counts_sync()
    emails_today = db.get_emails_sent_today_sync()
    
    # Agent state
    state_data = agent_state_manager.get_state()
    is_healthy, health_reason = agent_state_manager.is_healthy()
    
    # Recent errors
    logs = db.get_agent_logs_sync(limit=100)
    yesterday = (datetime.now() - timedelta(hours=24)).isoformat()
    error_count = sum(1 for l in logs if l.get("result") == "error" and l.get("timestamp", "") >= yesterday)
    
    return {
        "agent_state": state_data["state"],
        "last_transition_time": state_data["last_transition_time"],
        "last_heartbeat": state_data["last_heartbeat"],
        "current_task": state_data.get("current_task"),
        "discovery_query": state_data.get("discovery_query"),
        "discovery_location": state_data.get("discovery_location"),
        "is_healthy": is_healthy,
        "health_reason": health_reason,
        "error_message": state_data["error_message"],
        "error_count_24h": error_count,
        "emails_sent_today": emails_today,
        "email_quota": settings.MAX_EMAILS_PER_DAY,
        "lead_counts": counts
    }


# --- Email Templates & Test Email ---

# In-memory storage for custom email templates (per category)
# Default templates based on business category
default_templates = {
    "general": {
        "name": "General Outreach",
        "subject_template": "Quick question about {{business_name}}",
        "text_template": """Hi there,

I came across {{business_name}} and was impressed by what you're doing in {{location}}.

I help businesses like yours grow their online presence and attract more customers.

Would you be interested in a quick 15-minute call to discuss how this could benefit {{business_name}}?

Best regards,
{{sender_name}}

P.S. If this isn't relevant, just reply "not interested" and I won't reach out again."""
    },
    "restaurant": {
        "name": "Restaurant Outreach",
        "subject_template": "Helping {{business_name}} get more customers",
        "text_template": """Hi there,

I noticed {{business_name}} in {{location}} and love what you're doing!

I specialize in helping restaurants like yours increase table bookings and improve online reviews.

Would you be interested in learning how other restaurants in the area have seen a 25% increase in reservations?

Let me know if you'd like to chat!

Best,
{{sender_name}}"""
    },
    "plumber": {
        "name": "Plumber/Contractor Outreach",
        "subject_template": "More service calls for {{business_name}}?",
        "text_template": """Hi there,

I came across {{business_name}} and noticed you're serving the {{location}} area.

I help plumbing and contractor businesses generate more service calls and build trust with homeowners online.

Would you be open to a quick chat about how we could help you get more emergency service bookings?

Best regards,
{{sender_name}}"""
    },
    "salon": {
        "name": "Salon/Spa Outreach",
        "subject_template": "Grow {{business_name}}'s client base",
        "text_template": """Hi there,

I found {{business_name}} online and love the services you offer in {{location}}!

I help salons and spas like yours book more appointments and increase customer lifetime value.

Would you be interested in hearing how similar businesses have boosted their bookings by 50%?

Looking forward to connecting!

Best,
{{sender_name}}"""
    },
    "fitness": {
        "name": "Gym/Fitness Outreach",
        "subject_template": "Increase membership for {{business_name}}",
        "text_template": """Hi there,

I came across {{business_name}} in {{location}} and was impressed by your fitness offerings!

I help gyms and fitness centers increase membership sign-ups and improve retention rates.

Would you like to learn how similar gyms have seen a 45% improvement in membership conversions?

Let's connect!

Best,
{{sender_name}}"""
    }
}

# Store for custom templates (will be persisted in future versions)
custom_templates = {}


@app.get("/api/email-templates")
def get_email_templates():
    """Get all available email templates (default + custom)."""
    all_templates = {}
    
    # Add default templates
    for category, template in default_templates.items():
        all_templates[category] = {
            **template,
            "category": category,
            "type": "default",
            "variables": ["business_name", "location", "sender_name"]
        }
    
    # Override with custom templates
    for category, template in custom_templates.items():
        all_templates[category] = {
            **template,
            "category": category,
            "type": "custom",
            "variables": ["business_name", "location", "sender_name"]
        }
    
    return {"templates": all_templates}


@app.get("/api/email-templates/{category}")
def get_email_template(category: str):
    """Get a specific email template by category."""
    if category in custom_templates:
        template = custom_templates[category]
        template_type = "custom"
    elif category in default_templates:
        template = default_templates[category]
        template_type = "default"
    else:
        raise HTTPException(status_code=404, detail=f"Template not found for category: {category}")
    
    return {
        **template,
        "category": category,
        "type": template_type,
        "variables": ["business_name", "location", "sender_name"]
    }


@app.put("/api/email-templates/{category}")
def update_email_template(category: str, request: EmailTemplateUpdate):
    """Update or create a custom email template for a category."""
    custom_templates[category] = {
        "name": f"{category.title()} Outreach",
        "subject_template": request.subject_template,
        "text_template": request.text_template
    }
    
    db.add_agent_log_sync(
        module="templates",
        action="update",
        result="success",
        details=f"Email template updated for category: {category}"
    )
    
    return {
        "success": True,
        "message": f"Template updated for category: {category}",
        "template": {
            **custom_templates[category],
            "category": category,
            "type": "custom"
        }
    }


@app.delete("/api/email-templates/{category}")
def reset_email_template(category: str):
    """Reset a template to default (remove custom version)."""
    if category in custom_templates:
        del custom_templates[category]
        
        db.add_agent_log_sync(
            module="templates",
            action="reset",
            result="success",
            details=f"Email template reset to default for category: {category}"
        )
        
        return {"success": True, "message": f"Template reset to default for category: {category}"}
    else:
        return {"success": True, "message": "No custom template exists for this category"}


@app.post("/api/email/test")
def send_test_email(request: TestEmailRequest):
    """
    Send a test email to verify email configuration is working.
    This is for testing purposes only.
    """
    from services.email_service_simple import EmailService
    
    email_service = EmailService()
    
    # Log the test email attempt
    db.add_agent_log_sync(
        module="email_test",
        action="send_test",
        result="pending",
        details=f"Sending test email to {request.to_email}"
    )
    
    try:
        success, message = email_service.send_email(
            to_email=request.to_email,
            subject=request.subject,
            body=request.body
        )
        
        if success:
            db.add_agent_log_sync(
                module="email_test",
                action="send_test",
                result="success",
                details=f"Test email sent successfully to {request.to_email}"
            )
            return {
                "success": True,
                "message": f"Test email sent successfully to {request.to_email}",
                "details": message
            }
        else:
            db.add_agent_log_sync(
                module="email_test",
                action="send_test",
                result="error",
                details=f"Failed to send test email: {message}"
            )
            raise HTTPException(status_code=500, detail=f"Failed to send email: {message}")
            
    except Exception as e:
        db.add_agent_log_sync(
            module="email_test",
            action="send_test",
            result="error",
            details=f"Email error: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Email error: {str(e)}")


@app.get("/api/health")
def health_check():
    """Simple health check."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


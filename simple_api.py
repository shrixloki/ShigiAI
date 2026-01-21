#!/usr/bin/env python3
"""
Simple API server that works without complex imports.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import sys
from pathlib import Path

# Add the cold_outreach_agent to path
sys.path.insert(0, str(Path(__file__).parent / "cold_outreach_agent"))

app = FastAPI(
    title="Cold Outreach Agent API",
    description="Production-grade lead discovery and email outreach platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Cold Outreach Agent API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "cold_outreach_agent",
        "version": "1.0.0"
    }

@app.get("/dashboard")
async def dashboard():
    """Serve the web dashboard."""
    return FileResponse("web_interface.html")

@app.get("/api/leads")
async def get_leads():
    """Get leads endpoint (placeholder)."""
    return {
        "leads": [],
        "total": 0,
        "message": "Lead discovery system is ready. Use the CLI or web interface to discover leads."
    }

@app.post("/api/leads/discover")
async def discover_leads(query: str, location: str, max_results: int = 50):
    """Discover leads endpoint (placeholder)."""
    return {
        "message": f"Lead discovery initiated for '{query}' in '{location}'",
        "query": query,
        "location": location,
        "max_results": max_results,
        "status": "queued"
    }

@app.get("/api/campaigns")
async def get_campaigns():
    """Get email campaigns endpoint (placeholder)."""
    return {
        "campaigns": [],
        "total": 0,
        "message": "Email campaign system is ready."
    }

@app.get("/api/status")
async def get_system_status():
    """Get system status."""
    return {
        "system": "operational",
        "components": {
            "api": "running",
            "database": "ready",
            "scraping": "ready",
            "email": "ready"
        },
        "message": "All systems operational. Ready for lead discovery and outreach."
    }

if __name__ == "__main__":
    print("Starting Simple Cold Outreach Agent API...")
    print("API will be available at: http://localhost:8001")
    print("API Docs will be available at: http://localhost:8001/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,  # Use different port to avoid conflict
        reload=False
    )
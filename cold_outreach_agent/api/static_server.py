"""
Static file server for serving the React dashboard from the backend.
This serves the built frontend files from the backend API server.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path

def setup_static_files(app: FastAPI):
    """Setup static file serving for the React dashboard."""
    
    # Path to the built frontend files
    static_dir = Path(__file__).parent.parent / "dashboard" / "dist"
    assets_dir = static_dir / "assets"
    
    if static_dir.exists() and assets_dir.exists():
        # Serve assets at /assets/ to match HTML references
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        
        # Serve the main index.html for all non-API routes
        @app.get("/")
        @app.get("/leads")
        @app.get("/logs") 
        @app.get("/system")
        async def serve_frontend():
            return FileResponse(static_dir / "index.html")
    else:
        # Fallback message if frontend not built
        @app.get("/")
        async def frontend_not_available():
            return {
                "message": "Frontend not available. Use API endpoints.",
                "api_docs": "/docs",
                "api_health": "/api/agent/state",
                "build_frontend": "Run 'npm run build' in dashboard/ directory"
            }
#!/usr/bin/env python3
"""
Startup script for Cold Outreach Agent Backend Only
For when Node.js is not available
"""

import subprocess
import sys
import time
from pathlib import Path

def start_backend_only():
    print("🚀 Cold Outreach Agent Backend Launcher")
    print("=" * 50)
    
    project_root = Path(__file__).parent / "cold_outreach_agent"
    
    # Check if project directory exists
    if not project_root.exists():
        print(f"❌ Project directory not found: {project_root}")
        return
    
    # Check Python dependencies
    try:
        import fastapi
        import uvicorn
        print("✅ Python dependencies found")
    except ImportError as e:
        print(f"❌ Missing Python dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return
    
    print("🚀 Starting backend API server...")
    
    try:
        # Start backend server
        subprocess.run([
            sys.executable, '-m', 'uvicorn', 
            'api.server:app', 
            '--host', '0.0.0.0',
            '--port', '8000',
            '--reload'
        ], cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n🛑 Backend stopped")
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")

if __name__ == "__main__":
    start_backend_only()
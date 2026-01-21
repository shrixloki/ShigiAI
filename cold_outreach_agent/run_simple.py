#!/usr/bin/env python3
"""
Simple startup script for Cold Outreach Agent
No Docker required - just Python
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required Python packages are installed."""
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI found")
    except ImportError:
        print("❌ FastAPI not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"])
    
    try:
        import playwright
        print("✅ Playwright found")
    except ImportError:
        print("❌ Playwright not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

def start_server():
    """Start the FastAPI server."""
    print("🚀 Starting Cold Outreach Agent...")
    print("📊 API Server: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("🔧 Health Check: http://localhost:8000/api/agent/state")
    print("\nPress Ctrl+C to stop")
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "api.server:app", 
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

if __name__ == "__main__":
    print("🐍 Cold Outreach Agent - Simple Python Startup")
    print("=" * 50)
    
    # Change to the script directory
    os.chdir(Path(__file__).parent)
    
    check_dependencies()
    start_server()
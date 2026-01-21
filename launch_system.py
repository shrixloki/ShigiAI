#!/usr/bin/env python3
"""
Simple system launcher that bypasses import issues and gets the system running.
"""

import sys
import os
import subprocess
import time
import webbrowser
from pathlib import Path
from multiprocessing import Process

def start_backend():
    """Start the backend API server."""
    try:
        print("🚀 Starting backend API server...")
        
        # Change to the cold_outreach_agent directory
        os.chdir("cold_outreach_agent")
        
        # Start uvicorn directly with the old API structure
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "api.server:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ]
        
        subprocess.run(cmd)
        
    except Exception as e:
        print(f"❌ Backend failed: {e}")
        
        # Try alternative approach
        try:
            print("🔄 Trying alternative backend startup...")
            cmd = [
                sys.executable, "-c",
                """
import sys
sys.path.insert(0, '.')
from api.server import app
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8000)
"""
            ]
            subprocess.run(cmd)
        except Exception as e2:
            print(f"❌ Alternative backend also failed: {e2}")

def start_frontend():
    """Start the frontend development server."""
    try:
        print("🚀 Starting frontend...")
        
        frontend_dir = Path("Frontend")
        if not frontend_dir.exists():
            print("❌ Frontend directory not found")
            return
            
        os.chdir(frontend_dir)
        
        # Check if node_modules exists
        if not Path("node_modules").exists():
            print("📦 Installing frontend dependencies...")
            subprocess.run(["npm", "install"], check=True)
        
        # Start the development server
        subprocess.run(["npm", "run", "dev"])
        
    except Exception as e:
        print(f"❌ Frontend failed: {e}")

def main():
    """Main launcher function."""
    
    print("🚀 Cold Outreach Agent - System Launcher")
    print("=" * 50)
    
    # Get the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Start backend in a separate process
    backend_process = Process(target=start_backend)
    backend_process.start()
    
    # Give backend time to start
    print("⏳ Waiting for backend to start...")
    time.sleep(5)
    
    # Check if backend is running
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running!")
        else:
            print("⚠️ Backend may not be fully ready")
    except:
        print("⚠️ Backend health check failed, but continuing...")
    
    # Open browser to the API docs
    print("🌐 Opening API documentation...")
    webbrowser.open("http://localhost:8000/docs")
    
    # Start frontend in a separate process
    frontend_process = Process(target=start_frontend)
    frontend_process.start()
    
    print("\n🎉 System is starting!")
    print("📊 Backend API:     http://localhost:8000")
    print("📖 API Docs:       http://localhost:8000/docs")
    print("🌐 Frontend:       http://localhost:5173 (if available)")
    print("\nPress Ctrl+C to stop all services...")
    
    try:
        # Wait for processes
        backend_process.join()
        frontend_process.join()
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        backend_process.terminate()
        frontend_process.terminate()
        print("✅ Services stopped")

if __name__ == "__main__":
    main()
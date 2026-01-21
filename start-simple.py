#!/usr/bin/env python3
"""
Simple startup script for Cold Outreach Agent System
Minimal dependency checking, just starts the services
"""

import subprocess
import sys
import time
from pathlib import Path

class SimpleServiceManager:
    def __init__(self):
        self.processes = []
        self.root_dir = Path(__file__).parent
        self.backend_dir = self.root_dir / "cold_outreach_agent"
        self.dashboard_dir = self.backend_dir / "dashboard"
        self.frontend_dir = self.root_dir / "Frontend"
        
    def start_backend(self):
        """Start the FastAPI backend server."""
        print("🚀 Starting backend API server...")
        
        try:
            backend_process = subprocess.Popen([
                sys.executable, '-m', 'uvicorn', 
                'api.server:app', 
                '--host', '0.0.0.0',
                '--port', '8000',
                '--reload'
            ], cwd=self.backend_dir)
            
            self.processes.append(('Backend API', backend_process))
            print("✅ Backend API server starting on http://localhost:8000")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start backend: {e}")
            return False
    
    def start_dashboard(self):
        """Start the dashboard frontend."""
        print("🚀 Starting dashboard...")
        
        if not self.dashboard_dir.exists():
            print("⚠️  Dashboard directory not found, skipping...")
            return True
            
        try:
            dashboard_process = subprocess.Popen([
                'npm', 'run', 'dev'
            ], cwd=self.dashboard_dir)
            
            self.processes.append(('Dashboard', dashboard_process))
            print("✅ Dashboard starting on http://localhost:5173")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start dashboard: {e}")
            return False
    
    def start_frontend(self):
        """Start the main frontend application."""
        print("🚀 Starting main frontend...")
        
        if not self.frontend_dir.exists():
            print("⚠️  Frontend directory not found, skipping...")
            return True
            
        try:
            frontend_process = subprocess.Popen([
                'npm', 'run', 'dev'
            ], cwd=self.frontend_dir)
            
            self.processes.append(('Frontend', frontend_process))
            print("✅ Frontend starting (check console for port)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start frontend: {e}")
            return False
    
    def cleanup(self):
        """Stop all running processes."""
        print("\n🛑 Stopping all services...")
        
        for name, process in self.processes:
            try:
                print(f"   Stopping {name}...")
                if sys.platform == "win32":
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                 capture_output=True)
                else:
                    process.terminate()
                    process.wait(timeout=5)
            except Exception as e:
                print(f"   Error stopping {name}: {e}")
        
        print("✅ All services stopped")
    
    def run(self):
        """Main execution flow."""
        print("🚀 Cold Outreach Agent - Simple Launcher")
        print("=" * 50)
        
        try:
            # Start services
            if not self.start_backend():
                sys.exit(1)
            
            time.sleep(3)  # Give backend time to start
            
            if self.dashboard_dir.exists():
                self.start_dashboard()
            
            time.sleep(2)
            
            if self.frontend_dir.exists():
                self.start_frontend()
            
            print("\n🎉 Services are starting!")
            print("📊 Backend API:     http://localhost:8000")
            print("📖 API Docs:       http://localhost:8000/docs")
            if self.dashboard_dir.exists():
                print("📊 Dashboard:      http://localhost:5173")
            if self.frontend_dir.exists():
                print("🌐 Frontend:       Check console for port")
            print("\nPress Ctrl+C to stop all services...")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        
        finally:
            self.cleanup()

def main():
    manager = SimpleServiceManager()
    manager.run()

if __name__ == "__main__":
    main()
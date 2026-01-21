#!/usr/bin/env python3
"""
Startup script for Cold Outreach Agent System
Launches both backend API server and frontend dashboard
"""

import subprocess
import sys
import time
import os
import signal
from pathlib import Path

class SystemLauncher:
    def __init__(self):
        self.processes = []
        self.project_root = Path(__file__).parent
        
    def check_dependencies(self):
        """Check if required dependencies are available."""
        print("🔍 Checking dependencies...")
        
        # Check Python dependencies
        try:
            import fastapi
            import uvicorn
            import playwright
            print("✅ Python dependencies found")
        except ImportError as e:
            print(f"❌ Missing Python dependency: {e}")
            print("Run: pip install -r requirements.txt")
            return False
        
        # Check if Node.js is available for frontend
        try:
            result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Node.js/npm found")
            else:
                print("❌ npm not found")
                return False
        except FileNotFoundError:
            print("❌ Node.js/npm not found")
            print("Install Node.js from https://nodejs.org/")
            return False
        
        return True
    
    def install_frontend_deps(self):
        """Install frontend dependencies if needed."""
        dashboard_path = self.project_root / "dashboard"
        node_modules = dashboard_path / "node_modules"
        
        if not node_modules.exists():
            print("📦 Installing frontend dependencies...")
            try:
                subprocess.run(['npm', 'install'], cwd=dashboard_path, check=True)
                print("✅ Frontend dependencies installed")
            except subprocess.CalledProcessError:
                print("❌ Failed to install frontend dependencies")
                return False
        else:
            print("✅ Frontend dependencies already installed")
        
        return True
    
    def start_backend(self):
        """Start the FastAPI backend server."""
        print("🚀 Starting backend API server...")
        
        try:
            # Start backend server
            backend_process = subprocess.Popen([
                sys.executable, '-m', 'uvicorn', 
                'api.server:app', 
                '--host', '0.0.0.0',
                '--port', '8000',
                '--reload'
            ], cwd=self.project_root)
            
            self.processes.append(('Backend API', backend_process))
            print("✅ Backend API server started on http://localhost:8000")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start backend: {e}")
            return False
    
    def start_frontend(self):
        """Start the React frontend development server."""
        print("🚀 Starting frontend dashboard...")
        
        dashboard_path = self.project_root / "dashboard"
        
        try:
            # Start frontend dev server
            frontend_process = subprocess.Popen([
                'npm', 'run', 'dev'
            ], cwd=dashboard_path)
            
            self.processes.append(('Frontend Dashboard', frontend_process))
            print("✅ Frontend dashboard started on http://localhost:5173")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start frontend: {e}")
            return False
    
    def wait_for_services(self):
        """Wait for services to be ready."""
        print("⏳ Waiting for services to start...")
        time.sleep(3)
        
        # Check if backend is responding
        try:
            import requests
            response = requests.get('http://localhost:8000/api/agent/state', timeout=5)
            if response.status_code == 200:
                print("✅ Backend API is responding")
            else:
                print("⚠️  Backend API may not be fully ready")
        except:
            print("⚠️  Backend API not responding yet (this is normal)")
        
        print("\n🎉 Cold Outreach Agent System is starting up!")
        print("\n📊 Dashboard: http://localhost:5173")
        print("🔧 API Server: http://localhost:8000")
        print("📖 API Docs: http://localhost:8000/docs")
        print("\nPress Ctrl+C to stop all services")
    
    def cleanup(self):
        """Stop all running processes."""
        print("\n🛑 Stopping all services...")
        
        for name, process in self.processes:
            try:
                print(f"   Stopping {name}...")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"   Force killing {name}...")
                process.kill()
            except Exception as e:
                print(f"   Error stopping {name}: {e}")
        
        print("✅ All services stopped")
    
    def run(self):
        """Main execution flow."""
        print("🚀 Cold Outreach Agent System Launcher")
        print("=" * 50)
        
        try:
            # Check dependencies
            if not self.check_dependencies():
                sys.exit(1)
            
            # Install frontend dependencies
            if not self.install_frontend_deps():
                sys.exit(1)
            
            # Start services
            if not self.start_backend():
                sys.exit(1)
            
            time.sleep(2)  # Give backend time to start
            
            if not self.start_frontend():
                self.cleanup()
                sys.exit(1)
            
            # Wait and show status
            self.wait_for_services()
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
                    # Check if any process died
                    for name, process in self.processes:
                        if process.poll() is not None:
                            print(f"\n❌ {name} stopped unexpectedly")
                            raise KeyboardInterrupt
            
            except KeyboardInterrupt:
                pass
        
        finally:
            self.cleanup()

def main():
    launcher = SystemLauncher()
    launcher.run()

if __name__ == "__main__":
    main()
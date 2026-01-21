#!/usr/bin/env python3
"""
Comprehensive startup script for Cold Outreach Agent System
Launches all services: Backend API, Dashboard, and Frontend
Non-Docker version with full dependency management
"""

import subprocess
import sys
import time
import os
import signal
from pathlib import Path
import threading
import webbrowser

class ServiceManager:
    def __init__(self):
        self.processes = []
        self.root_dir = Path(__file__).parent
        self.backend_dir = self.root_dir / "cold_outreach_agent"
        self.dashboard_dir = self.backend_dir / "dashboard"
        self.frontend_dir = self.root_dir / "Frontend"
        
    def print_banner(self):
        """Print startup banner."""
        print("🚀 Cold Outreach Agent - Complete System Launcher")
        print("=" * 60)
        print("Starting all services without Docker...")
        print()
        
    def check_python_deps(self):
        """Check Python dependencies for backend."""
        print("🐍 Checking Python dependencies...")
        
        requirements_file = self.backend_dir / "requirements.txt"
        if not requirements_file.exists():
            print("❌ requirements.txt not found")
            return False
            
        try:
            # Check key dependencies
            import fastapi
            import uvicorn
            import playwright
            print("✅ Core Python dependencies found")
            return True
        except ImportError as e:
            print(f"❌ Missing Python dependency: {e}")
            print(f"💡 Run: pip install -r {requirements_file}")
            return False
    
    def check_node_deps(self):
        """Check Node.js availability."""
        print("📦 Checking Node.js...")
        
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Node.js found: {result.stdout.strip()}")
            else:
                print("❌ Node.js not found")
                print("💡 Install from: https://nodejs.org/")
                return False
        except FileNotFoundError:
            print("❌ Node.js not found")
            print("💡 Install from: https://nodejs.org/")
            return False
        
        try:
            npm_result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
            if npm_result.returncode == 0:
                print(f"✅ npm found: {npm_result.stdout.strip()}")
                return True
            else:
                print("❌ npm not found")
                return False
        except FileNotFoundError:
            print("❌ npm not found")
            return False
    
    def install_frontend_deps(self, directory, name):
        """Install frontend dependencies for a given directory."""
        node_modules = directory / "node_modules"
        package_json = directory / "package.json"
        
        if not package_json.exists():
            print(f"⚠️  No package.json found in {directory}")
            return False
            
        if not node_modules.exists():
            print(f"📦 Installing {name} dependencies...")
            try:
                subprocess.run(['npm', 'install'], cwd=directory, check=True)
                print(f"✅ {name} dependencies installed")
                return True
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install {name} dependencies")
                return False
        else:
            print(f"✅ {name} dependencies already installed")
            return True
    
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
            # Check if there's a specific port configuration
            frontend_process = subprocess.Popen([
                'npm', 'run', 'dev'
            ], cwd=self.frontend_dir)
            
            self.processes.append(('Frontend', frontend_process))
            print("✅ Frontend starting (check console for port)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start frontend: {e}")
            return False
    
    def wait_for_services(self):
        """Wait for services to be ready and show status."""
        print("\n⏳ Waiting for services to initialize...")
        time.sleep(5)
        
        # Check backend health
        try:
            import requests
            response = requests.get('http://localhost:8000/api/agent/state', timeout=10)
            if response.status_code == 200:
                print("✅ Backend API is responding")
            else:
                print("⚠️  Backend API responding but may not be fully ready")
        except Exception:
            print("⚠️  Backend API not responding yet (this may be normal)")
        
        print("\n🎉 Cold Outreach Agent System is running!")
        print("=" * 60)
        print("📊 Services:")
        print("   🔧 Backend API:     http://localhost:8000")
        print("   📖 API Docs:       http://localhost:8000/docs")
        
        if self.dashboard_dir.exists():
            print("   📊 Dashboard:      http://localhost:5173")
            
        if self.frontend_dir.exists():
            print("   🌐 Frontend:       Check console output for port")
            
        print("\n💡 Tips:")
        print("   • Press Ctrl+C to stop all services")
        print("   • Check individual console outputs for detailed logs")
        print("   • If a service fails, check the error messages above")
        print("=" * 60)
    
    def open_browser(self):
        """Open browser tabs for the services."""
        def delayed_open():
            time.sleep(8)  # Wait for services to fully start
            try:
                webbrowser.open('http://localhost:8000/docs')
                if self.dashboard_dir.exists():
                    time.sleep(1)
                    webbrowser.open('http://localhost:5173')
            except Exception:
                pass  # Browser opening is optional
        
        thread = threading.Thread(target=delayed_open, daemon=True)
        thread.start()
    
    def cleanup(self):
        """Stop all running processes."""
        print("\n🛑 Stopping all services...")
        
        for name, process in self.processes:
            try:
                print(f"   Stopping {name}...")
                if sys.platform == "win32":
                    # On Windows, use taskkill for better process cleanup
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                 capture_output=True)
                else:
                    process.terminate()
                    process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"   Force killing {name}...")
                if sys.platform == "win32":
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                 capture_output=True)
                else:
                    process.kill()
            except Exception as e:
                print(f"   Error stopping {name}: {e}")
        
        print("✅ All services stopped")
    
    def run(self):
        """Main execution flow."""
        self.print_banner()
        
        try:
            # Check all dependencies
            if not self.check_python_deps():
                print("\n❌ Python dependencies check failed")
                sys.exit(1)
            
            if not self.check_node_deps():
                print("\n❌ Node.js dependencies check failed")
                sys.exit(1)
            
            # Install frontend dependencies
            success = True
            
            if self.dashboard_dir.exists():
                success &= self.install_frontend_deps(self.dashboard_dir, "Dashboard")
            
            if self.frontend_dir.exists():
                success &= self.install_frontend_deps(self.frontend_dir, "Frontend")
            
            if not success:
                print("\n❌ Frontend dependency installation failed")
                sys.exit(1)
            
            print("\n🚀 Starting all services...")
            print("-" * 40)
            
            # Start services in order
            if not self.start_backend():
                sys.exit(1)
            
            time.sleep(3)  # Give backend time to start
            
            if self.dashboard_dir.exists():
                if not self.start_dashboard():
                    print("⚠️  Dashboard failed to start, continuing...")
            
            time.sleep(2)
            
            if self.frontend_dir.exists():
                if not self.start_frontend():
                    print("⚠️  Frontend failed to start, continuing...")
            
            # Show status and open browser
            self.wait_for_services()
            self.open_browser()
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
                    # Check if any critical process died
                    for name, process in self.processes:
                        if process.poll() is not None:
                            if name == 'Backend API':  # Backend is critical
                                print(f"\n❌ {name} stopped unexpectedly")
                                raise KeyboardInterrupt
                            else:
                                print(f"\n⚠️  {name} stopped")
            
            except KeyboardInterrupt:
                pass
        
        finally:
            self.cleanup()

def main():
    """Entry point."""
    try:
        manager = ServiceManager()
        manager.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
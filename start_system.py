#!/usr/bin/env python3
"""
Complete system launcher for Cold Outreach Agent.
Starts the API server and opens the web dashboard.
"""

import subprocess
import time
import webbrowser
import sys
import os
from pathlib import Path

def main():
    """Main launcher function."""
    
    print("🚀 Cold Outreach Agent - System Launcher")
    print("=" * 50)
    
    # Check if the API is already running
    try:
        import requests
        response = requests.get("http://localhost:8001/health", timeout=2)
        if response.status_code == 200:
            print("✅ API server is already running!")
            print("🌐 Opening dashboard...")
            webbrowser.open("http://localhost:8001/dashboard")
            print("\n🎉 System is ready!")
            print("📊 API Server:      http://localhost:8001")
            print("🌐 Web Dashboard:   http://localhost:8001/dashboard")
            print("📖 API Docs:       http://localhost:8001/docs")
            return
    except:
        pass
    
    print("🚀 Starting API server...")
    
    # Start the API server in background
    try:
        # Use subprocess.Popen to start in background
        process = subprocess.Popen(
            [sys.executable, "simple_api.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        
        print("⏳ Waiting for server to start...")
        time.sleep(3)
        
        # Check if server is running
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                import requests
                response = requests.get("http://localhost:8001/health", timeout=2)
                if response.status_code == 200:
                    print("✅ API server is running!")
                    break
            except:
                if attempt < max_attempts - 1:
                    print(f"⏳ Attempt {attempt + 1}/{max_attempts} - waiting...")
                    time.sleep(2)
                else:
                    print("❌ Server failed to start properly")
                    return
        
        # Open the dashboard
        print("🌐 Opening web dashboard...")
        webbrowser.open("http://localhost:8001/dashboard")
        
        print("\n🎉 System is ready!")
        print("📊 API Server:      http://localhost:8001")
        print("🌐 Web Dashboard:   http://localhost:8001/dashboard")
        print("📖 API Docs:       http://localhost:8001/docs")
        print("\n💡 The API server is running in a separate window.")
        print("💡 Close that window to stop the server.")
        print("💡 Or use Ctrl+C in the server window.")
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        print("🔧 Try running 'python simple_api.py' manually")

if __name__ == "__main__":
    main()
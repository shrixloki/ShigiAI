
import os
import sys
import subprocess
import time
import signal
from pathlib import Path
import shutil

def main():
    # Get project root
    project_root = Path(__file__).parent.absolute()
    frontend_dir = project_root / "Frontend"
    
    print(f">> Launching Cold Outreach Agent from {project_root}")
    
    # 1. Resolve npm executable
    # On Windows, we want npm.cmd to avoid PowerShell script execution policy issues with npm.ps1
    npm_cmd = "npm"
    if os.name == 'nt':
        npm_path = shutil.which("npm.cmd")
        if npm_path:
            npm_cmd = npm_path
        else:
            # Fallback to just npm and hope shell=True handles it via cmd.exe
            npm_cmd = "npm"
            
    print(f">> Using npm: {npm_cmd}")

    processes = []

    try:
        # 2. Start Backend
        print("\n[1/2] Starting Backend Server...")
        backend_process = subprocess.Popen(
            [sys.executable, "run_production.py", "server"],
            cwd=project_root,
            shell=True # Use shell to open in new window if possible? No, keep in same console for log visibility or separate?
            # actually better to keep them running. To have them pop up separate windows we need 'start' command equivalent or creationflags
        )
        processes.append(backend_process)
        
        # Give backend a moment
        time.sleep(2)

        # 3. Start Frontend
        print(f"\n[2/2] Starting Frontend in {frontend_dir}...")
        
        # Install dependencies if missing
        if not (frontend_dir / "node_modules").exists():
            print("Installing frontend dependencies (this may take a minute)...")
            subprocess.run([npm_cmd, "install"], cwd=frontend_dir, shell=True, check=True)
            
        frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=frontend_dir,
            shell=True
        )
        processes.append(frontend_process)

        print("\n++ System is running!")
        print("   - Backend: http://127.0.0.1:8000/docs")
        print("   - Frontend: http://localhost:8080")
        print("\nPress Ctrl+C to stop all services.")
        
        # Keep execution alive
        backend_process.wait()
        frontend_process.wait()

    except KeyboardInterrupt:
        print("\n-- Stopping services...")
    except Exception as e:
        print(f"\n!! Error: {e}")
    finally:
        # Kill child processes
        for p in processes:
            try:
                if os.name == 'nt':
                    # Force kill on windows including tree
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
                else:
                    p.terminate()
            except:
                pass
        sys.exit(0)

if __name__ == "__main__":
    main()
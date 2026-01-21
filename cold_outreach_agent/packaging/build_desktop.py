"""
Build Script for Cold Outreach Agent Desktop Application

This script handles the complete build process:
1. Install dependencies if needed
2. Build frontend (if applicable)
3. Package backend with PyInstaller
4. Create distributable archive

Usage:
    python packaging/build_desktop.py
    python packaging/build_desktop.py --onefile  # Single executable
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result."""
    print(f"  Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0 and check:
        print(f"  ERROR: {result.stderr}")
        return False
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n[1/4] Checking dependencies...")
    
    required = ['pyinstaller', 'uvicorn', 'fastapi', 'aiohttp', 'aiosqlite', 'playwright']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"  Missing packages: {', '.join(missing)}")
        print("  Installing missing packages...")
        run_command([sys.executable, '-m', 'pip', 'install'] + missing)
    else:
        print("  All dependencies installed.")
    
    return True


def build_frontend(project_root):
    """Build the frontend if it exists."""
    print("\n[2/4] Building frontend...")
    
    frontend_dir = project_root.parent / 'Frontend'
    
    if not frontend_dir.exists():
        print("  Frontend directory not found, skipping...")
        return True
    
    # Check if node_modules exists
    if not (frontend_dir / 'node_modules').exists():
        print("  Installing frontend dependencies...")
        if not run_command(['npm', 'install'], cwd=frontend_dir, check=False):
            print("  Warning: npm install failed, frontend may not be available")
            return True
    
    # Build frontend
    print("  Building frontend for production...")
    if not run_command(['npm', 'run', 'build'], cwd=frontend_dir, check=False):
        print("  Warning: Frontend build failed, frontend may not be available")
        return True
    
    # Copy dist to static folder
    dist_dir = frontend_dir / 'dist'
    static_dir = project_root / 'static'
    
    if dist_dir.exists():
        print("  Copying frontend build to static folder...")
        if static_dir.exists():
            shutil.rmtree(static_dir)
        shutil.copytree(dist_dir, static_dir)
        print("  Frontend build complete.")
    
    return True


def build_backend(project_root, onefile=False):
    """Build the backend with PyInstaller."""
    print("\n[3/4] Building backend with PyInstaller...")
    
    # Change to project directory
    os.chdir(project_root)
    
    # Build command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        '--name', 'ColdOutreachAgent',
        '--add-data', 'templates:templates',
    ]
    
    # Add static folder if it exists
    if (project_root / 'static').exists():
        cmd.extend(['--add-data', 'static:static'])
    
    # Add hidden imports
    hidden_imports = [
        'fastapi', 'uvicorn', 'uvicorn.logging', 'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto', 'uvicorn.lifespan.on',
        'starlette', 'starlette.routing', 'starlette.middleware.cors',
        'aiosqlite', 'aiohttp', 'bs4', 'pydantic',
        'api.server', 'config.settings', 'services.db_service',
        'services.agent_runner', 'services.agent_state_manager',
        'modules.hunter', 'modules.website_analyzer', 'modules.messenger',
    ]
    
    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])
    
    if onefile:
        cmd.append('--onefile')
    
    cmd.append('desktop_launcher.py')
    
    print(f"  Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  ERROR: PyInstaller failed")
        print(result.stderr)
        return False
    
    print("  Backend build complete.")
    return True


def create_distribution(project_root, onefile=False):
    """Create the final distribution package."""
    print("\n[4/4] Creating distribution package...")
    
    dist_dir = project_root / 'dist'
    
    if onefile:
        exe_path = dist_dir / 'ColdOutreachAgent.exe'
        if exe_path.exists():
            print(f"  Executable created: {exe_path}")
            print(f"  Size: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        app_dir = dist_dir / 'ColdOutreachAgent'
        if app_dir.exists():
            # Create a data directory for runtime files
            data_dir = app_dir / 'data'
            data_dir.mkdir(exist_ok=True)
            
            print(f"  Application created: {app_dir}")
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in app_dir.rglob('*') if f.is_file())
            print(f"  Total size: {total_size / 1024 / 1024:.2f} MB")
    
    print("\n" + "=" * 50)
    print("  BUILD COMPLETE!")
    print("=" * 50)
    print(f"\nOutput directory: {dist_dir}")
    print(f"\nTo run the application:")
    if onefile:
        print(f"  .\\dist\\ColdOutreachAgent.exe")
    else:
        print(f"  .\\dist\\ColdOutreachAgent\\ColdOutreachAgent.exe")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Build Cold Outreach Agent Desktop App')
    parser.add_argument('--onefile', action='store_true', help='Create single executable file')
    parser.add_argument('--skip-frontend', action='store_true', help='Skip frontend build')
    args = parser.parse_args()
    
    project_root = get_project_root()
    
    print("=" * 50)
    print("  Cold Outreach Agent - Desktop Build")
    print("=" * 50)
    print(f"Project root: {project_root}")
    print(f"Build type: {'Single file' if args.onefile else 'Directory'}")
    
    # Step 1: Check dependencies
    if not check_dependencies():
        return 1
    
    # Step 2: Build frontend
    if not args.skip_frontend:
        if not build_frontend(project_root):
            return 1
    else:
        print("\n[2/4] Skipping frontend build...")
    
    # Step 3: Build backend
    if not build_backend(project_root, args.onefile):
        return 1
    
    # Step 4: Create distribution
    if not create_distribution(project_root, args.onefile):
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

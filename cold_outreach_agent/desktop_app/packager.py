"""
Desktop application packager using PyInstaller.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from ..core.exceptions import DesktopPackagingError

class DesktopPackager:
    """Handles packaging of the application for desktop distribution."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        
    def validate_build_environment(self) -> Dict[str, Any]:
        """Validate that all requirements for building are met."""
        errors = []
        warnings = []
        
        # Check PyInstaller
        try:
            subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            errors.append("PyInstaller is not installed or not in PATH")
            
        # Check frontend build
        frontend_dist = self.project_root / "Frontend" / "dist"
        if not frontend_dist.exists():
            warnings.append("Frontend build directory not found. Building without frontend assets?")
            
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
        
    def package_application(
        self,
        app_name: str = "ColdOutreachAgent",
        version: str = "1.0.0",
        include_frontend: bool = True,
        create_installer: bool = True
    ) -> Dict[str, str]:
        """
        Package the application using PyInstaller.
        """
        
        # Entry point
        entry_point = self.project_root / "cold_outreach_agent" / "production_main.py"
        if not entry_point.exists():
            raise DesktopPackagingError(f"Entry point not found: {entry_point}")
            
        # PyInstaller arguments
        args = [
            "pyinstaller",
            "--name", app_name,
            "--onefile", # Create single executable
            "--clean",
            "--noconfirm",
            
            # Hidden imports (often needed for FastAPI/Uvicorn/SQLAlchemy)
            "--hidden-import", "uvicorn.logging",
            "--hidden-import", "uvicorn.loops",
            "--hidden-import", "uvicorn.loops.auto",
            "--hidden-import", "uvicorn.protocols",
            "--hidden-import", "uvicorn.protocols.http",
            "--hidden-import", "uvicorn.protocols.http.auto",
            "--hidden-import", "uvicorn.lifespan",
            "--hidden-import", "uvicorn.lifespan.on",
            "--hidden-import", "engineio.async_drivers.aiohttp",
            "--hidden-import", "aiosqlite",
            
            # Data files
            # "--add-data", f"{self.project_root}/cold_outreach_agent/templates;templates", # Example
            
            # Icon (if exists)
            # "--icon", "path/to/icon.ico",
            
            str(entry_point)
        ]
        
        try:
            subprocess.run(args, check=True, cwd=self.project_root)
        except subprocess.CalledProcessError as e:
            raise DesktopPackagingError(f"PyInstaller failed: {str(e)}")
            
        package_path = self.dist_dir / f"{app_name}.exe"
        
        return {
            "package_path": str(package_path),
            "installer_path": None # Not implemented yet
        }

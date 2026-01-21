"""Desktop application packager using PyInstaller."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..config.production_settings import ProductionSettings
from ..core.exceptions import DesktopPackagingError


class DesktopPackager:
    """Handles desktop application packaging with PyInstaller."""
    
    def __init__(self, settings: Optional[ProductionSettings] = None):
        self.settings = settings or ProductionSettings()
        self.project_root = Path(__file__).parent.parent.parent
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        
    def package_application(
        self,
        app_name: str = "ColdOutreachAgent",
        version: str = "1.0.0",
        include_frontend: bool = True,
        create_installer: bool = False
    ) -> Dict[str, Any]:
        """Package the application as a desktop executable."""
        
        try:
            print(f"Starting desktop packaging for {app_name} v{version}")
            
            # Clean previous builds
            self._clean_build_directories()
            
            # Prepare build environment
            build_info = self._prepare_build_environment()
            
            # Create PyInstaller spec
            spec_file = self._create_pyinstaller_spec(
                app_name=app_name,
                version=version,
                include_frontend=include_frontend
            )
            
            # Run PyInstaller
            executable_path = self._run_pyinstaller(spec_file)
            
            # Post-process the build
            final_package = self._post_process_build(
                executable_path=executable_path,
                app_name=app_name,
                version=version,
                include_frontend=include_frontend
            )
            
            # Create installer if requested
            installer_path = None
            if create_installer:
                installer_path = self._create_installer(final_package, app_name, version)
            
            result = {
                "success": True,
                "app_name": app_name,
                "version": version,
                "executable_path": str(executable_path),
                "package_path": str(final_package),
                "installer_path": str(installer_path) if installer_path else None,
                "build_info": build_info
            }
            
            print(f"✓ Desktop packaging completed successfully")
            print(f"  Package: {final_package}")
            if installer_path:
                print(f"  Installer: {installer_path}")
            
            return result
            
        except Exception as e:
            raise DesktopPackagingError(f"Desktop packaging failed: {str(e)}")
    
    def _clean_build_directories(self):
        """Clean previous build artifacts."""
        for directory in [self.build_dir, self.dist_dir]:
            if directory.exists():
                shutil.rmtree(directory)
                print(f"Cleaned {directory}")
    
    def _prepare_build_environment(self) -> Dict[str, Any]:
        """Prepare the build environment and gather info."""
        
        # Check dependencies
        required_packages = [
            "pyinstaller",
            "playwright",
            "fastapi",
            "uvicorn",
            "aiosqlite",
            "pydantic",
            "jinja2"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            raise DesktopPackagingError(
                f"Missing required packages: {', '.join(missing_packages)}"
            )
        
        # Install Playwright browsers if needed
        try:
            subprocess.run([
                sys.executable, "-m", "playwright", "install", "chromium"
            ], check=True, capture_output=True)
            print("✓ Playwright browsers installed")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to install Playwright browsers: {e}")
        
        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "required_packages": required_packages,
            "missing_packages": missing_packages
        }
    
    def _create_pyinstaller_spec(
        self,
        app_name: str,
        version: str,
        include_frontend: bool
    ) -> Path:
        """Create PyInstaller spec file."""
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

block_cipher = None

# Data files to include
datas = [
    ('cold_outreach_agent/infrastructure/email/templates', 'cold_outreach_agent/infrastructure/email/templates'),
    ('cold_outreach_agent/.env.example', 'cold_outreach_agent'),
]

# Include frontend if requested
{f"datas.append(('Frontend/dist', 'frontend'))" if include_frontend else "# Frontend not included"}

# Hidden imports for dynamic loading
hiddenimports = [
    'cold_outreach_agent',
    'cold_outreach_agent.api.production_server',
    'cold_outreach_agent.infrastructure.database.service',
    'cold_outreach_agent.infrastructure.email.service',
    'cold_outreach_agent.infrastructure.scraping.google_maps_scraper',
    'cold_outreach_agent.core.state_machines.lead_state_machine',
    'cold_outreach_agent.core.state_machines.email_state_machine',
    'playwright',
    'playwright._impl',
    'playwright.async_api',
    'aiosqlite',
    'sqlite3',
    'uvicorn',
    'uvicorn.main',
    'fastapi',
    'jinja2',
    'email.mime.text',
    'email.mime.multipart',
    'smtplib',
    'ssl'
]

# Exclude unnecessary modules
excludes = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PIL',
    'cv2'
]

a = Analysis(
    ['cold_outreach_agent/desktop-app/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{app_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if Path('assets/icon.ico').exists() else None,
    version_file='version_info.txt' if Path('version_info.txt').exists() else None,
)
'''
        
        spec_file = self.project_root / f"{app_name}.spec"
        spec_file.write_text(spec_content)
        print(f"Created PyInstaller spec: {spec_file}")
        
        return spec_file
    
    def _run_pyinstaller(self, spec_file: Path) -> Path:
        """Run PyInstaller to create the executable."""
        
        print("Running PyInstaller...")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_file)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True
            )
            
            print("✓ PyInstaller completed successfully")
            
            # Find the executable
            app_name = spec_file.stem
            if sys.platform == "win32":
                executable_path = self.dist_dir / f"{app_name}.exe"
            else:
                executable_path = self.dist_dir / app_name
            
            if not executable_path.exists():
                raise DesktopPackagingError(f"Executable not found at {executable_path}")
            
            return executable_path
            
        except subprocess.CalledProcessError as e:
            error_msg = f"PyInstaller failed: {e.stderr}"
            print(f"✗ {error_msg}")
            raise DesktopPackagingError(error_msg)
    
    def _post_process_build(
        self,
        executable_path: Path,
        app_name: str,
        version: str,
        include_frontend: bool
    ) -> Path:
        """Post-process the build to create final package."""
        
        print("Post-processing build...")
        
        # Create package directory
        package_name = f"{app_name}-v{version}-{sys.platform}"
        package_dir = self.dist_dir / package_name
        package_dir.mkdir(exist_ok=True)
        
        # Copy executable
        if executable_path.is_file():
            shutil.copy2(executable_path, package_dir)
        else:
            shutil.copytree(executable_path, package_dir / executable_path.name)
        
        # Create configuration files
        self._create_config_files(package_dir)
        
        # Create documentation
        self._create_documentation(package_dir, app_name, version)
        
        # Create launch scripts
        self._create_launch_scripts(package_dir, app_name)
        
        print(f"✓ Package created: {package_dir}")
        return package_dir
    
    def _create_config_files(self, package_dir: Path):
        """Create configuration files for the package."""
        
        # Copy .env.example
        env_example = self.project_root / "cold_outreach_agent" / ".env.example"
        if env_example.exists():
            shutil.copy2(env_example, package_dir / ".env.example")
        
        # Create default .env file
        default_env = package_dir / ".env"
        default_env.write_text(f"""# Cold Outreach Agent Configuration
# Copy this file to .env and configure your settings

# Email Configuration (REQUIRED)
SENDER_NAME=Your Name
SENDER_EMAIL=your@email.com
SMTP_USERNAME=your@email.com
SMTP_PASSWORD=your_app_password

# Rate Limits
MAX_EMAILS_PER_DAY=20
MAX_EMAILS_PER_HOUR=5

# Environment
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_PATH=data/cold_outreach.db

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
""")
        
        print("✓ Configuration files created")
    
    def _create_documentation(self, package_dir: Path, app_name: str, version: str):
        """Create user documentation."""
        
        readme_content = f"""# {app_name} v{version}

## Quick Start

1. **Configure Email Settings**
   - Edit the `.env` file with your email credentials
   - Use Gmail App Passwords for Gmail accounts

2. **Run the Application**
   - Windows: Double-click `{app_name}.exe` or run `start.bat`
   - Mac/Linux: Run `./{app_name}` or `./start.sh`

3. **Access Web Interface**
   - The application will automatically open your browser
   - If not, go to http://localhost:8000

## Configuration

Edit the `.env` file to configure:

- **Email Settings**: SMTP credentials for sending emails
- **Rate Limits**: Daily and hourly email limits
- **Logging**: Log level and directory

## Troubleshooting

### Application Won't Start
- Check that all required fields in `.env` are filled
- Ensure no other application is using port 8000
- Check logs in the `logs/` directory

### Email Sending Issues
- Verify SMTP credentials are correct
- For Gmail, use App Passwords instead of regular passwords
- Check rate limits haven't been exceeded

### Browser Doesn't Open
- Manually navigate to http://localhost:8000
- Check firewall settings

## Support

For issues and support:
1. Check the logs in the `logs/` directory
2. Verify configuration in `.env` file
3. Ensure all required dependencies are met

## Files

- `{app_name}.exe` - Main application executable
- `.env` - Configuration file (edit this)
- `.env.example` - Configuration template
- `start.bat` / `start.sh` - Launch scripts
- `logs/` - Application logs (created on first run)
- `data/` - Database files (created on first run)
"""
        
        readme_file = package_dir / "README.txt"
        readme_file.write_text(readme_content)
        
        print("✓ Documentation created")
    
    def _create_launch_scripts(self, package_dir: Path, app_name: str):
        """Create platform-specific launch scripts."""
        
        if sys.platform == "win32":
            # Windows batch file
            bat_content = f"""@echo off
echo Starting {app_name}...
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ERROR: Configuration file .env not found!
    echo Please copy .env.example to .env and configure your settings.
    echo.
    pause
    exit /b 1
)

REM Start the application
"{app_name}.exe"

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Application exited with an error. Check logs for details.
    pause
)
"""
            
            bat_file = package_dir / "start.bat"
            bat_file.write_text(bat_content)
            
        else:
            # Unix shell script
            sh_content = f"""#!/bin/bash

echo "Starting {app_name}..."
echo

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "ERROR: Configuration file .env not found!"
    echo "Please copy .env.example to .env and configure your settings."
    echo
    read -p "Press Enter to continue..."
    exit 1
fi

# Make executable if needed
chmod +x "./{app_name}"

# Start the application
"./{app_name}"

# Check exit code
if [ $? -ne 0 ]; then
    echo
    echo "Application exited with an error. Check logs for details."
    read -p "Press Enter to continue..."
fi
"""
            
            sh_file = package_dir / "start.sh"
            sh_file.write_text(sh_content)
            sh_file.chmod(0o755)
        
        print("✓ Launch scripts created")
    
    def _create_installer(self, package_dir: Path, app_name: str, version: str) -> Optional[Path]:
        """Create an installer for the application."""
        
        try:
            if sys.platform == "win32":
                return self._create_windows_installer(package_dir, app_name, version)
            else:
                return self._create_unix_installer(package_dir, app_name, version)
        except Exception as e:
            print(f"Warning: Failed to create installer: {e}")
            return None
    
    def _create_windows_installer(self, package_dir: Path, app_name: str, version: str) -> Path:
        """Create Windows installer using NSIS or Inno Setup."""
        
        # This would require NSIS or Inno Setup to be installed
        # For now, create a simple ZIP file
        import zipfile
        
        zip_path = self.dist_dir / f"{app_name}-v{version}-windows-installer.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in package_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(package_dir)
                    zipf.write(file_path, arcname)
        
        print(f"✓ Windows installer created: {zip_path}")
        return zip_path
    
    def _create_unix_installer(self, package_dir: Path, app_name: str, version: str) -> Path:
        """Create Unix installer (tar.gz)."""
        
        import tarfile
        
        tar_path = self.dist_dir / f"{app_name}-v{version}-{sys.platform}.tar.gz"
        
        with tarfile.open(tar_path, 'w:gz') as tar:
            tar.add(package_dir, arcname=package_dir.name)
        
        print(f"✓ Unix installer created: {tar_path}")
        return tar_path
    
    def get_build_requirements(self) -> List[str]:
        """Get list of build requirements."""
        return [
            "pyinstaller>=5.0",
            "playwright>=1.20.0",
            "fastapi>=0.68.0",
            "uvicorn>=0.15.0",
            "aiosqlite>=0.17.0",
            "pydantic>=1.8.0",
            "jinja2>=3.0.0",
            "python-dotenv>=0.19.0",
            "aiohttp>=3.8.0",
            "rich>=10.0.0",
            "click>=8.0.0"
        ]
    
    def validate_build_environment(self) -> Dict[str, Any]:
        """Validate the build environment."""
        
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # Check Python version
        if sys.version_info < (3, 8):
            validation["errors"].append("Python 3.8+ required")
            validation["valid"] = False
        
        # Check required packages
        requirements = self.get_build_requirements()
        missing_packages = []
        
        for req in requirements:
            package_name = req.split(">=")[0].split("==")[0]
            try:
                __import__(package_name.replace("-", "_"))
            except ImportError:
                missing_packages.append(req)
        
        if missing_packages:
            validation["errors"].extend([f"Missing package: {pkg}" for pkg in missing_packages])
            validation["valid"] = False
        
        # Check disk space (rough estimate)
        try:
            import shutil
            free_space = shutil.disk_usage(self.project_root).free
            required_space = 500 * 1024 * 1024  # 500MB
            
            if free_space < required_space:
                validation["warnings"].append(f"Low disk space: {free_space // (1024*1024)}MB available")
        except Exception:
            pass
        
        validation["info"] = {
            "python_version": sys.version,
            "platform": sys.platform,
            "project_root": str(self.project_root),
            "dist_dir": str(self.dist_dir)
        }
        
        return validation
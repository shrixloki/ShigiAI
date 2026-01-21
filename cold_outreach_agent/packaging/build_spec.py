# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Cold Outreach Agent Desktop Application

Build with:
    cd cold_outreach_agent
    pyinstaller --clean packaging/build_spec.py

Or for a single file:
    pyinstaller --onefile --clean packaging/build_spec.py
"""

import os
from pathlib import Path

# Get the project root directory
project_root = Path(SPECPATH).parent

# Analysis - collect all needed modules
a = Analysis(
    [str(project_root / 'desktop_launcher.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Include templates directory
        (str(project_root / 'templates'), 'templates'),
    ],
    hiddenimports=[
        # FastAPI and dependencies
        'fastapi',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.staticfiles',
        'pydantic',
        
        # Database
        'aiosqlite',
        'sqlite3',
        
        # HTTP clients
        'aiohttp',
        'httpx',
        
        # HTML parsing
        'bs4',
        'lxml',
        
        # Playwright (for Google Maps scraping)
        'playwright',
        'playwright.async_api',
        
        # Email
        'smtplib',
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        
        # Our modules
        'api.server',
        'config.settings',
        'services.db_service',
        'services.email_service',
        'services.email_service_simple',
        'services.agent_runner',
        'services.agent_state_manager',
        'services.lead_state_service',
        'services.location_service',
        'modules.hunter',
        'modules.website_analyzer',
        'modules.messenger',
        'modules.followup',
        'modules.reply_detector',
        'modules.logger',
        'core.state_machines.lead_state_machine',
        'core.models.lead',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test modules
        'pytest',
        'unittest',
        '_pytest',
        # Exclude development tools
        'IPython',
        'jupyter',
        'notebook',
        # Exclude unnecessary GUI toolkits
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# PYZ - compress Python modules
pyz = PYZ(a.pure, a.zipped_data)

# EXE - create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ColdOutreachAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False for no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: 'assets/icon.ico'
)

# COLLECT - gather all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ColdOutreachAgent',
)

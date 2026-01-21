@echo off
echo Starting Cold Outreach Agent Backend Only...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python.
    pause
    exit /b 1
)

echo Starting backend server...
python start-backend-only.py

pause
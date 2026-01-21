@echo off
echo 🐍 Starting Cold Outreach Agent (Simple Python)...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python.
    pause
    exit /b 1
)

echo ✅ Python found
echo.

echo 🚀 Starting Cold Outreach Agent...
cd cold_outreach_agent
python run_simple.py

pause
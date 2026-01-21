@echo off
echo Starting Cold Outreach Agent System...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python.
    pause
    exit /b 1
)

REM Check if npm is available
npm --version >nul 2>&1
if errorlevel 1 (
    echo Error: npm not found. Please install Node.js.
    pause
    exit /b 1
)

echo Starting system launcher...
python start.py

pause
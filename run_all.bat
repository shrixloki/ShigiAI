@echo off
setlocal
echo ===================================================
echo   Starting Cold Outreach Agent (All Services)
echo ===================================================

cd /d "%~dp0"

:: 1. Start Backend Server
echo.
echo [1/2] Starting Backend Server...
echo --------------------------------
start "Cold Outreach Backend" cmd /k "python run_production.py server"

:: 2. Start Frontend Application
echo.
echo [2/2] Starting Frontend Application...
echo --------------------------------
cd Frontend

:: Check if node_modules exists, install if missing
if not exist node_modules (
    echo Node modules not found. Installing dependencies...
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
)

:: Run the dev server
start "Cold Outreach Frontend" cmd /k "npm run dev"

echo.
echo ===================================================
echo   Services Started!
echo ===================================================
echo.
echo   - Backend API: http://127.0.0.1:8000/docs
echo   - Frontend UI: http://localhost:5173
echo.
echo   (Close the popup windows to stop the services)
echo ===================================================
pause

@echo off
setlocal enabledelayedexpansion

echo 🚀 Cold Outreach Agent - Complete System Launcher
echo ============================================================
echo Starting all services without Docker...
echo.

REM Check Python
echo 🐍 Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
echo ✅ Python found

REM Check Node.js
echo 📦 Checking Node.js...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Please install from https://nodejs.org/
    pause
    exit /b 1
)
echo ✅ Node.js found

npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ npm not found
    pause
    exit /b 1
)
echo ✅ npm found

REM Check Python dependencies
echo 🔍 Checking Python dependencies...
cd cold_outreach_agent
python -c "import fastapi, uvicorn, playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Missing Python dependencies
    echo 💡 Run: pip install -r requirements.txt
    pause
    exit /b 1
)
echo ✅ Python dependencies found
cd ..

REM Install Dashboard dependencies if needed
if exist "cold_outreach_agent\dashboard\package.json" (
    echo 📦 Checking Dashboard dependencies...
    if not exist "cold_outreach_agent\dashboard\node_modules" (
        echo Installing Dashboard dependencies...
        cd cold_outreach_agent\dashboard
        call npm install
        if %errorlevel% neq 0 (
            echo ❌ Failed to install Dashboard dependencies
            cd ..\..
            pause
            exit /b 1
        )
        cd ..\..
        echo ✅ Dashboard dependencies installed
    ) else (
        echo ✅ Dashboard dependencies already installed
    )
)

REM Install Frontend dependencies if needed
if exist "Frontend\package.json" (
    echo 📦 Checking Frontend dependencies...
    if not exist "Frontend\node_modules" (
        echo Installing Frontend dependencies...
        cd Frontend
        call npm install
        if %errorlevel% neq 0 (
            echo ❌ Failed to install Frontend dependencies
            cd ..
            pause
            exit /b 1
        )
        cd ..
        echo ✅ Frontend dependencies installed
    ) else (
        echo ✅ Frontend dependencies already installed
    )
)

echo.
echo 🚀 Starting all services...
echo ----------------------------------------

REM Start Backend API
echo 🔧 Starting Backend API Server...
cd cold_outreach_agent
start "Backend API" cmd /c "python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload"
cd ..
echo ✅ Backend API starting on http://localhost:8000

REM Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

REM Start Dashboard if it exists
if exist "cold_outreach_agent\dashboard\package.json" (
    echo 📊 Starting Dashboard...
    cd cold_outreach_agent\dashboard
    start "Dashboard" cmd /c "npm run dev"
    cd ..\..
    echo ✅ Dashboard starting on http://localhost:5173
)

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start Frontend if it exists
if exist "Frontend\package.json" (
    echo 🌐 Starting Frontend...
    cd Frontend
    start "Frontend" cmd /c "npm run dev"
    cd ..
    echo ✅ Frontend starting (check console for port)
)

echo.
echo ⏳ Waiting for services to initialize...
timeout /t 5 /nobreak >nul

echo.
echo 🎉 Cold Outreach Agent System is running!
echo ============================================================
echo 📊 Services:
echo    🔧 Backend API:     http://localhost:8000
echo    📖 API Docs:       http://localhost:8000/docs

if exist "cold_outreach_agent\dashboard\package.json" (
    echo    📊 Dashboard:      http://localhost:5173
)

if exist "Frontend\package.json" (
    echo    🌐 Frontend:       Check console output for port
)

echo.
echo 💡 Tips:
echo    • Each service runs in its own window
echo    • Close individual windows to stop specific services
echo    • Check each console window for detailed logs
echo    • Backend API docs available at /docs endpoint
echo ============================================================

REM Open browser to API docs
timeout /t 3 /nobreak >nul
start http://localhost:8000/docs

REM Open dashboard if it exists
if exist "cold_outreach_agent\dashboard\package.json" (
    timeout /t 2 /nobreak >nul
    start http://localhost:5173
)

echo.
echo Press any key to exit this launcher window...
echo (Services will continue running in their own windows)
pause >nul
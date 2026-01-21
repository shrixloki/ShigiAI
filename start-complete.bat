@echo off
echo 🚀 Starting Complete Cold Outreach Agent System...

REM Check if Node.js is available for frontend
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Trying Docker-only approach...
    goto docker_only
)

REM Check if Python is available for backend
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found. Trying Docker-only approach...
    goto docker_only
)

echo ✅ Node.js and Python found - using hybrid approach

REM Build and start frontend
echo 🔨 Building frontend...
cd cold_outreach_agent\dashboard
call npm install
if %errorlevel% neq 0 (
    echo ❌ Frontend npm install failed
    goto docker_only
)

call npm run build
if %errorlevel% neq 0 (
    echo ❌ Frontend build failed
    goto docker_only
)

echo ✅ Frontend built successfully

REM Start frontend dev server in background
echo 🌐 Starting frontend dev server...
start "Frontend Server" cmd /c "npm run dev"

cd ..\..

REM Start backend with Python
echo 🐍 Starting backend with Python...
cd cold_outreach_agent
python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

goto end

:docker_only
echo 🐳 Using Docker-only approach...
cd cold_outreach_agent

REM Check if Docker is available
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker not found. Please install Docker Desktop or Node.js/Python.
    pause
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

echo ✅ Docker found and running
echo 🐳 Building and starting with Docker...
docker-compose up --build

:end
echo 🛑 Cold Outreach Agent stopped.
pause
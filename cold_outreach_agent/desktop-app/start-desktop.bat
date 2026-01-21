@echo off
echo 🚀 Starting Cold Outreach Agent Desktop App...

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Please install Node.js first.
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)

REM Check if dependencies are installed
if not exist node_modules (
    echo 📦 Installing dependencies...
    call npm install
    if %errorlevel% neq 0 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
)

echo ✅ Starting desktop application...
call npm start
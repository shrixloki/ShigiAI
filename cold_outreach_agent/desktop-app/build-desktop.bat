@echo off
echo 🔨 Building Cold Outreach Agent Desktop App...

REM Check if Node.js is available
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js not found. Please install Node.js first.
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)

echo ✅ Node.js found

REM Install dependencies
echo 📦 Installing dependencies...
call npm install

if %errorlevel% neq 0 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies installed

REM Build the desktop app
echo 🏗️ Building desktop application...
call npm run build-win

if %errorlevel% neq 0 (
    echo ❌ Build failed
    pause
    exit /b 1
)

echo ✅ Desktop app built successfully!
echo 📁 Check the 'dist' folder for the installer
echo.
echo 🚀 You can also run the app in development mode with: npm start
pause
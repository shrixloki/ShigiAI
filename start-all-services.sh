#!/bin/bash

# Cold Outreach Agent - Complete System Launcher
# Non-Docker version for Linux/Mac

set -e

echo "🚀 Cold Outreach Agent - Complete System Launcher"
echo "============================================================"
echo "Starting all services without Docker..."
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_info() {
    echo -e "${BLUE}💡${NC} $1"
}

# Check Python
echo "🐍 Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    print_status "Python3 found"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    print_status "Python found"
else
    print_error "Python not found. Please install Python 3.8+"
    exit 1
fi

# Check Node.js
echo "📦 Checking Node.js..."
if ! command -v node &> /dev/null; then
    print_error "Node.js not found. Please install from https://nodejs.org/"
    exit 1
fi
print_status "Node.js found: $(node --version)"

if ! command -v npm &> /dev/null; then
    print_error "npm not found"
    exit 1
fi
print_status "npm found: $(npm --version)"

# Check Python dependencies
echo "🔍 Checking Python dependencies..."
cd cold_outreach_agent
if ! $PYTHON_CMD -c "import fastapi, uvicorn, playwright" &> /dev/null; then
    print_error "Missing Python dependencies"
    print_info "Run: pip install -r requirements.txt"
    exit 1
fi
print_status "Python dependencies found"
cd ..

# Install Dashboard dependencies if needed
if [ -f "cold_outreach_agent/dashboard/package.json" ]; then
    echo "📦 Checking Dashboard dependencies..."
    if [ ! -d "cold_outreach_agent/dashboard/node_modules" ]; then
        echo "Installing Dashboard dependencies..."
        cd cold_outreach_agent/dashboard
        npm install
        if [ $? -ne 0 ]; then
            print_error "Failed to install Dashboard dependencies"
            exit 1
        fi
        cd ../..
        print_status "Dashboard dependencies installed"
    else
        print_status "Dashboard dependencies already installed"
    fi
fi

# Install Frontend dependencies if needed
if [ -f "Frontend/package.json" ]; then
    echo "📦 Checking Frontend dependencies..."
    if [ ! -d "Frontend/node_modules" ]; then
        echo "Installing Frontend dependencies..."
        cd Frontend
        npm install
        if [ $? -ne 0 ]; then
            print_error "Failed to install Frontend dependencies"
            exit 1
        fi
        cd ..
        print_status "Frontend dependencies installed"
    else
        print_status "Frontend dependencies already installed"
    fi
fi

echo
echo "🚀 Starting all services..."
echo "----------------------------------------"

# Function to cleanup processes on exit
cleanup() {
    echo
    echo "🛑 Stopping all services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$DASHBOARD_PID" ]; then
        kill $DASHBOARD_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "✅ All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start Backend API
echo "🔧 Starting Backend API Server..."
cd cold_outreach_agent
$PYTHON_CMD -m uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..
print_status "Backend API starting on http://localhost:8000"

# Wait for backend to initialize
sleep 3

# Start Dashboard if it exists
if [ -f "cold_outreach_agent/dashboard/package.json" ]; then
    echo "📊 Starting Dashboard..."
    cd cold_outreach_agent/dashboard
    npm run dev &
    DASHBOARD_PID=$!
    cd ../..
    print_status "Dashboard starting on http://localhost:5173"
fi

# Wait a moment
sleep 2

# Start Frontend if it exists
if [ -f "Frontend/package.json" ]; then
    echo "🌐 Starting Frontend..."
    cd Frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    print_status "Frontend starting (check console for port)"
fi

echo
echo "⏳ Waiting for services to initialize..."
sleep 5

# Check if backend is responding
if command -v curl &> /dev/null; then
    if curl -s http://localhost:8000/api/agent/state &> /dev/null; then
        print_status "Backend API is responding"
    else
        print_warning "Backend API not responding yet (this may be normal)"
    fi
fi

echo
echo "🎉 Cold Outreach Agent System is running!"
echo "============================================================"
echo "📊 Services:"
echo "   🔧 Backend API:     http://localhost:8000"
echo "   📖 API Docs:       http://localhost:8000/docs"

if [ -f "cold_outreach_agent/dashboard/package.json" ]; then
    echo "   📊 Dashboard:      http://localhost:5173"
fi

if [ -f "Frontend/package.json" ]; then
    echo "   🌐 Frontend:       Check console output for port"
fi

echo
echo "💡 Tips:"
echo "   • Press Ctrl+C to stop all services"
echo "   • Check console output for detailed logs"
echo "   • Backend API docs available at /docs endpoint"
echo "============================================================"

# Open browser if available
if command -v xdg-open &> /dev/null; then
    sleep 3
    xdg-open http://localhost:8000/docs &> /dev/null &
    if [ -f "cold_outreach_agent/dashboard/package.json" ]; then
        sleep 2
        xdg-open http://localhost:5173 &> /dev/null &
    fi
elif command -v open &> /dev/null; then
    sleep 3
    open http://localhost:8000/docs &> /dev/null &
    if [ -f "cold_outreach_agent/dashboard/package.json" ]; then
        sleep 2
        open http://localhost:5173 &> /dev/null &
    fi
fi

# Keep running until interrupted
echo
echo "Press Ctrl+C to stop all services..."
wait
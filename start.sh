#!/bin/bash

echo "Starting Cold Outreach Agent System..."
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found. Please install Python."
    exit 1
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "Error: npm not found. Please install Node.js."
    exit 1
fi

echo "Starting system launcher..."
cd cold_outreach_agent
python3 start.py
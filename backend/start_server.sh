#!/bin/bash
# Startup script for backend server with A* search integration

cd /Users/abdullah/Documents/AI/backend

# Activate virtual environment
source /Users/abdullah/Documents/AI/.venv/bin/activate

# Start server on all network interfaces for phone connectivity
echo "🚀 Starting backend server on 0.0.0.0:8000"
echo "📱 Your phone can connect via: http://192.168.100.49:8000"
echo "🔍 A* Search Algorithm: ENABLED by default"
echo ""

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

#!/bin/bash
# Urban Kettle - Full System Launcher
# Starts both the Backend Server and Frontend UI

echo "========================================"
echo "   Urban Kettle - System Startup"
echo "========================================"

# Navigate to script directory
cd "$(dirname "$0")"

# 1. Start Backend Server
echo "Stopping existing backend..."
pkill -f polling_server2.py

echo "Starting Backend Server (polling_server2.py)..."
nohup python3 polling_server2.py > backend.log 2>&1 &

# Wait for backend to initialize
sleep 2
if pgrep -f polling_server2.py > /dev/null; then
    echo "✅ Backend started successfully."
else
    echo "❌ Backend failed to start. Check backend.log"
    exit 1
fi

# 2. Start Frontend UI
echo "Stopping existing frontend..."
pkill -f main_app.py

echo "Starting Frontend UI (main_app.py)..."

# Environment variables for Kivy on Pi
export DISPLAY=:0
export KIVY_WINDOW=sdl2
export KIVY_GL_BACKEND=gl
export KIVY_MULTISAMPLES=0

nohup python3 main_app.py > frontend.log 2>&1 &

sleep 3
if pgrep -f main_app.py > /dev/null; then
    echo "✅ Frontend started successfully."
    echo "📱 UI should be visible on the main display."
else
    echo "❌ Frontend failed to start. Check frontend.log"
    cat frontend.log
    exit 1
fi

echo "========================================"
echo "   System Running"
echo "========================================"
echo "Logs available at:"
echo "  - Backend: $(pwd)/backend.log"
echo "  - Frontend: $(pwd)/frontend.log"

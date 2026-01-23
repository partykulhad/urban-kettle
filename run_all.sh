#!/bin/bash
# Urban Kettle - Full System Launcher
# Starts both the Backend Server and Frontend UI

echo "========================================"
echo "   Urban Kettle - System Startup"
echo "========================================"

# Navigate to script directory
cd "$(dirname "$0")"

# Cleanup function to stop all processes
cleanup() {
    echo ""
    echo "🛑 Stopping all Urban Kettle processes..."
    pkill -f main_app.py
    pkill -f polling_server2.py
    docker-compose down 2>/dev/null
    echo "✓ All processes stopped"
    exit 0
}

# Set trap to cleanup on script exit or Ctrl+C
trap cleanup EXIT INT TERM

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

python3 main_app.py > frontend.log 2>&1 &
FRONTEND_PID=$!

echo "✅ Frontend started successfully (PID: $FRONTEND_PID)."
echo "📱 UI should be visible on the main display."
echo ""
echo "========================================"
echo "   System Running"
echo "========================================"
echo "Logs available at:"
echo "  - Backend: $(pwd)/backend.log"
echo "  - Frontend: $(pwd)/frontend.log"
echo ""
echo "Press Ctrl+C to stop all services, or wait for UI to close..."
echo ""

# Wait for frontend process to exit
wait $FRONTEND_PID
echo ""
echo "👋 UI closed. Cleaning up..."

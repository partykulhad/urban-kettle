#!/bin/bash
# Urban Kettle - Full System Launcher (DEV MODE)

echo "========================================"
echo "   Urban Kettle - System Startup"
echo "========================================"

cd "$(dirname "$0")"

# Wait for display server to be ready
echo "Waiting for display server..."
for i in {1..30}; do
    if [ -n "$DISPLAY" ] && xset q &>/dev/null; then
        echo "✓ Display server ready (DISPLAY=$DISPLAY)"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️ Display server not detected after 30s, proceeding anyway..."
    fi
    sleep 1
done

sleep 5

cleanup() {
    echo ""
    echo "🛑 Stopping all Urban Kettle processes..."
    pkill -f main_app.py || true
    pkill -f polling_server2.py || true
    docker-compose down 2>/dev/null || true
    echo "✓ All processes stopped"
}

# Trap system stop (systemctl stop, reboot)
trap cleanup SIGTERM SIGINT

# ---------------- BACKEND ----------------
echo "Stopping existing backend..."
pkill -f polling_server2.py || true

echo "Starting Backend Server (polling_server2.py)..."
./venv/bin/python3 polling_server2.py > backend.log 2>&1 &
BACKEND_PID=$!

sleep 5
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "❌ Backend failed to start! Check backend.log"
    tail -n 50 backend.log
    cleanup
    exit 1
fi

echo "✅ Backend running (PID=$BACKEND_PID)"

# Wait a bit longer for backend to initialize
echo "Waiting for backend to initialize..."
sleep 3

# ---------------- FRONTEND ----------------
echo "Stopping existing frontend..."
pkill -f main_app.py || true
sleep 2

export DISPLAY=:0
export XAUTHORITY="$HOME/.Xauthority"
export KIVY_WINDOW=sdl2
export KIVY_GL_BACKEND=gl
export KIVY_MULTISAMPLES=0

echo "Starting Frontend UI (main_app.py)..."
./venv/bin/python3 main_app.py > frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 3
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo "❌ Frontend failed to start! Check frontend.log"
    tail -n 100 frontend.log
    cleanup
    exit 1
fi

echo "✅ Frontend running (PID=$FRONTEND_PID)"
echo "========================================"
echo "   System Running"
echo "========================================"

# 🔴 Keep the service alive by monitoring both processes
while true; do
    if ! ps -p $BACKEND_PID > /dev/null; then
        echo "❌ Backend process died unexpectedly!"
        #tail -n 50 backend.log
        break
    fi
    
    if ! ps -p $FRONTEND_PID > /dev/null; then
        echo "👋 Frontend process ended"
        break
    fi
    
    sleep 2
done

echo ""
echo "👋 UI closed by user. Shutting down everything..."
cleanup
exit 0

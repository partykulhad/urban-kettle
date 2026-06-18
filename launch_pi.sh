#!/bin/bash
# Urban Kettle — Production Launcher
# Called by systemd (urban-kettle.service) on every boot.
# Do NOT run run_all.sh for production — use this file only.

set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"

echo "========================================"
echo "   Urban Kettle — Starting"
echo "   Dir: $APP_DIR"
echo "========================================"

# ── Wait for X display ────────────────────────────────────────────────────────
echo "Waiting for display server..."
for i in $(seq 1 60); do
    if xset -display :0 q &>/dev/null; then
        echo "✓ Display ready (${i}s)"
        break
    fi
    [ "$i" -eq 60 ] && echo "⚠️  Display not found after 60s — proceeding anyway"
    sleep 1
done

# ── Environment ───────────────────────────────────────────────────────────────
export DISPLAY=:0
export XAUTHORITY="$HOME/.Xauthority"
export KIVY_WINDOW=sdl2
export KIVY_GL_BACKEND=gl
export KIVY_MULTISAMPLES=0

# ── Kill any stale instances ──────────────────────────────────────────────────
pkill -f polling_server2.py 2>/dev/null || true
pkill -f main_app.py        2>/dev/null || true
sleep 1

# ── Ensure pcscd is running (required for ACR122U RFID reader via pyscard) ───
echo "Checking pcscd (RFID smartcard daemon)..."
if systemctl is-active --quiet pcscd 2>/dev/null; then
    echo "✓ pcscd already running"
else
    echo "▶ Starting pcscd..."
    sudo systemctl start pcscd 2>/dev/null || true
    sleep 1
    if systemctl is-active --quiet pcscd 2>/dev/null; then
        echo "✓ pcscd started"
    else
        echo "⚠️  pcscd could not be started — RFID card reader may not work"
    fi
fi

# ── Activate virtualenv if present ───────────────────────────────────────────
if [ -d "$APP_DIR/venv" ]; then
    source "$APP_DIR/venv/bin/activate"
    echo "✓ Virtualenv activated"
else
    echo "⚠️  No venv found — using system python3"
fi

PYTHON=$(command -v python3)
echo "✓ Python: $PYTHON"

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
    echo "🛑 Stopping Urban Kettle..."
    pkill -f main_app.py        2>/dev/null || true
    pkill -f polling_server2.py 2>/dev/null || true
    echo "✓ Stopped"
}
trap cleanup SIGTERM SIGINT EXIT

# ── Start backend ─────────────────────────────────────────────────────────────
echo "Starting polling server (ESP32 bridge)..."
"$PYTHON" "$APP_DIR/polling_server2.py" > "$APP_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Wait until Flask responds on :5000 (up to 15s) — process-alive check is not enough
BACKEND_READY=0
for i in $(seq 1 15); do
    sleep 1
    kill -0 "$BACKEND_PID" 2>/dev/null || { echo "❌ Backend crashed — check backend.log"; exit 1; }
    if curl -sf "http://localhost:5000/health" > /dev/null 2>&1 \
    || curl -sf "http://localhost:5000/api/status" > /dev/null 2>&1; then
        echo "✅ Backend ready and responding on :5000 (${i}s, PID=$BACKEND_PID)"
        BACKEND_READY=1
        break
    fi
done
[ "$BACKEND_READY" -eq 0 ] && echo "⚠️ Backend not responding on :5000 after 15s — starting frontend anyway"

# ── Start frontend ────────────────────────────────────────────────────────────
echo "Starting UI (main_app.py)..."
"$PYTHON" "$APP_DIR/main_app.py" > "$APP_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

sleep 3
kill -0 "$FRONTEND_PID" 2>/dev/null || { echo "❌ Frontend failed — check frontend.log"; cat "$APP_DIR/frontend.log" | tail -30; exit 1; }
echo "✅ Frontend running (PID=$FRONTEND_PID)"

echo "========================================"
echo "   Urban Kettle is RUNNING"
echo "========================================"

# ── Monitor — restart everything if either process dies ──────────────────────
while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "❌ Backend died — triggering service restart"
        exit 1   # systemd Restart=always will relaunch
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "👋 Frontend exited — shutting down"
        exit 0
    fi
    sleep 2
done

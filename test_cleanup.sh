#!/bin/bash
# Test script to verify cleanup works properly

echo "🧪 Testing cleanup behavior..."
echo ""

cd "$(dirname "$0")"

# Start the polling server
echo "1️⃣ Starting polling_server2.py..."
python3 polling_server2.py > /tmp/test_backend.log 2>&1 &
BACKEND_PID=$!
sleep 2

if ps -p $BACKEND_PID > /dev/null; then
    echo "   ✅ Backend running (PID: $BACKEND_PID)"
else
    echo "   ❌ Backend failed to start"
    exit 1
fi

# Simulate the cleanup that happens on app exit
echo ""
echo "2️⃣ Simulating app exit (calling hardware_monitor.stop())..."
python3 -c "
from utils.hardware_monitor import hardware_monitor
hardware_monitor.stop()
print('   ✅ Cleanup executed')
"

sleep 2

# Check if backend is still running
echo ""
echo "3️⃣ Checking if polling_server2.py was stopped..."
if ps -p $BACKEND_PID > /dev/null; then
    echo "   ❌ FAILED: Backend still running (PID: $BACKEND_PID)"
    echo "   Manual cleanup..."
    kill $BACKEND_PID
    exit 1
else
    echo "   ✅ SUCCESS: Backend properly stopped"
fi

# Also check with pkill pattern
if pgrep -f polling_server2.py > /dev/null; then
    echo "   ⚠️ WARNING: Found other polling_server2.py processes"
    pgrep -f polling_server2.py | xargs ps -p
    pkill -f polling_server2.py
else
    echo "   ✅ No lingering polling_server2.py processes"
fi

echo ""
echo "✅ Test completed successfully!"

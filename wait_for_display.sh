#!/bin/bash
# Wait for X11 display server to be ready
# This script ensures the graphical environment is fully initialized

echo "Waiting for display server to be ready..."

MAX_WAIT=60
COUNTER=0

# Check if X server is running and accessible
while [ $COUNTER -lt $MAX_WAIT ]; do
    # Try to connect to X display
    if [ -n "$DISPLAY" ]; then
        if xset q &>/dev/null || xdpyinfo &>/dev/null 2>&1; then
            echo "✓ Display server is ready (DISPLAY=$DISPLAY)"
            exit 0
        fi
    fi
    
    # Check for common display values
    for disp in :0 :1; do
        if DISPLAY=$disp xset q &>/dev/null 2>&1; then
            echo "✓ Display server found at $disp"
            export DISPLAY=$disp
            exit 0
        fi
    done
    
    COUNTER=$((COUNTER + 1))
    echo "  Waiting... ($COUNTER/$MAX_WAIT)"
    sleep 1
done

echo "⚠️ Display server not ready after ${MAX_WAIT}s, proceeding anyway"
echo "   You may need to manually set DISPLAY environment variable"
exit 1

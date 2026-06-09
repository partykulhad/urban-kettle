#!/bin/bash
# Quick test script for Urban Kettle autostart functionality

echo "========================================"
echo "Urban Kettle Autostart - Quick Test"
echo "========================================"
echo ""

# Check if service is enabled
echo "1. Checking if service is enabled..."
if systemctl is-enabled urban-kettle-autostart.service &>/dev/null; then
    echo "   ✅ Service is enabled (will start on boot)"
else
    echo "   ❌ Service is NOT enabled"
    echo "   Run: sudo systemctl enable urban-kettle-autostart.service"
fi
echo ""

# Check service status
echo "2. Checking service status..."
if systemctl is-active urban-kettle-autostart.service &>/dev/null; then
    echo "   ✅ Service is running"
    UPTIME=$(systemctl show urban-kettle-autostart.service -p ActiveEnterTimestamp --value)
    echo "   Started at: $UPTIME"
else
    echo "   ⚠️  Service is NOT running"
    echo "   Run: sudo systemctl start urban-kettle-autostart.service"
fi
echo ""

# Check processes
echo "3. Checking Urban Kettle processes..."
BACKEND_COUNT=$(ps aux | grep -F "polling_server2.py" | grep -v grep | wc -l)
FRONTEND_COUNT=$(ps aux | grep -F "main_app.py" | grep -v grep | wc -l)

if [ $BACKEND_COUNT -gt 0 ]; then
    BACKEND_PID=$(ps aux | grep -F "polling_server2.py" | grep -v grep | head -1 | awk '{print $2}')
    echo "   ✅ Backend running (PID: $BACKEND_PID)"
else
    echo "   ❌ Backend NOT running"
fi

if [ $FRONTEND_COUNT -gt 0 ]; then
    FRONTEND_PID=$(ps aux | grep -F "main_app.py" | grep -v grep | head -1 | awk '{print $2}')
    echo "   ✅ Frontend running (PID: $FRONTEND_PID)"
else
    echo "   ❌ Frontend NOT running"
fi
echo ""

# Check display
echo "4. Checking display server..."
if [ -n "$DISPLAY" ]; then
    echo "   DISPLAY=$DISPLAY"
    if xset q &>/dev/null; then
        echo "   ✅ Display server accessible"
    else
        echo "   ⚠️  Display server not accessible (may need to run from X session)"
    fi
else
    echo "   ⚠️  DISPLAY not set"
fi
echo ""

# Check logs for errors
echo "5. Checking recent logs for errors..."
ERROR_COUNT=$(sudo journalctl -u urban-kettle-autostart.service --since "5 minutes ago" | grep -iE "error|fail|crash" | wc -l)
if [ $ERROR_COUNT -gt 0 ]; then
    echo "   ⚠️  Found $ERROR_COUNT error-like messages in logs"
    echo "   View with: sudo journalctl -u urban-kettle-autostart.service -f"
else
    echo "   ✅ No recent errors in logs"
fi
echo ""

# Summary
echo "========================================"
echo "Summary"
echo "========================================"
if systemctl is-active urban-kettle-autostart.service &>/dev/null && [ $BACKEND_COUNT -gt 0 ] && [ $FRONTEND_COUNT -gt 0 ]; then
    echo "✅ Urban Kettle is running correctly!"
    echo ""
    echo "Useful commands:"
    echo "  View logs:        sudo journalctl -u urban-kettle-autostart.service -f"
    echo "  Restart service:  sudo systemctl restart urban-kettle-autostart.service"
    echo "  Stop service:     sudo systemctl stop urban-kettle-autostart.service"
else
    echo "⚠️  Urban Kettle has issues. Check the details above."
    echo ""
    echo "To debug:"
    echo "  1. View logs:   sudo journalctl -u urban-kettle-autostart.service -n 100"
    echo "  2. Try manual:  cd /home/urbanketl/Videos/urban-kettle && ./run_all.sh"
    echo "  3. Check guide: cat AUTOSTART_TROUBLESHOOTING.md"
fi
echo ""

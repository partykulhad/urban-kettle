#!/bin/bash
#
# Raspberry Pi UI Lag Diagnostic Script
# =====================================
# Run this to diagnose UI lag issues
#

echo "=================================================="
echo "  URBAN KETTLE - UI LAG DIAGNOSTIC SUITE"
echo "=================================================="
echo ""

# Create diagnostics folder
mkdir -p diagnostics

# Check for psutil
python3 -c "import psutil" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing psutil..."
    pip3 install psutil
fi

# Menu
echo "Select diagnostic mode:"
echo ""
echo "  1) Quick System Check (30 seconds)"
echo "  2) Full Recording (5 minutes)"
echo "  3) Live Monitor (real-time display)"
echo "  4) SD Card Speed Test"
echo "  5) Run App with Kivy Profiler"
echo "  6) Analyze Previous Recording"
echo "  0) Exit"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo "🔍 Running 30-second system check..."
        python3 rpi_diagnostic.py --duration 30
        ;;
    2)
        echo ""
        echo "🔍 Running 5-minute full recording..."
        echo "   USE THE APP NORMALLY DURING THIS TIME"
        echo "   Try to trigger the lag you're experiencing"
        echo ""
        python3 rpi_diagnostic.py --duration 300
        ;;
    3)
        echo ""
        echo "📊 Starting live monitor..."
        echo "   Press Ctrl+C to stop"
        echo ""
        python3 live_monitor.py
        ;;
    4)
        echo ""
        echo "💾 SD Card Speed Test"
        echo "-----------------------------------"
        
        # Write test
        echo "Testing write speed..."
        dd if=/dev/zero of=/tmp/sdtest bs=1M count=100 conv=fsync 2>&1 | grep -E "copied|MB/s"
        
        # Clear cache
        sync
        echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null 2>&1
        
        # Read test
        echo "Testing read speed..."
        dd if=/tmp/sdtest of=/dev/null bs=1M 2>&1 | grep -E "copied|MB/s"
        
        rm -f /tmp/sdtest
        
        echo ""
        echo "📌 Note: For smooth UI, you need at least:"
        echo "   - Write: >10 MB/s"
        echo "   - Read:  >20 MB/s"
        ;;
    5)
        echo ""
        echo "🎯 Starting app with Kivy profiler..."
        echo ""
        
        # Create a wrapper script
        cat > /tmp/run_profiled.py << 'EOF'
import kivy_profiler
kivy_profiler.enable()

# Import and run the main app
from main_app import UrbanKettleApp

# Patch the app
class ProfiledUrbanKettleApp(UrbanKettleApp):
    def build(self):
        root = super().build()
        kivy_profiler.patch_show_page(self)
        return root
    
    def on_stop(self):
        super().on_stop()
        print("\n")
        print(kivy_profiler.get_report())
        kivy_profiler.save_report('diagnostics/kivy_profile.txt')

if __name__ == '__main__':
    ProfiledUrbanKettleApp().run()
EOF
        
        python3 /tmp/run_profiled.py
        ;;
    6)
        echo ""
        echo "📂 Available recordings:"
        ls -la diagnostics/*.json 2>/dev/null || echo "   No recordings found"
        echo ""
        read -p "Enter filename to analyze: " filename
        if [ -f "$filename" ]; then
            python3 rpi_diagnostic.py --analyze "$filename"
        else
            echo "File not found: $filename"
        fi
        ;;
    0)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=================================================="
echo "  Diagnostic complete!"
echo "  Check the 'diagnostics/' folder for reports"
echo "=================================================="

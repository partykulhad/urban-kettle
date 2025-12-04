#!/bin/bash
# Urban Kettle - Raspberry Pi Launcher Script
# This script ensures the app runs in fullscreen mode on Raspberry Pi

echo "Starting Urban Kettle application for Raspberry Pi..."

# Kill any existing browser instances to free up resources
pkill chromium 2>/dev/null
pkill firefox 2>/dev/null

# Set environment variables for optimal Kivy performance on Pi
export KIVY_WINDOW=sdl2
export KIVY_GL_BACKEND=gl

# Disable multisampling for better performance
export KIVY_MULTISAMPLES=0

# Set display to use (usually :0 for main display)
export DISPLAY=:0

# Navigate to the application directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Launch the application
# Use python3 directly (not through browser)
python3 main_app.py

# Alternative: If you need to run in kiosk mode with Chromium
# Uncomment the following lines and comment the python3 line above
# chromium-browser \
#     --kiosk \
#     --noerrdialogs \
#     --disable-infobars \
#     --disable-session-crashed-bubble \
#     --check-for-update-interval=31536000 \
#     --app="http://localhost:8080" &
# python3 -m http.server 8080

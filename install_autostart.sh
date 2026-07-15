#!/bin/bash
# Urban Kettle - Auto-Start Installation Script for Raspberry Pi

echo "=================================================="
echo "Urban Kettle - Auto-Start Setup"
echo "=================================================="

# Check if running on Raspberry Pi (works on all Pi OS versions)
IS_PI=false
if grep -qi "raspberry" /proc/device-tree/model 2>/dev/null; then
    IS_PI=true
elif grep -qi "raspberry" /proc/cpuinfo 2>/dev/null; then
    IS_PI=true
fi

if [ "$IS_PI" = false ]; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "Continue anyway? (y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        echo "Installation cancelled."
        exit 1
    fi
else
    echo "✓ Raspberry Pi detected"
fi

# Get the current directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Installation directory: $INSTALL_DIR"

# Update the service file with correct paths
SERVICE_FILE="$INSTALL_DIR/urban-kettle.service"
TEMP_SERVICE="/tmp/urban-kettle.service"

# Replace /home/pi/urban-kettle with actual installation directory
sed "s|/home/pi/urban-kettle|$INSTALL_DIR|g" "$SERVICE_FILE" > "$TEMP_SERVICE"

# Replace pi user with correct desktop user
# When installed via .deb, whoami is 'root', which breaks the UI display.
# We try to detect the actual user (urbanketl or pi).
if id "urbanketl" &>/dev/null; then
    CURRENT_USER="urbanketl"
elif id "pi" &>/dev/null; then
    CURRENT_USER="pi"
else
    # Fallback just in case
    CURRENT_USER=$(who | grep -v root | awk '{print $1}' | head -n 1)
    if [ -z "$CURRENT_USER" ]; then
        CURRENT_USER="root"
    fi
fi

USER_HOME=$(eval echo "~$CURRENT_USER")

sed -i "s|User=pi|User=$CURRENT_USER|g" "$TEMP_SERVICE"
sed -i "s|/home/pi/.Xauthority|$USER_HOME/.Xauthority|g" "$TEMP_SERVICE"

echo "👤 Running service as user: $CURRENT_USER (Home: $USER_HOME)"

# Make launch script executable
chmod +x "$INSTALL_DIR/launch_pi.sh"
echo "✓ Made launch_pi.sh executable"

# Copy service file to systemd directory
echo "📋 Installing systemd service..."
sudo cp "$TEMP_SERVICE" /etc/systemd/system/urban-kettle.service

# Reload systemd
echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

# Enable the service to start on boot
echo "🚀 Enabling auto-start on boot..."
sudo systemctl enable urban-kettle.service

echo ""
echo "=================================================="
echo "✅ Installation Complete!"
echo "=================================================="
echo ""
echo "📌 Useful Commands:"
echo "   Start service:    sudo systemctl start urban-kettle"
echo "   Stop service:     sudo systemctl stop urban-kettle"
echo "   Check status:     sudo systemctl status urban-kettle"
echo "   View logs:        sudo journalctl -u urban-kettle -f"
echo "   Disable autostart: sudo systemctl disable urban-kettle"
echo ""
echo "🔄 The app will now start automatically on every boot!"
echo "💡 Reboot your Pi to test: sudo reboot"
echo ""

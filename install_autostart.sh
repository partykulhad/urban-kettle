#!/bin/bash
# Urban Kettle - Auto-Start Installation Script for Raspberry Pi

echo "=================================================="
echo "Urban Kettle - Auto-Start Setup"
echo "=================================================="

# Check if running on Raspberry Pi
if [ ! -f /etc/rpi-issue ]; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "Continue anyway? (y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        echo "Installation cancelled."
        exit 1
    fi
fi

# Get the current directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Installation directory: $INSTALL_DIR"

# Update the service file with correct paths
SERVICE_FILE="$INSTALL_DIR/urban-kettle.service"
TEMP_SERVICE="/tmp/urban-kettle.service"

# Replace /home/pi/urban-kettle with actual installation directory
sed "s|/home/pi/urban-kettle|$INSTALL_DIR|g" "$SERVICE_FILE" > "$TEMP_SERVICE"

# Replace pi user with current user
CURRENT_USER=$(whoami)
sed -i "s|User=pi|User=$CURRENT_USER|g" "$TEMP_SERVICE"
sed -i "s|/home/pi/.Xauthority|$HOME/.Xauthority|g" "$TEMP_SERVICE"

echo "👤 Running as user: $CURRENT_USER"

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

#!/bin/bash
# Urban Kettle - One-time Setup Script
# Run this once on each Raspberry Pi to install all dependencies
# Usage: ./setup.sh

set -e

echo "========================================"
echo "   Urban Kettle - Setup"
echo "========================================"

cd "$(dirname "$0")"

# Step 1: System packages
echo ""
echo "[1/6] Installing all system dependencies (Kivy, GStreamer, OpenCV, RFID)..."
sudo apt install -y python3-pip python3-dev python3-venv git build-essential \
    libgl1-mesa-dev libgles2-mesa-dev libegl1-mesa-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libmtdev-dev xclip xsel \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    libopencv-dev python3-opencv libjpeg-dev zlib1g-dev \
    pcscd pcsc-tools libpcsclite-dev swig watchdog

echo "✅ System dependencies installed"

echo "Applying NFC kernel module blacklists for ACR122U..."
sudo bash -c "echo 'blacklist pn533' >> /etc/modprobe.d/blacklist.conf"
sudo bash -c "echo 'blacklist nfc' >> /etc/modprobe.d/blacklist.conf"
sudo systemctl enable pcscd
sudo systemctl start pcscd

# Step 2: Create virtual environment
echo ""
echo "[2/4] Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Existing venv found — removing and recreating..."
    rm -rf venv
fi
python3 -m venv venv
echo "✅ Virtual environment created"

# Step 3: Install Python packages
echo ""
echo "[3/4] Installing Python packages (this may take a few minutes)..."
./venv/bin/pip install --upgrade pip --quiet
./venv/bin/pip install -r requirements.txt
echo "✅ Python packages installed"

# Step 4: Make scripts executable
echo ""
echo "[4/6] Setting permissions..."
chmod +x run_all.sh setup.sh deploy_to_pi.sh launch_pi.sh install_autostart.sh software_watchdog.sh update.sh 2>/dev/null || true
echo "✅ Permissions set"

# Step 5: Setup Auto-Start (systemd)
echo ""
echo "[5/6] Setting up Systemd Auto-Start..."
if [ -f "install_autostart.sh" ]; then
    # Pass 'y' to skip the prompt if it's not a Pi
    echo "y" | ./install_autostart.sh > /dev/null
    echo "✅ Systemd service installed and enabled"
else
    echo "⚠️  install_autostart.sh not found, skipping..."
fi

# Step 6: Setup Watchdog & OTA Updater Cronjobs
echo ""
echo "[6/6] Setting up Software Watchdog and Updater Cronjobs..."

CRON_WATCHDOG="* * * * * $(pwd)/software_watchdog.sh"
(crontab -l 2>/dev/null | grep -v "software_watchdog.sh"; echo "$CRON_WATCHDOG") | crontab -

# OTA Update Schedule — choose one:
# Option A: Every 5 minutes — uncomment to use
# CRON_UPDATE="*/5 * * * * $(pwd)/update.sh"
# Option B: Every night at 2:00 AM (production) — uncomment to use
# CRON_UPDATE="0 2 * * * $(pwd)/update.sh"
# Option C: Every 2 minutes (TESTING ONLY)
CRON_UPDATE="*/2 * * * * $(pwd)/update.sh"
(crontab -l 2>/dev/null | grep -v "update.sh"; echo "$CRON_UPDATE") | crontab -

echo "✅ Watchdog and Updater added to crontab"

# Step 7: Setup Hardware Watchdog
echo ""
echo "[7/8] Setting up Raspberry Pi Hardware Watchdog..."
sudo bash -c "grep -q 'dtparam=watchdog=on' /boot/config.txt || echo 'dtparam=watchdog=on' >> /boot/config.txt"
sudo bash -c "sed -i 's/#watchdog-device/watchdog-device/g' /etc/watchdog.conf"
sudo bash -c "sed -i 's/#max-load-1\t\t= 24/max-load-1 = 24/g' /etc/watchdog.conf"
sudo systemctl enable watchdog || true
sudo systemctl start watchdog || true
echo "✅ Hardware watchdog enabled"

# Step 8: Setup Periodic Reboot
echo ""
echo "[8/8] Setting up 3 AM Daily Reboot..."
CRON_REBOOT="0 4 * * * /sbin/reboot"
sudo bash -c "(crontab -l 2>/dev/null | grep -v '/sbin/reboot'; echo \"$CRON_REBOOT\") | crontab -"
echo "✅ Daily reboot scheduled"

echo ""
echo "========================================"
echo "   Setup Complete!"
echo "========================================"
echo ""
echo "⚠️  IMPORTANT: Update the DEVICE_ID in config.py"
echo "   for this specific machine before starting."
echo ""
echo "   Current DEVICE_ID:"
grep "DEVICE_ID" config.py | grep -v "#" | head -1
echo ""
echo "   To start the application:"
echo "   ./run_all.sh"
echo ""

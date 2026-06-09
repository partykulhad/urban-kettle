#!/bin/bash
# Urban Kettle - One-time Setup Script
# Run this once on each Raspberry Pi to install all dependencies
# Usage: ./setup.sh

set -e

echo "========================================"
echo "   Urban Kettle - Setup"
echo "========================================"

cd "$(dirname "$0")"

# Step 1: System packages required for pyscard
echo ""
echo "[1/4] Installing system dependencies..."
sudo apt install -y pcscd libpcsclite-dev swig
echo "✅ System dependencies installed"

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
echo "[4/4] Setting permissions..."
chmod +x run_all.sh setup.sh deploy_to_pi.sh launch_pi.sh 2>/dev/null || true
echo "✅ Permissions set"

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

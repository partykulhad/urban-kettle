#!/bin/bash
# Urban Kettle - Deploy to Raspberry Pi
# Copies code from this machine to a Pi over SSH and runs setup
#
# Usage:
#   ./deploy_to_pi.sh <PI_IP> [PI_USER] [DEVICE_ID]
#
# Examples:
#   ./deploy_to_pi.sh 192.168.1.101
#   ./deploy_to_pi.sh 192.168.1.101 urbanketl2
#   ./deploy_to_pi.sh 192.168.1.101 urbanketl2 UK_30C9223A073C

PI_IP="${1}"
PI_USER="${2:-urbanketl2}"
DEVICE_ID="${3}"

if [ -z "$PI_IP" ]; then
    echo "❌ Usage: ./deploy_to_pi.sh <PI_IP> [PI_USER] [DEVICE_ID]"
    echo "   Example: ./deploy_to_pi.sh 192.168.1.101 urbanketl2 UK_30C9223A073C"
    exit 1
fi

# Detect remote directory casing (withrfid vs withRFID)
echo "Checking remote folder path casing..."
if ssh -o ConnectTimeout=3 "$PI_USER@$PI_IP" "[ -d /home/$PI_USER/withrfid ]" 2>/dev/null; then
    PI_DIR="/home/$PI_USER/withrfid/urban-kettle-withRFID"
else
    PI_DIR="/home/$PI_USER/withRFID/urban-kettle-withRFID"
fi

echo "========================================"
echo "   Urban Kettle - Deploy to Pi"
echo "========================================"
echo "   Target : $PI_USER@$PI_IP"
echo "   Path   : $PI_DIR"
if [ -n "$DEVICE_ID" ]; then
echo "   Device : $DEVICE_ID"
fi
echo "========================================"

# Step 1: Create remote directory
echo ""
echo "[1/4] Preparing remote directory..."
ssh "$PI_USER@$PI_IP" "mkdir -p $PI_DIR"
echo "✅ Remote directory ready"

# Step 2: Sync code (exclude venv, cache, logs)
echo ""
echo "[2/4] Syncing code files..."
rsync -av --progress \
    --exclude='venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.log' \
    --exclude='.git/' \
    --exclude='*.mp4' \
    --exclude='screensaver_cache.json' \
    . "$PI_USER@$PI_IP:$PI_DIR/"
echo "✅ Code synced"

# Step 3: Update DEVICE_ID if provided
if [ -n "$DEVICE_ID" ]; then
    echo ""
    echo "[3/4] Setting DEVICE_ID to $DEVICE_ID..."
    ssh "$PI_USER@$PI_IP" "sed -i 's/^DEVICE_ID = .*/DEVICE_ID = \"$DEVICE_ID\"/' $PI_DIR/config.py"
    echo "✅ DEVICE_ID updated"
else
    echo ""
    echo "[3/4] Skipping DEVICE_ID update (not provided)"
    echo "⚠️  Remember to update DEVICE_ID manually in config.py on the Pi"
fi

# Step 4: Run setup on Pi
echo ""
echo "[4/4] Running setup on Pi..."
ssh -t "$PI_USER@$PI_IP" "cd $PI_DIR && bash setup.sh"

echo ""
echo "========================================"
echo "   Deployment Complete!"
echo "========================================"
echo ""
echo "   To start the app on the Pi:"
echo "   ssh $PI_USER@$PI_IP"
echo "   cd $PI_DIR && ./run_all.sh"
echo ""

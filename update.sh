#!/bin/bash
# urban-kettle-withRFID/update.sh
# OTA .deb Downloader - Runs every 5 minutes via crontab
set -euo pipefail

# --- Safegaurd to stop legacy Github-pulling machines ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" == *"/home/"* ]]; then
    echo "Legacy installation detected in $SCRIPT_DIR. Stopping update script."
    # To fully kill the old cronjob on legacy machines:
    (crontab -l 2>/dev/null | grep -v "update.sh") | crontab - || true
    exit 0
fi
# --------------------------------------------------------

# Kulhad dashboard URL (hosts both the version API and the .deb files)
VERCEL_URL="https://kulhad.vercel.app"
SERVICE="urban-kettle"
REPO_DIR="/opt/urban-kettle"
LOG_FILE="/tmp/update.log"
VERSION_FILE="$REPO_DIR/current_version.txt"
DEB_FILE="/tmp/urban_kettle_update.deb"

# Ensure we don't blow up the log file
if [ -f "$LOG_FILE" ]; then
    tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

# 1. Check what version we are currently running
if [ -f "$VERSION_FILE" ]; then
    LOCAL_VERSION=$(cat "$VERSION_FILE")
else
    LOCAL_VERSION="0.0.0" # If no file exists, we force an update
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking for updates..." >> "$LOG_FILE"

# 2. Ask Kulhad what the latest version is (via the OTA API endpoint)
OTA_DATA=$(curl -s --fail "$VERCEL_URL/api/ota-version" || echo "FAIL")

if [ "$OTA_DATA" = "FAIL" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Could not reach Vercel to check for updates." >> "$LOG_FILE"
    exit 1
fi

# The API returns raw JSON like {"version":"1.8.0","debUrl":"https://..."}
REMOTE_VERSION=$(echo "$OTA_DATA" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
DEB_URL=$(echo "$OTA_DATA" | grep -o '"debUrl":"[^"]*"' | cut -d'"' -f4)

if [ -z "$REMOTE_VERSION" ] || [ -z "$DEB_URL" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Invalid OTA data received: $OTA_DATA" >> "$LOG_FILE"
    exit 1
fi

# 3. Compare versions
if [ "$LOCAL_VERSION" = "$REMOTE_VERSION" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Already up to date ($LOCAL_VERSION). Nothing to do." >> "$LOG_FILE"
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] UPDATE FOUND! Downloading version $REMOTE_VERSION..." >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Downloading from: $DEB_URL" >> "$LOG_FILE"

# 4. Download it (without failing instantly if wget gives 404, so we can log it)
if ! wget -q -O "$DEB_FILE" "$DEB_URL"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Download failed. URL might be expired or invalid." >> "$LOG_FILE"
    exit 1
fi

# 5. Install the .deb file silently
if sudo dpkg -i "$DEB_FILE" >> "$LOG_FILE" 2>&1; then
    # 6. Save the new version so we don't download it again
    echo "$REMOTE_VERSION" > "$VERSION_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Successfully installed version $REMOTE_VERSION!" >> "$LOG_FILE"
    
    # Extract MACHINE_ID and report success to Kulhad
    MACHINE_ID=$(grep -o 'MACHINE_ID *= *"[^"]*"' "$REPO_DIR/machine_config.py" | cut -d'"' -f2 || true)
    if [ -n "$MACHINE_ID" ]; then
        curl -s -X POST -H "Content-Type: application/json" \
             -d "{\"machineId\":\"$MACHINE_ID\",\"version\":\"$REMOTE_VERSION\"}" \
             "$VERCEL_URL/api/ota-success" >> "$LOG_FILE" 2>&1 || true
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Reported OTA success to Kulhad backend for machine $MACHINE_ID." >> "$LOG_FILE"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Failed to install the .deb package." >> "$LOG_FILE"
    exit 1
fi

# Cleanup
rm -f "$DEB_FILE"

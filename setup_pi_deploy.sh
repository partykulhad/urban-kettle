#!/bin/bash
# Urban Kettle — one-time Pi setup for pull-based deployment.
# Run this once on the Pi. Safe to re-run (idempotent) if something fails
# partway and you need to retry.
set -euo pipefail

REPO_DIR="/home/pi/urban-kettle"
REPO_URL="https://github.com/partykulhad/urban-kettle.git"
SERVICE="urban-kettle"
CRON_LINE="0 * * * * $REPO_DIR/update.sh"

echo "==> Stopping $SERVICE (if running)..."
sudo systemctl stop "$SERVICE" 2>/dev/null || true

cd "$REPO_DIR"

# Migration: this machine's config.py still has DEVICE_ID/MACHINE_ID/
# RFID_MACHINE_ID/PUMP_FLOW_RATE_ML_PER_SEC hardcoded directly (the old
# layout). The new config.py imports those from machine_config.py instead
# (gitignored, so future `git reset --hard` calls never touch it). Extract
# this machine's REAL current values before the reset overwrites config.py,
# so nothing is lost and the app doesn't crash on the next import.
if [ ! -f "$REPO_DIR/machine_config.py" ] && [ -f "$REPO_DIR/config.py" ]; then
    echo "==> First run after the per-machine-config split — migrating this machine's identity..."
    DEVICE_ID_VAL=$(grep -oP '^DEVICE_ID\s*=\s*"\K[^"]+' "$REPO_DIR/config.py" || true)
    MACHINE_ID_VAL=$(grep -oP '^MACHINE_ID\s*=\s*"\K[^"]+' "$REPO_DIR/config.py" || true)
    RFID_MACHINE_ID_VAL=$(grep -oP '^RFID_MACHINE_ID\s*=\s*"\K[^"]+' "$REPO_DIR/config.py" || true)
    PUMP_RATE_VAL=$(grep -oP '^PUMP_FLOW_RATE_ML_PER_SEC\s*=\s*\K[0-9.]+' "$REPO_DIR/config.py" || true)

    if [ -n "$DEVICE_ID_VAL" ] && [ -n "$MACHINE_ID_VAL" ]; then
        cat > "$REPO_DIR/machine_config.py" <<EOF
"""Per-machine identity for THIS machine. Gitignored — see machine_config.py.example."""

DEVICE_ID = "$DEVICE_ID_VAL"
MACHINE_ID = "$MACHINE_ID_VAL"
RFID_MACHINE_ID = "${RFID_MACHINE_ID_VAL:-UK_0000}"
PUMP_FLOW_RATE_ML_PER_SEC = ${PUMP_RATE_VAL:-9.0}
EOF
        echo "    Extracted: DEVICE_ID=$DEVICE_ID_VAL MACHINE_ID=$MACHINE_ID_VAL RFID_MACHINE_ID=${RFID_MACHINE_ID_VAL:-UK_0000} PUMP_FLOW_RATE_ML_PER_SEC=${PUMP_RATE_VAL:-9.0}"
        echo "    -> Wrote $REPO_DIR/machine_config.py"
    else
        echo "    ⚠️  Could not extract DEVICE_ID/MACHINE_ID from the current config.py."
        echo "    You'll need to create machine_config.py manually from machine_config.py.example"
        echo "    before the app will start again."
    fi
fi

echo "==> Pointing $REPO_DIR at $REPO_URL and syncing..."
git remote set-url origin "$REPO_URL"
git fetch origin
git reset --hard origin/main

echo "==> Ensuring update.sh is executable..."
chmod +x "$REPO_DIR/update.sh"

echo "==> Granting passwordless restart permission for cron (NOPASSWD sudoers entry)..."
echo "pi ALL=(ALL) NOPASSWD: /bin/systemctl restart $SERVICE" | sudo tee /etc/sudoers.d/urban-kettle-restart > /dev/null
sudo chmod 440 /etc/sudoers.d/urban-kettle-restart

echo "==> Installing hourly cron job (idempotent — won't duplicate on re-run)..."
( crontab -l 2>/dev/null | grep -vF "$REPO_DIR/update.sh" ; echo "$CRON_LINE" ) | crontab -

echo "==> Starting $SERVICE..."
sudo systemctl start "$SERVICE"

echo ""
echo "Done. Current crontab:"
crontab -l
echo ""
echo "Verify machine_config.py matches this physical machine:"
cat "$REPO_DIR/machine_config.py"

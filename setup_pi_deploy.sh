#!/bin/bash
# Urban Kettle — one-time Pi setup for pull-based deployment.
# Run this once on the Pi. Safe to re-run (idempotent) if something fails
# partway and you need to retry.
set -euo pipefail

# Auto-detect this script's own directory and the user running it — don't
# assume /home/pi or user "pi", since the actual install path/user varies
# per machine (some are set up under a different username).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
REPO_URL="https://github.com/partykulhad/urban-kettle.git"
SERVICE="urban-kettle"
CRON_LINE="*/5 * * * * $REPO_DIR/update.sh"

echo "==> Checking GitHub is reachable before touching the running service..."
if ! git ls-remote "$REPO_URL" main >/dev/null 2>&1; then
    echo "❌ Cannot reach $REPO_URL — github.com may not be whitelisted on this network yet."
    echo "   The running kiosk has NOT been touched. Fix network/whitelist access and re-run this script."
    exit 1
fi
echo "    GitHub reachable — proceeding."

# Safety net: if anything fails after this point (stop), make sure the
# service comes back up rather than leaving the kiosk down. set -e means
# any failing command below exits immediately; this trap runs on any exit.
SERVICE_RESTARTED_BY_TRAP=0
ensure_service_running() {
    if [ "$SERVICE_RESTARTED_BY_TRAP" -eq 0 ]; then
        echo "==> (safety net) Restarting $SERVICE so the kiosk isn't left down..."
        sudo systemctl start "$SERVICE" 2>/dev/null || true
    fi
}
trap ensure_service_running EXIT

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

echo "==> Granting passwordless restart permission for cron (NOPASSWD sudoers entry, user: $CURRENT_USER)..."
echo "$CURRENT_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart $SERVICE" | sudo tee /etc/sudoers.d/urban-kettle-restart > /dev/null
sudo chmod 440 /etc/sudoers.d/urban-kettle-restart

echo "==> Installing 5-minute cron job (idempotent — won't duplicate on re-run)..."
( crontab -l 2>/dev/null | grep -vF "$REPO_DIR/update.sh" ; echo "$CRON_LINE" ) | crontab -

echo "==> Starting $SERVICE..."
sudo systemctl start "$SERVICE"
SERVICE_RESTARTED_BY_TRAP=1

echo ""
echo "Done. Current crontab:"
crontab -l
echo ""
echo "Verify machine_config.py matches this physical machine:"
cat "$REPO_DIR/machine_config.py"

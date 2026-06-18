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

echo "==> Pointing $REPO_DIR at $REPO_URL and syncing..."
cd "$REPO_DIR"
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
echo "Verify config.py MACHINE_ID matches this physical machine:"
grep "^MACHINE_ID" "$REPO_DIR/config.py"

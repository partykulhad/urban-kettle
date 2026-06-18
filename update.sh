#!/bin/bash
# Urban Kettle — pull-based auto-update.
# Run by cron every hour (see README/instructions). Only touches the running
# kiosk if a new commit is actually available — never restarts on a no-op
# check, since that would interrupt a customer mid-order for nothing.
set -euo pipefail

REPO_DIR="/home/pi/urban-kettle"
BRANCH="main"
SERVICE="urban-kettle"
LOG_FILE="$REPO_DIR/update.log"

cd "$REPO_DIR"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Checking for updates..." >> "$LOG_FILE"

git fetch origin "$BRANCH" >> "$LOG_FILE" 2>&1

LOCAL_REV=$(git rev-parse HEAD)
REMOTE_REV=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Already up to date ($LOCAL_REV) — nothing to do." >> "$LOG_FILE"
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Update found: $LOCAL_REV -> $REMOTE_REV" >> "$LOG_FILE"

# Safety check: machine_config.py holds this machine's identity (DEVICE_ID,
# MACHINE_ID, etc.) and is gitignored on purpose. If it's somehow missing,
# config.py will raise ImportError and the app will crash on restart — bail
# out now instead, so the kiosk keeps running on its last-known-good code.
if [ ! -f "$REPO_DIR/machine_config.py" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: machine_config.py missing — refusing to update/restart. See machine_config.py.example." >> "$LOG_FILE"
    exit 1
fi

# Hard reset instead of a plain pull: a few files (screensaver_cache.json,
# screensaver_current.mp4) are tracked in git but get rewritten by the app at
# runtime. A plain `git pull` would refuse to overwrite those local
# modifications and abort the whole update. They're just caches — safe to
# discard and let the app regenerate them.
git reset --hard "origin/$BRANCH" >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarting $SERVICE..." >> "$LOG_FILE"
sudo systemctl restart "$SERVICE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Updated to $REMOTE_REV and restarted $SERVICE." >> "$LOG_FILE"

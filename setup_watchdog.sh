#!/bin/bash
# Urban Kettle — one-time Pi reliability setup: hardware watchdog, SD-card
# wear reduction, and a daily safety reboot. Run this once per physical
# machine over SSH. Safe to re-run (idempotent).
#
# What this does NOT do: this is OS-level setup (apt, /boot/firmware/config.txt,
# /etc/watchdog.conf, /etc/fstab, cron). The 5-minute git auto-update pipeline
# only pulls files inside the repo and restarts the app service — it never
# touches these, so re-running this script after a fresh install (or on any
# machine that predates it) is a manual, deliberate step on each machine.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
REBOOT_HOUR="1"   # 1 AM — outside operating hours for every machine today

echo "==> Installing watchdog package..."
sudo apt update -qq
sudo apt install -y watchdog

echo "==> Enabling the hardware watchdog (dtparam=watchdog=on)..."
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_TXT=/boot/firmware/config.txt
elif [ -f /boot/config.txt ]; then
    CONFIG_TXT=/boot/config.txt
else
    echo "❌ Could not find /boot/firmware/config.txt or /boot/config.txt — skipping hardware watchdog enable."
    CONFIG_TXT=""
fi

if [ -n "$CONFIG_TXT" ]; then
    if grep -q "^dtparam=watchdog=on" "$CONFIG_TXT" 2>/dev/null; then
        echo "    Already enabled in $CONFIG_TXT."
    else
        echo "dtparam=watchdog=on" | sudo tee -a "$CONFIG_TXT" > /dev/null
        echo "    Added to $CONFIG_TXT — takes effect after next reboot."
    fi
fi

echo "==> Configuring /etc/watchdog.conf..."
# Watches /tmp/urban_kettle_heartbeat, written every 15s by main_app.py's Clock
# loop (only while Kivy's event loop is actually pumping — a real UI/payment
# freeze stops it). If the file's content hasn't changed in 60s, the watchdog
# daemon reboots the Pi — a full reboot, not just a service restart, since a
# truly wedged Kivy/X11 session often needs that to actually recover.
sudo tee /etc/watchdog.conf > /dev/null <<'EOF'
watchdog-device = /dev/watchdog
watchdog-timeout = 15
realtime = yes
priority = 1
file = /tmp/urban_kettle_heartbeat
change = 60
EOF

echo "==> Enabling and starting the watchdog service..."
sudo systemctl enable watchdog
sudo systemctl restart watchdog

echo "==> Mounting /tmp and /var/log as tmpfs (RAM) to reduce SD card wear..."
# Idempotent: only append each line if not already present.
add_fstab_line() {
    local line="$1"
    if grep -qF "$line" /etc/fstab 2>/dev/null; then
        echo "    Already present: $line"
    else
        echo "$line" | sudo tee -a /etc/fstab > /dev/null
        echo "    Added: $line"
    fi
}
add_fstab_line "tmpfs /tmp tmpfs defaults,noatime,nosuid,size=100m 0 0"
add_fstab_line "tmpfs /var/log tmpfs defaults,noatime,nosuid,size=50m 0 0"
echo "    (takes effect after next reboot)"

echo "==> Installing daily safety reboot (${REBOOT_HOUR}:00 AM, root crontab)..."
# Goes in root's crontab, not $CURRENT_USER's — /sbin/reboot needs root, and
# this avoids adding yet another passwordless-sudo sudoers entry just for this.
REBOOT_CRON_LINE="0 $REBOOT_HOUR * * * /sbin/reboot"
( sudo crontab -l 2>/dev/null | grep -vF "/sbin/reboot" || true ; echo "$REBOOT_CRON_LINE" ) | sudo crontab -

echo ""
echo "Done. Current user crontab ($CURRENT_USER):"
crontab -l 2>/dev/null || echo "(empty)"
echo ""
echo "Current root crontab:"
sudo crontab -l
echo ""
echo "⚠️  Reboot this machine once to apply dtparam=watchdog=on and the tmpfs mounts:"
echo "    sudo reboot"
echo "After reboot, verify with: sudo systemctl status watchdog"

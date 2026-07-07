#!/bin/bash
# software_watchdog.sh
# Soft watchdog that monitors the Kivy UI heartbeat file.
# Instead of hard-rebooting the Raspberry Pi (like a hardware watchdog),
# this script just cleanly restarts the urban-kettle systemd service 
# if the UI event loop freezes.

HEARTBEAT_FILE="/tmp/urban_kettle_heartbeat"
SERVICE_NAME="urban-kettle"
MAX_AGE=60

# Check if file exists. If it doesn't, the app might be starting up, 
# or systemd is already taking care of a crash.
if [ ! -f "$HEARTBEAT_FILE" ]; then
    exit 0
fi

# --- Safe Restart Logic (Prevents Infinite Bootloops) ---
trigger_restart() {
    REASON="$1"
    RESTART_LOG="/tmp/watchdog_restarts"
    MAX_RESTARTS=3
    TIME_WINDOW=900 # 15 minutes
    
    CURRENT_TIME=$(date +%s)
    VALID_RESTARTS=""
    RESTART_COUNT=0
    
    if [ -f "$RESTART_LOG" ]; then
        while read -r ts; do
            if [ -n "$ts" ] && [ $((CURRENT_TIME - ts)) -le $TIME_WINDOW ]; then
                VALID_RESTARTS="${VALID_RESTARTS}${ts}\n"
                RESTART_COUNT=$((RESTART_COUNT + 1))
            fi
        done < "$RESTART_LOG"
    fi
    
    if [ "$RESTART_COUNT" -ge "$MAX_RESTARTS" ]; then
        echo "$(date): 🛑 Too many crashes ($RESTART_COUNT in 15m). Halting watchdog restarts!" >> /tmp/software_watchdog.log
        
        # Notify backend it's offline due to crash loop
        MACHINE_ID=$(grep -o 'MACHINE_ID *= *"[^"]*"' /opt/urban-kettle/machine_config.py 2>/dev/null | cut -d'"' -f2 || true)
        if [ -z "$MACHINE_ID" ]; then
            MACHINE_ID=$(grep -o 'MACHINE_ID *= *"[^"]*"' /home/pi/urban-kettle/machine_config.py 2>/dev/null | cut -d'"' -f2 || true)
        fi
        
        if [ -n "$MACHINE_ID" ]; then
            curl -s -X POST -H "Content-Type: application/json" \
                 -d "{\"machineId\":\"$MACHINE_ID\",\"status\":\"offline\"}" \
                 "https://kulhad.vercel.app/api/MachinesStatus" > /dev/null || true
            echo "$(date): 📡 Sent offline notification to Kulhad API." >> /tmp/software_watchdog.log
        fi
        exit 0
    fi
    
    echo -e "${VALID_RESTARTS}${CURRENT_TIME}" > "$RESTART_LOG"
    echo "$(date): ⚠️ $REASON Restarting urban-kettle service..." >> /tmp/software_watchdog.log
    sudo systemctl restart "$SERVICE_NAME"
    exit 0
}
# --------------------------------------------------------

FILE_MOD_TIME=$(stat -c %Y "$HEARTBEAT_FILE")
CURRENT_TIME=$(date +%s)
AGE=$((CURRENT_TIME - FILE_MOD_TIME))

if [ "$AGE" -gt "$MAX_AGE" ]; then
    trigger_restart "UI Frozen! Heartbeat is ${AGE}s old."
fi

# ==========================================
# 2. Memory (RAM) Check
# ==========================================
# Get available free memory in Megabytes
FREE_MEM=$(free -m | awk '/^Mem:/{print $7}')
# If less than 80MB available, Python might be leaking memory
if [ "$FREE_MEM" -lt 80 ]; then
    trigger_restart "Low Memory! Only ${FREE_MEM}MB available."
fi

# ==========================================
# 3. Network Connection Check
# ==========================================
# First, check for complete network death
if ! ping -c 1 -W 5 8.8.8.8 &> /dev/null; then
    echo "$(date): ⚠️ Network ping failed. Trying one more time..." >> /tmp/software_watchdog.log
    sleep 5
    if ! ping -c 1 -W 5 8.8.8.8 &> /dev/null; then
        echo "$(date): 🔴 Network completely dead! Restarting NetworkManager..." >> /tmp/software_watchdog.log
        sudo systemctl restart NetworkManager || sudo systemctl restart dhcpcd
    fi
else
    # Network is alive, check for high latency (Wi-Fi degradation)
    LATENCY_STR=$(ping -c 1 -W 5 8.8.8.8 | grep 'time=' | sed -E 's/.*time=([0-9\.]+).*/\1/')
    if [ -n "$LATENCY_STR" ]; then
        # Convert float ms to integer
        LATENCY=$(printf "%.0f" "$LATENCY_STR")
        STATE_FILE="/tmp/watchdog_net_state"
        
        if [ ! -f "$STATE_FILE" ]; then
            echo "0 0" > "$STATE_FILE"
        fi
        
        read CONSECUTIVE_HIGH_LATENCY PREV_LATENCY < "$STATE_FILE"
        
        if [ "$LATENCY" -gt 300 ]; then
            CONSECUTIVE_HIGH_LATENCY=$((CONSECUTIVE_HIGH_LATENCY + 1))
            
            if [ "$CONSECUTIVE_HIGH_LATENCY" -ge 4 ]; then
                # It has been 4 minutes of >300ms latency. Is it getting worse/staying bad?
                if [ "$LATENCY" -ge "$PREV_LATENCY" ]; then
                    echo "$(date): 🔴 Network latency degraded (${LATENCY}ms >= previous ${PREV_LATENCY}ms). Restarting NetworkManager..." >> /tmp/software_watchdog.log
                    sudo systemctl restart NetworkManager || sudo systemctl restart dhcpcd
                    CONSECUTIVE_HIGH_LATENCY=0
                    LATENCY=0
                else
                    echo "$(date): ⚠️ Network latency high (${LATENCY}ms) but improving (was ${PREV_LATENCY}ms). Holding off restart." >> /tmp/software_watchdog.log
                fi
            fi
        else
            CONSECUTIVE_HIGH_LATENCY=0
        fi
        
        # Save state for next run
        echo "$CONSECUTIVE_HIGH_LATENCY $LATENCY" > "$STATE_FILE"
    fi
fi

# ==========================================
# 4. Disk Space Check
# ==========================================
# Check if the root partition (/) is over 95% full
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 95 ]; then
    echo "$(date): ⚠️ Disk critically full (${DISK_USAGE}%). Purging old logs to prevent crash..." >> /tmp/software_watchdog.log
    # Clean up systemd journal logs older than 1 day
    sudo journalctl --vacuum-time=1d
    # Remove old custom logs
    sudo rm -rf ~/.kivy/logs/*
    sudo rm -rf /tmp/*.txt /tmp/*.log
fi

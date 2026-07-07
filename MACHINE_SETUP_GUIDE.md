# Urban Kettle Kiosk - Fresh Machine Setup Guide

This document outlines the exact steps required to take a brand new Raspberry Pi and turn it into a fully functional, production-ready Urban Kettle Kiosk using the 1-Click Master Installer.

---

## Phase 1: Operating System Preparation

1. **Flash the OS:** Install Raspberry Pi OS (with Desktop/X11 environment) onto the SD card.
2. **System Update:** Ensure the base system is up to date.
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```
3. **Hardware Permissions:** Ensure the `pi` user has permission to access the screen, touch inputs, and serial ports (ESP32).
   ```bash
   sudo usermod -a -G dialout,video,input,plugdev pi
   ```

---

## Phase 2: Application Installation

1. **Clone the Repository:**
   Download the codebase to the home directory.
   ```bash
   cd /home/pi
   git clone <YOUR_GITHUB_REPO_URL> urban-kettle
   cd urban-kettle
   ```

2. **Run the Master Installer:**
   Make the setup script executable and run it. This script automatically handles system dependencies (like RFID drivers), creates the Python environment, installs libraries, copies the `systemd` auto-start service, and registers the watchdog in the crontab.
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

---

## Phase 3: Machine Identity

Every kiosk needs a unique ID so the backend (Kulhad) knows which machine is asking for configuration and reporting sales.

1. **Configure `machine_config.py`:**
   Copy the example configuration file and set the specific `DEVICE_ID` and `MACHINE_ID`.
   ```bash
   cp machine_config.py.example machine_config.py
   nano machine_config.py
   # Change DEVICE_ID and MACHINE_ID to this specific machine's unique identifier
   ```

---

## Phase 4: Final Boot

1. **Reboot the Machine:**
   The installation is fully complete. Reboot to test the automatic startup.
   ```bash
   sudo reboot
   ```

**What to expect on reboot:**
- The Pi will turn on and load the desktop.
- The `urban-kettle.service` (installed by the setup script) will automatically trigger.
- The RFID reader daemon (`pcscd`) will start.
- `polling_server2.py` will start in the background to talk to the ESP32 hardware.
- The Kivy User Interface will launch on the screen.
- Exactly 1 minute later, the `software_watchdog.sh` (installed via crontab) will begin silently monitoring the system for UI freezes or memory leaks.

Your machine is now fully deployed!

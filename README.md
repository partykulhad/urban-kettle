# 🫖 Urban Kettle - Kiosk & Hardware Controller Gateway

Welcome to the **Urban Kettle** kiosk repository. This project is a Python-based Chai Ordering System built using **Kivy** for the touchscreen user interface. It acts as a gateway interfacing with:
*   **ESP32 Hardware Controller** (controlling temperature, heaters, pumps, and water/tea dispense actions).
*   **ACR122U RFID Reader** (for contactless smart card payments and maintenance access).
*   **Kulhad Cloud API** (Vercel-hosted Convex API for QR code payments, machine statuses, and inventory management).

---

## 🚀 Quick Start Guide

Setting up the project on a new Raspberry Pi or Linux machine takes just a few steps.

### 1. Run the Setup Script
This script installs all system libraries (`pcscd`, `swig`, graphics dependencies), creates a Python virtual environment (`venv`), and installs all Python dependencies automatically.
```bash
./setup.sh
```

### 2. Configure the Network Routing (ESP32 Gateway)
The ESP32 is hardcoded to communicate with the RPi gateway at IP **`192.168.0.100`**. You must assign this IP as an alias to your Wi-Fi interface (`wlan0`):

*   **Temporary Fix (Resets on boot):**
    ```bash
    sudo ip addr add 192.168.0.100/24 dev wlan0
    ```
*   **Permanent Fix (Persists on boot via NetworkManager):**
    ```bash
    sudo nmcli connection modify "YOUR_WIFI_SSID" +ipv4.addresses "192.168.0.100/24"
    sudo nmcli connection up "YOUR_WIFI_SSID"
    ```

---

## 💻 Running the Kiosk

There are two ways to run the project:

### Method A: Run Manually (Testing/Development)
To run both the Python Flask server backend (which queues commands for the ESP32) and the Kivy UI frontend simultaneously:
```bash
./run_all.sh
```

### Method B: Run on Boot (Autostart Service)
To configure the kiosk to run automatically on system boot (headless Kiosk mode):
1.  Run the autostart installer:
    ```bash
    ./install_autostart.sh
    ```
2.  Manage the system service:
    *   **Start Kiosk:** `sudo systemctl start urban-kettle`
    *   **Stop Kiosk:** `sudo systemctl stop urban-kettle`
    *   **Restart Kiosk:** `sudo systemctl restart urban-kettle`
    *   **Check Status:** `sudo systemctl status urban-kettle`
    *   **View Real-Time Logs:** `sudo journalctl -u urban-kettle -f`

---

## 🔍 Hardware Debugging & Testing Endpoints

Use these `curl` commands from the terminal to test communication with the polling server and the Kulhad Vercel API.

### Local Polling Server APIs
*   **Check Registered Devices:**
    ```bash
    curl http://localhost:5000/api/devices
    ```
*   **Check Last Reported Temperature (Instant/Cached):**
    ```bash
    curl http://localhost:5000/api/device/UK_14335C5D48C8/temperature
    ```
*   **Queue a Live Health Check Command:**
    ```bash
    curl -X POST http://localhost:5000/api/device/command \
      -H "Content-Type: application/json" \
      -d '{"messageType":"command","commandType":"control","version":"1.0","commandId":"cmd_test_health","deviceId":"UK_14335C5D48C8","command":{"action":"health_check"}}'
    ```
*   **Queue a Start Dispense Command:**
    ```bash
    curl -X POST http://localhost:5000/api/device/command \
      -H "Content-Type: application/json" \
      -d '{"messageType":"command","commandType":"control","version":"1.0","commandId":"cmd_test_dispense","deviceId":"UK_14335C5D48C8","command":{"action":"start_dispense","parameters":{"jobId":"job_test_123","pumpOperationDuration":13333}}}'
    ```

### Kulhad Cloud Vercel APIs (e.g. `UKTL_BLN_001` - Bellandur)
*   **Check Machine Status on Vercel:**
    ```bash
    curl "https://kulhad.vercel.app/api/MachinesStatus?machineId=UKTL_BLN_001"
    ```
*   **Get Remaining Cups Count:**
    ```bash
    curl -X POST https://kulhad.vercel.app/api/reduce-cups \
      -H "Content-Type: application/json" \
      -d '{"machineId": "UKTL_BLN_001", "cupsToReduce": 0}'
    ```

---

## 📁 Repository Structure

*   `setup.sh` — Installs required dependencies and setups a python `venv`.
*   `install_autostart.sh` — Creates and registers the `systemd` service configuration.
*   `run_all.sh` — Launches backend and frontend in parallel.
*   `polling_server2.py` — Flask-based API server that communicates with the ESP32.
*   `main_app.py` — Core Kivy application entry point.
*   `config.py` — Centralized configuration file (Machine ID, low cup alerts, target temperature).
*   `utils/` — Integrations for RFID, payment API clients, and the hardware monitoring loop.
*   `ui_pages/` — Screen configurations for the ordering, payment, and error views.

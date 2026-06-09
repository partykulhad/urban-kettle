# 🚀 Urban Kettle - Deployment & Installation Guide

This guide provides step-by-step instructions to set up and deploy the **Urban Kettle Chai Ordering Kiosk** application on a new machine. It covers pre-requisite hardware drivers, system libraries, Python virtual environment setup, and start commands.

---

## 📋 System Requirements

*   **Operating System**: Linux (Ubuntu 20.04+, Debian, or Raspberry Pi OS 64-bit recommended)
*   **Python Version**: Python 3.9+ (Python 3.11 or 3.12 is highly recommended)
*   **Hardware Interface**: 
    *   Touchscreen display (1024x600 resolution)
    *   ACR122U RFID Card Reader (USB)
    *   ESP32 hardware dispenser connected via network (acting as local polling server)

---

## 🛠️ Step 1: Install System dependencies (Prerequisites)

Before installing Python packages, you must install several system-level libraries for graphics rendering (Kivy), video playback (OpenCV/GStreamer), and RFID smartcard communication (`pyscard`).

Open your terminal on the new machine and run the following command:

### 1. Core Python and Build Tools
```bash
sudo apt update
sudo apt install -y python3-pip python3-dev python3-venv git build-essential
```

### 2. Kivy Windowing & Graphics Dependencies (SDL2 + OpenGL)
Kivy requires SDL2 and OpenGL drivers to initialize hardware-accelerated touchscreen graphics:
```bash
sudo apt install -y \
    libgl1-mesa-dev \
    libgles2-mesa-dev \
    libegl1-mesa-dev \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libmtdev-dev \
    xclip \
    xsel
```

### 3. Video & Audio Playback (GStreamer)
Required by Kivy/OpenCV to render the screensaver videos smoothly:
```bash
sudo apt install -y \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav
```

### 4. OpenCV & Image Handling Utilities
For QR code cropping, scanning, and screensaver video rendering:
```bash
sudo apt install -y \
    libopencv-dev \
    python3-opencv \
    libjpeg-dev \
    zlib1g-dev
```

### 5. RFID / Smartcard Reader Service (ACR122U + PCSC)
If you are using the ACR122U NFC reader, you must install the PCSC daemon to manage smartcard readers:
```bash
sudo apt install -y \
    pcscd \
    pcsc-tools \
    libpcsclite-dev \
    swig
```
Start and enable the smartcard service:
```bash
sudo systemctl enable pcscd
sudo systemctl start pcscd
```

> [!IMPORTANT]
> **ACR122U Kernel Driver Conflict (Crucial for RFID Reader)**
> Linux kernels often load default drivers (`pn533` and `nfc`) that conflict with the ACR122U driver, causing `pyscard` to fail.
> To resolve this, blacklist the conflicting drivers:
> ```bash
> sudo bash -c "echo 'blacklist pn533' >> /etc/modprobe.d/blacklist.conf"
> sudo bash -c "echo 'blacklist nfc' >> /etc/modprobe.d/blacklist.conf"
> ```
> Reboot the machine after adding these files to apply the blacklist.

---

## 🐍 Step 2: Set Up Python Virtual Environment

It is highly recommended to run the kiosk inside a virtual environment to isolate dependencies.

### Option A: Using a Virtual Environment (Recommended)

1. Navigate to the project directory:
   ```bash
   cd /path/to/urban-kettle-withRFID
   ```

2. Create the virtual environment:
   ```bash
   python3 -m venv venv
   ```

3. Activate it:
   ```bash
   source venv/bin/activate
   ```

4. Upgrade `pip` to the latest version:
   ```bash
   pip install --upgrade pip
   ```

5. Install basic application requirements:
   ```bash
   pip install -r requirements.txt
   ```

6. Install main GUI, RFID, and hardware communication packages:
   ```bash
   pip install kivy opencv-python numpy requests pyscard
   ```

### Option B: System-wide Installation (Kiosk Mode)
If you are setting up a dedicated single-purpose kiosk device and want to run it globally:
```bash
# Note: Modern Linux distributions (PEP 668) may require '--break-system-packages'
pip install --break-system-packages -r requirements.txt
pip install --break-system-packages kivy opencv-python numpy requests pyscard
```

---

## ⚙️ Step 3: Device Configuration Check

Before running the application, make sure the local machine configurations match the physical hardware:

1. **Check `config.py`**:
   Ensure the `DEVICE_ID` matches your ESP32 physical MAC address:
   ```python
   DEVICE_ID = "UK_XXXXXXXXXXXX"  # Update with your ESP32's ID
   ```

2. **Network IP Setting**:
   If running on a Raspberry Pi serving a local network hotspot for the ESP32, verify the server IP in `utils/hardware_monitor.py` matches the router gateway (usually `http://192.168.4.1:5000` or similar).

---

## 🚀 Step 4: Starting the Application

The system requires two processes to run simultaneously:
1. **Backend Server** (`polling_server2.py`): Manages communications with the ESP32.
2. **Frontend UI** (`main_app.py`): Displays Kivy kiosk GUI and handles touchscreen events.

### Method 1: Using the Startup Script (Recommended)
We provide a unified shell script that starts the backend in background, sets Kivy graphic flags for optimal performance, and launches the UI:
```bash
# Make files executable
chmod +x run_all.sh wait_for_display.sh launch_pi.sh

# Run the complete system
./run_all.sh
```

### Method 2: Dynamic Python Runner
You can run the python script which performs dynamic dependency verification before running the UI:
```bash
python3 run_with_dependencies.py
```

### Method 3: Manual Execution
If you want to debug each module in separate terminal windows:
*   **Terminal 1 (Backend Server):**
    ```bash
    python3 polling_server2.py
    ```
*   **Terminal 2 (Frontend Kivy UI):**
    ```bash
    python3 main_app.py
    ```

---

## 🔄 Step 5: (Optional) Set up Auto-Start on System Boot

If this machine is a dedicated customer-facing kiosk, you can set it up to launch automatically whenever the machine turns on.

1. Run the systemd autostart setup script:
   ```bash
   chmod +x install_autostart_run_all.sh
   sudo ./install_autostart_run_all.sh
   ```

2. **Useful commands to manage the auto-start service**:
   *   **Start Kiosk**: `sudo systemctl start urban-kettle-autostart`
   *   **Stop Kiosk**: `sudo systemctl stop urban-kettle-autostart`
   *   **Check Status**: `sudo systemctl status urban-kettle-autostart`
   *   **Check Live Logs**: `sudo journalctl -u urban-kettle-autostart -f`

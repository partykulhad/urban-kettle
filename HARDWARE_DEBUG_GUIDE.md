# Hardware Monitor Debugging Guide

## Debugging Added to hardware_monitor.py

### What You'll See in Terminal:

```
--- DEBUG: get_latest_error() called ---
DEBUG: Checking if device connected (Base URL: http://192.168.4.200:5000)
DEBUG: Checking device connection via API call to http://192.168.4.200:5000/api/devices
DEBUG: API response status code: 200
DEBUG: Found 0 devices.
DEBUG: No devices found in API response.
DEBUG: Device NOT connected - returning error
```

---

## Handshake Flow Explained:

### STEP 1: ESP32 Registers (ESP32's Job, Not main_app.py)
```
ESP32 → POST http://polling_server:5000/api/device/handshake
Body: {
  "deviceId": "UK_54E1AD607DBC",
  "deviceType": "hardware_controller",
  "firmwareVersion": "2.1.5"
}

polling_server2.py → Stores in devices[] list
```

### STEP 2: main_app.py Checks Registration (Every 2 seconds)
```
main_app.py → check_hardware_errors()
    ↓
hardware_monitor.get_latest_error()
    ↓
hardware_monitor.is_device_connected()
    ↓
GET http://192.168.4.200:5000/api/devices
    ↓
Response: {"devices": ["UK_54E1AD607DBC"]}  ← If ESP32 registered
OR
Response: {"devices": []}  ← If ESP32 not registered
```

---

## Debug Output Meanings:

### ✅ WHEN HANDSHAKE EXISTS:
```
DEBUG: Checking device connection via API call to http://192.168.4.200:5000/api/devices
DEBUG: API response status code: 200
DEBUG: Found 1 devices.
DEBUG: Handshake complete (device found: UK_54E1AD607DBC)
DEBUG: Device IS connected - checking health data
```

### ❌ WHEN NO HANDSHAKE:
```
DEBUG: Checking device connection via API call to http://192.168.4.200:5000/api/devices
DEBUG: API response status code: 200
DEBUG: Found 0 devices.
DEBUG: No devices found in API response.
DEBUG: Device NOT connected - returning error
```

### ❌ WHEN SERVER NOT REACHABLE:
```
DEBUG: Checking device connection via API call to http://192.168.4.200:5000/api/devices
DEBUG: Error checking device connection: HTTPConnectionPool(host='192.168.4.200', port=5000): Max retries exceeded...
DEBUG: Device NOT connected - returning error
```

---

## What APIs Are Being Hit:

| When | API | URL | Purpose |
|------|-----|-----|---------|
| Every 2s | GET /api/devices | http://192.168.4.200:5000/api/devices | Check if ESP32 registered |
| After handshake | GET /api/device/{id}/history | http://192.168.4.200:5000/api/device/UK_XXX/history | Get health data |

---

## Navigation Flow with Debug:

```
Time  | Debug Output | Screen
------|--------------|-------
0s    | check_hardware_errors() starts | Payment Method
2s    | DEBUG: Found 0 devices | Payment Method
2s    | Device NOT connected | 
2s    | Hardware error detected: Hardware Not Connected | Hardware Error Page
4s    | DEBUG: Found 0 devices | Hardware Error Page
4s    | Device NOT connected |
5s    | [ESP32 CONNECTS]
5s    | ESP32 → POST /api/device/handshake |
6s    | DEBUG: Found 1 devices | Hardware Error Page
6s    | DEBUG: Handshake complete |
6s    | Device IS connected |
6s    | No error → Navigate back | Payment Method Page ✅
```

---

## How to Test:

### Option 1: With Test Server (Simulated)
```bash
# Terminal 1: Start test server
python3 test_hardware_navigation.py

# Terminal 2: Run app
python3 main_app.py

# Watch terminal for DEBUG output
```

### Option 2: With Real ESP32
```bash
# Make sure ESP32 is powered on and WiFi connected
# Run app
python3 main_app.py

# Watch DEBUG output to see when ESP32 registers
```

---

## Key Points:

1. **ESP32 initiates handshake** by calling POST /api/device/handshake
2. **main_app.py confirms handshake exists** by calling GET /api/devices
3. **If devices list is not empty** = Handshake confirmed
4. **If devices list is empty** = No handshake, show error page
5. **Debug shows every API call** and response for troubleshooting

---

## Remove Debug Later:

To remove debug output, search for `print(\"DEBUG:` in hardware_monitor.py and delete those lines.

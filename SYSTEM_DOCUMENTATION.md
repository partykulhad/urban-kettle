# Urban Kettle System Documentation

**Version:** 2.0  
**Last Updated:** December 1, 2025  
**Machine ID:** KH-01

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [How to Run](#how-to-run)
4. [Core Application Files](#core-application-files)
5. [UI Pages](#ui-pages)
6. [Utility Modules](#utility-modules)
7. [Server Components](#server-components)
8. [Complete User Flow](#complete-user-flow)
9. [API Integration](#api-integration)
10. [Hardware Communication](#hardware-communication)
11. [Implementation Status](#implementation-status)

---

## System Overview

Urban Kettle is a smart tea dispenser kiosk application running on Raspberry Pi with a 7-inch touchscreen (1024x600 resolution). The system handles:

- **Payment Processing**: UPI QR codes and RFID card payments
- **Dispensing Control**: Multi-cup tea dispensing with ESP32 hardware
- **Hardware Monitoring**: Real-time temperature and cup sensor monitoring
- **Screensaver Management**: Dynamic video screensavers from cloud
- **Maintenance Access**: Special RFID cards for maintenance operations

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi (Main App)                   │
│                                                              │
│  ┌──────────────┐     ┌──────────────┐    ┌──────────────┐ │
│  │  main_app.py │────▶│  UI Pages    │───▶│   Kivy UI    │ │
│  │   (Kivy)     │     │  (Screens)   │    │  (Display)   │ │
│  └──────────────┘     └──────────────┘    └──────────────┘ │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Utility Modules                         │  │
│  │  • API Client (Cloud APIs)                           │  │
│  │  • Hardware Monitor                                  │  │
│  │  • RFID Reader (ACR122U)                            │  │
│  │  • QR Utils                                          │  │
│  │  • Screensaver Manager                              │  │
│  └──────────────────────────────────────────────────────┘  │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          ├────────▶ Cloud APIs (kulhad.vercel.app)
          │          • Machine Status
          │          • Cup Management
          │          • Payment QR Generation
          │          • RFID Authentication
          │          • Screensaver Videos
          │
          └────────▶ Local Polling Server (localhost:5000)
                     │
                     ▼
                  ESP32 Hardware
                  • Dispenser Control
                  • Solenoid Valve
                  • Temperature Sensor (PT100)
                  • Cup Sensor
```

---

## How to Run

### **Step 1: Install Dependencies**

**Option A: Using Virtual Environment (Recommended)**
```bash
cd /home/mitron/Documents/urban-kettle

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install packages
pip install -r requirements.txt
```

**Option B: Install in System**
```bash
cd /home/mitron/Documents/urban-kettle
pip3 install kivy opencv-python requests pyscard pillow
```

### **Step 2: Start the Application**

```bash
python3 main_app.py
```

That's it! The GUI will open automatically.

### **Step 3: What You'll See**

The app opens to the **Payment Method Page** with:

**Top Right Corner:**
- **Cups Counter** - Shows remaining cups in machine (updates every 3 seconds)

**Main Screen - Two Payment Options:**

**Left Side: UPI Card**
- Click this to order via UPI payment
- Takes you to cup selection page

**Right Side: RFID Card**
- Click to show instructions for RFID payment
- Tap your RFID card on the reader to pay instantly
- Regular cards: Deduct balance, dispense 1 cup
- Maintenance cards: Opens solenoid for cleaning

### **Step 4: Complete Flow After Clicking UPI**

1. **Click UPI** → Selection Page opens
2. **Select cups** (use +/- buttons, max 5 cups)
3. **Click "Proceed to Payment"** → QR code appears
4. **Scan QR with phone** → Pay via UPI
5. **Wait for confirmation** → Payment Processing screen
6. **Place Cup page** → Put cup in holder
7. **Click "Confirm to Dispense"** → Dispensing starts
8. **Wait 8 seconds** → Tea dispensed
9. **If multiple cups** → Repeat place cup + dispense for each
10. **Thank You page** → Done! Auto-returns to home after 5 seconds

---

### **Important: Raspberry Pi Configuration**

When running on Raspberry Pi, you MUST change the API base URL:

**File:** `utils/hardware_monitor.py` (Line 19)

```python
# Change this line:
self.api_base_url = "http://192.168.68.162:5000"

# To this for Raspberry Pi:
self.api_base_url = "http://192.168.4.1:5000"
```

This is the ESP32's IP address on the Raspberry Pi network.

---

## Core Application Files

### **main_app.py**

**Purpose:** Main application entry point and coordinator

**Key Responsibilities:**
- Initializes Kivy application with 7-inch tablet dimensions (1024x600)
- Creates and manages all screen pages
- Coordinates payment flow (UPI/RFID)
- Handles cup dispensing logic (single and multiple cups)
- Manages screensaver activation/deactivation
- Integrates with all utility modules

**Important Variables:**
- `MACHINE_ID = "KH-01"` - Machine identifier
- `INACTIVE_TIMEOUT = 30` - Screensaver timeout in seconds
- `selected_cups` - Number of cups to dispense
- `current_cup_number` - Current cup being dispensed

**Main Methods:**
- `show_*_page()` - Navigate between screens
- `generate_qr_code()` - Create payment QR codes
- `check_payment_status()` - Poll for payment completion
- `start_dispensing_process()` - Begin multi-cup dispensing
- `handle_cup_completion()` - Move to next cup or finish

**App Flow:**
```
Start → Payment Method → Selection → Payment/RFID Auth → 
Place Cup → Dispensing → Thank You → Reset
```

---

### **polling_server2.py**

**Purpose:** Local HTTP server for ESP32 communication

**Port:** 5000  
**Protocol:** Client-Server Polling Architecture

**Key Endpoints:**

1. **POST /api/device/handshake**
   - Device registration and session management
   - Returns configuration (temperature, pump duration, etc.)

2. **POST /api/device/health**
   - Receives ESP32 health heartbeats (every 30s)
   - Stores temperature and sensor data

3. **GET /api/device/commands/pending**
   - ESP32 polls for queued commands
   - Returns next command or 204 if queue empty

4. **POST /api/device/command/result**
   - ESP32 sends command execution results
   - Stores completion status

5. **POST /api/device/command**
   - **Synchronous endpoint** - sends command and waits for ESP32 response
   - Used by main app for dispense/solenoid commands
   - Timeout: 30 seconds

6. **GET /api/status**
   - Server health check
   - Returns connected devices, queued commands, etc.

**Command Queue System:**
- Commands queued per device ID
- FIFO (First In, First Out)
- ESP32 polls every few seconds
- Commands timeout if ESP32 doesn't respond

**Logging:**
- All JSON requests/responses logged to console
- Timestamped with millisecond precision
- Helpful for debugging ESP32 communication

---

## UI Pages

All UI pages are in `ui_pages/` directory and inherit from `kivy.uix.screenmanager.Screen`.

### **payment_method_page.py**

**Purpose:** Initial screen - choose UPI or RFID payment

**Features:**
- Displays Urban Kettle logo
- Two payment cards: UPI (left) and RFID (right)
- Real-time cups counter (top-right corner)
- Background cup count refresh every 3 seconds
- RFID card polling (ACR122U reader)
- Maintenance card detection and handling
- Auto-navigates to machine empty page if cups = 0

**Key Methods:**
- `on_upi_selected()` - Navigate to cup selection
- `on_rfid_clicked()` - Show RFID instruction popup
- `handle_rfid_card_detected()` - Process RFID card tap
- `authenticate_rfid_card()` - AES authentication with cloud
- `send_maintenance_solenoid_command()` - **[IMPLEMENTED]** Trigger solenoid for maintenance
- `refresh_cups_count()` - Update cups display

**RFID Cards:**
- **Regular Cards:** Deduct balance, dispense 1 cup
- **Maintenance Cards:** Unlock solenoid valve for cleaning/refilling

**API Calls:**
- Maintenance solenoid: `POST localhost:5000/api/device/command` (action: open_solenoid)

---

### **selection_page.py**

**Purpose:** Select number of cups to order

**Features:**
- Dynamic cup counter (1-5 cups)
- Large +/- buttons for adjustment
- Shows price per cup and total amount
- Maximum cups limited by machine availability
- Auto-refresh from payment method page

**Key Methods:**
- `increment_cups()` - Increase count
- `decrement_cups()` - Decrease count
- `get_cup_count()` - Return selected cups
- `set_max_cups()` - Limit based on availability

---

### **payment_page.py**

**Purpose:** Display QR code for UPI payment

**Features:**
- Large QR code display (300x300px)
- Cropped and optimized QR image
- 2-minute countdown timer
- Real-time payment status polling (every 1 second)
- Auto-navigation on payment success/expiry
- Cancel button for manual abort

**Payment Flow:**
1. Generate QR via API (parallel status check)
2. Display QR with timer
3. Poll payment status every second
4. On "paid" status → Transaction Processing → Dispensing
5. On "expired" status → Auto-cancel → QR Expired Page

**Key Methods:**
- `update()` - Set QR image and data
- `start_timer()` - Begin countdown
- `update_status()` - Show payment status message
- `stop_timer()` - Cancel timer on completion

---

### **loading_page.py**

**Purpose:** Transitional loading screen

**Features:**
- Shows spinning animation
- Customizable message
- Used during QR generation, API calls, etc.

---

### **transaction_processing_page.py**

**Purpose:** Brief confirmation after payment

**Features:**
- Success checkmark animation
- "Payment Successful" message
- 4-second display before dispensing
- Modern, premium design

---

### **dispensing_page.py**

**Purpose:** Multi-cup dispensing orchestration

**Contains Two Classes:**

#### **1. PlaceCupPage**

**Purpose:** Instruct user to place cup before dispensing

**Features:**
- "Place cup in holder" instruction
- Cup image display
- Cup detection via hardware monitor
- "Cup Placed - Confirm to Dispense" button
- Button disabled until cup detected

**Key Methods:**
- `on_continue_pressed()` - **[IMPLEMENTED]** Triggers dispense command
- `send_dispense_command()` - **[IMPLEMENTED]** API call to start dispensing
- `check_cup_sensor()` - Poll cup status every 0.5s
- `update_cup_info()` - Show cup X of Y

**API Call:**
```
POST localhost:5000/api/device/command
Action: start_dispense
Parameters: { jobId: "job_xxxx" }
```

**Debug Output:**
- Job ID and Command ID
- Full JSON payload
- Response status and data
- Clear success/failure messages

#### **2. DispensingPage**

**Purpose:** Show dispensing progress animation

**Features:**
- Urban Kettle logo
- "DISPENSING..." text
- Cup counter (Cup X of Y)
- Dispensing video playback
- Progress bar (0-100%)
- 8-second animation duration
- Auto-advance to next cup or thank you page

**Key Methods:**
- `start_dispensing_animation()` - Begin progress
- `update_progress()` - Increment every 0.08s
- `set_cup_info()` - Update cup counter
- `stop_animations()` - Clean up on completion

---

### **thank_you_page.py**

**Purpose:** Final screen after all cups dispensed

**Features:**
- "Thank You!" message
- "Enjoy your tea" subtitle
- 5-second auto-return to home
- Manual "Order Again" button

---

### **screensaver_page.py**

**Purpose:** Video screensaver during idle periods

**Features:**
- Full-screen video playback using OpenCV
- Dynamic video from cloud (updated automatically)
- 30fps smooth playback
- Activates after 30 seconds inactivity
- Touch anywhere to deactivate

**Video Management:**
- Videos stored in `assets/screensaver_videos/`
- Current video: `assets/screensaver_current.mp4` (symlink)
- Auto-downloads new videos from API
- Cleans up old videos

---

### **qr_expired_page.py**

**Purpose:** Show when payment QR code expires

**Features:**
- Sad icon/illustration
- "QR Code Expired" message
- Two options:
  - "Try Again" - Return to selection
  - "Cancel" - Return to payment method

---

### **machine_empty_page.py**

**Purpose:** Display when machine has no cups or is offline

**Features:**
- "Out of Service" message
- Shows remaining cups (0)
- Animated icon
- "Refiller is on the way" message
- Auto-refresh every 5 seconds
- Auto-navigate when cups available

---

### **rfid_auth_page.py**

**Purpose:** RFID authentication progress screen

**Features:**
- 3-step authentication process:
  1. Reading card
  2. Authenticating
  3. Verifying
- Shows remaining balance on success
- Error messages on failure
- Auto-navigates after 1.5-3 seconds

---

### **hardware_debug_page.py**

**Purpose:** Developer debugging screen for hardware

**Features:**
- Real-time temperature display
- Cup sensor status
- Device connection status
- Manual command testing
- Accessible via "HW" button (removed for performance)

---

## Utility Modules

All utility modules are in `utils/` directory.

### **api_client.py**

**Purpose:** Centralized API client for cloud services

**Base URL:** `https://kulhad.vercel.app/api`

**Key Methods:**

1. **`check_machine_status(machine_id)`**
   - GET `/MachinesStatus?machineId={id}`
   - Returns: `{ success, data: { status, machineName } }`
   - Used to check if machine is online/offline

2. **`get_remaining_cups(machine_id)`**
   - POST `/reduce-cups` with `{ machineId, cupsToReduce: 0 }`
   - Returns: `{ success, cups, machineId, machineName }`
   - Query-only (cupsToReduce=0)

3. **`reduce_cups(machine_id, cups_count)`**
   - POST `/reduce-cups` with `{ machineId, cupsToReduce: count }`
   - Returns: `{ success, previousCups, newCups, message }`
   - Actually reduces inventory

4. **`generate_payment_qr(machine_id, num_cups)`**
   - POST `/qr/generate` with `{ machineId, numberOfCups }`
   - Returns: `{ success, imageUrl, amount, id, transactionId }`
   - Creates UPI payment QR code

5. **`check_payment_status(qr_code_id)`**
   - GET `/qr/status/{id}`
   - Returns: `{ message: "active"|"paid"|"expired" }`
   - Polls every second for payment

6. **`cancel_payment(qr_code_id)`**
   - POST `/qr/cancel/{id}`
   - Returns: `{ success, message }`
   - Cancels pending payment

7. **`validate_rfid_card_aes(rfid_handler)`**
   - POST `https://www.ukteawallet.com/api/rfid/auth/start`
   - AES encryption authentication
   - Returns: `{ success, authenticated, dispensed, remainingBalance, cardCategory }`
   - Handles both regular and maintenance cards

**Error Handling:**
- All methods use try-except
- Returns None on failure
- Logs errors to console

---

### **hardware_monitor.py**

**Purpose:** Background service for ESP32 hardware communication

**Device ID:** `UK_14335C5D48C8` (hardcoded)  
**API Base URL:** `http://192.168.68.162:5000` (ESP32 polling server)

**Key Responsibilities:**
1. Auto-start polling_server2.py on app launch
2. Send device handshake to ESP32
3. Fetch temperature from PT100 sensor every 1 second
4. Send temperature to cloud database
5. Query cup sensor status on demand

**Key Methods:**

1. **`start_mock_server()`**
   - Starts polling_server2.py as subprocess
   - Redirects output to `polling_server.log`
   - Waits for server to respond on port 5000
   - Checks `/api/status` endpoint

2. **`wait_for_handshake()`**
   - Continuously sends handshake to ESP32
   - Background thread (non-blocking)
   - Retries every 2 seconds until accepted

3. **`_temperature_loop()`**
   - Background thread
   - Fetches temperature every 1 second
   - POST to `/api/device/health`
   - Sends to cloud: `POST /api/machine-temperature`

4. **`get_cup_status()`**
   - Query cup sensor via `/api/device/health`
   - Returns: `True` if cup present, `False` otherwise
   - Used by PlaceCupPage to enable dispense button

5. **`get_temperature()`**
   - Returns last known temperature
   - Cached from background loop

**Temperature Flow:**
```
PT100 Sensor → ESP32 → Polling Server → Hardware Monitor → Cloud DB
```

---

### **qr_utils.py**

**Purpose:** QR code image processing utilities

**Key Methods:**

1. **`load_qr_from_url(image_url)`**
   - Downloads QR image from URL
   - Converts to PIL Image
   - Returns Image object or None

2. **`detect_and_crop_qr(image)`**
   - Uses OpenCV to detect QR code
   - Crops and centers QR code
   - Adds padding
   - Returns cropped Image

3. **`create_qr_placeholder(width, height)`**
   - Creates fallback QR image on error
   - Returns simple white rectangle

**QR Processing Pipeline:**
```
API URL → Download → Detect QR → Crop & Center → Display
```

---

### **screensaver_manager.py**

**Purpose:** Automatic screensaver video management

**Video Storage:**
- Cache dir: `assets/screensaver_videos/`
- Current video: `assets/screensaver_current.mp4` (symlink)
- Metadata: `assets/screensaver_videos/video_cache.json`

**Key Methods:**

1. **`update_video_async(callback)`**
   - Background thread
   - Fetches video info from cloud
   - Downloads if new video available
   - Calls callback when ready

2. **`_check_and_update_video()`**
   - GET `/api/machines/{machineId}/videos`
   - Compares videoId with cached
   - Downloads new video if different
   - Creates symlink to current

3. **`_cleanup_old_videos(current_video_id)`**
   - Removes old cached videos
   - Keeps only current video

**Video Update Flow:**
```
Cloud API → Check videoId → Download (if new) → 
Cache → Symlink → Callback → UI Update
```

---

### **rfid_reader.py**

**Purpose:** ACR122U RFID reader interface

**Key Components:**

1. **`RFIDAuthHandler` Class:**
   - Manages NFC connection
   - Handles card authentication
   - AES sector access
   - Read/write operations

2. **`RFIDReader` Class:**
   - Continuous card polling
   - Card detection events
   - Callback system
   - Handles card insertion/removal

**Key Methods:**

1. **`start_polling()`**
   - Background thread
   - Polls every 500ms
   - Detects new cards
   - Fires callbacks

2. **`stop_polling()`**
   - Stops background thread
   - Releases NFC connection

3. **Card Detection Flow:**
```
Poll → Card Detected → Read UID → 
Fire Callback → App Handles Authentication
```

**Supported Card Types:**
- MIFARE Classic
- MIFARE DESFire
- Custom AES authentication

---

## Server Components

### **polling_server2.py**

Detailed in [Core Application Files](#polling_server2py) section.

**Key Features:**
- Client-Server polling architecture
- Command queue per device
- Synchronous command execution (waits for ESP32)
- Health monitoring
- OTA update support
- Full JSON request/response logging

---

## Complete User Flow

### **Flow 1: UPI Payment → Dispense**

```
1. App Start
   ↓
2. Payment Method Page (cups counter shows, RFID polling starts)
   ↓
3. User taps UPI card
   ↓
4. Selection Page (choose 1-5 cups)
   ↓
5. User selects 2 cups, taps "Proceed to Payment"
   ↓
6. Loading Page (brief)
   ↓
7. API: Generate QR code + Check machine status (parallel)
   ↓
8. Payment Page (QR displayed, 2-min timer starts)
   ↓
9. Background: Poll payment status every 1 second
   ↓
10. User scans QR with phone → Payment successful
    ↓
11. API: Reduce cups (-2 cups from inventory)
    ↓
12. Transaction Processing Page (4 seconds)
    ↓
13. Place Cup Page - Cup 1 of 2
    ↓
14. Background: Check cup sensor every 0.5s
    ↓
15. Cup detected → Button enabled
    ↓
16. User taps "Confirm to Dispense"
    ↓
17. API: Send dispense command (start_dispense) → [IMPLEMENTED]
    ↓
18. Dispensing Page - Cup 1 of 2 (8-second animation)
    ↓
19. Cup 1 complete → Place Cup Page - Cup 2 of 2
    ↓
20. Repeat steps 14-18 for Cup 2
    ↓
21. All cups complete → Thank You Page
    ↓
22. After 5 seconds → Return to Payment Method Page
```

---

### **Flow 2: RFID Payment → Dispense**

```
1. App Start
   ↓
2. Payment Method Page (RFID polling every 0.5s)
   ↓
3. User taps RFID card on reader
   ↓
4. Card UID detected → RFID Auth Page
   ↓
5. API: AES authentication (www.ukteawallet.com)
   ↓
6. Authentication successful
   ↓
7. Check balance → Deduct 1 cup cost
   ↓
8. API: Reduce cups (-1 cup from inventory)
   ↓
9. Transaction Processing Page (4 seconds)
   ↓
10. Place Cup Page - Cup 1 of 1
    ↓
11. Cup detected → "Confirm to Dispense"
    ↓
12. API: Send dispense command → [IMPLEMENTED]
    ↓
13. Dispensing Page (8-second animation)
    ↓
14. Thank You Page
    ↓
15. Return to Payment Method Page
```

---

### **Flow 3: Maintenance Mode**

```
1. Payment Method Page
   ↓
2. Maintenance RFID card detected
   ↓
3. RFID Auth Page
   ↓
4. API: Authentication → cardCategory = "maintenance"
   ↓
5. API: Send solenoid command (open_solenoid) → [IMPLEMENTED]
   ↓
6. ESP32: Open solenoid valve for X seconds
   ↓
7. Success message on auth page
   ↓
8. After 3 seconds → Return to Payment Method Page
```

---

### **Flow 4: Screensaver Activation**

```
1. On Payment Method Page or Machine Empty Page
   ↓
2. No user interaction for 30 seconds
   ↓
3. Activate screensaver → Full-screen video playback
   ↓
4. User touches screen → Deactivate
   ↓
5. Background: Check machine status + cups
   ↓
6. If online + cups > 0 → Payment Method Page
7. If offline or cups = 0 → Machine Empty Page
```

---

## API Integration

### **Cloud APIs (kulhad.vercel.app)**

All API calls handled by `utils/api_client.py`.

**Machine Management:**
- `GET /api/MachinesStatus?machineId=KH-01` - Check online/offline
- `POST /api/reduce-cups` - Query or reduce cup inventory
- `GET /api/machines/KH-01/videos` - Get screensaver video

**Payment Processing:**
- `POST /api/qr/generate` - Create UPI payment QR
- `GET /api/qr/status/{id}` - Poll payment status
- `POST /api/qr/cancel/{id}` - Cancel payment

**RFID Authentication:**
- `POST https://www.ukteawallet.com/api/rfid/auth/start` - AES auth

**Temperature Monitoring:**
- `POST /api/machine-temperature` - Send temperature data

---

### **Local APIs (localhost:5000)**

All hardware commands via `polling_server2.py`.

**Device Management:**
- `POST /api/device/handshake` - Register ESP32
- `POST /api/device/health` - Receive heartbeat

**Command System:**
- `GET /api/device/commands/pending?deviceId=UK_14335C5D48C8` - ESP32 polls
- `POST /api/device/command/result` - ESP32 sends results
- `POST /api/device/command` - **Main app sends commands (synchronous)**

**Server Status:**
- `GET /api/status` - Health check
- `GET /api/devices` - List connected devices

---

## Hardware Communication

### **ESP32 Connection**

**IP Address:** 192.168.68.162  
**Port:** 5000  
**Protocol:** HTTP Polling

**Communication Pattern:**
```
Main App → Polling Server (localhost:5000)
                ↓
         Command Queue
                ↓
ESP32 polls → GET /api/device/commands/pending
                ↓
         ESP32 executes command
                ↓
ESP32 → POST /api/device/command/result
                ↓
         Polling Server → Returns to Main App
```

**Polling Intervals:**
- ESP32 health: Every 30 seconds
- ESP32 commands: Every 2-5 seconds (configurable)
- Main app payment: Every 1 second
- Cup sensor: Every 0.5 seconds

---

### **Sensors & Actuators**

**1. PT100 Temperature Sensor**
- Type: Analog temperature probe
- Range: 0-100°C
- Update: Every 1 second
- Flow: ESP32 → Polling Server → Hardware Monitor → Cloud

**2. Cup Sensor**
- Type: Digital proximity/pressure sensor
- States: cup_present / no_cup
- Update: On-demand query
- Used by: PlaceCupPage to enable dispense

**3. Solenoid Valve**
- Function: Water flow control
- Trigger: Maintenance card
- Duration: Configurable (default 10 seconds)
- Command: open_solenoid

**4. Dispenser (Pump/Motor)**
- Function: Tea dispensing
- Trigger: Confirm to Dispense button
- Duration: 8 seconds per cup
- Command: start_dispense

---

## Implementation Status

### ✅ **What's Currently Working**

**Payments:**
- UPI QR code payment (generates QR, polls status, processes payment)
- RFID card payment (AES authentication, balance deduction)
- Maintenance RFID cards (triggers solenoid valve)

**Dispensing:**
- Dispense command API implemented (`start_dispense`)
- Solenoid command API implemented (`open_solenoid`)
- Multi-cup dispensing flow (place cup → dispense → repeat)
- Progress animation (8 seconds per cup)

**Machine Management:**
- Real-time cup counter (updates every 3 seconds)
- Automatic cup reduction after payment
- Machine status checking (online/offline)
- Auto-navigation to empty page when cups = 0

**Hardware:**
- Temperature monitoring (PT100 sensor → Cloud, every 1 second)
- Polling server auto-starts with main app
- ESP32 handshake and connection
- Debug logging for all API calls

**UI:**
- All screens functional and designed
- Screensaver with cloud video updates
- 7-inch tablet optimized (1024x600)

---

### ❌ **What's NOT Working (Needs ESP32)**

**Cup Sensor:**
- Currently returns dummy `True` value
- Button always enables after delay
- Needs ESP32 to report actual sensor status

**Pump Status:**
- Uses fixed 8-second timer
- No real-time pump feedback
- Progress bar is simulated
- Needs ESP32 to report actual pump state

**Impact:** App works without these, but cup sensor should verify cup placement, and pump status should show real progress.

---

## Appendix: File Structure

```
urban-kettle/
├── main_app.py                    # Main application
├── polling_server2.py             # ESP32 polling server
├── launch_pi.sh                   # Raspberry Pi launcher
│
├── ui_pages/                      # All screen pages
│   ├── payment_method_page.py     # Home screen
│   ├── selection_page.py          # Cup selection
│   ├── payment_page.py            # QR payment
│   ├── loading_page.py            # Loading transitions
│   ├── transaction_processing_page.py
│   ├── dispensing_page.py         # Place cup + Dispensing
│   ├── thank_you_page.py          # Completion
│   ├── screensaver_page.py        # Video screensaver
│   ├── qr_expired_page.py         # QR timeout
│   ├── machine_empty_page.py      # No cups / Offline
│   ├── rfid_auth_page.py          # RFID authentication
│   └── hardware_debug_page.py     # Debug interface
│
├── utils/                         # Utility modules
│   ├── api_client.py              # Cloud API interface
│   ├── hardware_monitor.py        # ESP32 communication
│   ├── qr_utils.py                # QR processing
│   ├── screensaver_manager.py     # Video management
│   └── rfid_reader.py             # ACR122U interface
│
├── assets/                        # Media files
│   ├── urban_ketl_logo.png
│   ├── upilogo.png
│   ├── rfidlogo.png
│   ├── placecup.png
│   ├── dispensing.mp4
│   └── screensaver_videos/        # Video cache
│
└── SYSTEM_DOCUMENTATION.md        # This file
```

---

**End of Documentation**

For questions or issues, check the logs in:
- `polling_server.log` - Polling server output
- Terminal output - Main app debug logs

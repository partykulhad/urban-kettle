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










1. Project Overview

Urban Kettle is a self-service chai (tea) vending machine kiosk running on a 7-inch touch tablet (881×661 px, mounted upside-down, auto-rotated). The UI is built with Python + Kivy and communicates with an ESP32 microcontroller through a local polling bridge server. Payments are processed via Razorpay UPI QR codes and optionally via RFID prepaid cards.

---
2. System Architecture

┌─────────────────────────────────────────────────────────────┐
│                      Kivy UI (main_app.py)                  │
│  selection → payment/RFID → place_cup → dispensing → thanks │
└─────────────┬───────────────────────┬───────────────────────┘
              │                       │
     localhost:5000            kulhad.vercel.app
  (polling_server2.py)       (Kulhad Cloud API)
              │                       │
         ESP32 (Wi-Fi)         Razorpay / Wallet
              │
    Physical hardware:
    PT100 sensor, pump,
    heater, solenoid valve

Key Layers

┌──────────────┬──────────────────────────────────────┬────────────────────────────────────────┐
│    Layer     │              Technology              │                Purpose                 │
├──────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ UI           │ Python 3.9 + Kivy 2.3                │ All screens, touch events, animations  │
├──────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ Local bridge │ polling_server2.py (Flask) on port   │ Relay commands to ESP32, cache sensor  │
│              │ 5000                                 │ data                                   │
├──────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ ESP32 comms  │ HTTP polling (ESP32 polls every      │ Dispense, flush, health check commands │
│              │ 10–30 s)                             │                                        │
├──────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ Cloud        │ kulhad.vercel.app → Razorpay         │ QR generation, payment status, cup     │
│ payment      │                                      │ count                                  │
├──────────────┼──────────────────────────────────────┼────────────────────────────────────────┤
│ RFID auth    │ pyscard + ACR122U + ukteawallet.com  │ 5-step AES card authentication         │
└──────────────┴──────────────────────────────────────┴────────────────────────────────────────┘

---
3. Configuration (config.py)

┌───────────────────────────┬───────────────────────┬───────────────────────────────────────────┐
│         Constant          │         Value         │                Description                │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ DEVICE_ID                 │ UK_14335C5D4340       │ ESP32 MAC-based ID — set manually, never  │
│                           │                       │ auto-detected                             │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ MACHINE_ID                │ UKL_BLR_004           │ Kulhad cloud machine identifier           │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ RFID_MACHINE_ID           │ UK_0007               │ ukteawallet.com machine ID                │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ SERVING_TEMP              │ 80.0 °C               │ Minimum temperature before orders allowed │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ PUMP_FLOW_RATE_ML_PER_SEC │ 9.0                   │ Calibrated at 540 ml/min                  │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ POLLING_SERVER_URL        │ http://localhost:5000 │ ESP32 bridge                              │
├───────────────────────────┼───────────────────────┼───────────────────────────────────────────┤
│ ml_to_pump_ms(ml)         │ formula               │ (ml / 9.0) × 1000 ms — 100 ml = 11,111 ms │
└───────────────────────────┴───────────────────────┴───────────────────────────────────────────┘

---
4. All UI Screens

4.1 Selection Page (selection) — HOME SCREEN

The home screen. User selects 1–5 cups. Displays live cup count.
- On on_enter: RFID polling delegated from payment_method_page instance starts here
- On on_leave: RFID polling stops
- Confirm button → triggers QR prefetch for all counts up to selected, then navigates to payment page
- Cancel button → clears all prefetch cache, returns home
- Inactivity timer: 10 s then screensaver

4.2 Payment Method Page (payment_method)

Never navigated to in the normal user flow — exists only to hold RFID polling logic. show_payment_method_page() in main_app redirects to selection. Used internally as a logic container.

4.3 Loading Page (loading)

Shown while background QR generation is in progress. Animated spinner + cup image. Times out at 30 s and shows error fallback.

4.4 Payment Page (payment)

Shows the Razorpay UPI QR code. 2-minute countdown timer. Polls payment status every 2 s.
- Status active → keep polling
- Status paid → navigate to dispensing flow
- Status expired / timer ends → show QR expired page, auto-cancel

4.5 QR Expired Page (qr_expired)

Shown when 2-minute timer elapses. "Try Again" button returns to selection.

4.6 RFID Auth Page (rfid_auth)

Shown during RFID card authentication (3-step progress display). 9-second timeout. On success → directly to place_cup page with 1 cup pre-selected.

4.7 Place Cup Page (place_cup)

Instructs user to place cup. 30-second countdown timer. "Dispense Now" button.
- On button press: temp pre-check → decrement cups → navigate to dispensing → send ESP32 command in background
- On timeout: return home (last cup) or skip to next cup

4.8 Dispensing Page (dispensing)

Plays dispensing video synchronized to pump duration. Video speed-adjusted to finish in exactly pump_duration_s seconds.
- Primary timer: fires at pump_duration_s → handle_completion()
- handle_completion(): stops + clears video, immediately navigates to thank-you (no intermediate screen)
- Secondary: pump status polling (0.5 s interval, exits on completed/idle×3)
- Safety timeout: max(60 s, pump_duration_s + 30 s)
- Supports per-ml videos: dispensing_90.mp4, dispensing_100.mp4, dispensing_110.mp4, dispensing_120.mp4 — falls back to dispensing.mp4

4.9 Thank You Page (thank_you)

Auto-returns to home after ~5 s. Shows if cups hit 0 → navigates to machine empty page. Triggers auto-flush idle timer.

4.10 Heating Page (heating)

Shown when PT100 < 80 °C. Polls temperature every 1 s via hardware monitor. Redirects home when temperature ≥ 80 °C.

4.11 Hardware Error Page (hardware_error)

Shown on critical ESP32 errors (PT100 > 120 °C, status code 701, 3 read failures, sensor absent 300 s). Checks every 10 s; auto-clears in 5 s if error gone. RFID polling active for maintenance cards.

4.12 Machine Empty Page (machine_empty)

Shown when local_cups_count hits 0 or ESP32 machineState = OFFLINE. Checks cups API every 3 s. Returns home when cups > 0. Two modes: empty (cups ran out) and offline (remotely disabled).

4.13 Flush Page (flush)

Shown during automated maintenance flush. Displays phase: "Flushing water path..." → "Flushing tea path..." → "Cleaning complete!". Guards all new orders while flush is running (flush_in_progress = True).

4.14 Screensaver Page (screensaver)

Full-screen looping video after 30 s of inactivity. Video downloaded from Kulhad API and cached locally. Touch/motion wakes the app.

---
5. Complete User Flows

UPI Payment Flow

Selection → (Confirm) → Loading → Payment (QR, 2 min)
  → (paid) → Place Cup (30 s) → (Dispense Now)
  → Dispensing (video ~11 s) → Thank You (5 s) → Selection

RFID Card Flow

Selection → (tap card) → RFID Auth (9 s max)
  → (success) → Place Cup → Dispensing → Thank You → Selection

Multi-Cup Flow (e.g. 3 cups)

Place Cup [Cup 1 of 3] → Dispensing → Place Cup [Cup 2 of 3] → Dispensing
  → Place Cup [Cup 3 of 3] → Dispensing → Thank You → Selection

Heating Flow

(on startup or idle) Temperature < 80 °C detected
  → Heating Page (live temp, 1 s polling) → temp ≥ 80 °C → Selection

Auto-Flush Flow

(40 min idle after last dispense)
  → Flush Page → Water Flush command (ESP32) → Tea Flush command (ESP32)
  → "Cleaning complete!" → Selection

---
6. Backend API Integrations

6.1 Kulhad Cloud (kulhad.vercel.app)

┌──────────────────────────────────┬────────────────────────────────┬──────────────────────────┐
│             Endpoint             │          When Called           │         Purpose          │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│                                  │                                │ Create Razorpay UPI QR,  │
│ POST /api/direct-payment         │ On QR generation               │ returns imageContent     │
│                                  │                                │ (UPI string) + id +      │
│                                  │                                │ amount                   │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ POST /api/transaction-status     │ Every 2 s on payment page      │ Poll active / paid /     │
│                                  │                                │ expired                  │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ POST /api/qrcode-close           │ On cancel / timeout            │ Invalidate QR on         │
│                                  │                                │ Razorpay                 │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ POST /api/reduce-cups            │ Home screen / global status    │ Read-only cups count     │
│ (cupsToReduce=0)                 │ check                          │                          │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ POST /api/reduce-cups            │ After dispense confirm         │ Deduct N cups            │
│ (cupsToReduce=N)                 │                                │                          │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ GET                              │ Global status monitor (every   │ Check ONLINE/OFFLINE     │
│ /api/MachinesStatus?machineId=X  │ 10 s)                          │                          │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ GET                              │ Boot +                         │ Fetch flushTimeMinutes,  │
│ /api/getMachineData?machineId=X  │ _refresh_machine_config_cache  │ mlToDispense             │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ POST /api/canister-check         │ When local_cups_count == 5     │ Send low-stock alert     │
├──────────────────────────────────┼────────────────────────────────┼──────────────────────────┤
│ POST /api/machine-temperature    │ Every 2 min (hardware monitor) │ Cloud temperature        │
│                                  │                                │ logging                  │
└──────────────────────────────────┴────────────────────────────────┴──────────────────────────┘

6.2 ESP32 Polling Bridge (localhost:5000)

┌────────────────────────────────┬───────────────────────────────┬─────────────────────────────┐
│            Endpoint            │          When Called          │           Purpose           │
├────────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ GET                            │ Every 0.5–20 s                │ PT100 temp, machineState,   │
│ /api/device/{id}/temperature   │                               │ timestamp                   │
├────────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ GET                            │ Every 0.5 s during dispensing │ pumpState, progress,        │
│ /api/device/{id}/pump_status   │                               │ elapsedTime                 │
├────────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ GET /api/device/{id}/history   │ On get_latest_error (fast     │ Recent health data          │
│                                │ path)                         │                             │
├────────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ GET /api/devices               │ On is_device_connected        │ Confirm ESP32 is online     │
├────────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ GET /api/status                │ On startup check              │ Server health               │
├────────────────────────────────┼───────────────────────────────┼─────────────────────────────┤
│ POST /api/device/command       │ Dispense, flush, solenoid,    │ Send commands to ESP32      │
│                                │ settings                      │                             │
└────────────────────────────────┴───────────────────────────────┴─────────────────────────────┘

6.3 Tea Wallet (ukteawallet.com)

Five-step AES authentication for RFID prepaid cards. Endpoints: /api/rfid/auth/start, /api/rfid/auth/step2, /api/rfid/auth/verify.

---
7. Hardware Integrations

7.1 ESP32 Commands Sent

┌──────────────────────┬──────────────────────────┬───────────────────────────────────┐
│        Action        │         Trigger          │            Parameters             │
├──────────────────────┼──────────────────────────┼───────────────────────────────────┤
│ start_dispense       │ Dispense Now button      │ pumpOperationDuration (ms), jobId │
├──────────────────────┼──────────────────────────┼───────────────────────────────────┤
│ water_dispense       │ Auto-flush (water phase) │ jobId                             │
├──────────────────────┼──────────────────────────┼───────────────────────────────────┤
│ tea_dispense         │ Auto-flush (tea phase)   │ jobId                             │
├──────────────────────┼──────────────────────────┼───────────────────────────────────┤
│ solenoid_control     │ Low-temp bypass (legacy) │ duration (ms)                     │
├──────────────────────┼──────────────────────────┼───────────────────────────────────┤
│ update_pump_settings │ mlToDispense changed     │ pumpOperationDuration (ms)        │
└──────────────────────┴──────────────────────────┴───────────────────────────────────┘

7.2 RFID Reader (ACR122U via pyscard)

- FF CA 00 00 00 APDU to read card UID
- RF keep-alive every 2 s to maintain field
- LED control: green (ready), red (authenticating)
- Keep-alive paused during UI animations and authentication

7.3 Temperature Sensors

- PT100 — water temperature. Range check: < −10 °C or > 120 °C = sensor disconnected
- K-type — heater element temperature (logged, not used for flow control)
- Cache-first reads from ESP32 periodic health POST — no extra round-trips during normal operation

---
8. Fixes Applied in This Session

Fix 1 — RFID Not Detected After Navigation Redesign

Root cause: show_payment_method_page() was changed to navigate to selection instead of payment_method, so payment_method_page.on_enter() (which starts RFID polling) never fired.

Fix: selection_page.on_enter() now delegates to payment_method_page instance to start/stop RFID polling directly. Any screen that is the active home delegates its RFID lifecycle.

---
Fix 2 — RFID Cup-Count Guard Always Blocked

Root cause: Guard checked cups_counter.cups_count on payment_method_page — this value was never updated since the page is never entered, so it was permanently 0 → blocked every RFID tap as "machine empty."

Fix: Guard now reads app.local_cups_count (the authoritative live counter shared across all pages).

---
Fix 3 — RFID Restart Guard Skipped After Auth

Root cause: restart_rfid_after_auth() checked current != 'payment_method' — always true now, so polling was never restarted after a failed RFID auth.

Fix: Guard now checks current not in ('payment_method', 'selection').

---
Fix 4 — navigate_to_machine_empty Never Triggered from RFID Flow

Root cause: Checked manager.current == 'payment_method' — always false.

Fix: Checks in ('payment_method', 'selection').

---
Fix 5 — Boot-Only Config Loading

Root cause: start_scheduled_flush_monitor() re-fetched flushTimeMinutes and mlToDispense from Kulhad every 5 minutes while the UI was running, causing unnecessary network traffic.

Fix: Config is fetched once at startup via _refresh_machine_config_cache(). Periodic re-fetch disabled. Machine must be restarted to pick up Kulhad config changes.

---
Fix 6 — Hardware Error Flash After Successful Dispense

Root cause: send_command_and_wait() background thread in place_cup_page waits up to 35 s for the ESP32 response. If the pump timer fires first (dispense completes normally), the user is back on the home screen. When the delayed 701 response finally arrives, handle_dispense_error(701) fired unconditionally → hardware error page flashed for ~5 s then auto-cleared.

Fix (place_cup_page.py:620–630):
if getattr(app.dispensing_page, 'completion_handled', False):
    print(f"⚠️ Stale {status_code} — dispense already completed, ignoring")
else:
    Clock.schedule_once(lambda dt: app.handle_dispense_error(status_code), 0)

---
Fix 7 — Dispensing Video Frozen at End (~2.5 s)

Root cause (two parts):
1. Timer fired at pump_duration_s + 0.5 — 0.5 s gap after video ended where the last frame was frozen.
2. VideoWidget.stop_video() does not clear the canvas (by design for screensaver). So even after handle_completion() ran, the frozen last frame stayed visible in the video area for the full 2-second "YOUR TEA IS READY!" pause.

Fix (dispensing_page.py):
- Timer changed from pump_duration_s + 0.5 → pump_duration_s (zero gap)
- handle_completion() now explicitly calls self.video_widget.canvas.clear() after stop_video()

---
Fix 8 — "YOUR TEA IS READY!" Intermediate Screen Removed

User feedback: The green text overlay between dispensing and thank-you page was visually uncomfortable.

Fix: handle_completion() no longer updates text labels. Navigation to thank-you page fires on the next frame (Clock.schedule_once(..., 0)) — no 2-second pause.

---
Fix 9 — Auto-Flush Timer Never Armed (Critical Bug)

Root cause: schedule_auto_flush() had lines in the wrong order:
self._flush_cancelled = False   # 1. Allow arming
self.cancel_auto_flush()        # 2. cancel_auto_flush() sets _flush_cancelled = True again!
_arm_flush_timer always saw _flush_cancelled = True → "Arming aborted" printed every time → the 40-minute flush timer was never once scheduled.

Fix (main_app.py):
self.cancel_auto_flush()       # 1. Cancel old timer first
self._flush_cancelled = False  # 2. Then allow new timer

---
Fix 10 — Demo Mode Added (run_demo.py)

Purpose: Run the complete UI without any physical hardware.

How it works:
- Patches utils.api_client._localhost_session with a _MockLocalSession — all polling server calls return instant healthy responses without touching localhost:5000
- Replaces ApiClient with _DemoApiClient before main_app is imported — payment auto-completes after 5 s, cups = 50, machine = ONLINE
- Patches hardware_monitor singleton — start() is a no-op, get_latest_error() returns None, is_device_connected() returns True
- Stubs RFIDAESAuth — reader gracefully absent
- DemoChaiOrderingApp subclass overrides on_start() to set Window.fullscreen = False, Window.rotation = 0 for desktop display

---
9. Known Remaining Limitations

┌───────────────────┬──────────────────────────────────────────────────────────────────────────┐
│       Item        │                                  Detail                                  │
├───────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ Pump status       │ ESP32's pump_status endpoint returns static data (elapsed always 0), so  │
│ polling never     │ has_started_dispensing stays False and idle-based early exit never       │
│ fires early       │ triggers. Pump timer is the sole completion mechanism — this is          │
│                   │ intentional.                                                             │
├───────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ Multi-cup cup     │ reduce_one_cup() fires on each "Dispense Now" press. For a 3-cup order,  │
│ count reduces     │ cups are reduced 3 times (once per cup), which is correct.               │
│ once              │                                                                          │
├───────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ reduce_cups       │ water_flush / tea_flush return {"dispatched": True} on 504 — not stored  │
│ response not      │ as cup count; this is correct since these are flush commands, not        │
│ normalizing       │ dispense commands.                                                       │
├───────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ RFID reader       │ If pyscard is unavailable, rfid_auth_handler = None is set gracefully;   │
│ required at boot  │ all RFID flows are skipped without crashing.                             │
├───────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ Config only       │ Changes to flushTimeMinutes or mlToDispense on Kulhad require a machine  │
│ loaded at boot    │ restart to take effect.                                                  │
└───────────────────┴──────────────────────────────────────────────────────────────────────────┘

---
10. File Map

urban-kettle-withRFID/
├── config.py                    — Device ID, temp, pump calibration
├── main_app.py                  — ChaiOrderingApp: all screens, flows, state
├── polling_server2.py           — Local Flask bridge to ESP32
├── run_demo.py                  — Hardware-free UI demo (NEW this session)
│
├── ui_pages/
│   ├── selection_page.py        — HOME: cup selection + RFID delegation
│   ├── payment_method_page.py   — RFID logic container (not navigated to)
│   ├── payment_page.py          — QR display + payment polling
│   ├── loading_page.py          — Spinner during QR fetch
│   ├── place_cup_page.py        — "Dispense Now" button + 30 s timer
│   ├── dispensing_page.py       — Video animation, pump timer
│   ├── thank_you_page.py        — Order complete screen
│   ├── heating_page.py          — Wait for water to heat
│   ├── hardware_error_page.py   — Critical hardware errors
│   ├── machine_empty_page.py    — Out of stock / offline
│   ├── flush_page.py            — Maintenance flush in progress
│   ├── rfid_auth_page.py        — RFID card authentication progress
│   ├── screensaver_page.py      — Idle full-screen video
│   └── qr_expired_page.py       — Payment timeout
│
└── utils/
    ├── api_client.py            — All REST API calls (Kulhad, Razorpay, ESP32)
    ├── hardware_monitor.py      — Background temperature + connection polling
    ├── rfid_aes_auth.py         — ACR122U pyscard + 5-step AES auth
    ├── rfid_reader.py           — Legacy HID keyboard RFID (unused in production)
    ├── qr_utils.py              — QR image generation (qrcode library)
    └── screensaver_manager.py   — Download/cache screensaver video from Kulhad

---
11. How to Run

Production (real hardware):
cd ~/Videos/urban-kettle-withRFID
python polling_server2.py &     # start ESP32 bridge first
python main_app.py

Demo (no hardware needed):
cd ~/Videos/urban-kettle-withRFID
python run_demo.py
# Payment auto-completes after 5 s on the QR screen
# Dispensing plays ~11 s video then goes to thank-you page


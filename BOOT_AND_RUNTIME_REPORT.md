# Urban Kettle — Complete Boot & Runtime Reference

This document covers every event that happens from power-on to steady-state operation.
All timing figures are exact values from the code.

---

## Table of Contents

1. [Boot Sequence (launch_pi.sh)](#1-boot-sequence)
2. [App Startup (main_app.py build())](#2-app-startup)
3. [All Clock & Thread Schedules](#3-all-clock--thread-schedules)
4. [API Contact Map — What, When, How Often](#4-api-contact-map)
5. [Page-by-Page Behaviour](#5-page-by-page-behaviour)
6. [When "Under Maintenance" Page Shows](#6-under-maintenance-page)
7. [When Hardware Error Page Shows](#7-hardware-error-page)
8. [Temperature Monitoring — Full Detail](#8-temperature-monitoring)
9. [RFID — All Modes & Flows](#9-rfid-all-modes--flows)
10. [Payment & QR Prefetch Flow](#10-payment--qr-prefetch-flow)
11. [Dispensing Flow](#11-dispensing-flow)
12. [Auto Flush System](#12-auto-flush-system)
13. [Operating Hours Scheduler](#13-operating-hours-scheduler)
14. [Screensaver](#14-screensaver)
15. [Cups Count Tracking](#15-cups-count-tracking)
16. [State Machine — All Page Transitions](#16-state-machine)
17. [Configuration Sources](#17-configuration-sources)
18. [Error Codes from ESP32](#18-error-codes-from-esp32)

---

## 1. Boot Sequence

**File:** `launch_pi.sh`  
**Triggered by:** `systemd` unit `urban-kettle.service` (auto-start on every boot)

| Step | Action | Timeout / Wait |
|------|--------|---------------|
| 1 | Bash strict mode + `cd` to app directory | instant |
| 2 | **Wait for X display** — polls `xset -display :0 q` every 1 s | up to **60 s** |
| 3 | Export env vars: `DISPLAY=:0`, `XAUTHORITY`, `KIVY_WINDOW=sdl2`, `KIVY_GL_BACKEND=gl`, `KIVY_MULTISAMPLES=0` | instant |
| 4 | Kill stale `polling_server2.py` and `main_app.py` processes | instant + **1 s** sleep |
| 5 | Check if `pcscd` (RFID smartcard daemon) is running; start it if not | instant, or **1 s** restart |
| 6 | Activate Python virtualenv (if `./venv/` exists) | instant |
| 7 | Register `cleanup` trap on SIGTERM/SIGINT/EXIT (kills both processes on exit) | instant |
| 8 | **Start `polling_server2.py`** (ESP32 bridge, Flask on port 5000) — redirect to `backend.log` | background |
| 9 | **Wait for Flask** — polls `curl http://localhost:5000/health` every 1 s | up to **15 s** |
| 10 | **Start `main_app.py`** (Kivy UI) — redirect to `frontend.log` | background |
| 11 | Grace period: **sleep 3 s**, then verify process still alive | **3 s** |
| 12 | **Monitor loop** — every 2 s check if backend + frontend PIDs are alive | forever |

**Monitor loop behaviour:**
- Backend dies → `exit 1` → systemd `Restart=always` relaunches everything in 10 s
- Frontend dies → `exit 0` → graceful shutdown (user or error closed UI)

**Worst-case boot time:** ~79 s (60 s display + 1 s kill + 3 s pcscd + 15 s backend = 79 s max)  
**Typical boot time:** 5–15 s (display usually ready quickly, backend starts in 1–2 s)

---

## 2. App Startup

**File:** `main_app.py` → `build()` method

Everything below happens in the order listed, starting the moment Python loads `main_app.py`.

### 2.1  Immediate (t = 0 s)

| What | Detail |
|------|--------|
| Set window title | "Urban Kettle" |
| Load `DEVICE_ID` from `config.py` | e.g. `UK_14335C5D48C8` |
| Create `ApiClient()` instance | Session pool: 10 connections, 20 max |
| Initialize all state variables | cups=None, screensaver=False, flush=False, etc. |
| Create `ScreenManager` with `NoTransition` | Instant page changes, no animation |
| Create every page object | 14 pages: payment_method, selection, payment, loading, dispensing, place_cup, thank_you, screensaver, qr_expired, machine_empty, rfid_auth, hardware_error, heating, flush |
| Set initial screen | `'selection'` (user sees selection page first) |
| Configure window | Production: fullscreen 881×661, rotation=180 |
| Start `hardware_monitor` background thread | Polls ESP32 temperature continuously |
| Initialize `RFIDAESAuth` | PC/SC mode; base_url = ukteawallet.com |
| Start HID keyboard RFID listener | `rfid_reader.start_listening()` |
| Setup screensaver monitoring | Bind touch/key events, start 1 s activity monitor |

### 2.2  Background at t ≈ 0 s (spawned immediately, non-blocking)

| What | Method | Note |
|------|--------|------|
| Warm up cloud APIs | `api_client.warmup_apis()` | HEAD requests to Razorpay, Kulhad, ukteawallet |
| Fetch machine config | `_refresh_machine_config_cache()` | Gets flushTimeMinutes, mlToDispense, operating hours |
| Pre-warm PIL image library | `_prewarm_pil()` | Saves ~0.15 s on first QR code generation |
| Fetch screensaver video | background fetch + update `screensaver_page` | Only if video URL configured |

### 2.3  Delayed Starts

| Delay | What | Method |
|-------|------|--------|
| **1.5 s** | Check temperature → decide first page | `check_heating_on_startup()` |
| **3 s** | Start global RFID monitor (0.5 s polling) | `_start_global_rfid_monitor()` |
| **30 s** | Start global machine status monitor (10 s polling) | `start_global_status_monitoring()` |

> **Why 30 s delay on status monitor?**  
> The ESP32 takes time to connect to Wi-Fi and send its first health POST.  
> Starting the check too early would wrongly report the machine as OFFLINE and navigate to the maintenance page.

### 2.4  Always-running Intervals (set up in build())

| Interval | Method | Purpose |
|----------|--------|---------|
| **1 s** | `monitor_activity()` | Screensaver idle timer |
| **5 s** | `check_idle_temperature()` | Detect temp drop on idle pages |

---

## 3. All Clock & Thread Schedules

### 3.1  Clock Schedules (Kivy main thread)

| Type | Interval / Delay | Method | Runs on Pages |
|------|-----------------|--------|---------------|
| `schedule_once` | 1.5 s | `check_heating_on_startup` | (startup only) |
| `schedule_once` | 3.0 s | `_start_global_rfid_monitor` | (startup only) |
| `schedule_interval` | 1.0 s | `monitor_activity` | all pages |
| `schedule_interval` | 5.0 s | `check_idle_temperature` | payment_method, selection, screensaver, qr_expired |
| `schedule_interval` | 10.0 s | `check_global_machine_status` | payment_method, selection, payment, loading, **heating** (skips: machine_empty, screensaver, place_cup, dispensing, thank_you, rfid_auth, flush) |
| `schedule_interval` | 1.0 s | heating monitor `_trigger_read` | heating page only (active while heating) |
| `schedule_interval` | 0.5 s | `_grf_tick` (global RFID) | all except own-RFID pages and skip pages |
| `schedule_interval` | 0.5 s | `_poll_rfid` (per-page) | payment_method, heating, rfid_auth (while rfid_listening=True) |
| `schedule_interval` | 0.5 s | dots animation | machine_empty (while on page) |
| `schedule_interval` | 3.0 s | cups check | machine_empty (while on page) |
| `schedule_interval` | 1.0 s | countdown | place_cup (30 s timer) |
| `schedule_interval` | 2.0 s | `check_payment_status` | payment page (while waiting) |
| `schedule_interval` | 10.0 s | `check_status` (hardware error) | hardware_error page |

### 3.2  Background Threads (always daemon=True)

| When | Thread | What it does |
|------|--------|--------------|
| App start | `hardware_monitor._temperature_loop()` | Keeps `last_temperature` fresh from ESP32 health POSTs |
| App start | `hardware_monitor._cloud_temperature_loop()` | POSTs temperature to Kulhad every **120 s** |
| App start | `api_client.warmup_apis()` | Warm serverless containers |
| App start | `_refresh_machine_config_cache()` | Fetch config from Kulhad |
| App start | `_prewarm_pil()` | Load PIL image plugins |
| Every 10 s status check | `_do_global_status_check()` | ESP32 state + cups sync |
| Every 5 s idle check | `_do_check()` (inside idle temp) | Read cached temperature |
| QR generation | `generate_qr_code()` | API call + PIL encode |
| QR prefetch | `_prefetch_worker()` | Pre-generate QRs for 1–3 cups |
| Payment paid | `reduce_cups()` | Decrement cups in cloud |
| RFID card | `validate_rfid_card_aes()` | AES authentication |
| Dispense complete | `fetch_and_store_cups_count()` | Re-sync cups from cloud |
| End of day / pre-start | `threading.Timer` (operating hours) | OFFLINE/ONLINE commands |

---

## 4. API Contact Map

### 4.1  Kulhad Backend (HTTPS, kulhad.vercel.app)

| Endpoint | Method | When Called | Timeout |
|----------|--------|-------------|---------|
| `/api/getMachineData?machineId=...` | GET | App startup; every 5 min (if enabled) | — |
| `/api/direct-payment` | POST | User confirms cup selection (QR generation) | 6 s |
| `/api/transaction-status` | POST | Every **2 s** while on payment page | — |
| `/api/qrcode-close` | POST | Payment cancelled, expired, or abandoned | 10 s |
| `/api/reduce-cups` | POST | On "Dispense Now" button (cupsToReduce=N); also as read-only (cupsToReduce=0) | — |
| `/api/updateMachineStatus` | POST | When ESP32 changes ONLINE↔OFFLINE | — |
| `/api/MachinesStatus` | GET | Fallback if updateMachineStatus fails | — |
| `/api/canister-check` | POST | When local cups count hits **5** (low-stock alert) | — |
| `/api/machine-temperature` | POST | Every **120 s** (cloud temp reporting) | — |

### 4.2  Polling Server (HTTP, localhost:5000)

| Endpoint | Method | Caller | When |
|----------|--------|--------|------|
| `/api/status` or `/health` | GET | `launch_pi.sh` | Boot — wait for Flask ready |
| `/api/device/handshake` | POST | ESP32 | On ESP32 power-on |
| `/api/device/health` | POST | ESP32 | Every ~30 s (ESP32 health heartbeat) |
| `/api/device/commands/pending` | GET | ESP32 | Every ~30 s (ESP32 polls for commands) |
| `/api/device/command/result` | POST | ESP32 | After executing a command |
| `/api/device/command` | POST | `main_app.py` | Send dispense/flush/state commands to ESP32 |
| `/api/device/{ID}/temperature` | GET | `main_app.py` | Heating check (1.5 s startup); every 5 s idle; every 1 s on heating page; every 10 s global check |
| `/api/device/{ID}/history` | GET | `hardware_monitor` | When checking for hardware errors |
| `/api/devices` | GET | `hardware_monitor` | Liveness check when cache is stale |

### 4.3  RFID Wallet (HTTPS, ukteawallet.com)

| Action | When |
|--------|------|
| AES card authentication | User taps RFID card on payment_method or heating page |

---

## 5. Page-by-Page Behaviour

### payment_method_page  (Home Screen)
- **Entered from:** heating (when warm), machine_empty (when machine comes online), screensaver (on touch), qr_expired (go home), after dispense complete
- **On enter:** Fetch cups count from cloud, start RFID polling (0.5 s)
- **On leave:** Stop RFID polling, cancel QR prefetch if user backing out
- **Features:** UPI button, RFID wallet button, cups count display (top-right)
- **RFID card:** → rfid_auth page → (if OK) → dispensing

### selection_page
- **Entered from:** payment_method (user taps UPI)
- **On enter:** Fetch cups count, display max available (capped at 4)
- **Features:** Buttons 1–4 cups; Confirm navigates to loading page
- **On confirm:** Pre-fetch QRs for cups 1 through min(selected, 3) in background

### loading_page
- **Entered from:** selection (while QR is generating)
- **Timer:** 30 s timeout → show error popup
- **Animation:** Spinning arc, pulsing cup image
- **Exit:** QR ready → payment page; Timeout → error popup → selection

### payment_page
- **Entered from:** loading (QR received), or loading (cached QR delivered instantly)
- **Timer:** 120 s countdown on screen
- **On enter:** Start payment status polling every 2 s
- **Status responses:** active → keep polling | paid → thank_you in 1.5 s | expired → qr_expired
- **Cancel button:** Cancels payment, goes home
- **Timer expires:** Cancels payment, shows qr_expired

### place_cup_page
- **Entered from:** start_dispensing_process() after payment confirmed
- **Timer:** 30 s countdown (big red timer on screen)
- **On enter:** Show cup info ("Cup 1 of 3"), reset countdown
- **Dispense Now button:** Debounced (button_pressed flag), calls reduce_cups + send_tea_dispense_command → dispensing page
- **Timer expires:** Error popup → go home

### dispensing_page
- **Entered from:** place_cup_page (on "Dispense Now")
- **Video:** `assets/dispensing_{ml}.mp4` where `ml` is rounded from `ml_to_dispense`; fallback to `assets/dispensing.mp4`
- **Playback FPS:** Adjusted so video length equals pump duration exactly
- **Pump polling:** Every 0.5 s check pumpState transitions
- **Completion triggers (first one wins):**
  1. Pump duration timer fires (ml ÷ 9 ml/s seconds + 2 s padding)
  2. 3 consecutive idle pump polls
  3. 30 s of null responses (safety exit)
- **On complete:** → handle_cup_completion()

### thank_you_page
- **Entered from:** handle_cup_completion() when all cups dispensed
- **Duration:** ~3 s, then auto-navigate
- **If cups now = 0:** Schedules machine_empty in 3 s

### machine_empty_page  ← see Section 6 for full detail
- Modes: `'empty'` (cups=0) or `'offline'` (ESP32 offline / maintenance)

### heating_page  ← see Section 8 for full detail
- **Entered from:** check_heating_on_startup(), check_idle_temperature(), machine_empty recovery
- **On enter:** Steam animation, RFID polling (0.5 s for maintenance cards)
- **Exits when:** temp ≥ 80 °C → payment_method (or pending payment page)

### rfid_auth_page
- **Entered from:** payment_method on RFID card tap
- **On enter:** Start 9 s timeout; show progress animation; run AES auth in background
- **On success:** Show balance, navigate to dispensing in 2 s
- **On failure:** Show error, navigate to payment_method in 2 s

### hardware_error_page  ← see Section 7 for full detail
- **Entered from:** heating monitor (3 errors or 300 s no data), or sensor out-of-range (>120 °C)
- **Checks every 10 s** (first check at 5 s): resolve or stay

### screensaver_page  ← see Section 14 for full detail
- **Entered from:** 30 s inactivity on idle pages
- **Exit:** Any touch/key → payment_method (or machine_empty if offline)

### flush_page
- **Entered from:** Auto flush trigger (after idle_flush_time_minutes)
- **Phases:** Water flush → Tea flush → Done
- **Blocks orders:** show_payment_method_page() redirects here while flush_in_progress=True

### qr_expired_page
- **Entered from:** Payment timer (120 s) or status = "expired"
- **Exit:** "Try again" or go home

### maintenance_page
- **Entered from:** Staff RFID card tap (special card triggers show_page('maintenance'))
- **Features:** View/sync flush timing, pump duration from Kulhad

---

## 6. Under Maintenance Page

**Page:** `machine_empty_page` with `set_mode('offline')`  
**Title shown:** "Under Maintenance"  
**Subtitle:** "We'll be back soon!"

### 6.1  Triggers that SHOW Under Maintenance

| Trigger | When | Source |
|---------|------|--------|
| **ESP32 sends `machineState = OFFLINE`** | Global status monitor detects it (every 10 s) while on payment_method, selection, payment, loading, or heating page | `_do_global_status_check()` |
| **ESP32 health POST is >90 s old** | Same monitor — treats stale data as OFFLINE | `_do_global_status_check()` |
| **ESP32 never POSTed since server start (404)** | Same monitor — no data = offline | `_do_global_status_check()` |
| **Operating hours END time reached** | `threading.Timer` fires at closing time | `_on_operating_end()` → `_operating_go_offline()` |
| **App starts inside closed hours window** | `_schedule_operating_hours()` checks current time | `_operating_go_offline()` |

### 6.2  Pages That CANNOT be Interrupted by Maintenance

The global status check is **skipped** (returns immediately) on these pages:

| Page | Reason |
|------|--------|
| machine_empty | Already on offline/maintenance page |
| screensaver | Screensaver active (waking it handles offline detection) |
| place_cup | User is mid-dispense — do not interrupt |
| dispensing | Actively dispensing |
| thank_you | Post-dispense screen |
| rfid_auth | RFID auth in progress |
| flush | Maintenance flush in progress |

> **Note:** `heating` page is NOT in the skip list — if OFFLINE is received while heating, the maintenance page WILL show.

### 6.3  Recovery — How Machine Comes Back Online

**Three parallel mechanisms:**

1. **machine_empty page cups timer (every 3 s):**
   - Reads ESP32 state from polling server
   - If state = ONLINE AND cups > 0 → call `return_to_payment_method()` → `check_heating_on_startup()`
   - If state = ONLINE AND cups = 0 → switch mode to 'empty', stay on page

2. **Global status monitor (every 10 s):**
   - Detects OFFLINE → ONLINE transition on check_pages
   - Calls `check_heating_on_startup()` on main thread

3. **Operating hours pre-start timer (40 min before opening):**
   - `threading.Timer` fires → sends ONLINE command to ESP32 → notifies Kulhad
   - The machine_empty cups timer (above) will then detect ONLINE and navigate

**After recovery, `check_heating_on_startup()` runs:**
- If temp ≥ 80 °C → payment_method page
- If temp < 80 °C → heating page (machine warms up first)

### 6.4  Side Effects When Maintenance Shown

- Kulhad backend notified: `report_machine_status(MACHINE_ID, 'offline')`
- ESP32 notified (if triggered by operating hours): `send_machine_state_to_esp32("OFFLINE")`
- Dots animation starts (●●● cycling every 0.5 s)
- All active QR prefetches are cancelled

---

## 7. Hardware Error Page

**Page:** `hardware_error_page`  
**Activation:** Persistent hardware fault that cannot self-recover

### 7.1  Triggers that SHOW Hardware Error

| Trigger | Condition |
|---------|-----------|
| PT100 sensor reading > 120 °C | Sensor fault / disconnected (not real temperature) |
| 3 consecutive temperature read failures on heating page | ESP32 not responding during heat-up |
| 300 s (5 min) of no valid temperature data on heating page | Persistent sensor outage |
| ESP32 status code 701 | Temperature critical / PT100 out-of-range |
| ESP32 status code 705 | Flow failure |
| ESP32 status code 706 | Pump fault |
| ESP32 status code 707 | Heater fault |
| ESP32 status code 711 | Pump timeout |

### 7.2  What Happens on Hardware Error Page

- Error message displayed (from ESP32 status code or exception text)
- **First check after 5 s** (give user time to read)
- **Then every 10 s:** `check_status()` background thread
  - Calls `hardware_monitor.get_latest_error(force_fresh=True)`
  - Result = `('HEATING', temp)` → error cleared, navigate to heating page
  - Result = error string → update displayed message, stay on error page
  - Result = None → error fully cleared, navigate to payment_method page

### 7.3  Staff Override

- Hidden 5-tap zone at bottom of error page
- 5 taps force navigation to payment_method page (bypasses error monitor)
- For use by field technicians after manually resolving the fault

### 7.4  What Hardware Error Does NOT Show For

- ESP32 machineState = OFFLINE → handled by machine_empty/maintenance page instead
- WiFi disconnected (status 600) → logged but not shown as error page
- Temporary API failures → retry logic, not error page

---

## 8. Temperature Monitoring

Three independent temperature systems run simultaneously.

### 8.1  Startup Check (one-time, t = 1.5 s)

**Method:** `check_heating_on_startup()`

1. GET `/api/device/{DEVICE_ID}/temperature` (polling server cache, fast)
2. If `machineState = OFFLINE` → skip entirely (operating hours will handle it)
3. If reading > 120 °C → sensor fault → show hardware_error page
4. If no cached data → sleep 3 s → retry once
5. If still no data → show heating page (assume cold)
6. If temp < 80 °C → show heating page
7. If temp ≥ 80 °C → show payment_method page (ready to serve)

### 8.2  Idle Temperature Check (every 5 s)

**Method:** `check_idle_temperature()`  
**Pages monitored:** payment_method, selection, screensaver, qr_expired

1. Guard: skip if `_idle_temp_checking = True` (previous read in flight)
2. Set `_idle_temp_checking = True`
3. Background thread:
   - Read `hardware_monitor._fetch_cached_temperature()` (fast, no command sent)
   - If cache stale: fall back to `hardware_monitor.last_temperature`
   - Reject out-of-range (< −10 °C or > 120 °C) — sensor fault
   - If temp < 80 °C → schedule `show_heating_page(temp)` on main thread
4. Set `_idle_temp_checking = False`

> This is a **fast-path only** check — it reads the ESP32's last health POST cache.  
> The cache is updated every ~30 s (ESP32 health heartbeat), so detection lag is 5–35 s.

### 8.3  Heating Page Monitor (every 1 s)

**Method:** `start_heating_monitor()` → `_trigger_read()` every 1 s  
**Active only while on heating page**

1. Guard: skip if `_heating_poll_running = True`
2. Background: `hardware_monitor._fetch_temperature(force_fresh=True)`
   - Tries cached value first; if stale, sends health_check command (35 s timeout)
   - Non-blocking lock: if command already in flight, return cached immediately
3. Update heating page display label (`current_temp_label`)
4. Track `last_temperature`, consecutive errors, "data received" flag

**Exit conditions:**

| Condition | Action |
|-----------|--------|
| temp ≥ 80 °C | Stop monitor → show payment_method (or pending payment page) |
| 3 consecutive read errors | Stop monitor → show hardware_error page |
| 300 s with no valid temp data | Stop monitor → show hardware_error page ("sensor not responding") |

### 8.4  Global Status Check Temperature Sync (every 10 s)

- Reads machineState AND temperature from ESP32 cache in the same API call
- If machineState = OFFLINE → navigate to maintenance page
- If ONLINE and was previously OFFLINE → call check_heating_on_startup()

### 8.5  Cloud Temperature Reporting (every 120 s)

- `hardware_monitor._cloud_temperature_loop()` background thread
- POST latest temp to Kulhad `/api/machine-temperature`
- Skips during heating mode (to not spam the cloud during heat-up)

---

## 9. RFID — All Modes & Flows

### 9.1  Two Physical Reader Types

| Mode | Reader Type | How cards are read |
|------|-------------|-------------------|
| **PC/SC (Primary)** | ACR122U via pcscd | pyscard library reads raw card bytes; AES decryption on-device |
| **HID Keyboard (Fallback)** | Sycreader or any HID reader | Reader emits decimal digits on USB keyboard; app captures via evdev or Kivy |

Both modes are active simultaneously. The PC/SC mode is tried first for each card.

### 9.2  Global RFID Monitor (t = 3 s after startup)

- **Interval:** 0.5 s (`_grf_tick`)
- **Covers:** All pages that don't have their own per-page RFID polling
- **Skips (OWN_PAGES — have per-page polling):** payment_method, selection, heating, hardware_error, rfid_auth
- **Skips (SKIP_PAGES — no RFID during these):** dispensing, place_cup, thank_you, flush
- **Debounce:** 3 s minimum between card taps
- **On card detected:** Route to `payment_method_page.handle_rfid_card_detected(uid)`

### 9.3  Per-Page RFID Polling (0.5 s each)

| Page | When active | What it does |
|------|-------------|--------------|
| payment_method | While `rfid_listening = True` (set on enter, cleared on leave) | Validate card → rfid_auth page → dispense |
| heating | While on page | Maintenance card → maintenance page |
| rfid_auth | While on page | Already in auth flow |

### 9.4  RFID Authentication Flow (PC/SC)

1. Card tapped → `handle_rfid_card_detected(uid)` on payment_method
2. Navigate to rfid_auth page
3. Background: `rfid_auth_handler.process_card()`
   - AES decrypt card UID
   - POST to `ukteawallet.com/api/card/authenticate`
   - Response: `{authenticated, dispensed, remainingBalance, machineLocation}`
4. On success: Show balance popup → auto-close 2 s → navigate to dispensing (skips payment)
5. On failure: Show error popup → auto-close 2 s → back to payment_method

### 9.5  HID Keyboard Fallback (Sycreader)

- `rfid_reader.py` reads `/dev/input/eventN` via evdev
- Accumulates digit keypresses (keycodes 2–11 for digits 1–0)
- On Enter keycode or 300 ms inter-digit gap → fire card callback
- Callback: `app._on_hid_rfid_card(card_number)`
- Fallback to Kivy keyboard if evdev unavailable

---

## 10. Payment & QR Prefetch Flow

### 10.1  Normal QR Generation (Cold)

1. User confirms cups on selection page
2. `trigger_early_prefetch()` — pre-generate QRs for 1 to min(selected, 3) cups in background
3. `show_payment_page(num_cups)` called
4. Check prefetch cache (thread-safe lock):
   - **Cache hit & image ready** → instant reveal, skip loading page almost immediately
   - **Prefetch in flight** → wait; show loading page
   - **Not started** → spawn `generate_qr_code()`, show loading page
5. `generate_qr_code()` background thread:
   - Check ESP32 machineState (if OFFLINE → show error, abort)
   - POST `/api/direct-payment` (Kulhad → Razorpay, ~2–3 s)
   - Generate PIL image from imageContent
   - Encode to PNG bytes in background (avoids UI thread block)
   - Schedule `update_payment_page()` on main thread
6. `update_payment_page()`:
   - Guard: only if still on loading page
   - Cancel loading timeout
   - Show payment page with QR
   - Extract QR ID → `current_qr_code_id`
   - Start payment status polling (every 2 s)

### 10.2  Payment Status Polling

- Every **2 s**: POST `/api/transaction-status` with QR code ID
- Response `"active"` → reschedule check in 2 s
- Response `"paid"` → update display → schedule dispense in 1.5 s
- Response `"expired"` → show qr_expired page in 1 s
- Error → reschedule in 2 s

### 10.3  QR Prefetch Cache

- Stores up to **3 QR codes** (cup counts 1, 2, 3) per transaction
- Uses `{cup_count: {'data': qr_data, 'image': png_bytes}}` dict
- Thread-safe with `threading.Lock`
- Abandoned if user navigates away (`cancel_prefetched_qrs()`)
- Stale QRs cancelled via API (`/api/qrcode-close`) in background

### 10.4  Loading Page Timeout

- **30 s** from loading page enter
- If QR still not ready → show error popup with "Retry" button
- Retry: new `generate_qr_code()` call with **8 s** second timeout
- Second failure → navigate home

---

## 11. Dispensing Flow

### 11.1  After Payment Confirmed (RFID or QR)

1. `start_dispensing_process()` — set `_dispensing_cups = True`, `current_cup_number = 1`
2. `show_place_cup_page()` — show place cup page, start 30 s countdown

### 11.2  On "Dispense Now"

1. Debounce check (button_pressed flag)
2. Decrement cups in cloud: POST `/api/reduce-cups` (cupsToReduce = 1)
3. Decrement local cups counter immediately
4. POST dispense command to ESP32 via polling server
5. Navigate to dispensing page

### 11.3  Dispensing Page

- Video: `assets/dispensing_{int(ml)}.mp4` (e.g. `dispensing_100.mp4` for 100 ml)
- Fallback: `assets/dispensing.mp4` if specific file not found
- FPS adjusted: `video_fps = total_frames / pump_duration_seconds`
- Pump polling every 0.5 s for `pumpState` transitions

### 11.4  Pump Duration Calculation

```
Pump duration = ml_to_dispense ÷ 9.0 ml/s  (PUMP_FLOW_RATE_ML_PER_SEC from config.py)
Example: 100 ml ÷ 9.0 = 11.1 s  → pump runs for 11.1 s
Video padded by +2 s after pump stops
```

### 11.5  Completion

1. `handle_cup_completion()`
2. If more cups remaining: `current_cup_number += 1` → show place_cup_page (repeat)
3. If last cup:
   - Set `_dispensing_cups = False`
   - Refresh cups count from cloud (background)
   - Show thank_you page
   - If cups now = 0: schedule machine_empty page in 3 s
   - Schedule auto flush timer (idle flush countdown starts)

---

## 12. Auto Flush System

### 12.1  Trigger

- Scheduled after every dispense completion (in `handle_cup_completion()`)
- Delay: `flush_time_minutes × 60` seconds (default 40 min, fetched from Kulhad)
- Timer resets on each new order (cancel + re-arm)

### 12.2  Flush Process

1. `_trigger_auto_flush()` fires
2. Guard: only execute on safe pages — payment_method, machine_empty, screensaver, selection, qr_expired, thank_you
3. Set `flush_in_progress = True`
4. Navigate to flush page
5. Background `_run_auto_flush()`:
   a. Water flush: POST command to ESP32 → update page phase → wait
   b. Tea flush: POST command to ESP32 → update page phase → wait
   c. Done: set `flush_in_progress = False` → navigate home (fetch cups)

### 12.3  Cancellation

- `cancel_auto_flush()` called when new order starts (user taps confirm on selection)
- Sets `_flush_cancelled = True` → prevents arming
- If timer already fired but flush not started, guard aborts flush

### 12.4  Blocking Behaviour

- While `flush_in_progress = True`, `show_payment_method_page()` redirects to flush page
- Users cannot place new orders during flush

---

## 13. Operating Hours Scheduler

### 13.1  Source of Operating Hours (Priority Order)

1. Kulhad `/api/getMachineData` response fields `startTime` / `endTime` (currently commented out in route.ts)
2. `config.py` constants `OPERATING_START_TIME` / `OPERATING_END_TIME` (default: `None`)
3. If neither set → scheduler not active (machine runs 24/7)

### 13.2  Time Format

- `HH:MM` in 24-hour format (e.g. `"08:00"`, `"22:00"`)
- AM/PM also accepted as fallback (e.g. `"8:00 AM"`, `"10:00 PM"`)

### 13.3  How to Set Operating Hours on the Pi

Edit `config.py`:
```python
OPERATING_START_TIME = "09:00"   # Machine opens at 9 AM
OPERATING_END_TIME   = "21:00"   # Machine closes at 9 PM
```
Restart the app. No Kulhad dashboard change needed.

### 13.4  What Happens Each Day

| Event | When | Action |
|-------|------|--------|
| **Pre-start ONLINE** | 40 min before `OPERATING_START_TIME` | Send ONLINE to ESP32; notify Kulhad; machine_empty recovery runs → heating page |
| **End-of-day OFFLINE** | At `OPERATING_END_TIME` | Send OFFLINE to ESP32; notify Kulhad; show maintenance page |
| **App starts in closed window** | If `now` is outside (prestart − end) range | Immediately go offline (same as end-of-day trigger) |
| **Daily reschedule** | 1 s after each trigger fires | New `threading.Timer` set for next day's occurrence |

### 13.5  Overnight Behaviour (Important)

The timers are `threading.Timer` (daemon threads). On a Raspberry Pi that runs overnight:
- Pre-start fires at e.g. 08:20 (40 min before 09:00 open)
- End-of-day fires at e.g. 21:00
- Both reschedule themselves for the next day
- Timers survive as long as the process is alive (they are daemon threads — they die with the process but the service auto-restarts)

---

## 14. Screensaver

### 14.1  Activation

- **Timeout:** 30 s of inactivity (no touch, no key press)
- **Eligible pages:** payment_method, selection, machine_empty (only when mode = 'empty', NOT offline)
- **Triggered by:** `monitor_activity()` check (every 1 s)
- **Requires:** Screensaver video file exists in `assets/`

### 14.2  What Happens on Activation

1. `cancel_prefetched_qrs()` — user walked away, discard pre-generated QRs
2. Remember previous page
3. Set `screensaver_active = True`
4. Navigate to screensaver page
5. Video plays in loop at native FPS

### 14.3  Deactivation

- Any touch or keypress → reset activity timer → `deactivate_screensaver()`
- Checks if machine is still offline: if yes → show machine_empty (offline mode)
- Otherwise: → show payment_method page
- Does NOT re-fetch cups (uses local count)

### 14.4  Activity Reset Events

- Window `on_motion` event
- Window `on_key_down` event
- Window `on_touch_down` event

---

## 15. Cups Count Tracking

### 15.1  Local Counter vs Cloud

| Source | Authority | When Used |
|--------|-----------|-----------|
| `local_cups_count` | **Authoritative** for immediate display | All UI decisions |
| Kulhad cloud (`/api/reduce-cups?cupsToReduce=0`) | **Sync source** | Checked every 10 s via global monitor |

### 15.2  Local Counter Updates

| Event | Change |
|-------|--------|
| App startup / page enter | Fetch from cloud (set `local_cups_count`) |
| "Dispense Now" pressed | Decrement immediately (before cloud confirms) |
| `decrement_local_cups()` hits 0 | Navigate to machine_empty page in 2 s (if not actively dispensing) |
| Cloud sync (every 10 s) | If cloud cups > 0: update local. If cloud = 0: **skip** (post-dispense lag) |
| Dispense complete | Re-fetch from cloud (sync after order) |

### 15.3  Low Stock Alert

- When `local_cups_count` reaches **5**: `send_canister_alert()` (background)
- POST to `/api/canister-check` with `canisterLevel = 5`
- `canister_alert_sent = True` — sent only once per session

---

## 16. State Machine

### 16.1  Happy Path (Normal Order)

```
payment_method → selection → loading → payment → place_cup → dispensing → thank_you
    ↑                                                                           │
    └───────────────────── (cups > 0) ─────────────────────────────────────────┘
                                                                                │
                                                              (cups = 0) → machine_empty
```

### 16.2  RFID Fast Path (Skip Payment)

```
payment_method → rfid_auth → (auth OK) → place_cup → dispensing → thank_you
```

### 16.3  Error / Offline Paths

```
any idle page ──────────────────────────────────── (ESP32 OFFLINE) ──→ machine_empty (maintenance)
heating page ────────────────────────────────────── (ESP32 OFFLINE) ──→ machine_empty (maintenance)
any idle page ──────────────────────────── (temp < 80 °C detected) ──→ heating
heating page ─────────────────────────── (3 errors or 5 min no data) ──→ hardware_error
hardware_error ───────────────────────────────── (error cleared) ──→ heating / payment_method
machine_empty ─────────────────────────── (online + cups > 0) ──→ check_heating → payment_method
```

### 16.4  Inactivity Path

```
payment_method or selection ──── (30 s no touch) ──→ screensaver
screensaver ──────────────────────── (any touch) ──→ payment_method (or maintenance if offline)
```

### 16.5  Operating Hours Path

```
At closing time ──→ machine_empty (maintenance mode)
40 min before opening ──→ ESP32 ONLINE ──→ check_heating ──→ heating (pre-warm)
At opening time + 40 min ──→ tea is hot ──→ payment_method (ready to serve)
```

---

## 17. Configuration Sources

### 17.1  config.py (Pi-local, highest priority, static)

| Constant | Default | Purpose |
|----------|---------|---------|
| `DEVICE_ID` | `"UK_14335C5D48C8"` | ESP32 identifier (MAC-based) |
| `MACHINE_ID` | `"UKL_BLR_004"` | Kulhad machine ID |
| `SERVING_TEMP` | `80.0` °C | Temperature at which tea is ready |
| `RFID_MACHINE_ID` | `"UK_0007"` | ukteawallet.com machine ID for RFID wallet |
| `PUMP_FLOW_RATE_ML_PER_SEC` | `9.0` | Pump calibration (540 ml/min ÷ 60) |
| `PT100_SENSOR_ID` | `"pt100_sensor_01"` | Must match ESP32 firmware |
| `KTYPE_SENSOR_ID` | `"ktype_sensor_01"` | Must match ESP32 firmware |
| `OPERATING_START_TIME` | `None` | e.g. `"08:00"` — set to enable hours |
| `OPERATING_END_TIME` | `None` | e.g. `"22:00"` — set to enable hours |

### 17.2  Kulhad /api/getMachineData (fetched at startup)

| Field | Default (if missing) | Purpose |
|-------|---------------------|---------|
| `flushTimeMinutes` | 40 min | Idle flush delay |
| `mlToDispense` | 100 ml | Volume per cup |

### 17.3  ESP32 via Polling Server (runtime)

| Data | Endpoint | How Used |
|------|----------|----------|
| `machineState` | GET /api/device/{ID}/temperature | ONLINE/OFFLINE decisions |
| `pt100_temperature` | Same | Heating detection, idle temp check |
| `timestamp` | Same | Staleness check (> 90 s = treat as offline) |
| Status codes (700–711) | GET /api/device/{ID}/history | hardware_error triggers |

---

## 18. Error Codes from ESP32

| Code | Meaning | App Response |
|------|---------|--------------|
| 200 | OK | Normal operation |
| 600 | WiFi disconnected | Logged only |
| 700 | Temperature low (heating needed) | Navigate to heating page |
| 701 | PT100 out-of-range or critical temp | Navigate to hardware_error page |
| 704 | Cup removed mid-dispense | Return to place_cup page |
| 705 | Flow failure | Navigate to hardware_error page |
| 706 | Pump fault | Navigate to hardware_error page |
| 707 | Heater fault | Navigate to hardware_error page |
| 708 | Low water level | Navigate to hardware_error page |
| 711 | Pump timeout | Navigate to hardware_error page |

> **Note:** `machineState = OFFLINE` (not an error code) is handled separately by the global status monitor → maintenance page.

---

## Quick Reference — Timing Cheat Sheet

| What | Interval / Delay |
|------|-----------------|
| Boot: display wait | 60 s max |
| Boot: Flask backend ready | 15 s max |
| Boot: app startup grace | 3 s |
| First temperature check | **1.5 s** after app start |
| Global RFID monitor start | **3 s** after app start |
| Global status monitor start | **30 s** after app start |
| Global status check interval | **10 s** |
| Idle temperature check interval | **5 s** |
| Heating page temperature interval | **1 s** |
| RFID poll interval (all modes) | **0.5 s** |
| Machine empty cups check | **3 s** |
| Payment status poll | **2 s** |
| Screensaver idle timeout | **30 s** |
| QR generation (cold) | 3–4 s |
| QR generation (prefetch cache) | < 100 ms |
| Payment timer | **120 s** (2 min) |
| Auto flush default delay | **40 min** (from Kulhad) |
| Operating hours pre-start window | **40 min** before open |
| ESP32 health POST interval | ~30 s (ESP32 firmware) |
| ESP32 health data max age (offline trigger) | **90 s** |
| Temperature cache max age | **40 s** |
| Cloud temperature report interval | **120 s** |
| Auto flush per phase (water / tea) | ~20 s each |
| Hardware error monitor start | **5 s** after page enter |
| Hardware error recheck interval | **10 s** |
| Canister alert threshold | **5 cups** remaining |
| RFID card debounce | **3 s** |
| Loading page timeout | **30 s** (retry: 8 s) |
| Place cup page timeout | **30 s** |
| Force-exit on app stop | **8 s** |

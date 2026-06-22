# 🫖 Urban Kettle — Kiosk & Hardware Controller Gateway

Urban Kettle is a self-service chai (tea) vending kiosk running on a 7-inch touchscreen (881×661, mounted upside-down, auto-rotated). The UI is built with **Python + Kivy** and talks to an **ESP32** microcontroller through a local polling bridge, with payments via Razorpay UPI QR codes and RFID prepaid cards.

It acts as a gateway between three systems:

- **ESP32 Hardware Controller** — temperature, heater, pump, and water/tea dispense actions
- **ACR122U RFID Reader** — contactless smart-card payments and maintenance access
- **Kulhad Cloud API** (Vercel + Convex) — QR payments, machine status, and inventory

---

## Architecture

```
                      Kivy UI (main_app.py)
   selection → payment/RFID → place_cup → dispensing → thank_you
              │                                  │
       localhost:5000                    kulhad.vercel.app
    (polling_server2.py)                 (Kulhad Cloud API)
              │                                  │
         ESP32 (Wi-Fi)                  Razorpay / RFID Wallet
              │
   Physical hardware: PT100 sensor,
      pump, heater, solenoid valve
```

| Layer | Technology | Purpose |
|---|---|---|
| UI | Python 3.9 + Kivy 2.3 | All screens, touch events, animations |
| Local bridge | `polling_server2.py` (Flask, port 5000) | Relays commands to the ESP32, caches sensor data |
| ESP32 comms | HTTP long-polling (ESP32 polls every 10–30s) | Dispense, flush, and health-check commands |
| Cloud payment | `kulhad.vercel.app` → Razorpay | QR generation, payment status, cup count |
| RFID auth | pyscard + ACR122U + ukteawallet.com | 5-step AES card authentication |

---

## Quick Start

### 1. Install dependencies

```bash
./setup.sh
```

Installs system libraries (`pcscd`, `swig`, graphics deps), creates a Python virtualenv, and installs all Python dependencies.

### 2. Set this machine's identity

Per-machine values (`DEVICE_ID`, `MACHINE_ID`, `RFID_MACHINE_ID`, `PUMP_FLOW_RATE_ML_PER_SEC`) live in `machine_config.py`, which is **gitignored on purpose** — every kiosk shares the same code via git, but each physical machine has its own ESP32, its own Kulhad machine record, and its own pump calibration.

```bash
cp machine_config.py.example machine_config.py
# then edit machine_config.py with this machine's real values
```

### 3. Configure ESP32 network routing

The ESP32 is hardcoded to reach the RPi gateway at `192.168.0.100`. Assign that IP as an alias on `wlan0`:

```bash
# Temporary (resets on reboot)
sudo ip addr add 192.168.0.100/24 dev wlan0

# Permanent (via NetworkManager)
sudo nmcli connection modify "YOUR_WIFI_SSID" +ipv4.addresses "192.168.0.100/24"
sudo nmcli connection up "YOUR_WIFI_SSID"
```

---

## Running the Kiosk

### Development

```bash
./run_all.sh        # backend (polling_server2.py) + Kivy UI together
```

```bash
./run_demo.py       # full UI with no physical hardware — mocked ESP32/API responses
```

### Production (systemd, auto-restarting)

Production machines run via `launch_pi.sh` under a systemd service — **do not** use `run_all.sh` in production.

```bash
./install_autostart.sh     # one-time: generates and installs the systemd unit
./setup_pi_deploy.sh       # one-time: wires up the pull-based auto-update pipeline (see below)
```

```bash
sudo systemctl start urban-kettle      # start
sudo systemctl stop urban-kettle       # stop
sudo systemctl restart urban-kettle    # restart
sudo systemctl status urban-kettle     # status
sudo journalctl -u urban-kettle -f     # live logs
```

### Auto-update

Once `setup_pi_deploy.sh` has run, a cron job checks for new commits on `main` every 5 minutes (`update.sh`) and restarts the service only when an update is actually found — never mid-order. Deploying a change is just:

```bash
git push origin main
```

No manual deploy step on the kiosk itself. See `WATCHDOG_DESIGN.md` for a related reliability mechanism that's designed but not yet enabled.

---

## Configuration Reference

### `config.py` (shared, version-controlled)

| Constant | Value | Description |
|---|---|---|
| `POLLING_SERVER_URL` | `http://localhost:5000` | ESP32 bridge address |
| `PT100_SENSOR_ID` | `pt100_sensor_01` | Water temperature sensor ID (must match ESP32 firmware) |
| `KTYPE_SENSOR_ID` | `ktype_sensor_01` | Heater element temperature sensor ID |
| `SERVING_TEMP` | `80.0 °C` | Minimum temperature before orders are allowed |
| `CANISTER_ALERT_THRESHOLD` | `10` | Cups remaining at which the low-stock alert is sent to Kulhad |
| `MACHINE_EMPTY_THRESHOLD` | `2` | Cups remaining at/below which the machine shows the empty page |
| `ml_to_pump_ms(ml)` | — | `(ml / PUMP_FLOW_RATE_ML_PER_SEC) × 1000` ms |

### `machine_config.py` (gitignored, per physical machine)

| Constant | Description |
|---|---|
| `DEVICE_ID` | ESP32 MAC-based ID, e.g. `UK_XXXXXXXXXXXX` — set manually, never auto-detected |
| `MACHINE_ID` | This machine's identifier in the Kulhad dashboard, e.g. `UKL_BLR_XXX` |
| `RFID_MACHINE_ID` | This machine's terminal ID on ukteawallet.com, e.g. `UK_XXXX` |
| `PUMP_FLOW_RATE_ML_PER_SEC` | Measured by running the pump 60s and timing the output — re-measure if the pump is replaced |

Copy `machine_config.py.example` to get started — see Quick Start above.

---

## UI Screens

| Screen (`screen_manager` name) | Purpose |
|---|---|
| `selection` — **Home** | Cup count selection (1–5). Confirm → QR prefetch → payment. 10s inactivity → screensaver. |
| `payment_method` | Not navigated to directly — logic container that owns RFID polling lifecycle. |
| `loading` | Spinner while a QR code is generated in the background. 30s timeout → error fallback. |
| `payment` | Razorpay UPI QR, 2-minute countdown, polls payment status every 2s. |
| `qr_expired` | Shown when the payment timer elapses. "Try Again" returns home. |
| `rfid_auth` | RFID card authentication (3-step progress). 9s timeout. Success → `place_cup` with 1 cup pre-selected. |
| `place_cup` | "Place your cup" + 30s timer + "Dispense Now" button. |
| `dispensing` | Plays a dispensing video synced to the pump duration; falls back to a generic video if no per-ml clip exists. |
| `thank_you` | Auto-returns home after ~5s. Triggers the idle auto-flush timer. Routes to `machine_empty` if cups hit 0. |
| `heating` | Shown when PT100 < `SERVING_TEMP`. Polls temperature every 1s; redirects home once ready. |
| `hardware_error` | Critical ESP32 errors (overheat, sensor fault, repeated read failures). Auto-clears if the error resolves. |
| `machine_empty` | Cups at 0, or ESP32 offline. Two modes: `empty` (out of stock) and `offline` (unreachable). Polls every 3s. |
| `flush` | Automated maintenance flush in progress (water → tea). Blocks new orders while active. |
| `screensaver` | Idle video after 30s of inactivity, downloaded and cached from Kulhad. Touch/motion wakes it. |

---

## User Flows

```
UPI Payment
  Selection → Loading → Payment (QR, 2 min) → [paid] → Place Cup (30s)
    → Dispensing (~11s video) → Thank You (5s) → Selection

RFID Card
  Selection → [tap card] → RFID Auth (≤9s) → [success]
    → Place Cup → Dispensing → Thank You → Selection

Multi-Cup (e.g. 3 cups)
  Place Cup [1/3] → Dispensing → Place Cup [2/3] → Dispensing
    → Place Cup [3/3] → Dispensing → Thank You → Selection

Heating (on startup or after idle cooldown)
  Temperature < SERVING_TEMP → Heating (live polling) → ready → Selection

Auto-Flush (idle after last dispense)
  Flush Page → Water Flush (ESP32) → Tea Flush (ESP32) → Selection
```

---

## Backend API Integrations

### Kulhad Cloud (`kulhad.vercel.app`)

| Endpoint | When called | Purpose |
|---|---|---|
| `POST /api/direct-payment` | QR generation | Create a Razorpay UPI QR — returns the UPI image content, ID, and amount |
| `POST /api/transaction-status` | Every 2s on the payment page | Poll `active` / `paid` / `expired` |
| `POST /api/qrcode-close` | On cancel/timeout | Invalidate the QR on Razorpay |
| `POST /api/reduce-cups` (`cupsToReduce=0`) | Home screen / global status check | Read-only cup count |
| `POST /api/reduce-cups` (`cupsToReduce=N`) | After a confirmed dispense | Deduct N cups |
| `GET /api/MachinesStatus?machineId=X` | Global status monitor, every 10s | Check ONLINE/OFFLINE |
| `GET /api/getMachineData?machineId=X` | Boot + periodic config refresh | Fetch `flushTimeMinutes`, `mlToDispense` |
| `POST /api/canister-check` | Cup count crosses `CANISTER_ALERT_THRESHOLD` | Send low-stock alert |
| `POST /api/machine-temperature` | Every 2 minutes | Cloud temperature logging |
| `POST /api/water-level` | On a `waterLevelLow` transition | Report/clear the tank-low alert |

### ESP32 Polling Bridge (`localhost:5000`)

| Endpoint | When called | Purpose |
|---|---|---|
| `GET /api/device/{id}/temperature` | Frequently (0.5–20s, adaptive) | Cached PT100 temp, water level, `machineState`, timestamp |
| `GET /api/device/{id}/pump_status` | Every 0.5s during dispensing | Pump state, progress, elapsed time |
| `GET /api/device/{id}/history` | On error lookups | Recent raw health-check payloads |
| `GET /api/devices` | Connection check | Confirm the ESP32 is registered |
| `GET /api/status` | Startup | Server health |
| `POST /api/device/command` | Dispense, flush, solenoid, settings | Queue a command for the ESP32 |

### Tea Wallet (`ukteawallet.com`)

Five-step AES authentication for RFID prepaid cards: `/api/rfid/auth/start`, `/api/rfid/auth/step2`, `/api/rfid/auth/verify`.

---

## Hardware Integrations

### ESP32 Commands

| Action | Trigger | Parameters |
|---|---|---|
| `start_dispense` | "Dispense Now" button | `pumpOperationDuration` (ms), `jobId` |
| `water_dispense` | Auto-flush (water phase) | `jobId` |
| `tea_dispense` | Auto-flush (tea phase) | `jobId` |
| `solenoid_control` | Low-temp bypass (legacy) | `duration` (ms) |
| `update_pump_settings` | `mlToDispense` changed on Kulhad | `pumpOperationDuration` (ms) |
| `health_check` | Periodic + on-demand | — |

### RFID Reader (ACR122U via pyscard)

- `FF CA 00 00 00` APDU to read the card UID
- RF keep-alive every 2s to maintain the field (paused during UI animations/auth)
- LED: green (ready), red (authenticating)

### Temperature Sensors

- **PT100** — water temperature. Treated as disconnected if reading is `< -10°C` or `> 120°C`.
- **K-type** — heater element temperature (logged only, not used for flow control).
- Cache-first reads from the ESP32's periodic health POST — no extra round-trips in normal operation.

---

## Known Limitations

| Item | Detail |
|---|---|
| Pump completion timing | The ESP32's pump-status endpoint doesn't report real elapsed time, so the pump timer (not status polling) is the sole dispense-completion signal — intentional. |
| Config reload | Changes to `flushTimeMinutes` or `mlToDispense` on Kulhad require a service restart to take effect; they're only fetched at boot. |
| RFID optional | If `pyscard`/the reader is unavailable, RFID flows are skipped gracefully rather than crashing. |

---

## Hardware Debugging

```bash
# Registered devices
curl http://localhost:5000/api/devices

# Cached temperature/water-level reading
curl http://localhost:5000/api/device/<DEVICE_ID>/temperature

# Queue a live health check
curl -X POST http://localhost:5000/api/device/command \
  -H "Content-Type: application/json" \
  -d '{"messageType":"command","commandType":"control","version":"1.0","commandId":"cmd_test_health","deviceId":"<DEVICE_ID>","command":{"action":"health_check"}}'

# Check machine status on Kulhad
curl "https://kulhad.vercel.app/api/MachinesStatus?machineId=<MACHINE_ID>"
```

---

## Repository Structure

```
urban-kettle-withRFID/
├── config.py                    Shared config (sensor IDs, thresholds, serving temp)
├── machine_config.py.example    Template for per-machine identity (copy → machine_config.py)
├── main_app.py                  ChaiOrderingApp — all screens, flows, state
├── polling_server2.py           Local Flask bridge to the ESP32
├── run_demo.py                  Hardware-free UI demo
│
├── launch_pi.sh                 Production launcher, run by systemd
├── update.sh                    Pull-based auto-update, run by cron every 5 min
├── setup_pi_deploy.sh           One-time: cron + sudoers + systemd wiring for auto-update
├── setup.sh                     One-time: system deps + Python venv
├── install_autostart.sh         One-time: generates/installs the systemd unit
├── run_all.sh                   Dev-only: backend + UI together, no systemd
│
├── ui_pages/                    One file per screen (see "UI Screens" above)
│
└── utils/
    ├── api_client.py            All REST calls — Kulhad, Razorpay, ESP32 bridge
    ├── hardware_monitor.py      Background temperature/connection polling
    ├── rfid_aes_auth.py         ACR122U + 5-step AES auth
    ├── qr_utils.py              QR image generation
    └── screensaver_manager.py   Downloads/caches the screensaver video from Kulhad
```

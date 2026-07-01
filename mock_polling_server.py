#!/usr/bin/env python3
"""
Mock Polling Server — Urban Kettle local testing (no hardware required)

Drop-in replacement for polling_server2.py.  Exposes exactly the same
API endpoints the Kivy app and hardware_monitor call, but internally
simulates the ESP32 responses without any physical device.

Start order:
  Terminal 1 →  python3 mock_polling_server.py
  Terminal 2 →  UK_TEST_MODE=1 python3 main_app.py

Control endpoints (same port, /mock/ prefix):
  GET  /mock/state                       — view current simulated state
  POST /mock/set/temperature?value=75    — set water temp (below 80 → heating page)
  POST /mock/set/water?value=5           — set water level in cups
  POST /mock/set/offline                 — trigger maintenance page
  POST /mock/set/online                  — recover machine
  GET  /mock/help                        — list all control endpoints

RFID simulation (no hardware needed):
  The Sycreader won't be found on a dev machine so the app falls back to
  Kivy keyboard mode.  Click the Kivy window, type 8+ digits, press Enter.
  The app captures it as a card scan exactly like a real card tap.

Original polling_server2.py is NOT modified.
"""

import time
import uuid
import threading
import sys
from datetime import datetime

from flask import Flask, request, jsonify

app = Flask(__name__)

# ── suppress Flask's per-request log noise ────────────────────────────────────
import logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# Simulated ESP32 state — all reads/writes protected by _lock
# ─────────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()

_state = {
    "temperature":   85.0,     # PT100 water temp °C  (serving temp = 80.0)
    "ktype_temp":    93.0,     # heater element temp °C
    "water_level":   10.0,     # ultrasonic sensor → cups equivalent
    "water_level_low": False,  # ESP32 health_check → waterLevelLow flag
    "machine_state": "ONLINE", # ONLINE | OFFLINE

    # Pump — driven by start_time + duration so progress is always accurate
    "pump_start_time":   None,   # time.time() when pump started, None = idle
    "pump_duration_ms":  0,      # milliseconds for current run
    "pump_operation":    "idle", # "dispensing" | "water_dispense" | "tea_dispense" | "idle"
    "pump_completed":    False,  # True after duration elapsed (sticky until next command)

    # Health timestamp — keeps /temperature endpoint fresh
    "health_ts": datetime.now().isoformat(),
}


def _pump_data():
    """Return real-time pump state dict.  Call inside _lock."""
    s = _state
    if s["pump_start_time"] is None:
        return {
            "component":     "pump_01",
            "pumpState":     "idle",
            "operation":     "idle",
            "elapsedTime":   0,
            "remainingTime": 0,
            "progress":      0.0,
        }

    elapsed_ms  = (time.time() - s["pump_start_time"]) * 1000.0
    duration_ms = s["pump_duration_ms"]

    if elapsed_ms >= duration_ms:
        # Pump finished — mark completed and clear start_time so next call is idle
        s["pump_completed"]  = True
        s["pump_start_time"] = None
        
        # Enhance: Automatically decrement water level to simulate real dispense
        # 1 cup = approx 10000ms pump time (assuming 1 cup ≈ 100ml)
        cups_dispensed = duration_ms / 10000.0
        s["water_level"] = max(0.0, s["water_level"] - cups_dispensed)
        if s["water_level"] <= 0:
            s["water_level_low"] = True
            
        return {
            "component":     "pump_01",
            "pumpState":     "completed",
            "operation":     s["pump_operation"],
            "elapsedTime":   int(duration_ms),
            "remainingTime": 0,
            "progress":      100.0,
        }

    remaining_ms = duration_ms - elapsed_ms
    progress     = (elapsed_ms / duration_ms) * 100.0
    return {
        "component":     "pump_01",
        "pumpState":     "Ongoing",
        "operation":     s["pump_operation"],
        "elapsedTime":   int(elapsed_ms),
        "remainingTime": int(remaining_ms),
        "progress":      round(progress, 1),
    }


def _sensor_checks():
    """Return sensor check payload in ESP32 health-check format."""
    with _lock:
        temp    = _state["temperature"]
        ktype   = _state["ktype_temp"]
        water   = _state["water_level"]
        m_state = _state["machine_state"]
    return {
        "checks": {
            "sensor:pt100_sensor_01":       [{"observedValue": temp,   "unit": "celsius", "status": "ok"}],
            "sensor:ktype_sensor_01":        [{"observedValue": ktype,  "unit": "celsius", "status": "ok"}],
            "sensor:ultrasonic_sensor_01":   [{"observedValue": water,  "unit": "cups",    "status": "ok"}],
        },
        "machineState": m_state,
    }


def _log(action, detail=""):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}]  {action}"
    if detail:
        line += f"  — {detail}"
    print(line, flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core endpoints (same as polling_server2.py)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def api_status():
    """Alive check — hardware_monitor.check_polling_server()."""
    return jsonify({
        "status":    "running",
        "mode":      "mock",
        "timestamp": datetime.now().isoformat(),
    }), 200


@app.route("/api/devices", methods=["GET"])
def api_devices():
    """List connected devices — used by hardware_monitor for connection check."""
    from config import DEVICE_ID
    return jsonify({
        "devices": [{
            "deviceId":        DEVICE_ID,
            "status":          _state["machine_state"],
            "last_seen":       _state["health_ts"],
            "firmwareVersion": "2.1.6-MOCK",
        }],
        "count": 1,
    }), 200


@app.route("/api/device/<device_id>/temperature", methods=["GET"])
def api_temperature(device_id):
    """Cached sensor data — called by hardware_monitor and many UI pages."""
    sc = _sensor_checks()
    with _lock:
        ts = _state["health_ts"]
    return jsonify({
        "deviceId":          device_id,
        "pt100_temperature": sc["checks"]["sensor:pt100_sensor_01"][0]["observedValue"],
        "ktype_temperature": sc["checks"]["sensor:ktype_sensor_01"][0]["observedValue"],
        "water_level":       sc["checks"]["sensor:ultrasonic_sensor_01"][0]["observedValue"],
        "water_level_unit":  "cups",
        "machineState":      sc["machineState"],
        "timestamp":         ts,
        "source":            "mock",
    }), 200


@app.route("/api/device/<device_id>/history", methods=["GET"])
def api_history(device_id):
    """Device history — used by hardware_monitor connection check and the
    waterLevelLow read path (the /temperature cache endpoint doesn't expose
    that field, mirroring the real polling_server2.py's behaviour).
    """
    sc = _sensor_checks()
    with _lock:
        ts = _state["health_ts"]
        water_low = _state["water_level_low"]
    entry = {
        "timestamp": ts,
        "data": {
            "messageType":  "health_check",
            "deviceId":     device_id,
            "machineState": sc["machineState"],
            "waterLevelLow": water_low,
            "checks":       sc["checks"],
        },
    }
    return jsonify({"deviceId": device_id, "commands": {}, "health": [entry]}), 200


@app.route("/api/device/sensor/pump_status", methods=["GET", "POST"])
def api_pump_status():
    """
    GET  — app polls every 0.5 s during dispensing (dispensing_page).
    POST — normally sent by real ESP32; accepted silently in mock mode.
    """
    if request.method == "POST":
        return jsonify({"status": "received"}), 200

    from config import DEVICE_ID
    device_id = request.args.get("deviceId", DEVICE_ID)
    with _lock:
        pump = _pump_data()

    return jsonify({
        "messageType": "command_response",
        "version":     "1.0",
        "deviceId":    device_id,
        "response": {
            "statusCode": 200,
            "status":     "success",
            "data":       pump,
        },
    }), 200


@app.route("/api/device/command", methods=["POST"])
def api_command():
    """
    Central command endpoint — app POSTs all hardware commands here.

    Handles both plain commands and flush-wrapped {"commands": [...]} format.
    Simulates the ESP32 immediately and returns a realistic response so the
    app never has to wait for a real device.
    """
    body = request.get_json(silent=True) or {}

    # ── unwrap {"commands": [inner]} (flush commands) ──────────────────────
    if "commands" in body and isinstance(body["commands"], list) and body["commands"]:
        body = body["commands"][0]

    device_id  = body.get("deviceId", "UNKNOWN")
    command_id = body.get("commandId", f"mock_{uuid.uuid4().hex[:8]}")
    cmd_info   = body.get("command", {})
    action     = cmd_info.get("action", "")
    params     = cmd_info.get("parameters", {}) or {}

    _log(f"CMD  {action}", f"id={command_id[:20]}")

    # ── dispatch ────────────────────────────────────────────────────────────
    if action == "health_check":
        return _handle_health_check(command_id, device_id)

    elif action == "start_dispense":
        return _handle_start_dispense(command_id, device_id, params)

    elif action in ("water_dispense", "tea_dispense"):
        return _handle_flush(command_id, device_id, action)

    elif action == "solenoid_control":
        state = params.get("state", "open")
        _log(f"     solenoid → {state}")
        return _cmd_ok(command_id, device_id, {"solenoidState": state})

    elif action == "update_pump_settings":
        ms = int(params.get("pumpOperationDuration", 10000))
        _log(f"     pump settings → {ms} ms")
        return _cmd_ok(command_id, device_id, {"settingsUpdated": True, "pumpOperationDuration": ms})

    elif action == "set_state":
        new_state = params.get("machineState", "ONLINE").upper()
        with _lock:
            _state["machine_state"] = new_state
            _state["health_ts"]     = datetime.now().isoformat()
        _log(f"     set_state → {new_state}  (operating-hours scheduler)")
        return _cmd_ok(command_id, device_id, {"machineState": new_state})

    else:
        _log(f"     unknown action '{action}' — ACK'd")
        return _cmd_ok(command_id, device_id, {"status": "ok", "action": action})


# ── command handlers ──────────────────────────────────────────────────────────

def _handle_health_check(command_id, device_id):
    sc = _sensor_checks()
    with _lock:
        _state["health_ts"] = datetime.now().isoformat()
    _log(f"     health_check → temp={_state['temperature']}°C  "
         f"water={_state['water_level']} cups  state={_state['machine_state']}")
    return jsonify({
        "messageType":  "command_response",
        "commandId":    command_id,
        "deviceId":     device_id,
        "machineState": sc["machineState"],
        "checks":       sc["checks"],
        "response":     {"statusCode": 200, "status": "success"},
    }), 200


def _handle_start_dispense(command_id, device_id, params):
    duration_ms = int(params.get("pumpOperationDuration", 11111))
    job_id      = params.get("jobId", "?")

    with _lock:
        _state["pump_start_time"]  = time.time()
        _state["pump_duration_ms"] = duration_ms
        _state["pump_operation"]   = "dispensing"
        _state["pump_completed"]   = False
        _state["health_ts"]        = datetime.now().isoformat()

    _log(f"     start_dispense → {duration_ms} ms  job={job_id}")
    return jsonify({
        "messageType": "command_response",
        "commandId":   command_id,
        "deviceId":    device_id,
        "response": {
            "statusCode": 200,
            "status":     "success",
            "data": {
                "pumpState":     "Ongoing",
                "operation":     "dispensing",
                "elapsedTime":   0,
                "remainingTime": duration_ms,
                "progress":      0.0,
            },
        },
    }), 200


def _handle_flush(command_id, device_id, action):
    label = "WATER" if action == "water_dispense" else "TEA"
    _log(f"     {label} flush — running 3 s pump (blocking until done)")

    with _lock:
        _state["pump_start_time"]  = time.time()
        _state["pump_duration_ms"] = 3_000
        _state["pump_operation"]   = action
        _state["pump_completed"]   = False

    # ESP32 holds the response open for 3 s while pump runs, then returns 200.
    time.sleep(3)

    with _lock:
        _state["pump_completed"] = True
        _state["pump_operation"] = "idle"

    return jsonify({
        "messageType": "command_response",
        "commandId":   command_id,
        "deviceId":    device_id,
        "response":    {"statusCode": 200, "status": "success",
                        "data": {"flushComplete": True, "action": action}},
    }), 200


def _cmd_ok(command_id, device_id, data):
    return jsonify({
        "messageType": "command_response",
        "commandId":   command_id,
        "deviceId":    device_id,
        "response":    {"statusCode": 200, "status": "success", "data": data},
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Control endpoints  /mock/...   (adjust simulated state at runtime)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/mock/help", methods=["GET"])
def mock_help():
    return jsonify({
        "endpoints": {
            "GET  /mock/state":                       "View current simulated state",
            "POST /mock/set/temperature?value=<°C>":  "Set water temperature (80°C = serving temp)",
            "POST /mock/set/water?value=<cups>":      "Set water level in cups",
            "POST /mock/set/online":                  "Set machine ONLINE",
            "POST /mock/set/offline":                 "Set machine OFFLINE (shows maintenance page)",
            "POST /mock/set/waterlevel_low?value=true": "Set waterLevelLow flag (shows maintenance page)",
        }
    }), 200


@app.route("/mock/state", methods=["GET"])
def mock_state():
    with _lock:
        pump = _pump_data()
        return jsonify({
            "temperature":   _state["temperature"],
            "ktype_temp":    _state["ktype_temp"],
            "water_level":   _state["water_level"],
            "water_level_low": _state["water_level_low"],
            "machine_state": _state["machine_state"],
            "pump":          pump,
            "health_ts":     _state["health_ts"],
        }), 200


@app.route("/mock/set/temperature", methods=["POST"])
def mock_set_temp():
    try:
        val = float(request.args.get("value", 85))
    except ValueError:
        return jsonify({"error": "invalid value"}), 400
    with _lock:
        _state["temperature"] = val
        _state["ktype_temp"]  = val + 8.0
        _state["health_ts"]   = datetime.now().isoformat()
    marker = "above serving temp ✓" if val >= 80 else "⚠️  BELOW 80°C — heating page will show"
    _log(f"CTRL temperature → {val}°C  ({marker})")
    return jsonify({"ok": True, "temperature": val}), 200


@app.route("/mock/set/water", methods=["POST"])
def mock_set_water():
    try:
        val = float(request.args.get("value", 10))
    except ValueError:
        return jsonify({"error": "invalid value"}), 400
    with _lock:
        _state["water_level"] = val
        _state["health_ts"]   = datetime.now().isoformat()
    marker = "⚠️  machine empty" if val == 0 else "OK"
    _log(f"CTRL water level → {val} cups  ({marker})")
    return jsonify({"ok": True, "water_level": val}), 200


@app.route("/mock/set/online", methods=["POST"])
def mock_set_online():
    with _lock:
        _state["machine_state"] = "ONLINE"
        _state["health_ts"]     = datetime.now().isoformat()
    _log("CTRL machine → ONLINE")
    return jsonify({"ok": True, "machine_state": "ONLINE"}), 200


@app.route("/mock/set/waterlevel_low", methods=["POST"])
def mock_set_waterlevel_low():
    value = request.args.get("value", "true").lower() in ("1", "true", "yes")
    with _lock:
        _state["water_level_low"] = value
        _state["health_ts"]       = datetime.now().isoformat()
    _log(f"CTRL waterLevelLow → {value}  (maintenance page should appear)" if value
         else "CTRL waterLevelLow → False  (recovery)")
    return jsonify({"ok": True, "water_level_low": value}), 200


@app.route("/mock/set/offline", methods=["POST"])
def mock_set_offline():
    with _lock:
        _state["machine_state"] = "OFFLINE"
        _state["health_ts"]     = datetime.now().isoformat()
    _log("CTRL machine → OFFLINE  (maintenance page should appear)")
    return jsonify({"ok": True, "machine_state": "OFFLINE"}), 200


# ─────────────────────────────────────────────────────────────────────────────
# Stub endpoints that the real server has (silence 404s from the app)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/device/handshake",        methods=["POST"])
@app.route("/api/device/health",           methods=["POST"])
@app.route("/api/device/command/result",   methods=["POST"])
@app.route("/api/device/ota/progress",     methods=["POST"])
@app.route("/api/device/commands/ota",     methods=["POST"])
@app.route("/api/device/commands/pending", methods=["GET"])
def stub_endpoints():
    return jsonify({"status": "received"}), 200


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _print_banner(port):
    print(f"""
╔══════════════════════════════════════════════════════╗
║      Urban Kettle — Mock Polling Server              ║
║      (no hardware required)                          ║
╠══════════════════════════════════════════════════════╣
║  Simulates: ESP32 + real polling_server2.py          ║
║  Port     : {port:<42}║
╚══════════════════════════════════════════════════════╝

Default state:
  Temperature  : {_state['temperature']}°C  (serving temp = 80.0°C — skip heating page)
  Water level  : {_state['water_level']} cups
  Machine      : {_state['machine_state']}

Start the app in another terminal:
  UK_TEST_MODE=1 python3 main_app.py

Control commands (from any terminal):
  curl -s http://localhost:{port}/mock/state | python3 -m json.tool
  curl -s -X POST "http://localhost:{port}/mock/set/temperature?value=75"
  curl -s -X POST "http://localhost:{port}/mock/set/water?value=0"
  curl -s -X POST  http://localhost:{port}/mock/set/offline
  curl -s -X POST  http://localhost:{port}/mock/set/online
  curl -s -X POST "http://localhost:{port}/mock/set/waterlevel_low?value=true"
  curl -s -X POST "http://localhost:{port}/mock/set/waterlevel_low?value=false"

RFID simulation:
  Click the Kivy window → type 8+ digits → press Enter
  (e.g. type  1234567890  then Enter)

Logs follow:
""")


def _heartbeat_loop():
    """Simulate the ESP32's continuous health POSTs — keeps health_ts fresh
    so the app's staleness check (>90s → treat as hardware offline) never
    fires spuriously while the mock machine is ONLINE.
    Also simulates realistic temperature fluctuations (cooling and heating).
    """
    heating_active = False
    
    while True:
        time.sleep(5)
        with _lock:
            if _state["machine_state"] == "ONLINE":
                _state["health_ts"] = datetime.now().isoformat()
                
                # Enhance: Simulate boiler temperature physics
                if heating_active:
                    _state["temperature"] += 1.5  # Heat up quickly
                    if _state["temperature"] >= 85.0:
                        heating_active = False
                else:
                    _state["temperature"] -= 0.1  # Cool down slowly
                    if _state["temperature"] < 78.0:
                        heating_active = True
                        
                # Keep ktype relatively close to pt100
                _state["ktype_temp"] = _state["temperature"] + 8.0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Urban Kettle Mock Polling Server")
    parser.add_argument("--port",  type=int,   default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--temp",  type=float, default=85.0, help="Initial water temperature °C (default: 85)")
    parser.add_argument("--cups",  type=float, default=10.0, help="Initial water level in cups (default: 10)")
    parser.add_argument("--cold",  action="store_true",      help="Start with temp=60°C to trigger heating page")
    parser.add_argument("--empty", action="store_true",      help="Start with 0 cups to trigger machine-empty page")
    args = parser.parse_args()

    if args.cold:
        args.temp = 60.0
    if args.empty:
        args.cups = 0.0

    with _lock:
        _state["temperature"] = args.temp
        _state["ktype_temp"]  = args.temp + 8.0
        _state["water_level"] = args.cups

    _print_banner(args.port)

    threading.Thread(target=_heartbeat_loop, daemon=True).start()

    try:
        app.run(host="0.0.0.0", port=args.port, debug=False, use_reloader=False)
    except OSError as e:
        print(f"\n❌  Cannot start on port {args.port}: {e}")
        print(f"    Is polling_server2.py already running on that port?")
        print(f"    Stop it first, or use:  python3 mock_polling_server.py --port 5001")
        print(f"    Then set:  POLLING_SERVER_URL=http://localhost:5001  in config.py")
        sys.exit(1)

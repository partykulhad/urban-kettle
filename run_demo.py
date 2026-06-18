"""
DEMO MODE — runs the full Urban Kettle UI with all hardware mocked.
No ESP32, no polling server, no RFID reader, no internet required.

Usage:
    python run_demo.py

Demo behaviour:
  • Cup selection home screen starts with 50 cups
  • QR payment screen auto-pays after 5 seconds (simulates UPI scan)
  • Dispense runs for the real pump duration (~11 s for 100 ml) then completes
  • All temperature checks return 85 °C (above serving temp — no heating page)
  • Machine is always ONLINE
  • RFID: reader not available (graceful skip)
  • Window shown at 881×661, right-side-up, not fullscreen
"""

import os
import sys
import time
import json as _json
from datetime import datetime as _dt

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Mock the polling-server session (localhost:5000).
#     We patch _localhost_session in the api_client module so that the ORIGINAL
#     get_localhost_session() function returns our mock — no need to replace the
#     function itself, which means all callers (even those that imported the
#     function by name at module level) transparently get the mock.
# ─────────────────────────────────────────────────────────────────────────────
import utils.api_client as _api_mod


class _MockResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    @property
    def text(self):
        return _json.dumps(self._data)

    def raise_for_status(self):
        pass


class _MockLocalSession:
    """Drop-in for requests.Session — handles all localhost:5000 endpoints."""

    # Shared across all instances so state set via a command POST is visible
    # to subsequent temperature GETs (mirrors the real polling server's
    # single shared _state dict).
    _machine_state = "ONLINE"

    def _temp_resp(self):
        return _MockResponse({
            "pt100_temperature": 85.0,
            "ktype_temperature": 90.0,
            "machineState": _MockLocalSession._machine_state,
            "timestamp": _dt.now().isoformat(),
        })

    def get(self, url, **kwargs):
        u = url.lower()
        if 'temperature' in u:
            return self._temp_resp()
        if 'pump_status' in u:
            # Pump simulation is handled by _DemoApiClient.get_pump_status()
            # which is called before this session layer.  This fallback path
            # should not normally be reached.
            return _MockResponse({
                "response": {
                    "data": {
                        "pumpState": "idle",
                        "progress": 0,
                        "elapsedTime": 0,
                        "remainingTime": 0,
                    }
                }
            })
        if '/history' in u:
            return _MockResponse({"health": [], "temperature": []})
        if '/api/status' in u:
            return _MockResponse({"status": "ok"})
        if '/api/devices' in u:
            from config import DEVICE_ID
            return _MockResponse({"devices": [{"deviceId": DEVICE_ID, "online": True}]})
        if '/health' in u:
            return _MockResponse({"checks": [], "statusCode": 200})
        return _MockResponse({"status": "ok"})

    def post(self, url, **kwargs):
        u = url.lower()
        if '/api/device/command' in u:
            body = kwargs.get('json', {}) or {}
            action = (body.get('command') or {}).get('action', '')
            if action == 'set_state':
                new_state = (body.get('command') or {}).get('parameters', {}).get('machineState', 'ONLINE').upper()
                _MockLocalSession._machine_state = new_state
                print(f"🎭 [DEMO] machineState → {new_state}  (operating-hours scheduler)")
            return _MockResponse({"statusCode": 200, "status": "success",
                                  "response": {"statusCode": 200, "status": "success"}})
        return _MockResponse({"status": "ok"})

    def head(self, url, **kwargs):
        return _MockResponse({})


# Install the mock session — get_localhost_session() reads _localhost_session
# from this module so all callers automatically get the mock.
_api_mod._localhost_session = _MockLocalSession()


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Replace ApiClient with a demo subclass.
#     Must happen BEFORE main_app is imported so that
#     `from utils.api_client import ApiClient` in main_app picks up the mock.
# ─────────────────────────────────────────────────────────────────────────────
_OrigApiClient = _api_mod.ApiClient

# Track when each QR was "issued" to simulate auto-pay after 5 s
_qr_issue_time: dict = {}


class _DemoApiClient(_OrigApiClient):

    def warmup_apis(self):
        print("🎭 [DEMO] warmup_apis — skipped")

    def generate_payment_qr(self, machine_id, number_of_cups):
        qr_id = f"DEMO_QR_{int(time.time())}_{number_of_cups}"
        txn_id = f"DEMO_TXN_{int(time.time())}_{number_of_cups}"
        _qr_issue_time[qr_id] = time.time()
        amount = number_of_cups * 30
        print(f"🎭 [DEMO] generate_payment_qr → id={qr_id}, amount=₹{amount}")
        return {
            "id": qr_id,
            "transactionId": txn_id,
            # imageContent is the UPI deep-link; QRUtils.generate_qr_from_content
            # turns this string into a real QR image using the qrcode library.
            "imageContent": (
                f"upi://pay?pa=demo@upi&pn=UrbanKettle"
                f"&am={amount}&cu=INR&tn=Demo-{number_of_cups}cups"
            ),
            "amount": amount,
            "success": True,
        }

    def check_payment_status(self, qr_code_id):
        issued = _qr_issue_time.get(qr_code_id, time.time())
        elapsed = time.time() - issued
        if elapsed >= 5.0:
            print("🎭 [DEMO] payment status → PAID")
            return {"message": "paid", "status": "paid"}
        print(f"🎭 [DEMO] payment status → active ({elapsed:.1f}s / 5s)")
        return {"message": "active", "status": "active"}

    def cancel_payment(self, qr_code_id):
        _qr_issue_time.pop(qr_code_id, None)
        print(f"🎭 [DEMO] cancel_payment({qr_code_id})")
        return {"success": True}

    def check_machine_status(self, machine_id):
        return {"success": True, "data": {"status": "online"}}

    def get_remaining_cups(self, machine_id):
        return {"success": True, "cups": 50}

    def reduce_cups(self, machine_id, number_of_cups):
        # Reset pump simulation so each dispense gets its own fresh timer.
        self._pump_sim_start = None
        print(f"🎭 [DEMO] reduce_cups({number_of_cups}) — pump timer reset")
        return {"success": True, "cups": 49}

    def get_pump_status(self, device_id):
        """Simulate pump lifecycle: 'ongoing' for pump_duration_s, then 'idle'."""
        from config import ml_to_pump_ms
        try:
            from kivy.app import App
            app = App.get_running_app()
            ml = getattr(app, 'ml_to_dispense', 100)
        except Exception:
            ml = 100
        pump_duration_s = ml_to_pump_ms(ml) / 1000.0

        if not hasattr(self, '_pump_sim_start') or self._pump_sim_start is None:
            self._pump_sim_start = time.time()
            print(f"🎭 [DEMO] Pump sim started — duration {pump_duration_s:.1f}s ({ml}ml)")

        elapsed = time.time() - self._pump_sim_start
        if elapsed < pump_duration_s:
            state = "ongoing"
            progress = (elapsed / pump_duration_s) * 100.0
        else:
            state = "idle"
            progress = 100.0

        return {
            "response": {
                "data": {
                    "pumpState": state,
                    "progress": round(progress, 1),
                    "elapsedTime": int(elapsed * 1000),
                    "remainingTime": max(0, int((pump_duration_s - elapsed) * 1000)),
                }
            }
        }

    def get_machine_data(self, machine_id):
        return {
            "success": True,
            "data": {"flushTimeMinutes": 40, "mlToDispense": 100},
        }

    def get_flush_schedule(self, machine_id):
        return {
            "success": True,
            "data": {"flushTimeMinutes": 40},
        }

    def check_canister_level(self, machine_id, canister_level=5):
        print("🎭 [DEMO] check_canister_level — skipped")
        return {"success": True}

    def water_flush(self, device_id):
        print("🎭 [DEMO] water_flush — instant success")
        return {"dispatched": True, "action": "water_dispense"}

    def tea_flush(self, device_id):
        print("🎭 [DEMO] tea_flush — instant success")
        return {"dispatched": True, "action": "tea_dispense"}

    def validate_rfid_card_aes(self, rfid_auth_handler):
        print("🎭 [DEMO] validate_rfid_card_aes → authenticated")
        return {
            "success": True,
            "authenticated": True,
            "cardId": "DEMO_CARD_001",
            "remainingBalance": 100,
            "machineLocation": "Demo Location",
        }


_api_mod.ApiClient = _DemoApiClient


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Patch the hardware_monitor singleton.
#     The module is already imported by api_client/hardware_monitor; we just
#     replace key instance methods so the app never tries to talk to the ESP32.
# ─────────────────────────────────────────────────────────────────────────────
import utils.hardware_monitor as _hw_mod

_hw = _hw_mod.hardware_monitor  # the singleton

_hw.last_temperature = 85.0
_hw.handshake_complete = True

_hw.start = lambda *a, **kw: print("🎭 [DEMO] hardware_monitor.start() — skipped")
_hw.get_latest_error = lambda *a, **kw: None          # no hardware errors
_hw.is_device_connected = lambda *a, **kw: True
_hw.check_polling_server = lambda *a, **kw: True


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Mock RFID so the app starts even without pyscard / ACR122U.
# ─────────────────────────────────────────────────────────────────────────────
try:
    import utils.rfid_aes_auth as _rfid_mod

    class _DemoRFIDAuth:
        reader_active = False
        _auth_in_progress = False

        def __init__(self, *a, **kw):
            pass

        def start_keepalive(self): pass
        def stop_keepalive(self): pass
        def pause_keepalive(self): pass
        def resume_keepalive(self): pass
        def stop(self): pass
        def get_card_uid(self): return None
        def process_card(self): return {"success": False, "error": "Demo mode — no reader"}

    _rfid_mod.RFIDAESAuth = _DemoRFIDAuth
    print("🎭 [DEMO] RFIDAESAuth replaced with stub")
except Exception as _rfid_err:
    print(f"🎭 [DEMO] Could not patch RFIDAESAuth: {_rfid_err}")


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Import main_app AFTER all patches — so every `from utils.api_client import
#     ApiClient` in main_app (and transitively imported pages) gets the mock.
# ─────────────────────────────────────────────────────────────────────────────
from main_app import ChaiOrderingApp
from kivy.core.window import Window


class DemoChaiOrderingApp(ChaiOrderingApp):
    """Thin subclass that restores desktop-friendly window settings after build()."""

    def on_start(self):
        # build() sets fullscreen='auto' and rotation=180 for the physical
        # tablet.  We undo both so the UI looks correct on a desktop monitor.
        Window.fullscreen = False
        Window.rotation = 0
        Window.resizable = True
        Window.size = (881, 661)
        print()
        print("=" * 60)
        print("🎭  URBAN KETTLE — DEMO MODE")
        print("=" * 60)
        print("  All hardware is simulated — no ESP32 or RFID needed.")
        print("  Payment auto-completes 5 s after the QR screen appears.")
        print("  Dispense runs ~11 s then navigates directly to the thank-you page.")
        print("=" * 60)
        print()


if __name__ == "__main__":
    DemoChaiOrderingApp().run()

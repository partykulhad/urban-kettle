"""
Central Configuration File

Per-machine identity (DEVICE_ID, MACHINE_ID, RFID_MACHINE_ID,
PUMP_FLOW_RATE_ML_PER_SEC) lives in machine_config.py, which is gitignored —
every kiosk shares this file via git, but each one has its own machine_config.py
that's never touched by an update. See machine_config.py.example.
"""

try:
    from machine_config import DEVICE_ID, MACHINE_ID, RFID_MACHINE_ID, PUMP_FLOW_RATE_ML_PER_SEC
except ImportError:
    raise ImportError(
        "machine_config.py not found. This file holds THIS machine's identity "
        "(DEVICE_ID, MACHINE_ID, RFID_MACHINE_ID, PUMP_FLOW_RATE_ML_PER_SEC) and "
        "is intentionally not committed to git. Copy machine_config.py.example to "
        "machine_config.py and fill in this machine's real values before starting."
    )

# ============================================================================
# API CONFIGURATION
# ============================================================================

# Polling server URL (ESP32 communication)
POLLING_SERVER_URL = "http://localhost:5000"


# ============================================================================
# SENSOR ID CONFIGURATION
# ============================================================================
# These must match the component IDs reported by the ESP32 in health_check responses.
# If the ESP32 firmware uses different names, update these values.

PT100_SENSOR_ID = "pt100_sensor_01"    # Water temperature sensor (used for heating check)
KTYPE_SENSOR_ID = "ktype_sensor_01"   # Heater element temperature sensor

# ============================================================================
# MACHINE CONFIGURATION
# ============================================================================

# Cups remaining at which the canister-low alert is sent to Kulhad.
CANISTER_ALERT_THRESHOLD = 10

# Cups remaining at or below which the machine is treated as empty (shows the
# machine_empty page) — a small buffer before truly hitting 0, not literal 0.
MACHINE_EMPTY_THRESHOLD = 2

# ============================================================================
# HEATING CONFIGURATION
# ============================================================================

# Temperature (°C) at which tea is considered ready to serve.
# Change this value if the ESP32 firmware team updates the serving temperature.
SERVING_TEMP = 80.0

# RFID_MACHINE_ID and PUMP_FLOW_RATE_ML_PER_SEC are imported from
# machine_config.py above — both vary per physical machine.


def ml_to_pump_ms(ml: float) -> int:
    """Convert a volume in ml to pump run duration in milliseconds.

    Uses the calibrated PUMP_FLOW_RATE_ML_PER_SEC.
    Examples (540 ml/min pump):
        90  ml → 10,000 ms
        100 ml → 11,111 ms
        110 ml → 12,222 ms
        120 ml → 13,333 ms
    """
    return round((ml / PUMP_FLOW_RATE_ML_PER_SEC) * 1000)


# ============================================================================
# NOTES
# ============================================================================
#
# To change this machine's identity (device replaced, etc.):
# 1. Edit the value in machine_config.py (NOT this file)
# 2. Save and restart the application
#

"""
Central Configuration File
"""

# ============================================================================
# DEVICE CONFIGURATION
# ============================================================================

# ESP32 Device ID.
# Format: UK_XXXXXXXXXXXX (MAC-address based, set by ESP32 firmware).
#
# Leave DEVICE_ID as an empty string ("") on a NEW machine installation.
# The app will query the polling server on startup, detect the connected
# ESP32 automatically, and write its ID back here — no manual step needed.
#
# On an EXISTING machine this value is already filled in.  Change it only
# if the ESP32 board is physically replaced.
DEVICE_ID = ""

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

# Machine ID for cloud APIs
MACHINE_ID = "UKTL_BLN_001"

# ============================================================================
# HEATING CONFIGURATION
# ============================================================================

# Temperature (°C) at which tea is considered ready to serve.
# Change this value if the ESP32 firmware team updates the serving temperature.
SERVING_TEMP = 80.0

# RFID ID for ukteawallet.com (e.g., UK_0007)
RFID_MACHINE_ID = "UK_0007"

# ============================================================================
# PUMP CALIBRATION
# ============================================================================

# Physical flow rate of the pump, measured by running it for 60 seconds and
# measuring the output.  Current calibration: 540 ml/min = 9 ml/s.
# Update this value if the pump is ever replaced or re-calibrated.
PUMP_FLOW_RATE_ML_PER_SEC = 9.0   # 540 ml/min ÷ 60


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
# To change the device ID:
# 1. Edit the DEVICE_ID value above
# 2. Save this file
# 3. Restart the application
#
# The device ID will be automatically used by all hardware API calls
#

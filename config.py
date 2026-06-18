"""
Central Configuration File
"""

# ============================================================================
# DEVICE CONFIGURATION
# ============================================================================
#UK_14335C5D3FB4
#UK_30C9223A073C
# ESP32 Device ID.
# Format: UK_XXXXXXXXXXXX (MAC-address based, printed on the ESP32 board or
# read from the serial monitor at boot).
# Set this manually before deploying.  Change it only if the ESP32 board
# is physically replaced.
DEVICE_ID = "UK_14335C5D48C8"

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
MACHINE_ID = "UKL_BLR_004"

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

"""
Central Configuration File
Edit the DEVICE_ID here to change it for the entire application
"""

# ============================================================================
# DEVICE CONFIGURATION
# ============================================================================

# Device ID for ESP32 communication
# Change this value to match your device's ID
# Format: UK_XXXXXXXXXXXX (where X is your device's MAC address)
DEVICE_ID = "UK_14335C5D48C8"

# ============================================================================
# API CONFIGURATION
# ============================================================================

# Polling server URL (ESP32 communication)
POLLING_SERVER_URL = "http://localhost:5000"

# ============================================================================
# MACHINE CONFIGURATION
# ============================================================================

# Machine ID for cloud APIs
MACHINE_ID = "KH-01"

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

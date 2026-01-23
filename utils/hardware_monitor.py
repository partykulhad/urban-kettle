"""
Hardware Monitor Service
Runs in background to monitor temperature and cup status
"""

import threading
import time
import requests
from datetime import datetime
import subprocess
import sys
import os
import socket


class HardwareMonitor:
    """Background service for hardware monitoring"""
    
    def __init__(self, machine_id="KH-01", api_base_url="http://192.168.68.136:5000"):
        # Use hardcoded device ID from config
        from config import DEVICE_ID
        self.device_id = DEVICE_ID
        print(f"Initialized HardwareMonitor with Device ID: {self.device_id}")
        
        self.machine_id = machine_id
        self.api_base_url = api_base_url  # Static URL - never changes
        
        self.running = False
        self.temp_thread = None
        self.server_process = None
        
        self.last_temperature = None
        self.last_cup_status = None
        self.handshake_complete = False
        
        # Adaptive polling strategy
        self.consecutive_success_count = 0  # Count consecutive 200 responses
        self.polling_interval = 1  # Start with 1 second
        self.is_heating_mode = False  # Flag for temperature heating page
        
        # Adaptive connection status cache
        self._connection_status = None
        self._connection_check_time = 0
        self._connection_cache_ttl_disconnected = 1  # Fast checks when disconnected
        self._connection_cache_ttl_connected = 15    # Slow checks when connected
        self._connection_check_lock = threading.Lock()
        self._background_check_running = False

    def check_polling_server(self):
        """Check if polling server is running (no Docker startup)"""
        try:
            print(f"🔍 Checking polling server at {self.api_base_url}...")
            
            # Check if server is responding
            response = requests.get(f"{self.api_base_url}/api/status", timeout=2)
            if response.status_code == 200:
                print(f"✅ Polling server is RUNNING at {self.api_base_url}")
                print(f"📡 Waiting for ESP32 handshake...")
                return True
            else:
                print(f"⚠️ Server responded with status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to polling server at {self.api_base_url}")
            print(f"💡 Make sure to run: ./run_all.sh")
            return False
        except Exception as e:
            print(f"❌ Error checking polling server: {e}")
            print(f"💡 Make sure to run: ./run_all.sh")
            return False
    
    def wait_for_handshake(self):
        """Wait for ESP32 to connect to the server"""
        print(f"⏳ Waiting for ANY device to connect...")
        
        def handshake_loop():
            while not self.handshake_complete and self.running:
                try:
                    # Check if device is connected
                    url = f"{self.api_base_url}/api/devices"
                    response = requests.get(url, timeout=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        devices = data.get('devices', [])
                        
                        # If any device is connected, accept it
                        if len(devices) > 0:
                            # Pick the first device found
                            device = devices[0]
                            found_id = device.get('deviceId')
                            
                            self.handshake_complete = True
                            self.device_id = found_id
                            print(f"✓ Device connected! ID: {self.device_id}")
                            return
                        
                except Exception as e:
                    pass
                
                time.sleep(2)  # Try every 2 seconds
        
        # Start monitoring in background thread
        handshake_thread = threading.Thread(target=handshake_loop, daemon=True)
        handshake_thread.start()
    
    def start(self):
        """Start the monitoring service"""
        if self.running:
            return
        
        # Check if polling server is running
        server_running = self.check_polling_server()
        
        if not server_running:
            print("⚠️ Hardware monitoring disabled (no polling server)")
            print("⚠️ Please start the server with: ./run_all.sh")
            return
        
        self.running = True
        
        # Start handshake detection in background (non-blocking)
        if not self.handshake_complete:
            self.wait_for_handshake()
        
        # Start temperature monitoring thread
        self.temp_thread = threading.Thread(target=self._temperature_loop, daemon=True)
        self.temp_thread.start()
        
        print("✓ Hardware monitoring started (waiting for handshake in background)")
    
    def stop(self):
        """Stop the monitoring service"""
        self.running = False
        
        # Kill polling_server2.py process
        try:
            print("🛑 Stopping polling_server2.py process...")
            result = subprocess.run(
                ["pkill", "-f", "polling_server2.py"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print("✓ polling_server2.py stopped")
            else:
                print("✓ polling_server2.py already stopped or not found")
        except Exception as e:
            print(f"⚠️ Could not stop polling_server2.py: {e}")
        
        print("✓ Hardware monitoring stopped")
    
    def _temperature_loop(self):
        """Background loop with adaptive polling interval"""
        while self.running:
            try:
                # Fetch temperature
                temp = self._fetch_temperature()
                
                if temp:
                    self.last_temperature = temp
                    # Temperature sending to DB removed - not needed
                
                # Adaptive sleep based on current mode
                time.sleep(self.polling_interval)
                
            except Exception as e:
                print(f"Temperature monitoring error: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _fetch_temperature(self):
        """Fetch temperature via health check command with adaptive polling"""
        try:
            if not self.api_base_url or not self.device_id:
                return None
            
            # Send health check command
            url = f"{self.api_base_url}/api/device/command"
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": f"cmd_temp_check_{int(time.time())}",
                "deviceId": self.device_id,
                "command": {"action": "health_check"}
            }
            
            response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                result = response.json()
                checks = result.get('checks', {})
                
                # Update adaptive polling logic
                self._update_polling_interval(success=True)
                
                # Look for PT100 sensor
                pt100_list = checks.get('sensor:pt100_sensor_01', [])
                if pt100_list:
                    temp = pt100_list[0].get('observedValue')
                    return temp
            else:
                self._update_polling_interval(success=False)
            
        except:
            self._update_polling_interval(success=False)
        
        return None
    
    def _update_polling_interval(self, success):
        """Update polling interval based on success/failure and mode"""
        if self.is_heating_mode:
            # Always poll every 1 second during heating
            self.polling_interval = 1
            return
        
        if success:
            self.consecutive_success_count += 1
            
            # After 3 consecutive successes, switch to 20-second interval
            if self.consecutive_success_count >= 3:
                if self.polling_interval != 20:
                    print("✅ Handshake confirmed (3 consecutive 200s) - switching to 20-second polling")
                    self.polling_interval = 20
                    self.handshake_complete = True
        else:
            # Reset on failure
            if self.consecutive_success_count > 0:
                print("⚠️ Health check failed - resetting to 1-second polling")
            self.consecutive_success_count = 0
            self.polling_interval = 1
    
    def enable_heating_mode(self):
        """Enable fast polling for temperature heating page"""
        print("🔥 Heating mode enabled - polling every 1 second")
        self.is_heating_mode = True
        self.polling_interval = 1
    
    def disable_heating_mode(self):
        """Disable heating mode and return to adaptive polling"""
        print("✅ Heating mode disabled - returning to adaptive polling")
        self.is_heating_mode = False
        # Will automatically adjust based on consecutive_success_count
        if self.consecutive_success_count >= 3:
            self.polling_interval = 20
        else:
            self.polling_interval = 1
    
    def get_cup_status(self):
        """Get current cup sensor status via health check command"""
        try:
            if not self.api_base_url or not self.device_id:
                return None
            
            # Send health check command
            url = f"{self.api_base_url}/api/device/command"
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": f"cmd_cup_check_{int(time.time())}",
                "deviceId": self.device_id,
                "command": {"action": "health_check"}
            }
            
            response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                result = response.json()
                checks = result.get('checks', {})
                
                # Look for cup sensor
                for key in ['sensor:cup_sensor_01', 'cup_sensor_01']:
                    if key in checks:
                        cup_data = checks[key]
                        if isinstance(cup_data, list) and len(cup_data) > 0:
                            cup_data = cup_data[0]
                        
                        cup_value = cup_data.get('observedValue', 'no_cup')
                        
                        # Determine if cup is present
                        is_present = cup_value in ['cup_present', 'cup', 'present', 'yes', 'true', '1']
                        self.last_cup_status = is_present
                        return is_present
                
                # Default: no cup (if no data found)
                return False
            
        except Exception as e:
            print(f"Cup status check error: {e}")
        
        return None
    
    def get_temperature(self):
        """Get last known temperature"""
        return self.last_temperature
    
    def get_pt100_temperature(self):
        """Get PT100 sensor temperature for heating check via health check command
        Returns: temperature in Celsius or None if unavailable
        """
        try:
            if not self.api_base_url or not self.device_id:
                return None
            
            # Send health check command
            url = f"{self.api_base_url}/api/device/command"
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": f"cmd_pt100_check_{int(time.time())}",
                "deviceId": self.device_id,
                "command": {"action": "health_check"}
            }
            
            response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                result = response.json()
                checks = result.get('checks', {})
                
                # Look for PT100 sensor (tea heating temperature)
                pt100_list = checks.get('sensor:pt100_sensor_01', [])
                if pt100_list and len(pt100_list) > 0:
                    temp = pt100_list[0].get('observedValue')
                    if temp is not None:
                        return float(temp)
            
        except Exception as e:
            print(f"PT100 temperature check error: {e}")
        
        return None
    
    def is_device_connected(self):
        """Check if device is connected (cached, adaptive timing)
        - Disconnected: Check every 1 second (fast reconnection)
        - Connected: Check every 20 seconds (reduce load)
        Returns cached result immediately, triggers background refresh if stale
        """
        import time
        
        current_time = time.time()
        
        with self._connection_check_lock:
            # Determine cache TTL based on current status
            if self._connection_status:
                cache_ttl = self._connection_cache_ttl_connected  # 20s when connected
            else:
                cache_ttl = self._connection_cache_ttl_disconnected  # 1s when disconnected
            
            # Check if cache is valid
            if self._connection_status is not None:
                cache_age = current_time - self._connection_check_time
                if cache_age < cache_ttl:
                    # Cache is fresh - return immediately (NO BLOCKING!)
                    return self._connection_status
            
            # Cache is stale or missing - trigger background check
            if not self._background_check_running:
                self._background_check_running = True
                threading.Thread(target=self._background_connection_check, daemon=True).start()
            
            # Return cached value or default
            if self._connection_status is None:
                # First time - assume disconnected until proven otherwise
                return False
            return self._connection_status
    
    def _background_connection_check(self):
        """Background thread - checks connection and updates cache (non-blocking)"""
        import time
        
        try:
            devices_check = [False]
            health_check = [False]
            completed_event = threading.Event()
            
            def check_devices():
                try:
                    url = f"{self.api_base_url}/api/devices"
                    response = requests.get(url, timeout=2)
                    
                    if response.status_code == 200:
                        devices = response.json().get('devices', [])
                        
                        if len(devices) > 0:
                            # Device is connected - don't change the hardcoded device_id
                            devices_check[0] = True
                            completed_event.set()
                except:
                    pass
            
            def check_health():
                try:
                    url = f"{self.api_base_url}/api/device/command"
                    payload = {
                        "messageType": "command",
                        "commandType": "control",
                        "version": "1.0",
                        "commandId": "cmd_health_check",
                        "deviceId": self.device_id,
                        "command": {"action": "health_check"}
                    }
                    response = requests.post(url, json=payload, timeout=5)
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Check both top-level statusCode and response.statusCode
                        status_code = result.get('statusCode') or result.get('response', {}).get('statusCode')
                        
                        if status_code == 200:
                            health_check[0] = True
                            completed_event.set()
                            print(f"✅ Health check passed (statusCode: {status_code})")
                except Exception as e:
                    print(f"Health check failed: {e}")
                    pass
            
            # Run both in parallel
            t1 = threading.Thread(target=check_devices, daemon=True)
            t2 = threading.Thread(target=check_health, daemon=True)
            t1.start()
            t2.start()
            
            # Wait max 6 seconds
            completed_event.wait(timeout=6)
            t1.join(timeout=0.1)
            t2.join(timeout=0.1)
            
            # Update cache (this runs in background, doesn't block UI)
            is_connected = devices_check[0] or health_check[0]
            
            with self._connection_check_lock:
                self._connection_status = is_connected
                self._connection_check_time = time.time()
                self._background_check_running = False
                
                if is_connected and not self.handshake_complete:
                    self.handshake_complete = True
                    print(f"✅ Connected (dev={devices_check[0]}, health={health_check[0]})")
        
        except Exception as e:
            with self._connection_check_lock:
                self._background_check_running = False

    def get_latest_error(self):
        """Check for CRITICAL hardware errors from the latest health check
        Only returns errors that should block the app (connection issues, critical faults)
        Does NOT return operational status like low temp or no cup (handled by specific pages)
        """
        print("\n--- DEBUG: get_latest_error() called ---")
        try:
            if not self.api_base_url or not self.device_id:
                print("DEBUG: Configuration missing (api_base_url or device_id)")
                return "Internal Error: Configuration Missing"
                
            # Check connection first
            print(f"DEBUG: Checking if device connected (Base URL: {self.api_base_url})")
            if not self.is_device_connected():
                print("DEBUG: Device NOT connected - returning error")
                return "Hardware Not Connected"
            
            print("DEBUG: Device IS connected - checking for CRITICAL errors only")
            
            # Send health check command directly to get fresh status
            url = f"{self.api_base_url}/api/device/command"
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": f"cmd_health_check_{int(time.time())}",
                "deviceId": self.device_id,
                "command": {"action": "health_check"}
            }
            
            print(f"DEBUG: Sending health check command to {url}")
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                
                # Get status from direct response
                status_code = result.get('statusCode')
                status = result.get('status', 'unknown')
                machine_state = result.get('machineState', 'UNKNOWN')
                checks = result.get('checks', {})
                
                print(f"DEBUG: Health check response - status={status}, statusCode={status_code}, machineState={machine_state}")
                print(f"DEBUG: Found {len(checks)} component checks")
                
                # Check if health check succeeded (status 200 means ESP32 responded)
                if status_code == 200:
                    print("DEBUG: Health check succeeded (statusCode 200), checking components...")
                    
                    # Check PT100 temperature FIRST - if < 83°C, return heating status
                    pt100_checks = checks.get('sensor:pt100_sensor_01', [])
                    if pt100_checks:
                        pt100_data = pt100_checks[0]
                        temp = pt100_data.get('observedValue')
                        
                        if temp is not None and temp < 83:
                            print(f"DEBUG: 🔥 Temperature low ({temp}°C) - Needs heating")
                            return ('HEATING', temp)  # Return tuple to indicate heating needed
                    
                    # Only check for CRITICAL errors that should block the app
                    # Exclude operational status like low temp (700), no cup (704)
                    CRITICAL_ERROR_CODES = [701, 705, 706, 707, 711, 600]
                    
                    # Iterate through all checks to find CRITICAL failures only
                    for comp_key, check_list in checks.items():
                        for check in check_list:
                            check_status = check.get('status', 'pass').lower()
                            code = check.get('statusCode')
                            
                            # Only return error if it's a critical code
                            if check_status != 'pass' and code in CRITICAL_ERROR_CODES:
                                # Found a critical error!
                                error_msg = check.get('message') or check.get('errorMessage')
                                if not error_msg:
                                    # Construct message from code
                                    value = check.get('observedValue')
                                    
                                    if code == 701:
                                        error_msg = f"Temperature Critical ({value}°C)"
                                    elif code == 705:
                                        error_msg = "Flow Failure Detected"
                                    elif code == 706:
                                        error_msg = "Pump Fault Detected"
                                    elif code == 707:
                                        error_msg = "Heater Fault Detected"
                                    elif code == 711:
                                        error_msg = "Pump Timeout: Exceeded Duration"
                                    elif code == 600:
                                        error_msg = "WiFi Disconnected (Reported)"
                                    else:
                                        comp_id = check.get('componentId', 'Unknown Component')
                                        error_msg = f"Critical Hardware Error: {comp_id}"
                                
                                print(f"DEBUG: Found CRITICAL error - Code {code}: {error_msg}")
                                return error_msg
                    
                    print("DEBUG: ✅ No critical errors found in component checks")
                    
                    # Check machine state
                    if machine_state == 'OFFLINE':
                        reason = result.get('reason', 'Unknown reason')
                        details = result.get('details', {})
                        err_msg = details.get('errorMessage') or reason
                        print(f"DEBUG: Machine is OFFLINE - {err_msg}")
                        return f"Machine Offline: {err_msg}"
                    
                    # All checks passed!
                    print("DEBUG: ✅ All checks passed - No blocking errors")
                    return None
                    
                else:
                    # Health check failed with non-200 status
                    print(f"DEBUG: Health check failed - statusCode={status_code}")
                    return f"Health Check Failed (Code: {status_code})"
                        
        except requests.exceptions.ReadTimeout:
            print(f"⚠️ Health check timeout (device busy dispensing) - assuming OK")
            return None
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection error - device may be disconnected")
            return "Hardware Not Connected"
        except Exception as e:
            print(f"❌ Error checking for hardware errors: {e}")
        
        print("DEBUG: ✅ Returning None - No blocking errors found")
        return None


# Global instance
hardware_monitor = HardwareMonitor()

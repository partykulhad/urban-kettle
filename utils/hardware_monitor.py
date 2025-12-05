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
    
    def __init__(self, machine_id="KH-01", api_base_url="http://127.0.0.1:5000"):
        # Default to RPI MAC address based ID
        self.device_id = self.get_rpi_device_id()
        print(f"Initialized HardwareMonitor with Device ID: {self.device_id}")
        
        self.machine_id = machine_id
        self.api_base_url = api_base_url  # Static URL - never changes
        self.db_api_url = "https://kulhad.vercel.app/api/machine-temperature"
        
        self.running = False
        self.temp_thread = None
        self.server_process = None
        
        self.last_temperature = None
        self.last_cup_status = None
        self.handshake_complete = False
    
    def get_rpi_device_id(self):
        """Get Device ID based on RPI MAC address"""
        try:
            # Try to get MAC from sysfs (most reliable on RPI)
            if os.path.exists('/sys/class/net/wlan0/address'):
                with open('/sys/class/net/wlan0/address', 'r') as f:
                    mac = f.read().strip().upper().replace(':', '')
                    return f"UK_{mac}"
            
            if os.path.exists('/sys/class/net/eth0/address'):
                with open('/sys/class/net/eth0/address', 'r') as f:
                    mac = f.read().strip().upper().replace(':', '')
                    return f"UK_{mac}"
            
            # Fallback to uuid
            import uuid
            mac_num = uuid.getnode()
            mac = ':'.join(['{:02x}'.format((mac_num >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
            mac = mac.upper().replace(':', '')
            return f"UK_{mac}"
            
        except Exception as e:
            print(f"Error getting MAC address: {e}")
            return "UK_14335C5D48C8" # Fallback to hardcoded

    def start_polling_server(self):
        """Start polling_server2.py to receive ESP32 data"""
        try:
            print(f"🚀 Starting polling_server2.py...")
            
            # Check if polling_server2.py exists
            if not os.path.exists("polling_server2.py"):
                print("⚠️ polling_server2.py not found in current directory")
                return False
            
            # Start server in background
            self.server_process = subprocess.Popen(
                [sys.executable, "polling_server2.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            print(f"✓ polling_server2.py process started (PID: {self.server_process.pid})")
            print(f"⏳ Waiting for server to respond at {self.api_base_url}...")
            
            # Wait for server to start and test connection
            for i in range(10):
                time.sleep(0.5)
                try:
                    # Check server status
                    response = requests.get(f"{self.api_base_url}/api/status", timeout=1)
                    if response.status_code == 200:
                        print(f"✓ polling_server2.py is running and responding at {self.api_base_url}")
                        print(f"✓ Waiting for ESP32 handshake...")
                        return True
                except Exception as e:
                    if i == 9:
                        print(f"⚠️ Connection attempt {i+1}/10 failed: {e}")
                    continue
            
            print(f"⚠️ polling_server2.py started but not responding after 5 seconds")
            print(f"⚠️ Check if port 5000 is available or if there are network issues")
            return False
            
        except Exception as e:
            print(f"⚠️ Could not start hardware server: {e}")
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
        
        # Start polling server
        server_started = self.start_polling_server()
        
        if not server_started:
            print("⚠️ Hardware monitoring disabled (no polling server)")
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
        print("✓ Hardware monitoring stopped")
    
    def _temperature_loop(self):
        """Background loop to fetch and send temperature every second"""
        while self.running:
            try:
                # Fetch temperature
                temp = self._fetch_temperature()
                
                if temp:
                    self.last_temperature = temp
                    # Send to database
                    self._send_temperature_to_db(temp)
                
                time.sleep(1)  # Every second
                
            except Exception as e:
                print(f"Temperature monitoring error: {e}")
                time.sleep(5)  # Wait longer on error
    
    def _fetch_temperature(self):
        """Fetch temperature from hardware history"""
        try:
            if not self.api_base_url or not self.device_id:
                return None
            
            # Get history instead of posting empty health check
            url = f"{self.api_base_url}/api/device/{self.device_id}/history"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                health_list = data.get('health', [])
                
                if health_list:
                    # Get latest health data
                    latest = health_list[-1].get('data', {})
                    checks = latest.get('checks', {})
                    
                    # Look for PT100 sensor
                    pt100_list = checks.get('sensor:pt100_sensor_01', [])
                    if pt100_list:
                        temp = pt100_list[0].get('observedValue')
                        return temp
            
        except:
            pass
        
        return None
    
    def _send_temperature_to_db(self, temperature):
        """Send temperature to database"""
        try:
            payload = {
                "machineId": self.machine_id,
                "temperature": int(temperature)
            }
            requests.post(self.db_api_url, json=payload, timeout=5)
        except:
            pass
    
    def get_cup_status(self):
        """Get current cup sensor status"""
        try:
            if not self.api_base_url or not self.device_id:
                return None
            
            # Get history
            url = f"{self.api_base_url}/api/device/{self.device_id}/history"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                health_list = data.get('health', [])
                
                if health_list:
                    latest = health_list[-1].get('data', {})
                    checks = latest.get('checks', {})
                
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
    
    def is_device_connected(self):
        """Check if device is connected via handshake or recent activity"""
        # Always check server for active devices
        try:
            url = f"{self.api_base_url}/api/devices"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                devices = response.json().get('devices', [])
                if len(devices) > 0:
                    # If we have a device, ensure our ID matches the active one
                    # This handles if the device ID changed (e.g. different ESP32 connected)
                    active_device = devices[0]
                    active_id = active_device.get('deviceId')
                    
                    if active_id and active_id != self.device_id:
                        print(f"🔄 Device ID changed from {self.device_id} to {active_id}")
                        self.device_id = active_id
                    
                    # Mark handshake as complete if we found a device
                    if not self.handshake_complete:
                        self.handshake_complete = True
                        
                    return True
                else:
                    # No devices listed
                    return False
        except:
            pass
            
        return False

    def get_latest_error(self):
        """Check for hardware errors from the latest health check"""
        try:
            if not self.api_base_url or not self.device_id:
                return "Internal Error: Configuration Missing"
                
            # Check connection first
            if not self.is_device_connected():
                return "Hardware Not Connected"
            
            # Get history
            url = f"{self.api_base_url}/api/device/{self.device_id}/history"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                health_list = data.get('health', [])
                
                if health_list:
                    latest = health_list[-1].get('data', {})
                    checks = latest.get('checks', {})
                    
                    # Iterate through all checks to find failures
                    for comp_key, check_list in checks.items():
                        for check in check_list:
                            status = check.get('status', 'pass').lower()
                            if status != 'pass':
                                # Found an error!
                                error_msg = check.get('message') or check.get('errorMessage')
                                if not error_msg:
                                    # Try to construct message from value/unit or codes
                                    comp_id = check.get('componentId', 'Unknown Component')
                                    code = check.get('statusCode')
                                    value = check.get('observedValue')
                                    
                                    if code == 700:
                                        error_msg = f"Temperature Low ({value}°C)"
                                    elif code == 701:
                                        error_msg = f"Temperature Critical ({value}°C)"
                                    elif code == 704:
                                        error_msg = "Cup not detected"
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
                                        error_msg = f"Hardware Error: {comp_id} status is {status}"
                                
                                return error_msg
                    
                    # Check for top-level error message types (Section 9.1)
                    if latest.get('messageType') == 'error':
                        error_obj = latest.get('error', {})
                        code = latest.get('statusCode') or error_obj.get('code')
                        msg = error_obj.get('message', 'Unknown Error')
                        
                        if code == 600 or code == 'WIFI_DISCONNECTED':
                            return f"WiFi Error: {msg}"
                        else:
                            return f"Device Error ({code}): {msg}"
                                
                    # Also check for explicit offline state with reason
                    machine_state = latest.get('machineState', 'ONLINE')
                    if machine_state == 'OFFLINE':
                        reason = latest.get('reason', 'Unknown reason')
                        details = latest.get('details', {})
                        err_msg = details.get('errorMessage') or reason
                        return f"Machine Offline: {err_msg}"
                        
        except Exception as e:
            print(f"Error checking for hardware errors: {e}")
            
        return None


# Global instance
hardware_monitor = HardwareMonitor()

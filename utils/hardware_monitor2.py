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
    
    def __init__(self, machine_id="KH-01", api_base_url="http://192.168.100.236:5000"):
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
        """Start polling server via Docker (automatic background startup)"""
        try:
            print(f"🐳 Starting polling server via Docker...")
            
            # Check if Docker container is already running
            try:
                response = requests.get(f"{self.api_base_url}/api/status", timeout=1)
                if response.status_code == 200:
                    print(f"✅ Polling server ALREADY RUNNING at {self.api_base_url}")
                    print(f"✅ Docker container is active - skipping startup")
                    return True
            except:
                # Server not responding, need to start it
                pass
            
            # Clean up any old/corrupted containers first
            print(f"🧹 Cleaning up old containers...")
            cleanup = subprocess.run(
                ["docker-compose", "down"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=10
            )
            if cleanup.returncode == 0:
                print(f"✓ Old containers cleaned up")
            
            # Start Docker container in background
            print(f"🚀 Launching docker-compose up -d...")
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Docker compose failed!")
                print(f"Error: {result.stderr}")
                print(f"\n💡 Try manually: docker-compose down && docker-compose up -d")
                return False
            
            # Show docker startup output
            if result.stdout:
                print(f"📋 Docker output: {result.stdout.strip()}")
            
            print(f"✅ Docker container STARTED successfully")
            print(f"⏳ Waiting for server to respond at {self.api_base_url}...")
            
            # Wait for server to be ready (up to 10 seconds)
            for i in range(20):
                time.sleep(0.5)
                try:
                    response = requests.get(f"{self.api_base_url}/api/status", timeout=1)
                    if response.status_code == 200:
                        print(f"✅ ✅ ✅ POLLING SERVER IS READY ✅ ✅ ✅")
                        print(f"📍 Server URL: {self.api_base_url}")
                        print(f"📡 Waiting for ESP32 handshake...")
                        return True
                except:
                    continue
            
            print(f"⚠️ Polling server not responding after 10 seconds")
            print(f"⚠️ Check Docker logs: docker-compose logs")
            return False
            
        except Exception as e:
            print(f"⚠️ Could not start polling server: {e}")
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
        
        # Stop Docker container
        try:
            print("🐳 Stopping Docker container...")
            result = subprocess.run(
                ["docker-compose", "down"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print("✓ Docker container stopped")
            else:
                print(f"⚠️ Docker stop warning: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Could not stop Docker: {e}")
        
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
        # Check TWO APIs for handshake confirmation:
        # 1. /api/devices - checks device list
        # 2. /api/device/command (health_check) - checks ESP32 responds with status 200
        
        devices_check = False
        health_check = False
        
        # Method 1: Check /api/devices
        try:
            url = f"{self.api_base_url}/api/devices"
            print(f"DEBUG: Checking device list via {url}")
            response = requests.get(url, timeout=2)
            print(f"DEBUG: /api/devices response status: {response.status_code}")
            if response.status_code == 200:
                devices = response.json().get('devices', [])
                print(f"DEBUG: Found {len(devices)} devices in list")
                if len(devices) > 0:
                    # Device found in list
                    active_device = devices[0]
                    active_id = active_device.get('deviceId')
                    
                    if active_id and active_id != self.device_id:
                        print(f"🔄 Device ID changed from {self.device_id} to {active_id}")
                        self.device_id = active_id
                    
                    devices_check = True
                    print(f"DEBUG: ✅ Devices API check PASSED (device in list)")
                else:
                    print(f"DEBUG: ❌ Devices API check FAILED (empty list)")
        except Exception as e:
            print(f"DEBUG: /api/devices check error: {e}")
        
        # Method 2: Check health_check API
        try:
            url = f"{self.api_base_url}/api/device/command"
            print(f"DEBUG: Checking health via {url}")
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": "cmd_health_handshake_check",
                "deviceId": self.device_id,
                "command": {
                    "action": "health_check"
                }
            }
            response = requests.post(url, json=payload, timeout=5)
            print(f"DEBUG: /api/device/command response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                status_code = data.get('statusCode', 0)
                print(f"DEBUG: Health check statusCode in response: {status_code}")
                
                if status_code == 200:
                    health_check = True
                    print(f"DEBUG: ✅ Health Check API PASSED (statusCode 200)")
                else:
                    print(f"DEBUG: ❌ Health Check API FAILED (statusCode {status_code})")
            else:
                print(f"DEBUG: ❌ Health Check API HTTP failed (status {response.status_code})")
        except Exception as e:
            print(f"DEBUG: Health check error: {e}")
        
        # If EITHER check passed, device is connected
        if devices_check or health_check:
            if not self.handshake_complete:
                self.handshake_complete = True
                print(f"DEBUG: ✅ HANDSHAKE CONFIRMED (devices={devices_check}, health={health_check})")
            return True
        else:
            print(f"DEBUG: ❌ NO HANDSHAKE (both API checks failed)")
            return False

    def get_latest_error(self):
        """Check for hardware errors from the latest health check"""
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
            
            print("DEBUG: Device IS connected - checking health data")
            
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

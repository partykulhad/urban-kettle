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
    
    def __init__(self, machine_id="KH-01", api_base_url="http://192.168.68.162:5000"):
        self.device_id = "UK_14335C5D48C8"  # Hardcoded device ID
        self.machine_id = machine_id
        self.api_base_url = api_base_url  # Static URL - never changes
        self.db_api_url = "https://kulhad.vercel.app/api/machine-temperature"
        
        self.running = False
        self.temp_thread = None
        self.server_process = None
        
        self.last_temperature = None
        self.last_cup_status = None
        self.handshake_complete = False
    
    def start_mock_server(self):
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
                    response = requests.get(f"{self.api_base_url}/test/devices", timeout=1)
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
        """Send handshake request continuously until accepted - runs in background"""
        print(f"⏳ Sending handshake requests for device {self.device_id}...")
        
        def handshake_loop():
            while not self.handshake_complete and self.running:
                try:
                    # Send handshake request
                    url = f"{self.api_base_url}/api/device/handshake"
                    payload = {
                        "messageType": "handshake",
                        "version": "1.0",
                        "request": {
                            "deviceId": self.device_id,
                            "deviceType": "hardware_controller",
                            "firmwareVersion": "2.1.5"
                        }
                    }
                    
                    response = requests.post(url, json=payload, timeout=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        status = data.get('response', {}).get('status')
                        
                        if status == 'accepted':
                            self.handshake_complete = True
                            session_id = data.get('response', {}).get('sessionId', 'N/A')
                            print(f"✓ Handshake accepted! Device ID: {self.device_id}")
                            print(f"✓ Session ID: {session_id}")
                            return
                        else:
                            print(f"⚠️ Handshake status: {status}")
                    else:
                        print(f"⚠️ Handshake failed with status code: {response.status_code}")
                        
                except Exception as e:
                    # Connection failed - server not ready yet
                    pass
                
                time.sleep(2)  # Try every 2 seconds
        
        # Start handshake in background thread
        handshake_thread = threading.Thread(target=handshake_loop, daemon=True)
        handshake_thread.start()
    
    def start(self):
        """Start the monitoring service"""
        if self.running:
            return
        
        # Start polling server
        server_started = self.start_mock_server()
        
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
        """Fetch temperature from hardware"""
        try:
            if not self.api_base_url or not self.device_id:
                return None
            
            url = f"{self.api_base_url}/api/device/health"
            payload = {
                "messageType": "health_check",
                "version": "1.0",
                "deviceId": self.device_id,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                pt100_data = data.get('checks', {}).get('sensor:pt100_sensor_01', [{}])[0]
                temp = pt100_data.get('observedValue')
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
            
            url = f"{self.api_base_url}/api/device/health"
            payload = {
                "messageType": "health_check",
                "version": "1.0",
                "deviceId": self.device_id,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(url, json=payload, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                checks = data.get('checks', {})
                
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
                
                # Default: no cup
                self.last_cup_status = False
                return False
            
        except Exception as e:
            print(f"Cup status check error: {e}")
        
        return None
    
    def get_temperature(self):
        """Get last known temperature"""
        return self.last_temperature


# Global instance
hardware_monitor = HardwareMonitor()

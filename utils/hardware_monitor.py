"""
Hardware Monitor Service
Runs in background to monitor temperature and cup status
"""

import threading
import time
import uuid
import requests
import subprocess
from config import MACHINE_ID, PT100_SENSOR_ID, SERVING_TEMP
from utils.api_client import get_localhost_session


class HardwareMonitor:
    """Background service for hardware monitoring"""
    
    def __init__(self, machine_id=MACHINE_ID, api_base_url=None):
        from config import DEVICE_ID, POLLING_SERVER_URL
        self.device_id = DEVICE_ID
        if api_base_url is None:
            api_base_url = POLLING_SERVER_URL
        print(f"Initialized HardwareMonitor with Device ID: {self.device_id}")
        
        self.machine_id = machine_id
        self.api_base_url = api_base_url  # Static URL - never changes
        
        self.running = False
        self.temp_thread = None
        self.server_process = None
        
        self.last_temperature = None
        # self.last_cup_status = None  # Cup sensor disabled
        self.handshake_complete = False
        
        # Cloud API for temperature reporting (every 2 minutes)
        self.cloud_api_url = "https://kulhad.vercel.app/api/machine-temperature"
        self.cloud_temp_thread = None
        self.CLOUD_TEMP_INTERVAL = 15  # seconds — live temperature reporting to Kulhad
        
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

        # Slow-path lock: ensures only one health_check command is in-flight at a time.
        # _temperature_loop and check_idle_temperature both call _fetch_temperature() from
        # background threads; without this, a stale cache causes them to both queue a
        # health_check simultaneously.
        self._slow_path_lock = threading.Lock()

    def check_polling_server(self):
        """Check if polling server is running (no Docker startup)"""
        try:
            print(f"🔍 Checking polling server at {self.api_base_url}...")
            
            # Check if server is responding
            response = get_localhost_session().get(f"{self.api_base_url}/api/status", timeout=2)
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
                    response = get_localhost_session().get(url, timeout=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        devices = data.get('devices', [])
                        
                        # If any device is connected, accept it
                        if len(devices) > 0:
                            # Device is connected — keep the DEVICE_ID from config.py
                            self.handshake_complete = True
                            print(f"✓ Device connected! Using config DEVICE_ID: {self.device_id}")
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
        
        # Start cloud temperature reporting thread (every 2 minutes)
        self.cloud_temp_thread = threading.Thread(target=self._cloud_temperature_loop, daemon=True)
        self.cloud_temp_thread.start()
        
        print("✓ Hardware monitoring started (waiting for handshake in background)")
        print(f"✓ Cloud temperature reporting enabled (every {self.CLOUD_TEMP_INTERVAL}s)")
    
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
        """Background loop — keeps last_temperature fresh from ESP32 health POSTs.

        Uses ONLY the fast path (GET /temperature cache endpoint).  Never sends a
        health_check command, so it never competes with check_idle_temperature or
        start_heating_monitor for _slow_path_lock.
        """
        while self.running:
            try:
                if self.is_heating_mode:
                    time.sleep(1)
                    continue

                # Fast path only: read last health POST cached by the polling server.
                # Returns None if no data yet or cache is stale; caller handles that.
                temp = self._fetch_cached_temperature()

                if temp is not None:
                    self.last_temperature = temp

                time.sleep(5)  # Fixed 5s — independent of handshake polling_interval

            except Exception as e:
                print(f"Temperature monitoring error: {e}")
                time.sleep(5)
    
    def _cloud_temperature_loop(self):
        """Background loop to send temperature to cloud API every CLOUD_TEMP_INTERVAL seconds.
        Runs continuously regardless of online/offline state — only hardware_monitor.stop()
        (full app shutdown) ends this loop.
        """
        print("☁️ Cloud temperature reporting thread started")

        while self.running:
            try:
                # Don't report temperature while the machine is offline — the
                # heater is off then (confirmed by the ESP32 team), so a cooling
                # reading would be noise on the dashboard rather than a live value.
                if self.is_machine_offline():
                    time.sleep(self.CLOUD_TEMP_INTERVAL)
                    continue

                # During heating mode, start_heating_monitor's own 1s poller owns
                # all _fetch_temperature() calls (avoid conflicting ESP32 commands).
                # We don't call _fetch_temperature() ourselves here, but that poller
                # keeps self.last_temperature fresh, so report it on the same
                # cadence instead of freezing Kulhad on the pre-heating value.
                if self.is_heating_mode:
                    if self.last_temperature is not None:
                        self._send_temperature_if_changed(self.last_temperature)
                    time.sleep(self.CLOUD_TEMP_INTERVAL)
                    continue

                # Use cached temperature if available to avoid an extra health_check
                temp = self.last_temperature if self.last_temperature is not None \
                       else self._fetch_temperature()

                if temp is not None:
                    self._send_temperature_if_changed(temp)
                else:
                    print("☁️ No temperature available to send to cloud")

                time.sleep(self.CLOUD_TEMP_INTERVAL)

            except Exception as e:
                print(f"☁️ Cloud temperature loop error: {e}")
                time.sleep(30)
    
    def _send_temperature_if_changed(self, temperature):
        """Send temperature to cloud only if it changes significantly or 5 minutes have passed"""
        current_time = time.time()
        
        # Initialize tracking attributes if they don't exist yet (backward compatibility)
        if not hasattr(self, '_last_reported_temp'):
            self._last_reported_temp = None
        if not hasattr(self, '_last_reported_time'):
            self._last_reported_time = 0
            
        should_send = False
        if self._last_reported_temp is None or self._last_reported_time == 0:
            should_send = True
        elif abs(float(temperature) - float(self._last_reported_temp)) >= 0.5:
            should_send = True
        elif (current_time - self._last_reported_time) >= 300: # 5 minutes keepalive
            should_send = True
            
        if should_send:
            self._send_temperature_to_cloud(temperature)
            self._last_reported_temp = temperature
            self._last_reported_time = current_time
        else:
            # Skip sending to save Convex DB writes when temperature is stable
            pass

    def _send_temperature_to_cloud(self, temperature):
        """Send temperature to cloud API
        
        Args:
            temperature: Current temperature in Celsius
        """
        try:
            from config import MACHINE_ID
            
            payload = {
                "machineId": MACHINE_ID,
                "temperature": temperature
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                self.cloud_api_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"☁️ Temperature sent to cloud: {temperature}°C (Machine: {MACHINE_ID})")
                else:
                    print(f"☁️ Cloud API returned success=false: {result}")
            else:
                print(f"☁️ Cloud API error: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("☁️ Cloud API timeout - will retry next interval")
        except requests.exceptions.ConnectionError:
            print("☁️ Cloud API connection error - will retry next interval")
        except Exception as e:
            print(f"☁️ Error sending temperature to cloud: {e}")
    
    @staticmethod
    def _extract_health_data(result):
        """Normalise an ESP32 health-check response into (status_code, machine_state, checks).

        ESP32 firmware may respond in two formats:
          A) Flat  — checks/statusCode/machineState at the top level (protocol spec §6.1)
          B) Nested — wrapped under a 'response' key (command_response §7.4 style)

        Returns (status_code: int|None, machine_state: str, checks: dict)
        so callers never have to handle the two formats themselves.
        """
        # Try flat format first
        checks = result.get('checks')
        status_code = result.get('statusCode') or result.get('response', {}).get('statusCode')
        machine_state = result.get('machineState', 'UNKNOWN')

        if not checks:
            # Try nested under 'response'
            resp = result.get('response', {})
            checks = resp.get('checks') or resp.get('data', {}).get('checks')
            if not machine_state or machine_state == 'UNKNOWN':
                machine_state = resp.get('machineState', 'UNKNOWN')

        if not checks:
            # Try nested under 'data' at top level (some firmware variants)
            checks = result.get('data', {}).get('checks')

        return status_code, machine_state, (checks or {})

    def _fetch_cached_temperature(self):
        """Fast path only: read PT100 temperature from the polling server's health-POST
        cache.  Returns None if no data exists or the cached reading is more than 40 s
        old (ESP32 posts every ~30 s; 40 s gives a 10 s jitter buffer).
        Never sends a health_check command — no lock, no round-trip.
        """
        try:
            cache_url = f"{self.api_base_url}/api/device/{self.device_id}/temperature"
            resp = get_localhost_session().get(cache_url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                pt100 = data.get('pt100_temperature')
                ts = data.get('timestamp')
                if pt100 is not None and ts:
                    from datetime import datetime as _dt
                    age = time.time() - _dt.fromisoformat(ts).timestamp()
                    if age < 40:
                        self._update_polling_interval(success=True)
                        return float(pt100)
        except Exception:
            pass
        return None

    def _fetch_temperature(self, force_fresh=False):
        """Fetch temperature. Tries cached health data first (unless force_fresh or
        self.is_heating_mode is True), falls back to a full health_check command to
        read the fresh temperature from the ESP32."""
        try:
            if not self.api_base_url or not self.device_id:
                return None

            # --- Fast path: use temperature cached from ESP32's periodic health POST ---
            # Bypass cache only on an explicit force_fresh call.
            # Heating mode still uses cache first — showing a stale-but-recent value is
            # far better than showing "--°C" for up to 35 s while the slow path runs.
            if not force_fresh:
                temp = self._fetch_cached_temperature()
                if temp is not None:
                    return temp

            # --- Slow path: send health_check command and wait for ESP32 response ---
            # Non-blocking acquire: if another thread already owns the lock it is
            # already fetching a fresh reading — return the cached value immediately
            # rather than queuing a second health_check command.
            if not self._slow_path_lock.acquire(blocking=False):
                return float(self.last_temperature) if self.last_temperature is not None else None

            try:
                url = f"{self.api_base_url}/api/device/command"
                payload = {
                    "messageType": "command",
                    "commandType": "control",
                    "version": "1.0",
                    "commandId": f"cmd_temp_check_{uuid.uuid4().hex[:12]}",
                    "deviceId": self.device_id,
                    "command": {"action": "health_check"}
                }

                # 35s: one ESP32 poll cycle. Cache-first path above means this rarely fires.
                response = get_localhost_session().post(url, json=payload, timeout=35)

                if response.status_code == 200:
                    result = response.json()
                    _, _, checks = self._extract_health_data(result)

                    self._update_polling_interval(success=True)

                    pt100_list = checks.get(f'sensor:{PT100_SENSOR_ID}', [])
                    if pt100_list:
                        temp = pt100_list[0].get('observedValue')
                        if temp is not None:
                            return float(temp)
                else:
                    self._update_polling_interval(success=False)
            finally:
                self._slow_path_lock.release()

        except Exception:
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
    
    # def get_cup_status(self):
    #     """Get current cup sensor status via health check command"""
    #     try:
    #         if not self.api_base_url or not self.device_id:
    #             return None
    #         
    #         # Send health check command
    #         url = f"{self.api_base_url}/api/device/command"
    #         payload = {
    #             "messageType": "command",
    #             "commandType": "control",
    #             "version": "1.0",
    #             "commandId": f"cmd_cup_check_{int(time.time())}",
    #             "deviceId": self.device_id,
    #             "command": {"action": "health_check"}
    #         }
    #         
    #         response = requests.post(url, json=payload, timeout=3)
    #         
    #         if response.status_code == 200:
    #             result = response.json()
    #             checks = result.get('checks', {})
    #             
    #             # Look for cup sensor
    #             for key in ['sensor:cup_sensor_01', 'cup_sensor_01']:
    #                 if key in checks:
    #                     cup_data = checks[key]
    #                     if isinstance(cup_data, list) and len(cup_data) > 0:
    #                         cup_data = cup_data[0]
    #                     
    #                     cup_value = cup_data.get('observedValue', 'no_cup')
    #                     
    #                     # Determine if cup is present
    #                     is_present = cup_value in ['cup_present', 'cup', 'present', 'yes', 'true', '1']
    #                     self.last_cup_status = is_present
    #                     return is_present
    #             
    #             # Default: no cup (if no data found)
    #             return False
    #         
    #     except Exception as e:
    #         print(f"Cup status check error: {e}")
    #     
    #     return None
    
    def get_temperature(self):
        """Get last known temperature"""
        return self.last_temperature
    
    def get_pt100_temperature(self, force_fresh=False):
        """Get PT100 sensor temperature for heating check via health check command
        Returns: temperature in Celsius or None if unavailable
        """
        # In heating mode _temperature_loop owns ALL polling (cache-first, 35s slow-path).
        # Always
        # return the cached value — even if still None — to avoid a second
        # concurrent health_check command that would flood the command queue.
        if self.is_heating_mode:
            return float(self.last_temperature) if self.last_temperature is not None else None

        # Delegate to _fetch_temperature which already tries cache-first
        return self._fetch_temperature(force_fresh=force_fresh)

    def get_water_level(self):
        """Read the water level from the ESP32's cached health POST.
        The ESP32 reports water level via sensor:ultrasonic_sensor_01.
        Returns (value, unit) tuple, or (None, None) if not available.
        value is whatever the ESP32 firmware reports (usually cups remaining).
        """
        try:
            if not self.api_base_url or not self.device_id:
                return None, None
            resp = get_localhost_session().get(
                f"{self.api_base_url}/api/device/{self.device_id}/temperature",
                timeout=2
            )
            if resp.status_code == 200:
                data = resp.json()
                level = data.get('water_level')
                unit = data.get('water_level_unit', 'cups')
                if level is not None:
                    return level, unit
        except Exception as e:
            print(f"[HW] get_water_level error: {e}")
        return None, None

    def get_water_level_low(self):
        """Read the ESP32's waterLevelLow flag from its latest health-check payload.

        The /temperature cache endpoint (polling_server2.py, not modified by this
        project) only echoes a fixed set of fields and does not pass through
        waterLevelLow. The /history endpoint, however, returns the raw health-check
        payload as posted by the ESP32 — so waterLevelLow is read from there instead.
        Returns False if unavailable (fail-safe: never blocks the UI on missing data).
        """
        try:
            if not self.api_base_url or not self.device_id:
                return False
            resp = get_localhost_session().get(
                f"{self.api_base_url}/api/device/{self.device_id}/history",
                timeout=2
            )
            if resp.status_code == 200:
                health = resp.json().get('health', [])
                if health:
                    last_data = health[-1].get('data', {})
                    low = last_data.get('waterLevelLow')
                    if low is None:
                        # Some firmware variants nest the response under 'response'/'data'.
                        resp_data = last_data.get('response', {}) or {}
                        low = resp_data.get('waterLevelLow')
                        if low is None:
                            low = resp_data.get('data', {}).get('waterLevelLow')
                    return bool(low)
        except Exception as e:
            print(f"[HW] get_water_level_low error: {e}")
        return False

    def is_machine_offline(self):
        """Check the ESP32's machineState from the cached health endpoint.
        Returns True if explicitly OFFLINE, or if no health POST has arrived in
        over 90s (same staleness rule used by the global status monitor).
        Fails open (returns False) on any read error or missing data — a
        transient read failure should never be treated as "offline".
        """
        try:
            if not self.api_base_url or not self.device_id:
                return False
            resp = get_localhost_session().get(
                f"{self.api_base_url}/api/device/{self.device_id}/temperature",
                timeout=2
            )
            if resp.status_code != 200:
                return False  # 404 (no health data yet) or error — don't assume offline
            data = resp.json()
            machine_state = str(data.get('machineState', 'UNKNOWN')).upper()
            ts = data.get('timestamp')
            if ts:
                from datetime import datetime as _dt
                age = time.time() - _dt.fromisoformat(ts).timestamp()
                if age > 90:
                    return True
            return machine_state == 'OFFLINE'
        except Exception as e:
            print(f"[HW] is_machine_offline error: {e}")
            return False

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
                    response = get_localhost_session().get(url, timeout=2)
                    
                    if response.status_code == 200:
                        devices = response.json().get('devices', [])
                        
                        if len(devices) > 0:
                            # Device is connected - don't change the hardcoded device_id
                            devices_check[0] = True
                            completed_event.set()
                except:
                    pass
            
            def check_health():
                # Use the cached temperature endpoint — no command queued, no server thread tied up.
                # If the ESP32 sent a health POST within the last 60s it's alive.
                try:
                    url = f"{self.api_base_url}/api/device/{self.device_id}/temperature"
                    response = get_localhost_session().get(url, timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        ts = data.get('timestamp')
                        if ts:
                            from datetime import datetime as _dt
                            age = time.time() - _dt.fromisoformat(ts).timestamp()
                            if age < 60:
                                health_check[0] = True
                                completed_event.set()
                                print(f"✅ Device alive — last health POST {age:.0f}s ago")
                except Exception as e:
                    print(f"Health cache check failed: {e}")
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

    def get_latest_error(self, force_fresh=False):
        """Check for CRITICAL hardware errors from the latest health check
        Only returns errors that should block the app (connection issues, critical faults)
        Does NOT return operational status like low temp or no cup (handled by specific pages)
        """
        print(f"\n--- DEBUG: get_latest_error(force_fresh={force_fresh}) called ---")
        try:
            if not self.api_base_url or not self.device_id:
                print("DEBUG: Configuration missing (api_base_url or device_id)")
                return "Internal Error: Configuration Missing"

            # Fast liveness check via cached health data (no command sent).
            # If ESP32 posted health data recently it's alive — skip is_device_connected().
            _cache_alive = False
            try:
                _cr = get_localhost_session().get(
                    f"{self.api_base_url}/api/device/{self.device_id}/temperature", timeout=2)
                if _cr.status_code == 200:
                    _ts = _cr.json().get('timestamp')
                    if _ts:
                        from datetime import datetime as _dt2
                        _age = time.time() - _dt2.fromisoformat(_ts).timestamp()
                        _cache_alive = _age < 60
            except Exception:
                pass

            if not _cache_alive:
                # Fall back to the full connection check (checks /api/devices)
                print(f"DEBUG: Checking if device connected (Base URL: {self.api_base_url})")
                if not self.is_device_connected():
                    print("DEBUG: Device NOT connected - returning error")
                    return "Hardware Not Connected"
            else:
                print("DEBUG: Device alive (recent health POST)")

            print("DEBUG: Device IS connected - checking for CRITICAL errors only")

            result = None
            checks = None
            machine_state = 'UNKNOWN'
            status_code = None

            if not force_fresh:
                # Fast path: query history from polling server to get the last health POST checks
                try:
                    history_url = f"{self.api_base_url}/api/device/{self.device_id}/history"
                    history_resp = get_localhost_session().get(history_url, timeout=2)
                    if history_resp.status_code == 200:
                        hist_json = history_resp.json()
                        health_list = hist_json.get('health', [])
                        if health_list:
                            latest_health = health_list[-1]
                            ts = latest_health.get('timestamp')
                            if ts:
                                from datetime import datetime as _dt
                                age = time.time() - _dt.fromisoformat(ts).timestamp()
                                if age < 60:
                                    result = latest_health.get('data', {})
                                    status_code, machine_state, checks = self._extract_health_data(result)
                                    print(f"DEBUG: Using cached health checks (age: {age:.1f}s)")
                except Exception as e:
                    print(f"DEBUG: Failed to get cached health: {e}")

            if result is None:
                # Send health check command directly to get fresh status
                url = f"{self.api_base_url}/api/device/command"
                payload = {
                    "messageType": "command",
                    "commandType": "control",
                    "version": "1.0",
                    "commandId": f"cmd_health_check_{uuid.uuid4().hex[:12]}",
                    "deviceId": self.device_id,
                    "command": {"action": "health_check"}
                }
                
                print(f"DEBUG: Sending health check command to {url}")
                response = get_localhost_session().post(url, json=payload, timeout=35)
                
                if response.status_code == 200:
                    result = response.json()
                    status_code, machine_state, checks = self._extract_health_data(result)
                else:
                    # Health check failed with non-200 status
                    print(f"DEBUG: Health check failed - statusCode={response.status_code}")
                    return f"Health Check Failed (Code: {response.status_code})"

            # Process the component checks (either from cached health or direct command)
            if checks is not None:
                status = result.get('status') or result.get('response', {}).get('status', 'unknown')
                print(f"DEBUG: Processing checks - status={status}, statusCode={status_code}, machineState={machine_state}")
                print(f"DEBUG: Found {len(checks)} component checks")
                
                # Check if health check succeeded (status 200 means ESP32 responded or cache has valid response)
                if status_code == 200:
                    print("DEBUG: Health check succeeded (statusCode 200), checking components...")
                    
                    # Check PT100 temperature FIRST
                    pt100_checks = checks.get(f'sensor:{PT100_SENSOR_ID}', [])
                    if pt100_checks:
                        pt100_data = pt100_checks[0]
                        temp = pt100_data.get('observedValue')

                        if temp is not None:
                            # Out-of-range = sensor disconnected / open circuit.
                            # Water physically cannot exceed ~100°C at atmospheric pressure;
                            # readings above 120°C are a known artifact of an open PT100 wire.
                            # Treat these as a persistent hardware fault so the error page stays.
                            if float(temp) > 120:
                                err = f"PT100 Sensor Error: reading {float(temp):.0f}°C (sensor disconnected?)"
                                print(f"DEBUG: ⚠️ {err}")
                                return err

                            if float(temp) < SERVING_TEMP:
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
                    
                    # Check machine state - OFFLINE is NOT a hardware error
                    # It's handled by the global status check which navigates to machine_empty page
                    if machine_state == 'OFFLINE':
                        reason = result.get('reason', 'Heater is off')
                        print(f"DEBUG: Machine is OFFLINE (reason: {reason}) - NOT a hardware error, handled by global status check")
                        # Return None - let global status check handle OFFLINE state
                        # This ensures offline goes to machine_empty, not hardware_error
                        return None
                    
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

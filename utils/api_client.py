import requests
import json
import time
import uuid
from config import MACHINE_ID

# Shared session for localhost API calls (polling server)
# This enables connection pooling for all local API requests
_localhost_session = None

def get_localhost_session():
    """Get or create a shared session for localhost API calls"""
    global _localhost_session
    if _localhost_session is None:
        _localhost_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=2
        )
        _localhost_session.mount('http://', adapter)
    return _localhost_session


class ApiClient:
    """Class to handle all API interactions"""
    
    def __init__(self):
        # API endpoints
        self.PAYMENT_API_URL = "https://kulhad.vercel.app/api/direct-payment"
        self.CANCEL_API_URL = "https://kulhad.vercel.app/api/qrcode-close"
        self.STATUS_API_URL = "https://kulhad.vercel.app/api/transaction-status"
        self.MACHINE_STATUS_CHECK_URL = "https://kulhad.vercel.app/api/MachinesStatus"
        self.REDUCE_CUPS_API_URL = "https://kulhad.vercel.app/api/reduce-cups"
        self.RFID_VALIDATE_API_URL = "https://tea-wallet-prasadthirtha.replit.app/api/rfid/validate"
        self.CANISTER_CHECK_API_URL = "https://kulhad.vercel.app/api/canister-check"
        self.WATER_LEVEL_API_URL = "https://kulhad.vercel.app/api/water-level"
        self.REFILL_RESOLVED_API_URL = "https://kulhad.vercel.app/api/refill-resolved"
        from config import POLLING_SERVER_URL
        self.HARDWARE_COMMAND_URL = f"{POLLING_SERVER_URL}/api/device/command"
        # Use persistent session for connection pooling
        self.session = requests.Session()
        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
    
    def warmup_apis(self):
        """Warm up API connections to reduce cold start latency"""
        import threading
        
        def warmup_background():
            try:
                print("🔥 Warming up API connections...")
                
                # Warm up kulhad.vercel.app (where QR APIs are hosted)
                warmup_urls = [
                    f"https://kulhad.vercel.app/api/MachinesStatus?machineId={MACHINE_ID}",
                    "https://www.ukteawallet.com",
                ]
                
                for url in warmup_urls:
                    try:
                        # HEAD request is faster than GET
                        self.session.head(url, timeout=3)
                        print(f"✓ Warmed up: {url.split('/')[2]}")
                    except Exception as e:
                        print(f"⚠ Warmup failed for {url}: {e}")

                # ── OPT 3: Warm up the payment endpoint so the serverless
                # container stays hot for the real POST request.
                try:
                    self.session.head(
                        "https://kulhad.vercel.app/api/direct-payment",
                        timeout=3
                    )
                    print("✓ Warmed up: direct-payment endpoint")
                except Exception:
                    pass  # Ignore – warmup is best-effort

                print("✅ API warmup complete!")
                
            except Exception as e:
                print(f"Warmup error: {e}")
        
        # Run warmup in background thread
        threading.Thread(target=warmup_background, daemon=True).start()
    
    def generate_payment_qr(self, machine_id, number_of_cups):
        """Generate a payment QR code"""
        import time
        start_time = time.time()
        try:
            payload = {
                "machineId": machine_id,
                "numberOfCups": number_of_cups
            }
            
            print(f"🔄 Requesting QR code for {number_of_cups} cups...")
            
            # ── OPT 4: Tightened timeout from 10s → 6s.
            # Razorpay API consistently responds in 2-3s; 6s gives headroom
            # while failing faster on genuine errors.
            response = self.session.post(self.PAYMENT_API_URL, json=payload, timeout=6)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                has_image_content = 'imageContent' in result and result['imageContent']
                print(f"✅ QR API responded in {elapsed:.2f}s (hasImageContent: {has_image_content})")
                if not has_image_content:
                    print(f"⚠️ QR API response missing imageContent: {list(result.keys())}")
                return result
            else:
                print(f"❌ QR API failed: {response.status_code} in {elapsed:.2f}s")
                print(f"Response: {response.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            print(f"⏱️ Timeout generating payment QR ({elapsed:.2f}s exceeded)")
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Error generating payment QR in {elapsed:.2f}s: {e}")
            return None
    
    def check_payment_status(self, qr_code_id):
        """Check the status of a payment"""
        try:
            payload = {"transactionId": qr_code_id}
            headers = {"Content-Type": "application/json"}
            
            print(f"Sending status check payload: {payload}")
            
            response = self.session.post(
                self.STATUS_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Status check failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error checking payment status: {e}")
            return None
    
    def cancel_payment(self, qr_code_id):
        """Cancel a payment"""
        try:
            payload = {"qrCodeId": qr_code_id}
            headers = {"Content-Type": "application/json"}
            
            print(f"Cancelling QR code with ID: {qr_code_id}")
            
            response = self.session.post(
                self.CANCEL_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Successfully cancelled QR code: {qr_code_id}")
                print(f"Response: {result}")
                return result
            else:
                print(f"Failed to cancel QR code: {response.status_code}")
                print(f"Error: {response.text}")
                return None
        except Exception as e:
            print(f"Error cancelling payment: {e}")
            return None
    
    def report_machine_status(self, machine_id, status):
        """Report machine online/offline status to the Kulhad backend.
        Args:
            machine_id: e.g. 'UKL_BLR_004'
            status: 'online' or 'offline'
        """
        try:
            # /api/updateMachineStatus doesn't exist on Kulhad — confirmed by
            # checking its routes directly, every call there 404s. Go straight
            # to /api/MachinesStatus, which actually handles this POST.
            url = f"https://kulhad.vercel.app/api/MachinesStatus"
            payload = {"machineId": machine_id, "status": status}
            response = self.session.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                print(f"✅ [Status] Reported machine {machine_id} → {status}")
                return response.json()
            print(f"⚠️ [Status] report_machine_status HTTP {response.status_code}: {response.text[:200]}")
            return None
        except Exception as e:
            print(f"⚠️ [Status] report_machine_status error: {e}")
            return None

    def check_machine_status(self, machine_id):
        """Check machine status (online/offline)"""
        try:
            # Use GET request with query parameter
            url = f"{self.MACHINE_STATUS_CHECK_URL}?machineId={machine_id}"
            
            print(f"Checking machine {machine_id} status...")
            
            # Add timeout to prevent hanging - machine status should be fast
            response = self.session.get(url, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                print(f"Machine status check result: {result}")
                return result
            else:
                print(f"Failed to check machine status: {response.status_code}")
                print(f"Error: {response.text}")
                return None
        except requests.exceptions.Timeout:
            print(f"Timeout checking machine status (5s exceeded)")
            # Return success=True to allow QR generation to proceed
            # (better to show QR than fail due to status check timeout)
            return {"success": True, "data": {"status": "online"}}
        except Exception as e:
            print(f"Error checking machine status: {e}")
            return None
    
    def get_remaining_cups(self, machine_id):
        """Get remaining cups count for the machine (READ-ONLY).

        /api/remaining-cups does not exist on the Kulhad backend (always 404).
        The only working endpoint is /api/reduce-cups with cupsToReduce=0,
        which returns the current count without modifying it.
        """
        try:
            print(f"Getting remaining cups for machine {machine_id}...")
            payload = {"machineId": machine_id, "cupsToReduce": 0}
            response = self.session.post(
                self.REDUCE_CUPS_API_URL,
                json=payload,
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                print(f"Remaining cups API full response: {result}")
                # Normalize: callers always read result.get("cups", 0).
                # The API may return the count under different key names;
                # search common variants and write it back as "cups".
                if "cups" not in result:
                    for alt_key in ("remainingCups", "cupsRemaining", "remaining_cups",
                                    "cupsCount", "cups_count", "count"):
                        if alt_key in result:
                            result["cups"] = result[alt_key]
                            print(f"  ↳ normalized '{alt_key}' → 'cups' = {result['cups']}")
                            break
                    else:
                        # No known key found — log all keys so we can fix it
                        print(f"  ⚠️ 'cups' key not found in response. Available keys: {list(result.keys())}")
                return result
            print(f"Failed to get remaining cups: {response.status_code} — {response.text[:300]}")
            return None
        except Exception as e:
            print(f"Error getting remaining cups: {e}")
            return None

    
    def reduce_cups(self, machine_id, number_of_cups):
        """Reduce cups count when payment is successful"""
        try:
            payload = {
                "machineId": machine_id,
                "numberOfCups": number_of_cups
            }

            print(f"Reducing {number_of_cups} cups for machine {machine_id}...")

            response = self.session.post(
                self.REDUCE_CUPS_API_URL,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Cups reduction result: {result}")
                # Same normalization as get_remaining_cups — callers read result.get("cups")
                if "cups" not in result:
                    for alt_key in ("remainingCups", "cupsRemaining", "remaining_cups",
                                    "cupsCount", "cups_count", "count"):
                        if alt_key in result:
                            result["cups"] = result[alt_key]
                            break
                return result
            else:
                print(f"Failed to reduce cups: {response.status_code}")
                print(f"Error: {response.text}")
                return None
        except Exception as e:
            print(f"Error reducing cups: {e}")
            return None
    
    def validate_rfid_card_aes(self, rfid_auth_handler):
        """
        Validate RFID card using AES authentication.
        Returns the raw result dict from authenticate_and_dispense so the
        caller can inspect all fields (cardCategory, remainingBalance, etc.).
        """
        try:
            print(f"🔐 Starting AES authentication...")
            result = rfid_auth_handler.process_card()

            print(f"🔍 RFID auth raw result: {result}")

            if result.get('success') and result.get('authenticated'):
                # Server confirmed this card is valid and authenticated.
                # 'dispensed' is a server-side billing flag — don't gate on it;
                # the machine controls the physical dispense.
                print(f"✅ Authentication successful!")
                print(f"   Card: {result.get('cardId')}")
                print(f"   Balance: ₹{result.get('remainingBalance')}")
                print(f"   Location: {result.get('machineLocation')}")
                print(f"   Dispensed flag from server: {result.get('dispensed')}")
            else:
                print(f"❌ Authentication failed: {result.get('error', 'Unknown error')}")
                print(f"   success={result.get('success')}, authenticated={result.get('authenticated')}, dispensed={result.get('dispensed')}")

            return result

        except Exception as e:
            print(f"Error in AES authentication: {e}")
            return {"success": False, "error": str(e)}
    
    def check_canister_level(self, machine_id, canister_level):
        """
        Send canister level alert when cups reach the alert threshold.
        Args:
            machine_id: Machine ID (e.g., 'KH-01')
            canister_level: The cup count to report (caller passes CANISTER_ALERT_THRESHOLD)
        """
        try:
            payload = {
                "machineId": machine_id,
                "canisterLevel": canister_level
            }
            headers = {"Content-Type": "application/json"}
            
            print(f"🔔 Sending canister level alert for machine {machine_id} (level: {canister_level})")
            
            response = self.session.post(
                self.CANISTER_CHECK_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Canister alert sent successfully")
                print(f"   Request ID: {result.get('data', {}).get('requestId')}")
                print(f"   Message: {result.get('message')}")
                return result
            else:
                print(f"❌ Failed to send canister alert: {response.status_code}")
                print(f"   Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error sending canister alert: {e}")
            return None

    def resolve_refill_alert(self, machine_id):
        """Tell Kulhad cups are back above the canister-alert threshold, so it
        closes any still-open refill request(s) for this machine — otherwise
        the dashboard's Refill Requests alert sits forever even after refilling.
        """
        try:
            payload = {"machineId": machine_id}
            headers = {"Content-Type": "application/json"}

            print(f"🔄 Resolving refill alert for machine {machine_id}")

            response = self.session.post(
                self.REFILL_RESOLVED_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Refill alert resolved (closed {result.get('resolvedCount')} request(s))")
                return result
            else:
                print(f"❌ Failed to resolve refill alert: {response.status_code}")
                print(f"   Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error resolving refill alert: {e}")
            return None

    def report_water_level(self, machine_id, water_level_low):
        """Report the ESP32's waterLevelLow flag to Kulhad.
        water_level_low=True  → tank is low, Kulhad alerts staff and flags the machine.
        water_level_low=False → tank refilled, Kulhad clears the flag (no alert).
        """
        try:
            payload = {
                "machineId": machine_id,
                "waterLevelLow": water_level_low
            }
            headers = {"Content-Type": "application/json"}

            print(f"💧 Reporting waterLevelLow={water_level_low} for machine {machine_id}")

            response = self.session.post(
                self.WATER_LEVEL_API_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Water level reported successfully: {result.get('machineName')}")
                return result
            else:
                print(f"❌ Failed to report water level: {response.status_code}")
                print(f"   Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Error reporting water level: {e}")
            return None

    def send_hardware_command(self, device_id, action, parameters=None):
        """Send a command to the hardware via the polling server"""
        try:
            # Strip internal flags before sending to ESP32
            is_flush = action in ['water_dispense', 'tea_dispense']
            clean_params = {k: v for k, v in parameters.items() if k != 'wrapped'} if parameters else {"jobId": str(uuid.uuid4())}

            if action == 'water_dispense':
                command_id = f"Wa_dispense_{uuid.uuid4().hex[:12]}"
            elif action == 'tea_dispense':
                command_id = f"Tea_dispense_{uuid.uuid4().hex[:12]}"
            else:
                command_id = f"cmd_flush_{uuid.uuid4().hex[:12]}"

            inner = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": command_id,
                "deviceId": device_id,
                "command": {
                    "action": action,
                    "parameters": clean_params
                }
            }
            # Flush commands must be wrapped in {"commands": [...]} per ESP32 spec
            payload = {"commands": [inner]} if is_flush else inner

            headers = {"Content-Type": "application/json"}
            print(f"📡 Sending hardware command: {action} (ID: {command_id})")

            session = get_localhost_session()

            # Flush commands block up to 30 s on the polling server side waiting
            # for the ESP32 to POST back a completion result.  Since a flush
            # takes ~20 s and the ESP32 poll cycle can be up to 30 s, the server
            # usually returns HTTP 504 before the ESP32 finishes.  Use a 35 s
            # client timeout — just over the server's 30 s wait — so the 504
            # reaches the client cleanly and is treated as "dispatched".
            client_timeout = 35

            try:
                response = session.post(
                    self.HARDWARE_COMMAND_URL,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=client_timeout
                )
            except requests.exceptions.Timeout:
                print(f"❌ Timeout waiting for ESP32 response to {action}")
                raise

            if response.status_code == 200:
                result = response.json()
                pump_state = result.get('response', {}).get('data', {}).get('pumpState')
                if pump_state:
                    print(f"💧 Pump state: {pump_state}")
                return result
            elif is_flush and response.status_code == 504:
                # Server timed out waiting for ESP32 completion result.
                # The command WAS queued and dispatched to ESP32; it is executing now.
                print(f"ℹ️ {action} command dispatched to ESP32 (server wait timed out — normal for long flushes)")
                return {"dispatched": True, "action": action}
            return None
        except Exception as e:
            print(f"❌ Error sending hardware command: {e}")
            return None

    def water_flush(self, device_id):
        """Trigger a water flush maintenance action"""
        return self.send_hardware_command(device_id, "water_dispense", {"jobId": str(uuid.uuid4())})

    def tea_flush(self, device_id):
        """Trigger a tea flush maintenance action"""
        return self.send_hardware_command(device_id, "tea_dispense", {"jobId": str(uuid.uuid4())})

    def get_machine_data(self, machine_id):
        """Fetch machine config (flushTimeMinutes, price, mlToDispense) from the backend"""
        try:
            url = f"https://kulhad.vercel.app/api/getMachineData?machineId={machine_id}"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ Error fetching machine data: {e}")
            return None

    def get_flush_schedule(self, machine_id):
        """Fetch flush schedule from Kulhad backend.
        Tries the dedicated /api/getFlushSchedule endpoint first.
        Falls back to /api/getMachineData if the endpoint doesn't exist yet.
        Expected response fields (all optional):
          data.flushTimeMinutes       — idle minutes after last dispense before auto-flush
          data.flushIntervalHours     — periodic flush every N hours (0 = disabled)
          data.scheduledFlushTimes    — list of HH:MM strings e.g. ["06:00", "18:00"]
          data.waterFlushDurationSecs — seconds the water pump runs (default 20)
          data.teaFlushDurationSecs   — seconds the tea pump runs (default 20)
        """
        try:
            url = f"https://kulhad.vercel.app/api/getFlushSchedule?machineId={machine_id}"
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Flush schedule fetched from /api/getFlushSchedule")
                return response.json()
            # Dedicated endpoint not available — fall back to getMachineData
            print(f"⚠️ /api/getFlushSchedule not found (HTTP {response.status_code}), falling back to getMachineData")
            return self.get_machine_data(machine_id)
        except Exception as e:
            print(f"❌ Error fetching flush schedule: {e}")
            try:
                return self.get_machine_data(machine_id)
            except Exception:
                return None



    def get_pump_status(self, device_id):
        """Poll the current status of the pump from the bridge server"""
        try:
            from config import POLLING_SERVER_URL
            url = f"{POLLING_SERVER_URL}/api/device/sensor/pump_status?deviceId={device_id}"
            
            session = get_localhost_session()
            response = session.get(url, timeout=2)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            # Silent fail for polling
            return None

    def update_pump_settings(self, device_id, duration):
        """Update pump operation duration settings"""
        try:
            command_id = f"cmd_settings_{uuid.uuid4().hex[:12]}"
            payload = {
                "messageType": "command",
                "commandType": "update_settings",
                "version": "1.0",
                "commandId": command_id,
                "deviceId": device_id,
                "command": {
                    "action": "update_pump_settings",
                    "parameters": {
                        "component": "pump_01",
                        "pumpOperationDuration": duration
                    }
                }
            }
            headers = {"Content-Type": "application/json"}
            
            print(f"📡 Sending update settings: {duration}ms (ID: {command_id})")
            
            session = get_localhost_session()
            response = session.post(
                self.HARDWARE_COMMAND_URL,
                data=json.dumps(payload),
                headers=headers,
                timeout=35
            )

            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"❌ Error updating pump settings: {e}")
            return None


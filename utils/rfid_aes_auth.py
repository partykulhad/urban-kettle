"""
RFID AES Authentication Module
Handles secure AES authentication with RFID cards using live connection
"""

try:
    from smartcard.System import readers
    from smartcard.util import toHexString, toBytes
    from smartcard.scard import (
        SCardEstablishContext, SCardConnect, SCardDisconnect, SCardControl,
        SCardReleaseContext, SCARD_SCOPE_USER, SCARD_SHARE_DIRECT, 
        SCARD_LEAVE_CARD, SCARD_S_SUCCESS
    )
    SMARTCARD_AVAILABLE = True
except ImportError:
    SMARTCARD_AVAILABLE = False
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


from config import MACHINE_ID, RFID_MACHINE_ID, RFID_BASE_URL

class RFIDAESAuth:
    """RFID AES Authentication Handler"""
    
    def __init__(self, base_url=None, machine_id=RFID_MACHINE_ID):
        self.machine_id = machine_id
        # Default to whichever backend config.py points at.
        # Pass base_url explicitly to override (e.g. for testing).
        self.base_url = (base_url or RFID_BASE_URL).rstrip("/")
        # Kulhad mode: if the backend is NOT ukteawallet.com we skip the
        # physical DESFire APDU exchange — auth is a pure server-side balance check.
        self.kulhad_mode = "ukteawallet.com" not in self.base_url
        if self.kulhad_mode:
            print(f"✓ RFID using Kulhad backend: {self.base_url}")
        else:
            print(f"✓ RFID using ukteawallet backend: {self.base_url}")
        self.session_id = None
        self.connection = None
        self.reader = None  # Store reader object
        self.reader_active = False
        self.last_card_uid = None  # Store last read card UID
        self._reader_lock = threading.Lock()  # Serialize all smartcard operations
        
        # RF Keep-Alive state
        self._rf_connection = None  # Persistent connection for RF field
        self._rf_keepalive_active = False
        self._last_keepalive_time = 0
        self._auth_in_progress = False  # Flag to pause keep-alive during authentication
        self._ui_pause = False  # Flag to pause keep-alive during UI animations
        
        # Initialize reader at startup
        self._init_reader()
        
        # Keep-Alive HTTP Session for faster requests
        self.http_session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=20,  # Increased for better connection pooling
            pool_maxsize=20,
            max_retries=Retry(total=1, backoff_factor=0.05),  # Reduced retries for speed
            pool_block=False
        )
        self.http_session.mount("https://", adapter)
        self.http_session.mount("http://", adapter)
        
        self.http_session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=120, max=10000',
            'Content-Type': 'application/json'
        })
        
        # Pre-warm the connection
        self._prewarm_connection()
    
    def _init_reader(self):
        """Initialize card reader once at startup"""
        if not SMARTCARD_AVAILABLE:
            print("✗ RFID library (pyscard) not installed. RFID functionality disabled.")
            self.reader_active = False
            return

        try:
            # Just check if reader exists, don't connect yet
            r = readers()
            if len(r) > 0:
                self.reader = r[0]
                self.reader_active = True
                print("✓ RFID Reader found and ready")
                # Turn on green LED to indicate reader is ready
                self.set_led_green()
                # Start RF keep-alive to prevent first-read failures
                self._start_rf_keepalive()
            else:
                print("✗ No RFID reader found")
                self.reader_active = False
        except Exception as e:
            print(f"✗ Reader initialization failed: {e}")
            self.reader_active = False
    
    def _start_rf_keepalive(self):
        """Start RF field keep-alive - sends periodic FF CA 00 00 00 to keep PN532 awake"""
        if self._rf_keepalive_active:
            return
        
        import threading
        import time
        
        def keepalive_loop():
            self._rf_keepalive_active = True
            print("🔄 RF Keep-Alive started (polling every 2s with FF CA 00 00 00)")
            
            while self._rf_keepalive_active and self.reader_active:
                try:
                    # Skip keep-alive pulse if authentication or UI animation is in progress
                    if not self._auth_in_progress and not self._ui_pause:
                        # Send Get UID APDU to keep RF field active and PN532 awake
                        self._send_rf_keepalive_pulse()
                        self._last_keepalive_time = time.time()
                except Exception as e:
                    # Reconnect on failure
                    self._rf_connection = None
                
                # Sleep 2 seconds between pulses
                time.sleep(2)
            
            print("🛑 RF Keep-Alive stopped")
        
        threading.Thread(target=keepalive_loop, daemon=True).start()
    
    def _send_rf_keepalive_pulse(self):
        """Send FF CA 00 00 00 to keep RF field on and PN532 awake"""
        with self._reader_lock:
            try:
                if not self.reader:
                    return

                if self._rf_connection is None:
                    self._rf_connection = self.reader.createConnection()
                    self._rf_connection.connect()

                get_uid_apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                self._rf_connection.transmit(get_uid_apdu)

            except Exception:
                self._rf_connection = None
    
    def pause_keepalive(self):
        """Pause RF keep-alive during UI animations to prevent GIL contention"""
        self._ui_pause = True
    
    def resume_keepalive(self):
        """Resume RF keep-alive after UI animations complete"""
        self._ui_pause = False
    
    def stop_rf_keepalive(self):
        """Stop the RF keep-alive loop"""
        self._rf_keepalive_active = False
        if self._rf_connection:
            try:
                self._rf_connection.disconnect()
            except:
                pass
            self._rf_connection = None
    
    def set_led_green(self):
        """Set the ACR122U LED to green (ready state)"""
        try:
            if not self.reader:
                return False
            
            reader_name = str(self.reader)
            
            # Establish context for direct connection
            hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
            if hresult != SCARD_S_SUCCESS:
                print(f"✗ Failed to establish context for LED control")
                return False
            
            # Connect in DIRECT mode (no card needed for LED control)
            hresult, hcard, dwActiveProtocol = SCardConnect(
                hcontext, 
                reader_name, 
                SCARD_SHARE_DIRECT,
                0
            )
            
            if hresult != SCARD_S_SUCCESS:
                SCardReleaseContext(hcontext)
                print(f"✗ Failed to connect for LED control")
                return False
            
            # ACR122U LED control command
            # FF 00 40 [LED State] 04 [Duration] [Color T1] [Color T2] [Repeat]
            # LED State 0x0E = Green ON, Red OFF (00001110)
            # Bit 1: Final Green LED State = ON
            # Bit 2: Red LED State Mask = update
            # Bit 3: Green LED State Mask = update
            led_cmd = bytes([0xFF, 0x00, 0x40, 0x0E, 0x04, 0x00, 0x00, 0x00, 0x00])
            
            # IOCTL for ACR122U on Linux
            IOCTL_CCID_ESCAPE = 0x003136B0
            
            hresult, response = SCardControl(hcard, IOCTL_CCID_ESCAPE, list(led_cmd))
            
            SCardDisconnect(hcard, SCARD_LEAVE_CARD)
            SCardReleaseContext(hcontext)
            
            if hresult == SCARD_S_SUCCESS:
                print("✓ RFID Reader LED set to GREEN (ready)")
                return True
            else:
                print(f"✗ Failed to set LED: {hresult}")
                return False
                
        except Exception as e:
            print(f"✗ LED control error: {e}")
            return False
    
    def set_led_red(self):
        """Set the ACR122U LED to red (busy/error state)"""
        try:
            if not self.reader:
                return False
            
            reader_name = str(self.reader)
            
            hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
            if hresult != SCARD_S_SUCCESS:
                return False
            
            hresult, hcard, dwActiveProtocol = SCardConnect(
                hcontext, 
                reader_name, 
                SCARD_SHARE_DIRECT,
                0
            )
            
            if hresult != SCARD_S_SUCCESS:
                SCardReleaseContext(hcontext)
                return False
            
            # LED State 0x0D = Red ON, Green OFF (00001101)
            led_cmd = bytes([0xFF, 0x00, 0x40, 0x0D, 0x04, 0x00, 0x00, 0x00, 0x00])
            
            IOCTL_CCID_ESCAPE = 0x003136B0
            hresult, response = SCardControl(hcard, IOCTL_CCID_ESCAPE, list(led_cmd))
            
            SCardDisconnect(hcard, SCARD_LEAVE_CARD)
            SCardReleaseContext(hcontext)
            
            return hresult == SCARD_S_SUCCESS
                
        except Exception as e:
            print(f"✗ LED control error: {e}")
            return False

    def _prewarm_connection(self):
        """Pre-warm HTTP connection to reduce first request latency"""
        try:
            import threading
            def prewarm():
                try:
                    # Pre-warm by making OPTIONS/HEAD requests to actual API endpoints
                    # This establishes TCP connections and SSL handshakes in advance
                    warmup_urls = [
                        f"{self.base_url}",
                        f"{self.base_url}/api/rfid/auth/start",
                        f"{self.base_url}/api/rfid/auth/step2",
                        f"{self.base_url}/api/rfid/auth/verify",
                    ]
                    
                    for url in warmup_urls:
                        try:
                            # Use HEAD request with short timeout
                            self.http_session.head(url, timeout=2)
                        except:
                            pass  # Ignore errors, just warming up
                    
                    # Do a few more HEAD requests to fill connection pool
                    for _ in range(3):
                        try:
                            self.http_session.head(self.base_url, timeout=1)
                        except:
                            pass
                    
                    print("✓ RFID HTTP connections pre-warmed (4 endpoints)")
                except Exception as e:
                    print(f"⚠️ RFID prewarm partial: {e}")
            
            # Do this in background to not block initialization
            threading.Thread(target=prewarm, daemon=True).start()
        except:
            pass  # Not critical if this fails
    
    def refresh_connection(self):
        """Refresh HTTP connection pool - call this periodically to prevent cold starts"""
        try:
            # Quick HEAD request to keep connection alive
            self.http_session.head(self.base_url, timeout=2)
        except:
            pass
    
    def get_card_uid(self):
        """Read card UID from the reader - supports DESFire and MIFARE cards
        Uses FF CA 00 00 00 first (recommended for ACR122U), then falls back to DESFire method.
        Includes retry with reconnect on failure.
        """
        if not self.reader_active or not self.reader:
            return None
        
        # Try up to 2 times (initial + 1 retry)
        for attempt in range(2):
            with self._reader_lock:
                try:
                    connection = self.reader.createConnection()
                    connection.connect()

                    # Method 1: FF CA 00 00 00 (recommended for ACR122U)
                    try:
                        get_uid_apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                        response, sw1, sw2 = connection.transmit(get_uid_apdu)
                        if sw1 == 0x90 and sw2 == 0x00 and len(response) > 0:
                            uid = bytes(response).hex().upper()
                            self.last_card_uid = uid
                            self.connection = connection
                            return uid
                    except Exception:
                        pass

                    # Method 2: DESFire fallback for 7-byte UID
                    try:
                        connection.transmit([0x90, 0x5A, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
                        response, sw1, sw2 = connection.transmit([0x90, 0x60, 0x00, 0x00, 0x00])
                        if sw1 == 0x91 and sw2 == 0xAF:
                            connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                            response, sw1, sw2 = connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                            if len(response) >= 7:
                                uid = bytes(response[0:7]).hex().upper()
                                self.last_card_uid = uid
                                self.connection = connection
                                print(f"✓ DESFire Card UID: {uid}")
                                return uid
                    except Exception:
                        pass

                    return None

                except Exception:
                    pass

            if attempt == 0:
                import time
                time.sleep(0.3)

        return None
    
    def convert_apdu_hex_to_bytes(self, apdu_hex):
        """Convert hex string APDU to bytes"""
        apdu_hex = apdu_hex.replace(" ", "").upper()
        
        if apdu_hex == "90AA00000100":
            return toBytes("90 AA 00 00 01 00 00")
        
        if apdu_hex.startswith("90AF000020"):
            apdu_list = list(bytes.fromhex(apdu_hex))
            apdu_list.append(0x00)
            return apdu_list
        
        if not SMARTCARD_AVAILABLE:
            return []
        return toBytes(apdu_hex)
    
    def authenticate_and_dispense(self, card_uid=None, retry_attempt=0):
        """
        Complete AES authentication flow with retry on card communication failure
        Args:
            card_uid: Optional card UID. If not provided, will use last read UID.
            retry_attempt: Internal retry counter (0 = first attempt, 1 = retry)
        Returns: dict with success, authenticated, dispensed, balance, etc.
        """
        import time
        
        # Pause RF keep-alive during authentication to prevent card reset
        self._auth_in_progress = True
        print("⏸️ RF Keep-Alive paused for authentication")
        
        try:
            # If card_uid not provided, use last read UID
            if not card_uid:
                card_uid = self.last_card_uid
                if not card_uid:
                    self._auth_in_progress = False
                    return {"success": False, "error": "No card UID available"}
            
            print(f"🔐 Authenticating card: {card_uid}" + (f" (retry {retry_attempt})" if retry_attempt > 0 else ""))

            # Step 1: Start authentication (no card connection needed yet)
            response = self.http_session.post(
                f"{self.base_url}/api/rfid/auth/start",
                json={
                    "cardId": card_uid,
                    "keyNumber": 0,
                    "machineId": self.machine_id
                },
                timeout=3
            )

            if response.status_code != 200:
                self._auth_in_progress = False
                return {"success": False, "error": "Auth start failed"}

            data = response.json()
            if not data.get('success'):
                self._auth_in_progress = False
                return {"success": False, "error": "Auth start error"}

            card_category = data.get('cardCategory')

            if card_category == 'maintenance':
                print(f"✓ Maintenance Card Detected")
                print(f"   Action: {data.get('action')}")
                print(f"   Duration: {data.get('duration')} seconds")
                self._auth_in_progress = False
                return {
                    "success": True,
                    "authenticated": True,
                    "dispensed": False,
                    "cardCategory": "maintenance",
                    "action": data.get('action'),
                    "message": data.get('message'),
                    "duration": data.get('duration'),
                    "cardId": card_uid
                }

            # ── Kulhad mode: no physical APDU exchange needed ─────────────────
            # Kulhad auth is purely a server-side balance check (card UID +
            # machine ID is enough).  We still call /step2 and /verify to keep
            # the URL contract identical, but we send dummy cardResponse values
            # instead of real APDU data from the physical card.
            if self.kulhad_mode:
                session_id = data['sessionId']
                print(f"✓ Kulhad session: {session_id}")

                # Step 2 (dummy cardResponse — no card crypto needed)
                r2 = self.http_session.post(
                    f"{self.base_url}/api/rfid/auth/step2",
                    json={"sessionId": session_id, "cardResponse": "KULHAD_BYPASS"},
                    timeout=4
                )
                if r2.status_code != 200 or not r2.json().get('success'):
                    self._auth_in_progress = False
                    return {"success": False, "error": "Kulhad step2 failed"}

                # Verify (dummy cardResponse)
                r3 = self.http_session.post(
                    f"{self.base_url}/api/rfid/auth/verify",
                    json={"sessionId": session_id, "cardResponse": "KULHAD_BYPASS", "machineId": self.machine_id},
                    timeout=4
                )
                if r3.status_code != 200:
                    self._auth_in_progress = False
                    return {"success": False, "error": "Kulhad verify failed"}

                v = r3.json()
                self._auth_in_progress = False
                print("▶️ RF Keep-Alive resumed (Kulhad mode)")
                return {
                    "success": v.get('success', False),
                    "authenticated": v.get('authenticated', False),
                    "dispensed": v.get('dispensed', False),
                    "remainingBalance": v.get('remainingBalance', '0'),
                    "businessUnitName": v.get('businessUnitName', ''),
                    "machineLocation": v.get('machineLocation', ''),
                    "cardId": card_uid,
                    "error": v.get('error', None)
                }

            # ── ukteawallet mode: full DESFire APDU exchange ───────────────────
            # Dispensing card — needs PC/SC APDU exchange with the physical card.
            # Try to open a fresh connection now (after verifying card type).
            print("🔗 Creating PC/SC connection for APDU exchange...")
            connection = None
            with self._reader_lock:
                try:
                    if self.reader:
                        connection = self.reader.createConnection()
                        connection.connect()
                        print("✓ PC/SC connection established")
                except Exception:
                    connection = None

            if connection is None:
                self._auth_in_progress = False
                print("❌ No PC/SC connection — reader may be in HID keyboard mode")
                return {"success": False, "error": "Reader not in smartcard mode — cannot authenticate dispensing card"}

            # Dispensing card - continue with full AES authentication
            self.session_id = data['sessionId']
            apdu1 = data['apduCommand']
            print(f"✓ Dispensing Card - Session ID: {self.session_id}")

            # Step 2: Get Enc(RndB) from card
            apdu = self.convert_apdu_hex_to_bytes(apdu1)
            card_response, sw1, sw2 = connection.transmit(apdu)
            
            if sw1 != 0x91 or sw2 != 0xAF:
                # Card communication error - retry once with reconnect
                if retry_attempt == 0:
                    print("⚠️ Card error at step 2 - retrying with reconnect...")
                    try:
                        connection.disconnect()
                    except:
                        pass
                    time.sleep(0.3)  # 300ms wait as per recommended flow
                    return self.authenticate_and_dispense(card_uid, retry_attempt=1)
                self._auth_in_progress = False
                return {"success": False, "error": "Card error at step 2"}
            
            enc_rndb = toHexString(card_response).replace(" ", "")
            print(f"✓ Enc(RndB): {enc_rndb}")
            
            # Step 3: Send Enc(RndB) to server
            response = self.http_session.post(
                f"{self.base_url}/api/rfid/auth/step2",
                json={
                    "sessionId": self.session_id,
                    "cardResponse": enc_rndb
                },
                timeout=3  # Reduced from 5s to 3s
            )
            
            if response.status_code != 200:
                self._auth_in_progress = False
                return {"success": False, "error": "Step 2 failed"}
            
            data = response.json()
            if not data.get('success'):
                self._auth_in_progress = False
                return {"success": False, "error": "Step 2 error"}
            
            apdu2 = data['apduCommand']
            print(f"✓ Next APDU received")
            
            # Step 4: Send final APDU and get Enc(Rot(RndA))
            apdu = self.convert_apdu_hex_to_bytes(apdu2)
            card_response, sw1, sw2 = connection.transmit(apdu)
            
            if sw1 != 0x91 or sw2 != 0x00:
                # Card communication error - retry once with reconnect
                if retry_attempt == 0:
                    print("⚠️ Card error at verify - retrying with reconnect...")
                    try:
                        connection.disconnect()
                    except:
                        pass
                    time.sleep(0.3)  # 300ms wait as per recommended flow
                    return self.authenticate_and_dispense(card_uid, retry_attempt=1)
                self._auth_in_progress = False
                return {"success": False, "error": "Card error at verify"}
            
            enc_rot_rnda = toHexString(card_response).replace(" ", "")
            print(f"✓ Enc(Rot(RndA)): {enc_rot_rnda}")
            
            # Step 5: Verify and dispense
            response = self.http_session.post(
                f"{self.base_url}/api/rfid/auth/verify",
                json={
                    "sessionId": self.session_id,
                    "cardResponse": enc_rot_rnda,
                    "machineId": self.machine_id
                },
                timeout=3  # Reduced from 5s to 3s
            )
            
            if response.status_code != 200:
                self._auth_in_progress = False
                return {"success": False, "error": "Verify failed"}
            
            data = response.json()
            
            # Return the complete response
            self._auth_in_progress = False
            print("▶️ RF Keep-Alive resumed")
            return {
                "success": data.get('success', False),
                "authenticated": data.get('authenticated', False),
                "dispensed": data.get('dispensed', False),
                "remainingBalance": data.get('remainingBalance', '0'),
                "businessUnitName": data.get('businessUnitName', ''),
                "machineLocation": data.get('machineLocation', ''),
                "cardId": card_uid,
                "error": data.get('error', None)
            }
            
        except Exception as e:
            self._auth_in_progress = False
            print("▶️ RF Keep-Alive resumed")
            print(f"✗ Authentication error: {e}")
            return {"success": False, "error": str(e)}
    
    def process_card(self):
        """
        Complete flow: Read card UID and authenticate.
        Falls back to last_card_uid (set by HID reader) when pyscard returns None.
        """
        card_uid = self.get_card_uid()
        if not card_uid:
            # HID keyboard readers store the number in last_card_uid before calling this
            card_uid = self.last_card_uid
        if not card_uid:
            return {"success": False, "error": "Failed to read card"}
        return self.authenticate_and_dispense(card_uid)
    
    def stop(self):
        """Stop RFID handler and clean up resources"""
        print("🛑 Stopping RFID AES Auth handler...")
        
        # Stop RF keep-alive
        self.stop_rf_keepalive()
        
        # Close any open connections
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass
            self.connection = None
        
        self.reader_active = False
        print("✓ RFID handler stopped")

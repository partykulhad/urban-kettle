"""
RFID AES Authentication Module
Handles secure AES authentication with RFID cards using live connection
"""

from smartcard.System import readers
from smartcard.util import toHexString, toBytes
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RFIDAESAuth:
    """RFID AES Authentication Handler"""
    
    def __init__(self, base_url="https://www.ukteawallet.com", machine_id="UK_0007"):
        self.machine_id = machine_id
        self.base_url = base_url
        self.session_id = None
        self.connection = None
        self.reader = None  # Store reader object
        self.reader_active = False
        self.last_card_uid = None  # Store last read card UID
        
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
        try:
            # Just check if reader exists, don't connect yet
            r = readers()
            if len(r) > 0:
                self.reader = r[0]
                self.reader_active = True
                print("✓ RFID Reader found and ready")
            else:
                print("✗ No RFID reader found")
                self.reader_active = False
        except Exception as e:
            print(f"✗ Reader initialization failed: {e}")
            self.reader_active = False
    
    def _prewarm_connection(self):
        """Pre-warm HTTP connection to reduce first request latency"""
        try:
            import threading
            def prewarm():
                try:
                    # Make multiple requests to fully establish connection pool
                    for _ in range(3):
                        self.http_session.head(self.base_url, timeout=1)
                    print("✓ HTTP connection pre-warmed (3 connections)")
                except:
                    pass  # Silently fail, not critical
            
            # Do this in background to not block initialization
            threading.Thread(target=prewarm, daemon=True).start()
        except:
            pass  # Not critical if this fails
    
    def get_card_uid(self):
        """Read card UID from the reader - supports DESFire and MIFARE cards"""
        if not self.reader_active or not self.reader:
            return None
        
        try:
            # Create new connection to detect card presence
            connection = self.reader.createConnection()
            connection.connect()
            
            # Method 1: Try DESFire (your current cards)
            try:
                # Select master application
                connection.transmit([0x90, 0x5A, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
                
                # Get version to retrieve UID
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
            except:
                pass
            
            # Method 2: Try MIFARE Classic/Ultralight
            try:
                # Get UID using standard ISO14443A command
                get_uid = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                response, sw1, sw2 = connection.transmit(get_uid)
                
                if sw1 == 0x90 and sw2 == 0x00 and len(response) > 0:
                    uid = bytes(response).hex().upper()
                    self.last_card_uid = uid
                    self.connection = connection
                    print(f"✓ MIFARE Card UID: {uid}")
                    return uid
            except:
                pass
            
            return None
        except Exception as e:
            # No card present or error - this is normal during polling
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
        
        return toBytes(apdu_hex)
    
    def authenticate_and_dispense(self, card_uid=None):
        """
        Complete AES authentication flow
        Args:
            card_uid: Optional card UID. If not provided, will use last read UID.
        Returns: dict with success, authenticated, dispensed, balance, etc.
        """
        try:
            # If card_uid not provided, use last read UID
            if not card_uid:
                card_uid = self.last_card_uid
                if not card_uid:
                    return {"success": False, "error": "No card UID available"}
            
            print(f"🔐 Authenticating card: {card_uid}")
            
            # Create a FRESH connection for authentication
            print("🔗 Creating fresh connection for authentication...")
            if not self.reader:
                return {"success": False, "error": "Reader not available"}
            
            connection = self.reader.createConnection()
            connection.connect()
            print("✓ Fresh connection established")
            
            # Step 1: Start authentication
            response = self.http_session.post(
                f"{self.base_url}/api/rfid/auth/start",
                json={
                    "cardId": card_uid,
                    "keyNumber": 0,
                    "machineId": self.machine_id
                },
                timeout=3  # Reduced from 5s to 3s
            )
            
            if response.status_code != 200:
                return {"success": False, "error": "Auth start failed"}
            
            data = response.json()
            if not data.get('success'):
                return {"success": False, "error": "Auth start error"}
            
            # Check card category
            card_category = data.get('cardCategory')
            
            if card_category == 'maintenance':
                # Maintenance card - return immediately without authentication
                print(f"✓ Maintenance Card Detected")
                print(f"   Action: {data.get('action')}")
                print(f"   Duration: {data.get('duration')} seconds")
                return {
                    "success": True,
                    "authenticated": True,
                    "dispensed": False,  # No dispense for maintenance
                    "cardCategory": "maintenance",
                    "action": data.get('action'),
                    "message": data.get('message'),
                    "duration": data.get('duration'),
                    "cardId": card_uid
                }
            
            # Dispensing card - continue with full authentication
            self.session_id = data['sessionId']
            apdu1 = data['apduCommand']
            print(f"✓ Dispensing Card - Session ID: {self.session_id}")
            
            # Step 2: Get Enc(RndB) from card
            apdu = self.convert_apdu_hex_to_bytes(apdu1)
            card_response, sw1, sw2 = connection.transmit(apdu)
            
            if sw1 != 0x91 or sw2 != 0xAF:
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
                return {"success": False, "error": "Step 2 failed"}
            
            data = response.json()
            if not data.get('success'):
                return {"success": False, "error": "Step 2 error"}
            
            apdu2 = data['apduCommand']
            print(f"✓ Next APDU received")
            
            # Step 4: Send final APDU and get Enc(Rot(RndA))
            apdu = self.convert_apdu_hex_to_bytes(apdu2)
            card_response, sw1, sw2 = connection.transmit(apdu)
            
            if sw1 != 0x91 or sw2 != 0x00:
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
                return {"success": False, "error": "Verify failed"}
            
            data = response.json()
            
            # Return the complete response
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
            print(f"✗ Authentication error: {e}")
            return {"success": False, "error": str(e)}
    
    def process_card(self):
        """
        Complete flow: Read card UID and authenticate
        Returns: dict with authentication result
        """
        # Get card UID
        card_uid = self.get_card_uid()
        if not card_uid:
            return {"success": False, "error": "Failed to read card"}
        
        # Authenticate and dispense
        result = self.authenticate_and_dispense(card_uid)
        return result

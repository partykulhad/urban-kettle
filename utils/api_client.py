import requests
import json
import time

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
                    "https://kulhad.vercel.app/api/MachinesStatus?machineId=KH-01",
                    "https://www.ukteawallet.com",
                ]
                
                for url in warmup_urls:
                    try:
                        # HEAD request is faster than GET
                        self.session.head(url, timeout=3)
                        print(f"✓ Warmed up: {url.split('/')[2]}")
                    except Exception as e:
                        print(f"⚠ Warmup failed for {url}: {e}")
                
                print("✅ API warmup complete!")
                
            except Exception as e:
                print(f"Warmup error: {e}")
        
        # Run warmup in background thread
        threading.Thread(target=warmup_background, daemon=True).start()
    
    def generate_payment_qr(self, machine_id, number_of_cups):
        """Generate a payment QR code"""
        try:
            payload = {
                "machineId": machine_id,
                "numberOfCups": number_of_cups
            }
            
            response = self.session.post(self.PAYMENT_API_URL, json=payload)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error generating payment QR: {e}")
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
                headers=headers
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
                headers=headers
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
    
    def check_machine_status(self, machine_id):
        """Check machine status (online/offline)"""
        try:
            # Use GET request with query parameter
            url = f"{self.MACHINE_STATUS_CHECK_URL}?machineId={machine_id}"
            
            print(f"Checking machine {machine_id} status...")
            
            response = self.session.get(url)
            
            if response.status_code == 200:
                result = response.json()
                print(f"Machine status check result: {result}")
                return result
            else:
                print(f"Failed to check machine status: {response.status_code}")
                print(f"Error: {response.text}")
                return None
        except Exception as e:
            print(f"Error checking machine status: {e}")
            return None
    
    def get_remaining_cups(self, machine_id):
        """Get remaining cups count for the machine"""
        try:
            payload = {"machineId": machine_id}
            headers = {"Content-Type": "application/json"}
            
            print(f"Getting remaining cups for machine {machine_id}...")
            
            response = self.session.post(
                self.REDUCE_CUPS_API_URL,
                data=json.dumps(payload),
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Remaining cups result: {result}")
                return result
            else:
                print(f"Failed to get remaining cups: {response.status_code}")
                print(f"Error: {response.text}")
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
            headers = {"Content-Type": "application/json"}
            
            print(f"Reducing {number_of_cups} cups for machine {machine_id}...")
            
            response = self.session.post(
                self.REDUCE_CUPS_API_URL,
                data=json.dumps(payload),
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"Cups reduction result: {result}")
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
        Validate RFID card using AES authentication
        Uses the new secure authentication flow
        """
        try:
            print(f"🔐 Starting AES authentication...")
            
            # Process card with AES authentication
            result = rfid_auth_handler.process_card()
            
            if result.get('success') and result.get('authenticated') and result.get('dispensed'):
                print(f"✅ Authentication successful!")
                print(f"   Card: {result.get('cardId')}")
                print(f"   Balance: ₹{result.get('remainingBalance')}")
                print(f"   Location: {result.get('machineLocation')}")
                return result
            else:
                print(f"❌ Authentication failed: {result.get('error', 'Unknown error')}")
                return result
                
        except Exception as e:
            print(f"Error in AES authentication: {e}")
            return {"success": False, "error": str(e)}
    
    def check_canister_level(self, machine_id, canister_level=5):
        """
        Send canister level alert when cups reach critical level (5 cups)
        Args:
            machine_id: Machine ID (e.g., 'KH-01')
            canister_level: Always send 5 as per requirement
        """
        try:
            payload = {
                "machineId": machine_id,
                "canisterLevel": canister_level
            }
            headers = {"Content-Type": "application/json"}
            
            print(f"🔔 Sending canister level alert for machine {machine_id} (level: {canister_level})")
            
            response = requests.post(
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


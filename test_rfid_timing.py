#!/usr/bin/env python3
"""
RFID Authentication Timing Diagnostic Script
=============================================

This script diagnoses RFID authentication performance by measuring
the time taken for each step of the authentication process.

Steps measured:
1. Reader initialization
2. HTTP session creation
3. Connection warmup (to each endpoint)
4. Card detection / UID read
5. Auth/start API call
6. Step2 API call  
7. Verify API call

Usage:
    python test_rfid_timing.py

The script will prompt you to tap your card and show detailed timing
for each step. It will also compare cold start vs warm subsequent calls.
"""

import time
import socket
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.connection import create_connection

# RFID imports
try:
    from smartcard.System import readers
    from smartcard.util import toHexString, toBytes
    SMARTCARD_AVAILABLE = True
except ImportError:
    SMARTCARD_AVAILABLE = False
    print("⚠️ pyscard not installed. Install with: pip install pyscard")

# Configuration
BASE_URL = "https://www.ukteawallet.com"
MACHINE_ID = "UK_14335C5D48C8"

# SSL Verification - set to False if certificate is expired (for testing only)
# WARNING: Disabling SSL verification is insecure and should only be used for diagnostics
SSL_VERIFY = False  # Set to True for production

# Suppress SSL warnings when verification is disabled
if not SSL_VERIFY:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TimingStats:
    """Helper to track timing statistics"""
    def __init__(self, name):
        self.name = name
        self.times = []
    
    def add(self, duration):
        self.times.append(duration)
    
    def avg(self):
        return sum(self.times) / len(self.times) if self.times else 0
    
    def min(self):
        return min(self.times) if self.times else 0
    
    def max(self):
        return max(self.times) if self.times else 0
    
    def first(self):
        return self.times[0] if self.times else 0
    
    def __str__(self):
        if not self.times:
            return f"{self.name}: No data"
        return f"{self.name}: First={self.first()*1000:.0f}ms, Avg={self.avg()*1000:.0f}ms, Min={self.min()*1000:.0f}ms, Max={self.max()*1000:.0f}ms"


def time_function(func, *args, **kwargs):
    """Execute a function and return (result, duration_seconds)"""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    duration = time.perf_counter() - start
    return result, duration


def test_dns_resolution():
    """Test DNS resolution time"""
    print("\n" + "="*60)
    print("🔍 DNS RESOLUTION TEST")
    print("="*60)
    
    host = "ukteawallet.com"
    
    # Cold DNS (may be cached by OS)
    start = time.perf_counter()
    try:
        ip = socket.gethostbyname(host)
        duration = time.perf_counter() - start
        print(f"✓ DNS resolution for {host}: {ip}")
        print(f"  Time: {duration*1000:.2f}ms")
    except Exception as e:
        print(f"✗ DNS resolution failed: {e}")


def test_tcp_ssl_connection():
    """Test raw TCP + SSL connection time"""
    print("\n" + "="*60)
    print("🔌 TCP + SSL CONNECTION TEST")
    print("="*60)
    
    host = "ukteawallet.com"
    port = 443
    
    for i in range(3):
        try:
            # Time TCP connection
            tcp_start = time.perf_counter()
            sock = socket.create_connection((host, port), timeout=10)
            tcp_time = time.perf_counter() - tcp_start
            
            # Time SSL handshake
            ssl_start = time.perf_counter()
            context = ssl.create_default_context()
            if not SSL_VERIFY:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            ssl_sock = context.wrap_socket(sock, server_hostname=host)
            ssl_time = time.perf_counter() - ssl_start
            
            total_time = tcp_time + ssl_time
            
            label = "COLD" if i == 0 else f"WARM #{i}"
            print(f"  [{label}] TCP: {tcp_time*1000:.0f}ms, SSL: {ssl_time*1000:.0f}ms, Total: {total_time*1000:.0f}ms")
            
            ssl_sock.close()
        except ssl.SSLCertVerificationError as e:
            print(f"⚠️ SSL Certificate Error: {e}")
            print(f"   The server's SSL certificate may have expired.")
            print(f"   Set SSL_VERIFY=False in this script to bypass (for testing only).")
            break
        except Exception as e:
            print(f"✗ Connection #{i+1} failed: {e}")


def create_http_session():
    """Create an HTTP session similar to what the app uses"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        pool_connections=20,
        pool_maxsize=20,
        max_retries=retry_strategy
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set SSL verification
    session.verify = SSL_VERIFY
    
    return session


def test_http_warmup_methods():
    """Test different warmup strategies"""
    print("\n" + "="*60)
    print("🔥 HTTP WARMUP METHODS COMPARISON")
    print("="*60)
    
    endpoints = [
        f"{BASE_URL}",
        f"{BASE_URL}/api/rfid/auth/start",
        f"{BASE_URL}/api/rfid/auth/step2",
        f"{BASE_URL}/api/rfid/auth/verify",
    ]
    
    try:
        # Test 1: No warmup (cold)
        print("\n📊 Method 1: No Warmup (Cold Start)")
        session1 = create_http_session()
        
        start = time.perf_counter()
        resp = session1.post(f"{BASE_URL}/api/rfid/auth/start", json={"test": True}, timeout=10)
        cold_time = time.perf_counter() - start
        print(f"  Cold POST to /auth/start: {cold_time*1000:.0f}ms (Status: {resp.status_code})")
        
        # Test 2: HEAD request warmup
        print("\n📊 Method 2: HEAD Request Warmup")
        session2 = create_http_session()
        
        warmup_start = time.perf_counter()
        for url in endpoints:
            try:
                session2.head(url, timeout=2)
            except:
                pass
        warmup_time = time.perf_counter() - warmup_start
        print(f"  Warmup (4 HEAD requests): {warmup_time*1000:.0f}ms")
        
        start = time.perf_counter()
        resp = session2.post(f"{BASE_URL}/api/rfid/auth/start", json={"test": True}, timeout=10)
        warm_time = time.perf_counter() - start
        print(f"  Warm POST to /auth/start: {warm_time*1000:.0f}ms (Status: {resp.status_code})")
        print(f"  ⚡ Improvement: {(cold_time - warm_time)*1000:.0f}ms faster")
        
        # Test 3: OPTIONS request warmup
        print("\n📊 Method 3: OPTIONS Request Warmup")
        session3 = create_http_session()
        
        warmup_start = time.perf_counter()
        try:
            session3.options(BASE_URL, timeout=2)
        except:
            pass
        warmup_time = time.perf_counter() - warmup_start
        print(f"  Warmup (1 OPTIONS request): {warmup_time*1000:.0f}ms")
        
        start = time.perf_counter()
        resp = session3.post(f"{BASE_URL}/api/rfid/auth/start", json={"test": True}, timeout=10)
        options_warm_time = time.perf_counter() - start
        print(f"  POST to /auth/start after OPTIONS: {options_warm_time*1000:.0f}ms")
        
        # Test 4: GET warmup
        print("\n📊 Method 4: GET Request Warmup")
        session4 = create_http_session()
        
        warmup_start = time.perf_counter()
        try:
            session4.get(BASE_URL, timeout=2)
        except:
            pass
        warmup_time = time.perf_counter() - warmup_start
        print(f"  Warmup (1 GET request): {warmup_time*1000:.0f}ms")
        
        start = time.perf_counter()
        resp = session4.post(f"{BASE_URL}/api/rfid/auth/start", json={"test": True}, timeout=10)
        get_warm_time = time.perf_counter() - start
        print(f"  POST to /auth/start after GET: {get_warm_time*1000:.0f}ms")
        
    except requests.exceptions.SSLError as e:
        print(f"\n⚠️ SSL Error: {str(e)[:100]}...")
        print("   The server's SSL certificate may have expired.")
        print("   Set SSL_VERIFY=False at the top of this script to bypass (for testing only).")
    except Exception as e:
        print(f"\n✗ HTTP test error: {e}")


def test_reader_initialization():
    """Test RFID reader initialization time"""
    print("\n" + "="*60)
    print("📖 RFID READER INITIALIZATION TEST")
    print("="*60)
    
    if not SMARTCARD_AVAILABLE:
        print("⚠️ pyscard not available, skipping reader tests")
        return None
    
    # Cold initialization
    start = time.perf_counter()
    try:
        available_readers = readers()
        reader_list_time = time.perf_counter() - start
        print(f"✓ Reader list time: {reader_list_time*1000:.0f}ms")
        
        if not available_readers:
            print("✗ No readers found")
            return None
        
        # Find ACR122U
        acr_reader = None
        for r in available_readers:
            if "ACR122U" in str(r) or "ACR122" in str(r):
                acr_reader = r
                break
        
        if not acr_reader:
            acr_reader = available_readers[0]
        
        print(f"✓ Using reader: {acr_reader}")
        return acr_reader
        
    except Exception as e:
        print(f"✗ Reader initialization failed: {e}")
        return None


def test_card_detection(reader):
    """Test card detection and UID reading time"""
    print("\n" + "="*60)
    print("💳 CARD DETECTION TEST")
    print("="*60)
    print("Please tap and hold your card on the reader...")
    print("(Waiting for card...)")
    
    if not reader:
        print("⚠️ No reader available")
        return None
    
    # Poll for card
    max_wait = 30  # seconds
    poll_interval = 0.1
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            # Time connection creation
            conn_start = time.perf_counter()
            connection = reader.createConnection()
            connection.connect()
            conn_time = time.perf_counter() - conn_start
            print(f"\n✓ Card detected!")
            print(f"  Connection time: {conn_time*1000:.0f}ms")
            
            # Time UID reading - DESFire method
            uid_start = time.perf_counter()
            
            # Select master application
            connection.transmit([0x90, 0x5A, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
            
            # Get version to retrieve UID
            response, sw1, sw2 = connection.transmit([0x90, 0x60, 0x00, 0x00, 0x00])
            
            if sw1 == 0x91 and sw2 == 0xAF:
                connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                response, sw1, sw2 = connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                
                if len(response) >= 7:
                    uid = bytes(response[0:7]).hex().upper()
                    uid_time = time.perf_counter() - uid_start
                    print(f"✓ DESFire Card UID: {uid}")
                    print(f"  UID read time: {uid_time*1000:.0f}ms")
                    return uid, connection
            
            # Try MIFARE method
            get_uid = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            response, sw1, sw2 = connection.transmit(get_uid)
            
            if sw1 == 0x90 and sw2 == 0x00 and len(response) > 0:
                uid = bytes(response).hex().upper()
                uid_time = time.perf_counter() - uid_start
                print(f"✓ MIFARE Card UID: {uid}")
                print(f"  UID read time: {uid_time*1000:.0f}ms")
                return uid, connection
            
            uid_time = time.perf_counter() - uid_start
            print(f"✗ Could not read UID (took {uid_time*1000:.0f}ms)")
            return None, None
            
        except Exception as e:
            elapsed += poll_interval
            time.sleep(poll_interval)
    
    print(f"\n✗ Timeout waiting for card after {max_wait}s")
    return None, None


def test_card_stability(reader):
    """Test card stability - detect card moved/removed during processing"""
    print("\n" + "="*60)
    print("🔄 CARD STABILITY TEST")
    print("="*60)
    print("This test checks if the card stays connected during processing.")
    print("Place your card on the reader and keep it there...")
    
    if not reader:
        print("⚠️ No reader available")
        return
    
    # Wait for initial card
    print("\nWaiting for card...")
    connection = None
    max_wait = 30
    poll_interval = 0.1
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            connection = reader.createConnection()
            connection.connect()
            print("✓ Card detected!")
            break
        except:
            elapsed += poll_interval
            time.sleep(poll_interval)
    
    if not connection:
        print("✗ No card detected")
        return
    
    # Test card stability over 10 seconds with multiple operations
    print("\n📊 Testing card stability for 10 seconds...")
    print("   Keep the card on the reader! Watch for disconnections.\n")
    
    test_duration = 10
    check_interval = 0.5
    checks = int(test_duration / check_interval)
    
    successful_reads = 0
    failed_reads = 0
    card_removed_count = 0
    last_status = "connected"
    
    for i in range(checks):
        try:
            # Try to read UID to verify card is still there
            # Method 1: DESFire
            try:
                connection.transmit([0x90, 0x5A, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
                response, sw1, sw2 = connection.transmit([0x90, 0x60, 0x00, 0x00, 0x00])
                if sw1 == 0x91:
                    successful_reads += 1
                    if last_status == "removed":
                        print(f"  [{i*check_interval:.1f}s] ✓ Card reconnected")
                    last_status = "connected"
                    continue
            except:
                pass
            
            # Method 2: MIFARE
            try:
                response, sw1, sw2 = connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                if sw1 == 0x90:
                    successful_reads += 1
                    if last_status == "removed":
                        print(f"  [{i*check_interval:.1f}s] ✓ Card reconnected")
                    last_status = "connected"
                    continue
            except:
                pass
            
            # If we get here, card read failed
            failed_reads += 1
            if last_status == "connected":
                card_removed_count += 1
                print(f"  [{i*check_interval:.1f}s] ⚠️ Card removed/moved!")
            last_status = "removed"
            
            # Try to reconnect
            try:
                connection = reader.createConnection()
                connection.connect()
            except:
                pass
                
        except Exception as e:
            failed_reads += 1
            if last_status == "connected":
                card_removed_count += 1
                print(f"  [{i*check_interval:.1f}s] ⚠️ Card error: {str(e)[:30]}")
            last_status = "removed"
            
            # Try to reconnect
            try:
                connection = reader.createConnection()
                connection.connect()
            except:
                pass
        
        time.sleep(check_interval)
    
    # Summary
    print(f"\n📊 Stability Test Results:")
    print(f"   Total checks: {checks}")
    print(f"   Successful reads: {successful_reads}")
    print(f"   Failed reads: {failed_reads}")
    print(f"   Card removed/moved events: {card_removed_count}")
    
    if card_removed_count == 0:
        print(f"\n   ✅ Card is STABLE - no disconnections detected")
    elif card_removed_count <= 2:
        print(f"\n   ⚠️ Card is UNSTABLE - occasional disconnections")
        print(f"      This may cause RFID processing failures")
    else:
        print(f"\n   ❌ Card is VERY UNSTABLE - frequent disconnections")
        print(f"      Check card placement and reader connection")


def test_uid_reading_reliability(reader):
    """Test UID reading reliability - multiple attempts"""
    print("\n" + "="*60)
    print("🎯 UID READING RELIABILITY TEST")
    print("="*60)
    print("This tests UID reading success rate over multiple attempts.")
    print("Place your card on the reader...")
    
    if not reader:
        print("⚠️ No reader available")
        return
    
    # Wait for card
    print("\nWaiting for card...")
    max_wait = 30
    poll_interval = 0.1
    elapsed = 0
    card_found = False
    
    while elapsed < max_wait and not card_found:
        try:
            connection = reader.createConnection()
            connection.connect()
            card_found = True
            print("✓ Card detected! Starting reliability test...\n")
        except:
            elapsed += poll_interval
            time.sleep(poll_interval)
    
    if not card_found:
        print("✗ No card detected")
        return
    
    # Test UID reading 20 times
    test_count = 20
    results = {
        'desfire_success': 0,
        'mifare_success': 0,
        'failed': 0,
        'times': []
    }
    
    uids_read = set()
    
    for i in range(test_count):
        start = time.perf_counter()
        uid = None
        method = None
        
        try:
            # Reconnect each time (simulates real polling behavior)
            connection = reader.createConnection()
            connection.connect()
            
            # Try DESFire
            try:
                connection.transmit([0x90, 0x5A, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
                response, sw1, sw2 = connection.transmit([0x90, 0x60, 0x00, 0x00, 0x00])
                
                if sw1 == 0x91 and sw2 == 0xAF:
                    connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                    response, sw1, sw2 = connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                    
                    if len(response) >= 7:
                        uid = bytes(response[0:7]).hex().upper()
                        method = "DESFire"
                        results['desfire_success'] += 1
            except:
                pass
            
            # Try MIFARE if DESFire failed
            if not uid:
                try:
                    response, sw1, sw2 = connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                    if sw1 == 0x90 and sw2 == 0x00 and len(response) > 0:
                        uid = bytes(response).hex().upper()
                        method = "MIFARE"
                        results['mifare_success'] += 1
                except:
                    pass
            
            if not uid:
                results['failed'] += 1
                
        except Exception as e:
            results['failed'] += 1
        
        duration = time.perf_counter() - start
        results['times'].append(duration)
        
        if uid:
            uids_read.add(uid)
            status = "✓"
        else:
            status = "✗"
        
        print(f"  [{i+1:2d}/{test_count}] {status} {method or 'FAILED':8} {duration*1000:6.1f}ms {uid or ''}")
        
        time.sleep(0.1)  # Small delay between reads
    
    # Summary
    total_success = results['desfire_success'] + results['mifare_success']
    success_rate = (total_success / test_count) * 100
    avg_time = sum(results['times']) / len(results['times']) if results['times'] else 0
    
    print(f"\n📊 UID Reading Results:")
    print(f"   Success rate: {success_rate:.1f}% ({total_success}/{test_count})")
    print(f"   DESFire reads: {results['desfire_success']}")
    print(f"   MIFARE reads: {results['mifare_success']}")
    print(f"   Failed reads: {results['failed']}")
    print(f"   Avg read time: {avg_time*1000:.1f}ms")
    print(f"   Unique UIDs: {len(uids_read)}")
    
    if len(uids_read) > 1:
        print(f"\n   ⚠️ WARNING: Multiple different UIDs detected!")
        print(f"      This may indicate card was moved or multiple cards present")
        for uid in uids_read:
            print(f"      - {uid}")
    
    if success_rate >= 95:
        print(f"\n   ✅ UID reading is RELIABLE")
    elif success_rate >= 80:
        print(f"\n   ⚠️ UID reading has occasional failures")
    else:
        print(f"\n   ❌ UID reading is UNRELIABLE - check card/reader")


def test_authentication_with_card_monitoring(card_uid, reader, session):
    """Test authentication while monitoring for card removal"""
    print("\n" + "="*60)
    print("🔐 AUTHENTICATION WITH CARD MONITORING")
    print("="*60)
    print("This simulates real authentication and detects card issues.")
    print("Keep the card on the reader throughout the test!")
    
    if not card_uid or not reader:
        print("⚠️ Card UID or reader not available")
        return None
    
    issues_detected = []
    
    # Create fresh connection
    try:
        connection = reader.createConnection()
        connection.connect()
        print("✓ Card connection established")
    except Exception as e:
        print(f"✗ Initial connection failed: {e}")
        issues_detected.append("Initial connection failed")
        return {'issues': issues_detected}
    
    # Helper to check card presence
    def check_card_present():
        try:
            response, sw1, sw2 = connection.transmit([0x90, 0x60, 0x00, 0x00, 0x00])
            return sw1 == 0x91
        except:
            return False
    
    timings = {}
    
    # Step 1: Auth/start API
    print(f"\n📍 Step 1: Calling /api/rfid/auth/start...")
    
    # Check card before API call
    if not check_card_present():
        print("  ⚠️ Card not present before API call!")
        issues_detected.append("Card removed before auth/start")
    
    step1_start = time.perf_counter()
    try:
        response = session.post(
            f"{BASE_URL}/api/rfid/auth/start",
            json={
                "cardId": card_uid,
                "keyNumber": 0,
                "machineId": MACHINE_ID
            },
            timeout=10
        )
        timings['auth_start'] = time.perf_counter() - step1_start
        print(f"  API call: {timings['auth_start']*1000:.0f}ms")
        
        # Check card after API call (simulates what happens during slow API)
        if not check_card_present():
            print("  ⚠️ Card removed during/after auth/start API call!")
            issues_detected.append("Card removed during auth/start")
        
        if response.status_code != 200:
            print(f"✗ Auth start failed: {response.status_code}")
            issues_detected.append(f"Auth start failed: {response.status_code}")
            return {'timings': timings, 'issues': issues_detected}
        
        data = response.json()
        if not data.get('success'):
            error = data.get('error', 'Unknown error')
            print(f"✗ Auth start error: {error}")
            issues_detected.append(f"Auth start error: {error}")
            return {'timings': timings, 'issues': issues_detected}
        
        if data.get('cardCategory') == 'maintenance':
            print("✓ Maintenance card - no further auth needed")
            return {'timings': timings, 'issues': issues_detected, 'maintenance': True}
        
        session_id = data['sessionId']
        apdu1 = data['apduCommand']
        print(f"  ✓ Got session: {session_id[:20]}...")
        
    except Exception as e:
        timings['auth_start'] = time.perf_counter() - step1_start
        print(f"✗ Exception: {e}")
        issues_detected.append(f"Auth start exception: {str(e)}")
        return {'timings': timings, 'issues': issues_detected}
    
    # Step 2: Card APDU
    print(f"\n📍 Step 2: Sending APDU to card...")
    
    step2_start = time.perf_counter()
    try:
        apdu = convert_apdu(apdu1)
        card_response, sw1, sw2 = connection.transmit(apdu)
        timings['card_apdu1'] = time.perf_counter() - step2_start
        print(f"  Card APDU: {timings['card_apdu1']*1000:.0f}ms")
        
        if sw1 != 0x91 or sw2 != 0xAF:
            print(f"  ⚠️ Unexpected card response: SW1={sw1:02X} SW2={sw2:02X}")
            if sw1 == 0x6A and sw2 == 0x82:
                issues_detected.append("Card removed during APDU (file not found)")
            elif sw1 == 0x69 and sw2 == 0x82:
                issues_detected.append("Security status not satisfied - card moved?")
            else:
                issues_detected.append(f"Card APDU error: SW1={sw1:02X} SW2={sw2:02X}")
            return {'timings': timings, 'issues': issues_detected}
        
        enc_rndb = toHexString(card_response).replace(" ", "")
        print(f"  ✓ Got Enc(RndB)")
        
    except Exception as e:
        timings['card_apdu1'] = time.perf_counter() - step2_start
        error_str = str(e).lower()
        if 'no card' in error_str or 'removed' in error_str or 'not transacted' in error_str:
            print(f"  ❌ CARD REMOVED during APDU!")
            issues_detected.append("Card removed during first APDU")
        else:
            print(f"✗ Card APDU exception: {e}")
            issues_detected.append(f"Card APDU exception: {str(e)}")
        return {'timings': timings, 'issues': issues_detected}
    
    # Step 3: Step2 API
    print(f"\n📍 Step 3: Calling /api/rfid/auth/step2...")
    
    step3_start = time.perf_counter()
    try:
        response = session.post(
            f"{BASE_URL}/api/rfid/auth/step2",
            json={
                "sessionId": session_id,
                "cardResponse": enc_rndb
            },
            timeout=10
        )
        timings['auth_step2'] = time.perf_counter() - step3_start
        print(f"  API call: {timings['auth_step2']*1000:.0f}ms")
        
        # Check card after API
        if not check_card_present():
            print("  ⚠️ Card removed during/after step2 API!")
            issues_detected.append("Card removed during step2 API")
        
        if response.status_code != 200:
            issues_detected.append(f"Step2 failed: {response.status_code}")
            return {'timings': timings, 'issues': issues_detected}
        
        data = response.json()
        apdu2 = data['apduCommand']
        print(f"  ✓ Got next APDU")
        
    except Exception as e:
        timings['auth_step2'] = time.perf_counter() - step3_start
        issues_detected.append(f"Step2 exception: {str(e)}")
        return {'timings': timings, 'issues': issues_detected}
    
    # Step 4: Final card APDU
    print(f"\n📍 Step 4: Sending final APDU to card...")
    
    step4_start = time.perf_counter()
    try:
        apdu = convert_apdu(apdu2)
        card_response, sw1, sw2 = connection.transmit(apdu)
        timings['card_apdu2'] = time.perf_counter() - step4_start
        print(f"  Card APDU: {timings['card_apdu2']*1000:.0f}ms")
        
        if sw1 != 0x91 or sw2 != 0x00:
            print(f"  ⚠️ Final APDU error: SW1={sw1:02X} SW2={sw2:02X}")
            if sw1 == 0x91 and sw2 == 0xAE:
                issues_detected.append("Authentication error - card may have been moved")
            else:
                issues_detected.append(f"Final APDU error: SW1={sw1:02X} SW2={sw2:02X}")
            return {'timings': timings, 'issues': issues_detected}
        
        enc_rot_rnda = toHexString(card_response).replace(" ", "")
        print(f"  ✓ Got Enc(Rot(RndA))")
        
    except Exception as e:
        timings['card_apdu2'] = time.perf_counter() - step4_start
        error_str = str(e).lower()
        if 'no card' in error_str or 'removed' in error_str:
            issues_detected.append("Card removed during final APDU")
        else:
            issues_detected.append(f"Final APDU exception: {str(e)}")
        return {'timings': timings, 'issues': issues_detected}
    
    # Step 5: Verify API
    print(f"\n📍 Step 5: Calling /api/rfid/auth/verify...")
    
    step5_start = time.perf_counter()
    try:
        response = session.post(
            f"{BASE_URL}/api/rfid/auth/verify",
            json={
                "sessionId": session_id,
                "cardResponse": enc_rot_rnda,
                "machineId": MACHINE_ID
            },
            timeout=10
        )
        timings['auth_verify'] = time.perf_counter() - step5_start
        print(f"  API call: {timings['auth_verify']*1000:.0f}ms")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"  ✓ Authentication SUCCESS!")
                print(f"    Balance: {data.get('remainingBalance', 'N/A')}")
            else:
                error = data.get('error', 'Unknown')
                print(f"  ⚠️ Verify failed: {error}")
                issues_detected.append(f"Verify failed: {error}")
        
    except Exception as e:
        timings['auth_verify'] = time.perf_counter() - step5_start
        issues_detected.append(f"Verify exception: {str(e)}")
    
    # Summary
    print(f"\n📊 Authentication Summary:")
    total_time = sum(timings.values())
    print(f"   Total time: {total_time*1000:.0f}ms")
    
    if issues_detected:
        print(f"\n   ⚠️ Issues detected ({len(issues_detected)}):")
        for issue in issues_detected:
            print(f"      - {issue}")
    else:
        print(f"\n   ✅ No issues detected!")
    
    return {'timings': timings, 'issues': issues_detected}


def test_full_authentication(card_uid, reader, session=None, label="", require_retap=True):
    """Test full authentication flow with timing for each step
    
    Args:
        card_uid: Card UID (if None, will detect card)
        reader: RFID reader object
        session: HTTP session (creates new if None)
        label: Label for this test run
        require_retap: If True, asks user to remove and retap card
    """
    print(f"\n{'='*60}")
    print(f"🔐 FULL AUTHENTICATION TEST {label}")
    print("="*60)
    
    timings = {}  # Initialize timings dict early
    
    # If require_retap, ask user to remove and retap card
    if require_retap:
        print("\n⏏️  Please REMOVE the card from the reader...")
        # Wait for card to be removed
        card_removed = False
        for _ in range(100):  # 10 seconds max
            try:
                connection = reader.createConnection()
                connection.connect()
                # Card still present
                time.sleep(0.1)
            except:
                # Card removed
                card_removed = True
                print("✓ Card removed")
                break
        
        if not card_removed:
            print("⚠️ Card was not removed, continuing anyway...")
        
        print("\n💳 Now TAP the card again...")
        print("(Waiting for card...)")
        
        # Wait for card and read UID
        card_detected = False
        detect_start = time.perf_counter()
        uid_time = 0
        for _ in range(300):  # 30 seconds max
            try:
                connection = reader.createConnection()
                connection.connect()
                detect_time = time.perf_counter() - detect_start
                timings['card_detect'] = detect_time
                print(f"✓ Card detected! (Detection time: {detect_time*1000:.0f}ms)")
                card_detected = True
                
                # Read UID
                uid_start = time.perf_counter()
                # Try DESFire
                connection.transmit([0x90, 0x5A, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
                response, sw1, sw2 = connection.transmit([0x90, 0x60, 0x00, 0x00, 0x00])
                
                if sw1 == 0x91 and sw2 == 0xAF:
                    connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                    response, sw1, sw2 = connection.transmit([0x90, 0xAF, 0x00, 0x00, 0x00])
                    if len(response) >= 7:
                        card_uid = bytes(response[0:7]).hex().upper()
                        uid_time = time.perf_counter() - uid_start
                        timings['uid_read'] = uid_time
                        print(f"✓ Card UID: {card_uid} (UID read: {uid_time*1000:.0f}ms)")
                        break
                
                # Try MIFARE
                response, sw1, sw2 = connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                if sw1 == 0x90 and sw2 == 0x00 and len(response) > 0:
                    card_uid = bytes(response).hex().upper()
                    uid_time = time.perf_counter() - uid_start
                    timings['uid_read'] = uid_time
                    print(f"✓ Card UID: {card_uid} (UID read: {uid_time*1000:.0f}ms)")
                    break
                    
            except:
                time.sleep(0.1)
        
        if not card_detected:
            print("✗ Timeout waiting for card")
            return None
    
    if not card_uid:
        print("✗ No card UID available")
        return None
    
    # Create fresh session if not provided
    if not session:
        session_start = time.perf_counter()
        session = create_http_session()
        session_time = time.perf_counter() - session_start
        print(f"  Session creation: {session_time*1000:.0f}ms")
    
    # Create fresh connection for auth
    conn_start = time.perf_counter()
    try:
        connection = reader.createConnection()
        connection.connect()
        conn_time = time.perf_counter() - conn_start
        print(f"✓ Fresh connection: {conn_time*1000:.0f}ms")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None
    
    # timings dict already initialized at the start of the function
    
    # Step 1: Auth/start API
    print(f"\n📍 Step 1: /api/rfid/auth/start")
    step1_start = time.perf_counter()
    try:
        response = session.post(
            f"{BASE_URL}/api/rfid/auth/start",
            json={
                "cardId": card_uid,
                "keyNumber": 0,
                "machineId": MACHINE_ID
            },
            timeout=10
        )
        timings['auth_start'] = time.perf_counter() - step1_start
        print(f"  Time: {timings['auth_start']*1000:.0f}ms (Status: {response.status_code})")
        
        if response.status_code != 200:
            print(f"✗ Auth start failed: {response.text}")
            return timings
        
        data = response.json()
        if not data.get('success'):
            print(f"✗ Auth start error: {data}")
            return timings
        
        # Check for maintenance card
        if data.get('cardCategory') == 'maintenance':
            print(f"✓ Maintenance card detected - authentication complete")
            return timings
        
        session_id = data['sessionId']
        apdu1 = data['apduCommand']
        print(f"  Session ID: {session_id}")
        
    except Exception as e:
        timings['auth_start'] = time.perf_counter() - step1_start
        print(f"✗ Exception: {e}")
        return timings
    
    # Step 2: Get Enc(RndB) from card
    print(f"\n📍 Step 2: Card APDU (Get Enc(RndB))")
    step2_card_start = time.perf_counter()
    try:
        apdu = convert_apdu(apdu1)
        card_response, sw1, sw2 = connection.transmit(apdu)
        timings['card_apdu1'] = time.perf_counter() - step2_card_start
        
        if sw1 != 0x91 or sw2 != 0xAF:
            print(f"✗ Card error: SW1={sw1:02X}, SW2={sw2:02X}")
            return timings
        
        enc_rndb = toHexString(card_response).replace(" ", "")
        print(f"  Time: {timings['card_apdu1']*1000:.0f}ms")
        print(f"  Enc(RndB): {enc_rndb[:16]}...")
        
    except Exception as e:
        timings['card_apdu1'] = time.perf_counter() - step2_card_start
        print(f"✗ Exception: {e}")
        return timings
    
    # Step 3: Step2 API
    print(f"\n📍 Step 3: /api/rfid/auth/step2")
    step2_api_start = time.perf_counter()
    try:
        response = session.post(
            f"{BASE_URL}/api/rfid/auth/step2",
            json={
                "sessionId": session_id,
                "cardResponse": enc_rndb
            },
            timeout=10
        )
        timings['auth_step2'] = time.perf_counter() - step2_api_start
        print(f"  Time: {timings['auth_step2']*1000:.0f}ms (Status: {response.status_code})")
        
        if response.status_code != 200:
            print(f"✗ Step2 failed: {response.text}")
            return timings
        
        data = response.json()
        if not data.get('success'):
            print(f"✗ Step2 error: {data}")
            return timings
        
        apdu2 = data['apduCommand']
        
    except Exception as e:
        timings['auth_step2'] = time.perf_counter() - step2_api_start
        print(f"✗ Exception: {e}")
        return timings
    
    # Step 4: Final card APDU
    print(f"\n📍 Step 4: Card APDU (Enc(Rot(RndA)))")
    step4_card_start = time.perf_counter()
    try:
        apdu = convert_apdu(apdu2)
        card_response, sw1, sw2 = connection.transmit(apdu)
        timings['card_apdu2'] = time.perf_counter() - step4_card_start
        
        if sw1 != 0x91 or sw2 != 0x00:
            print(f"✗ Card error: SW1={sw1:02X}, SW2={sw2:02X}")
            return timings
        
        enc_rot_rnda = toHexString(card_response).replace(" ", "")
        print(f"  Time: {timings['card_apdu2']*1000:.0f}ms")
        print(f"  Enc(Rot(RndA)): {enc_rot_rnda[:16]}...")
        
    except Exception as e:
        timings['card_apdu2'] = time.perf_counter() - step4_card_start
        print(f"✗ Exception: {e}")
        return timings
    
    # Step 5: Verify API
    print(f"\n📍 Step 5: /api/rfid/auth/verify")
    step5_start = time.perf_counter()
    try:
        response = session.post(
            f"{BASE_URL}/api/rfid/auth/verify",
            json={
                "sessionId": session_id,
                "cardResponse": enc_rot_rnda,
                "machineId": MACHINE_ID
            },
            timeout=10
        )
        timings['auth_verify'] = time.perf_counter() - step5_start
        print(f"  Time: {timings['auth_verify']*1000:.0f}ms (Status: {response.status_code})")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✓ Authentication successful!")
                print(f"  Balance: {data.get('remainingBalance', 'N/A')}")
            else:
                print(f"⚠️ Verify returned error: {data.get('error', 'Unknown')}")
        else:
            print(f"⚠️ Verify returned status {response.status_code}")
        
    except Exception as e:
        timings['auth_verify'] = time.perf_counter() - step5_start
        print(f"✗ Exception: {e}")
    
    return timings


def convert_apdu(apdu_hex):
    """Convert hex string APDU to bytes"""
    apdu_hex = apdu_hex.replace(" ", "").upper()
    
    if apdu_hex == "90AA00000100":
        return toBytes("90 AA 00 00 01 00 00")
    
    if apdu_hex.startswith("90AF000020"):
        apdu_list = list(bytes.fromhex(apdu_hex))
        apdu_list.append(0x00)
        return apdu_list
    
    return toBytes(apdu_hex)


def print_summary(all_timings):
    """Print summary of all timing data"""
    print("\n" + "="*60)
    print("📊 TIMING SUMMARY")
    print("="*60)
    
    if not all_timings:
        print("No timing data available")
        return
    
    # Collect stats for each step
    steps = ['card_detect', 'uid_read', 'auth_start', 'card_apdu1', 'auth_step2', 'card_apdu2', 'auth_verify']
    step_names = {
        'card_detect': 'Card Detection',
        'uid_read': 'UID Read',
        'auth_start': '/api/rfid/auth/start',
        'card_apdu1': 'Card APDU #1',
        'auth_step2': '/api/rfid/auth/step2',
        'card_apdu2': 'Card APDU #2',
        'auth_verify': '/api/rfid/auth/verify'
    }
    
    stats = {step: TimingStats(step_names[step]) for step in steps}
    
    for run_timings in all_timings:
        for step in steps:
            if step in run_timings:
                stats[step].add(run_timings[step])
    
    # Print stats
    print("\nPer-step timing:")
    for step in steps:
        if stats[step].times:
            print(f"  {stats[step]}")
    
    # Calculate totals
    totals = []
    for run_timings in all_timings:
        total = sum(run_timings.get(step, 0) for step in steps)
        totals.append(total)
    
    if totals:
        print(f"\nTotal authentication time (from tap to complete):")
        for i, total in enumerate(totals):
            label = f"Test #{i+1}"
            print(f"  {label}: {total*1000:.0f}ms")
        
        if len(totals) > 1:
            avg = sum(totals) / len(totals)
            print(f"\n  Average: {avg*1000:.0f}ms")
            print(f"  First call: {totals[0]*1000:.0f}ms")
            if totals[0] > avg:
                print(f"  ⚡ First call overhead: {(totals[0] - avg)*1000:.0f}ms")
    
    # Identify slowest step
    if all_timings:
        # Find slowest step across all runs
        step_averages = {}
        for step in steps:
            if stats[step].times:
                step_averages[step] = stats[step].avg()
        
        if step_averages:
            slowest_step = max(step_averages, key=step_averages.get)
            print(f"\n🔍 Slowest step (avg): {step_names[slowest_step]} ({step_averages[slowest_step]*1000:.0f}ms)")
            
            # If first call has overhead, identify which step
            if len(all_timings) > 1:
                first_run = all_timings[0]
                avg_times = {step: stats[step].avg() for step in steps if stats[step].times}
                
                max_overhead = 0
                overhead_step = None
                for step in steps:
                    if step in first_run and step in avg_times:
                        overhead = first_run[step] - avg_times[step]
                        if overhead > max_overhead:
                            max_overhead = overhead
                            overhead_step = step
                
                if overhead_step and max_overhead > 100:  # More than 100ms overhead
                    print(f"🔍 Biggest first-call overhead: {step_names[overhead_step]} (+{max_overhead*1000:.0f}ms)")


def main():
    print("="*60)
    print("🔬 RFID AUTHENTICATION TIMING DIAGNOSTIC")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Machine ID: {MACHINE_ID}")
    print(f"SSL Verify: {SSL_VERIFY}")
    if not SSL_VERIFY:
        print("⚠️  WARNING: SSL verification disabled (insecure, for testing only)")
    
    print("\n📋 Available Tests:")
    print("   1. Full diagnostic (all tests)")
    print("   2. Network tests only (DNS, TCP/SSL, HTTP warmup)")
    print("   3. Card stability test")
    print("   4. UID reading reliability test")
    print("   5. Authentication with card monitoring")
    print("   6. Quick authentication test (3 cycles)")
    
    choice = input("\nSelect test [1-6] (default: 1): ").strip() or "1"
    
    if choice == "2":
        # Network tests only
        test_dns_resolution()
        test_tcp_ssl_connection()
        test_http_warmup_methods()
        return
    
    # Initialize reader for all other tests
    reader = test_reader_initialization()
    
    if not reader:
        print("\n⚠️ Cannot proceed without RFID reader")
        return
    
    if choice == "3":
        # Card stability test
        test_card_stability(reader)
        return
    
    if choice == "4":
        # UID reliability test
        test_uid_reading_reliability(reader)
        return
    
    if choice == "5":
        # Authentication with monitoring
        result = test_card_detection(reader)
        if result and result[0]:
            card_uid, _ = result
            session = create_http_session()
            # Warmup
            for url in [BASE_URL, f"{BASE_URL}/api/rfid/auth/start"]:
                try:
                    session.head(url, timeout=2)
                except:
                    pass
            test_authentication_with_card_monitoring(card_uid, reader, session)
        return
    
    if choice == "6":
        # Quick auth test - each test requires fresh card tap
        print("\n📋 Quick Authentication Test")
        print("   Each test will ask you to remove and retap the card")
        print("   This measures the complete flow from card tap to authentication")
        
        all_timings = []
        session = create_http_session()
        
        # Warmup the session first
        print("\nWarming up HTTP session...")
        for url in [BASE_URL, f"{BASE_URL}/api/rfid/auth/start"]:
            try:
                session.head(url, timeout=2)
            except:
                pass
        print("✓ Session warmed up")
        
        for i in range(3):
            input(f"\n>>> Press Enter to start test {i+1}/3...")
            label = f"(Test #{i+1})"
            timings = test_full_authentication(None, reader, session, label, require_retap=True)
            if timings:
                all_timings.append(timings)
        
        print_summary(all_timings)
        return
    
    # Full diagnostic (choice == "1" or default)
    # Run network tests
    test_dns_resolution()
    test_tcp_ssl_connection()
    test_http_warmup_methods()
    
    # Wait for card
    result = test_card_detection(reader)
    if not result or not result[0]:
        print("\n⚠️ Cannot proceed without card")
        return
    
    card_uid, _ = result
    
    # Run stability test
    print("\n" + "="*60)
    print("Would you like to run card stability test? (takes 10 seconds)")
    if input("Run stability test? [y/N]: ").strip().lower() == 'y':
        test_card_stability(reader)
    
    # Run UID reliability test
    print("\n" + "="*60)
    print("Would you like to run UID reliability test? (20 reads)")
    if input("Run UID reliability test? [y/N]: ").strip().lower() == 'y':
        test_uid_reading_reliability(reader)
    
    # Run multiple authentication tests
    print("\n" + "="*60)
    print("🔄 RUNNING AUTHENTICATION TESTS")
    print("="*60)
    print("Each test will ask you to REMOVE and RETAP the card")
    print("This measures complete timing from card tap to authentication\n")
    
    all_timings = []
    
    # Test 1: Cold start (new session, no warmup)
    print("\n" + "-"*40)
    print("TEST 1: COLD START (no warmup)")
    print("-"*40)
    input("Press Enter when ready...")
    cold_session = create_http_session()
    timings1 = test_full_authentication(None, reader, cold_session, "(COLD)", require_retap=True)
    if timings1:
        all_timings.append(timings1)
    
    # Test 2: Warm (same session, connection pooled)
    print("\n" + "-"*40)
    print("TEST 2: WARM (same session, pooled)")
    print("-"*40)
    input("Press Enter when ready...")
    timings2 = test_full_authentication(None, reader, cold_session, "(WARM #1)", require_retap=True)
    if timings2:
        all_timings.append(timings2)
    
    # Test 3: Another warm
    print("\n" + "-"*40)
    print("TEST 3: WARM (same session)")
    print("-"*40)
    input("Press Enter when ready...")
    timings3 = test_full_authentication(None, reader, cold_session, "(WARM #2)", require_retap=True)
    if timings3:
        all_timings.append(timings3)
    
    # Test 4: New session with warmup
    print("\n" + "-"*40)
    print("TEST 4: NEW SESSION WITH WARMUP")
    print("-"*40)
    input("Press Enter when ready...")
    
    warmed_session = create_http_session()
    print("Warming up HTTP connections...")
    warmup_start = time.perf_counter()
    for url in [BASE_URL, f"{BASE_URL}/api/rfid/auth/start", f"{BASE_URL}/api/rfid/auth/step2", f"{BASE_URL}/api/rfid/auth/verify"]:
        try:
            warmed_session.head(url, timeout=2)
        except:
            pass
    warmup_time = time.perf_counter() - warmup_start
    print(f"✓ Warmup completed in {warmup_time*1000:.0f}ms")
    
    timings4 = test_full_authentication(None, reader, warmed_session, "(PRE-WARMED)", require_retap=True)
    if timings4:
        all_timings.append(timings4)
    
    # Print summary
    print_summary(all_timings)
    
    print("\n" + "="*60)
    print("✅ DIAGNOSTIC COMPLETE")
    print("="*60)
    print("\n🔍 Common Issues and Solutions:")
    print("   - Card moved/removed: Keep card steady on reader")
    print("   - Slow first request: HTTP connection warmup needed")
    print("   - UID read failures: Check card/reader alignment")
    print("   - Auth errors (0x91AE): Card was moved during auth")
    print("   - Timeout errors: Check network connectivity")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted by user")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

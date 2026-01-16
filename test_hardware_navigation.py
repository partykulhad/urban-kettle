#!/usr/bin/env python3
"""
Test Script: Hardware Error Page → Payment Method Page Navigation
Tests the automatic navigation when handshake becomes available
"""

from flask import Flask, jsonify
import threading
import time
import requests
import sys

app = Flask(__name__)

# Test state
test_start_time = None
HANDSHAKE_DELAY = 3  # Seconds before handshake becomes available

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """
    Simulates polling_server2.py /api/devices endpoint
    - First 3 seconds: Returns empty list (no handshake)
    - After 3 seconds: Returns device (handshake complete)
    """
    global test_start_time
    
    if test_start_time is None:
        test_start_time = time.time()
    
    elapsed = time.time() - test_start_time
    
    if elapsed < HANDSHAKE_DELAY:
        # NO HANDSHAKE YET - Simulate ESP32 not connected
        print(f"⏳ [{elapsed:.1f}s] No devices (handshake pending)")
        return jsonify({
            "devices": [],
            "count": 0
        }), 200
    else:
        # HANDSHAKE COMPLETE - Simulate ESP32 connected
        print(f"✅ [{elapsed:.1f}s] Device connected! (handshake complete)")
        return jsonify({
            "devices": ["UK_TEST_DEVICE_12345678"],
            "count": 1
        }), 200

@app.route('/api/status', methods=['GET'])
def server_status():
    """Server status check (for hardware_monitor startup)"""
    return jsonify({
        "status": "running",
        "test_mode": True,
        "devices_connected": 0
    }), 200

@app.route('/api/device/<device_id>/history', methods=['GET'])
def device_history(device_id):
    """Device history endpoint (returns 404 when no device)"""
    global test_start_time
    elapsed = time.time() - test_start_time if test_start_time else 0
    
    if elapsed < HANDSHAKE_DELAY:
        # No history yet
        return jsonify({
            "error": "Device not found"
        }), 404
    else:
        # Return healthy status
        return jsonify({
            "health": [{
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "data": {
                    "messageType": "health",
                    "checks": {
                        "sensor:pt100_sensor_01": [{
                            "componentId": "pt100_sensor_01",
                            "status": "pass",
                            "observedValue": 83,
                            "unit": "°C"
                        }]
                    }
                }
            }]
        }), 200

def run_test_server():
    """Run the mock polling server"""
    print("="*80)
    print("🧪 HARDWARE NAVIGATION TEST SERVER")
    print("="*80)
    print(f"Simulating handshake delay: {HANDSHAKE_DELAY} seconds")
    print("Server running on http://127.0.0.1:5000")
    print("="*80)
    print("\n📋 Test Sequence:")
    print(f"  0-{HANDSHAKE_DELAY}s: No handshake → Should show Hardware Error Page")
    print(f"  {HANDSHAKE_DELAY}s+:  Handshake complete → Should navigate to Payment Method Page")
    print("\n🔄 Monitoring /api/devices requests...\n")
    
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def monitor_navigation():
    """Monitor the test and provide feedback"""
    time.sleep(1)  # Wait for server to start
    
    print("\n" + "="*80)
    print("📊 TEST MONITORING")
    print("="*80)
    
    for i in range(10):
        try:
            response = requests.get("http://127.0.0.1:5000/api/devices", timeout=1)
            data = response.json()
            devices = data.get('devices', [])
            
            if len(devices) == 0:
                print(f"⏱️  {i+1}s: No handshake - App should be on Hardware Error Page")
            else:
                print(f"✅ {i+1}s: Handshake complete - App should navigate to Payment Method Page!")
                print(f"   Device: {devices[0]}")
                
        except Exception as e:
            print(f"❌ {i+1}s: Error checking status: {e}")
        
        time.sleep(1)
    
    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)
    print("\nExpected Results:")
    print(f"  • Seconds 0-{HANDSHAKE_DELAY}: Hardware Error Page visible")
    print(f"  • Seconds {HANDSHAKE_DELAY}+: Auto-navigate to Payment Method Page")
    print("\nPress Ctrl+C to stop the test server")
    print("="*80 + "\n")

if __name__ == '__main__':
    print("\n🚀 Starting Hardware Navigation Test\n")
    
    # Run server in background thread
    server_thread = threading.Thread(target=run_test_server, daemon=True)
    server_thread.start()
    
    # Monitor the test
    try:
        monitor_navigation()
        
        # Keep server running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Test stopped by user")
        sys.exit(0)

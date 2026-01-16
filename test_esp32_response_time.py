"""
ESP32 Response Time Test
Tests dispense command and pump status API response times
"""

import requests
import time
import uuid
import statistics
from datetime import datetime


class ESP32ResponseTester:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.device_id = "UK_14335C5D48C8"
        
    def test_dispense_command(self, iterations=5):
        """Test dispense command response time"""
        print("\n" + "="*80)
        print("🧪 TESTING DISPENSE COMMAND RESPONSE TIME")
        print("="*80)
        
        response_times = []
        
        for i in range(iterations):
            job_id = f"test_job_{uuid.uuid4().hex[:8]}"
            command_id = f"test_cmd_{i}"
            
            url = f"{self.base_url}/api/device/command"
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": command_id,
                "deviceId": self.device_id,
                "command": {
                    "action": "start_dispense",
                    "parameters": {
                        "jobId": job_id
                    }
                }
            }
            
            print(f"\n📤 Test {i+1}/{iterations}: Sending dispense command...")
            start_time = time.time()
            
            try:
                response = requests.post(url, json=payload, timeout=30)
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                if response.status_code == 200:
                    result = response.json()
                    status_code = result.get('response', {}).get('statusCode', 'N/A')
                    print(f"✅ Response received in {response_time:.2f}ms")
                    print(f"   Status Code: {status_code}")
                    response_times.append(response_time)
                else:
                    print(f"❌ Failed with HTTP {response.status_code}")
                    print(f"   Response time: {response_time:.2f}ms")
                    
            except requests.Timeout:
                print(f"⏱️ TIMEOUT after 30 seconds")
            except Exception as e:
                print(f"❌ Error: {e}")
            
            # Wait between tests
            if i < iterations - 1:
                print("⏳ Waiting2 seconds before next test...")
                time.sleep(2)
        
        # Statistics
        if response_times:
            print("\n" + "="*80)
            print("📊 DISPENSE COMMAND STATISTICS")
            print("="*80)
            print(f"Total Tests: {len(response_times)}")
            print(f"Average Response Time: {statistics.mean(response_times):.2f}ms")
            print(f"Min Response Time: {min(response_times):.2f}ms")
            print(f"Max Response Time: {max(response_times):.2f}ms")
            if len(response_times) > 1:
                print(f"Std Deviation: {statistics.stdev(response_times):.2f}ms")
        
        return response_times
    
    def test_pump_status(self, iterations=10, interval=0.5):
        """Test pump status polling response time"""
        print("\n" + "="*80)
        print("🧪 TESTING PUMP STATUS POLLING RESPONSE TIME")
        print("="*80)
        print(f"Polling {iterations} times with {interval}s interval")
        
        response_times = []
        
        for i in range(iterations):
            url = f"{self.base_url}/api/device/sensor/pump_status?deviceId={self.device_id}"
            
            print(f"\n📤 Poll {i+1}/{iterations}: Checking pump status...")
            start_time = time.time()
            
            try:
                response = requests.get(url, timeout=5)
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                if response.status_code == 200:
                    result = response.json()
                    pump_data = result.get('response', {}).get('data', {})
                    pump_state = pump_data.get('pumpState', 'Unknown')
                    print(f"✅ Response received in {response_time:.2f}ms")
                    print(f"   Pump State: {pump_state}")
                    response_times.append(response_time)
                else:
                    print(f"❌ Failed with HTTP {response.status_code}")
                    print(f"   Response time: {response_time:.2f}ms")
                    
            except requests.Timeout:
                print(f"⏱️ TIMEOUT after 5 seconds")
            except Exception as e:
                print(f"❌ Error: {e}")
            
            # Wait between polls
            if i < iterations - 1:
                time.sleep(interval)
        
        # Statistics
        if response_times:
            print("\n" + "="*80)
            print("📊 PUMP STATUS POLLING STATISTICS")
            print("="*80)
            print(f"Total Polls: {len(response_times)}")
            print(f"Average Response Time: {statistics.mean(response_times):.2f}ms")
            print(f"Min Response Time: {min(response_times):.2f}ms")
            print(f"Max Response Time: {max(response_times):.2f}ms")
            if len(response_times) > 1:
                print(f"Std Deviation: {statistics.stdev(response_times):.2f}ms")
        
        return response_times
    
    def test_cup_detection(self, iterations=10, interval=1.0):
        """Test cup detection polling response time"""
        print("\n" + "="*80)
        print("🧪 TESTING CUP DETECTION POLLING RESPONSE TIME")
        print("="*80)
        print(f"Polling {iterations} times with {interval}s interval")
        
        response_times = []
        
        for i in range(iterations):
            url = f"{self.base_url}/api/device/command"
            payload = {
                "messageType": "request_cup",
                "commandType": "request",
                "version": "1.0",
                "deviceId": self.device_id
            }
            
            print(f"\n📤 Poll {i+1}/{iterations}: Checking cup detection...")
            start_time = time.time()
            
            try:
                response = requests.post(url, json=payload, timeout=5)
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                if response.status_code == 200:
                    result = response.json()
                    status_code = result.get('statusCode', 'N/A')
                    cup_status = "Cup Detected" if status_code == 200 else "No Cup"
                    print(f"✅ Response received in {response_time:.2f}ms")
                    print(f"   Status: {cup_status} (Code: {status_code})")
                    response_times.append(response_time)
                else:
                    print(f"❌ Failed with HTTP {response.status_code}")
                    print(f"   Response time: {response_time:.2f}ms")
                    
            except requests.Timeout:
                print(f"⏱️ TIMEOUT after 5 seconds")
            except Exception as e:
                print(f"❌ Error: {e}")
            
            # Wait between polls
            if i < iterations - 1:
                time.sleep(interval)
        
        # Statistics
        if response_times:
            print("\n" + "="*80)
            print("📊 CUP DETECTION POLLING STATISTICS")
            print("="*80)
            print(f"Total Polls: {len(response_times)}")
            print(f"Average Response Time: {statistics.mean(response_times):.2f}ms")
            print(f"Min Response Time: {min(response_times):.2f}ms")
            print(f"Max Response Time: {max(response_times):.2f}ms")
            if len(response_times) > 1:
                print(f"Std Deviation: {statistics.stdev(response_times):.2f}ms")
        
        return response_times
    
    def run_all_tests(self):
        """Run all response time tests"""
        print("\n" + "="*80)
        print("🚀 ESP32 RESPONSE TIME TEST SUITE")
        print("="*80)
        print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Base URL: {self.base_url}")
        print(f"Device ID: {self.device_id}")
        
        # Test 1: Cup Detection (most frequent in app)
        cup_times = self.test_cup_detection(iterations=10, interval=1.0)
        
        # Test 2: Pump Status (during dispensing)
        pump_times = self.test_pump_status(iterations=10, interval=0.5)
        
        # Test 3: Dispense Command (critical for user experience)
        dispense_times = self.test_dispense_command(iterations=3)
        
        # Overall Summary
        print("\n" + "="*80)
        print("📋 OVERALL SUMMARY")
        print("="*80)
        
        if cup_times:
            print(f"\n🔍 Cup Detection:")
            print(f"   Average: {statistics.mean(cup_times):.2f}ms")
            print(f"   Range: {min(cup_times):.2f}ms - {max(cup_times):.2f}ms")
        
        if pump_times:
            print(f"\n⚙️  Pump Status:")
            print(f"   Average: {statistics.mean(pump_times):.2f}ms")
            print(f"   Range: {min(pump_times):.2f}ms - {max(pump_times):.2f}ms")
        
        if dispense_times:
            print(f"\n💧 Dispense Command:")
            print(f"   Average: {statistics.mean(dispense_times):.2f}ms")
            print(f"   Range: {min(dispense_times):.2f}ms - {max(dispense_times):.2f}ms")
        
        print("\n" + "="*80)
        print(f"Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)


if __name__ == "__main__":
    tester = ESP32ResponseTester()
    tester.run_all_tests()

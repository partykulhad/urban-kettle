#!/usr/bin/env python3
"""
Kulhad API Benchmark Script
Measures response times and calculates average speed for all kulhad.vercel.app APIs
Run this on Raspberry Pi to diagnose slow QR generation issues
"""

import requests
import time
import statistics
import json
from datetime import datetime
import socket

# API Endpoints to test
APIS = {
    # ============ KULHAD VERCEL APIS ============
    "Machine Status": {
        "url": "https://kulhad.vercel.app/api/MachinesStatus",
        "method": "GET",
        "params": {"machineId": "KH-01"},
        "category": "kulhad"
    },
    "Direct Payment (QR Generation)": {
        "url": "https://kulhad.vercel.app/api/direct-payment",
        "method": "POST",
        "json": {"machineId": "KH-01", "numberOfCups": 1},
        "category": "kulhad"
    },
    "Transaction Status": {
        "url": "https://kulhad.vercel.app/api/transaction-status",
        "method": "POST",
        "json": {"transactionId": "test-transaction-id"},
        "category": "kulhad"
    },
    "Canister Check": {
        "url": "https://kulhad.vercel.app/api/canister-check",
        "method": "GET",
        "params": {"machineId": "KH-01"},
        "category": "kulhad"
    },
    "Reduce Cups": {
        "url": "https://kulhad.vercel.app/api/reduce-cups",
        "method": "POST",
        "json": {"machineId": "KH-01", "cups": 0},  # 0 cups to not actually reduce
        "category": "kulhad"
    },
    
    # ============ RFID / UKTEAWALLET APIS ============
    "RFID Auth Start": {
        "url": "https://www.ukteawallet.com/api/rfid/auth/start",
        "method": "POST",
        "json": {
            "machineId": "UK_0007",
            "cardUid": "TEST00000000000"  # Dummy UID for testing
        },
        "category": "rfid"
    },
    "RFID Auth Step2": {
        "url": "https://www.ukteawallet.com/api/rfid/auth/step2",
        "method": "POST",
        "json": {
            "sessionId": "test-session-id",
            "cardResponse": "0000000000000000"  # Dummy response
        },
        "category": "rfid"
    },
    "RFID Auth Verify": {
        "url": "https://www.ukteawallet.com/api/rfid/auth/verify",
        "method": "POST",
        "json": {
            "sessionId": "test-session-id",
            "cardResponse": "0000000000000000"  # Dummy response
        },
        "category": "rfid"
    }
}

# Number of times to test each API
TEST_ITERATIONS = 5

# Timeout for each request
REQUEST_TIMEOUT = 30


def get_network_info():
    """Get basic network information"""
    info = {
        "hostname": socket.gethostname(),
        "timestamp": datetime.now().isoformat()
    }
    
    # Try to get external IP
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        info["external_ip"] = response.json().get("ip", "Unknown")
    except:
        info["external_ip"] = "Unable to fetch"
    
    return info


def measure_dns_resolution(host="kulhad.vercel.app"):
    """Measure DNS resolution time"""
    start = time.time()
    try:
        socket.gethostbyname(host)
        elapsed = (time.time() - start) * 1000
        return elapsed
    except:
        return None


def test_cold_start(url, name):
    """Test cold start latency - first request after connection is closed"""
    # Create a fresh session (no connection pooling)
    fresh_session = requests.Session()
    
    results = []
    for i in range(3):
        # Close any existing connections
        fresh_session.close()
        fresh_session = requests.Session()
        
        start = time.time()
        try:
            response = fresh_session.head(url, timeout=15)
            elapsed = (time.time() - start) * 1000
            results.append({
                "attempt": i + 1,
                "time_ms": elapsed,
                "status": response.status_code
            })
        except Exception as e:
            results.append({
                "attempt": i + 1,
                "error": str(e)[:50]
            })
        
        # Wait a bit between tests
        time.sleep(1)
    
    fresh_session.close()
    return results


def measure_internet_speed():
    """Measure approximate download speed using a small file"""
    test_urls = [
        ("Cloudflare", "https://www.cloudflare.com/cdn-cgi/trace"),
        ("Google", "https://www.google.com/generate_204"),
    ]
    
    results = []
    for name, url in test_urls:
        try:
            start = time.time()
            response = requests.get(url, timeout=10)
            elapsed = time.time() - start
            size_bytes = len(response.content)
            speed_kbps = (size_bytes / 1024) / elapsed if elapsed > 0 else 0
            results.append({
                "name": name,
                "time_ms": elapsed * 1000,
                "size_bytes": size_bytes,
                "speed_kbps": speed_kbps
            })
        except Exception as e:
            results.append({
                "name": name,
                "error": str(e)
            })
    
    return results


def test_api(name, config, iteration):
    """Test a single API endpoint and return timing data"""
    url = config["url"]
    method = config["method"]
    
    result = {
        "name": name,
        "iteration": iteration,
        "url": url,
        "method": method,
        "success": False,
        "status_code": None,
        "response_time_ms": None,
        "error": None
    }
    
    try:
        start_time = time.time()
        
        if method == "GET":
            response = requests.get(
                url, 
                params=config.get("params"),
                timeout=REQUEST_TIMEOUT
            )
        elif method == "POST":
            response = requests.post(
                url,
                json=config.get("json"),
                timeout=REQUEST_TIMEOUT
            )
        else:
            result["error"] = f"Unknown method: {method}"
            return result
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        result["success"] = response.status_code == 200
        result["status_code"] = response.status_code
        result["response_time_ms"] = elapsed_ms
        
        # Try to get response size
        result["response_size_bytes"] = len(response.content)
        
    except requests.exceptions.Timeout:
        result["error"] = f"Timeout after {REQUEST_TIMEOUT}s"
        result["response_time_ms"] = REQUEST_TIMEOUT * 1000
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {str(e)[:100]}"
    except Exception as e:
        result["error"] = f"Error: {str(e)[:100]}"
    
    return result


def run_benchmark():
    """Run the complete benchmark"""
    print("=" * 70)
    print("🚀 KULHAD API BENCHMARK")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test iterations per API: {TEST_ITERATIONS}")
    print(f"Request timeout: {REQUEST_TIMEOUT}s")
    print()
    
    # Network Info
    print("-" * 70)
    print("📡 NETWORK INFORMATION")
    print("-" * 70)
    net_info = get_network_info()
    print(f"Hostname: {net_info['hostname']}")
    print(f"External IP: {net_info['external_ip']}")
    
    # DNS Resolution
    print()
    print("-" * 70)
    print("🔍 DNS RESOLUTION TEST")
    print("-" * 70)
    
    # Test kulhad.vercel.app
    print("\n  kulhad.vercel.app:")
    dns_times_kulhad = []
    for i in range(3):
        dns_time = measure_dns_resolution("kulhad.vercel.app")
        if dns_time:
            dns_times_kulhad.append(dns_time)
            print(f"    Attempt {i+1}: {dns_time:.2f}ms")
        else:
            print(f"    Attempt {i+1}: FAILED")
    if dns_times_kulhad:
        print(f"    Average: {statistics.mean(dns_times_kulhad):.2f}ms")
    
    # Test ukteawallet.com (RFID)
    print("\n  www.ukteawallet.com (RFID):")
    dns_times_rfid = []
    for i in range(3):
        dns_time = measure_dns_resolution("www.ukteawallet.com")
        if dns_time:
            dns_times_rfid.append(dns_time)
            print(f"    Attempt {i+1}: {dns_time:.2f}ms")
        else:
            print(f"    Attempt {i+1}: FAILED")
    if dns_times_rfid:
        print(f"    Average: {statistics.mean(dns_times_rfid):.2f}ms")
    
    # Cold Start Test (RFID first-request issue)
    print()
    print("-" * 70)
    print("❄️ COLD START TEST (First Request After Idle)")
    print("-" * 70)
    print("  This simulates the 'first RFID request is slow' issue")
    print()
    
    print("  Testing ukteawallet.com cold start:")
    cold_results = test_cold_start("https://www.ukteawallet.com", "ukteawallet")
    for r in cold_results:
        if "error" in r:
            print(f"    Cold start {r['attempt']}: FAILED - {r['error']}")
        else:
            print(f"    Cold start {r['attempt']}: {r['time_ms']:.0f}ms")
    
    # Analyze cold start
    cold_times = [r['time_ms'] for r in cold_results if 'time_ms' in r]
    if len(cold_times) >= 2:
        first_vs_rest = cold_times[0] - statistics.mean(cold_times[1:])
        if first_vs_rest > 500:
            print(f"\n  ⚠️ COLD START PENALTY DETECTED!")
            print(f"     First request: {cold_times[0]:.0f}ms")
            print(f"     Subsequent avg: {statistics.mean(cold_times[1:]):.0f}ms")
            print(f"     Penalty: +{first_vs_rest:.0f}ms on first request")
    
    # Basic connectivity test
    print()
    print("-" * 70)
    print("🌐 CONNECTIVITY TEST")
    print("-" * 70)
    speed_results = measure_internet_speed()
    for r in speed_results:
        if "error" in r:
            print(f"  {r['name']}: FAILED - {r['error']}")
        else:
            print(f"  {r['name']}: {r['time_ms']:.2f}ms ({r['size_bytes']} bytes)")
    
    # API Tests
    print()
    print("-" * 70)
    print("📊 API RESPONSE TIME TESTS")
    print("-" * 70)
    
    all_results = {}
    
    # Group APIs by category
    kulhad_apis = {k: v for k, v in APIS.items() if v.get("category") == "kulhad"}
    rfid_apis = {k: v for k, v in APIS.items() if v.get("category") == "rfid"}
    
    print("\n" + "=" * 40)
    print("📦 KULHAD.VERCEL.APP APIs")
    print("=" * 40)
    
    for api_name, api_config in kulhad_apis.items():
        print(f"\n🔄 Testing: {api_name}")
        print(f"   URL: {api_config['url']}")
        print(f"   Method: {api_config['method']}")
        
        api_times = []
        api_results = []
        
        for i in range(TEST_ITERATIONS):
            result = test_api(api_name, api_config, i + 1)
            api_results.append(result)
            
            if result["success"]:
                api_times.append(result["response_time_ms"])
                status = f"✅ {result['response_time_ms']:.0f}ms"
            elif result["error"]:
                status = f"❌ {result['error'][:40]}"
            else:
                status = f"⚠️ HTTP {result['status_code']} - {result['response_time_ms']:.0f}ms"
            
            print(f"   Iteration {i+1}: {status}")
            
            # Small delay between requests
            time.sleep(0.5)
        
        # Calculate statistics
        if api_times:
            stats = {
                "min": min(api_times),
                "max": max(api_times),
                "avg": statistics.mean(api_times),
                "median": statistics.median(api_times),
                "stdev": statistics.stdev(api_times) if len(api_times) > 1 else 0,
                "success_rate": len(api_times) / TEST_ITERATIONS * 100
            }
            all_results[api_name] = stats
            
            print(f"\n   📈 Statistics for {api_name}:")
            print(f"      Min: {stats['min']:.0f}ms")
            print(f"      Max: {stats['max']:.0f}ms")
            print(f"      Avg: {stats['avg']:.0f}ms")
            print(f"      Median: {stats['median']:.0f}ms")
            print(f"      Std Dev: {stats['stdev']:.0f}ms")
            print(f"      Success Rate: {stats['success_rate']:.0f}%")
        else:
            all_results[api_name] = {"error": "All requests failed"}
            print(f"\n   ❌ All requests failed for {api_name}")
    
    # RFID APIs
    print("\n" + "=" * 40)
    print("🏷️ UKTEAWALLET.COM RFID APIs")
    print("=" * 40)
    print("  (Note: These will fail without real card data, but we measure latency)")
    
    for api_name, api_config in rfid_apis.items():
        print(f"\n🔄 Testing: {api_name}")
        print(f"   URL: {api_config['url']}")
        print(f"   Method: {api_config['method']}")
        
        api_times = []
        api_results = []
        
        for i in range(TEST_ITERATIONS):
            result = test_api(api_name, api_config, i + 1)
            api_results.append(result)
            
            # For RFID, we accept 400/401 as valid responses (means server responded)
            if result["response_time_ms"] and result["status_code"] in [200, 400, 401, 404]:
                api_times.append(result["response_time_ms"])
                status = f"📡 {result['response_time_ms']:.0f}ms (HTTP {result['status_code']})"
            elif result["error"]:
                status = f"❌ {result['error'][:40]}"
            else:
                status = f"⚠️ HTTP {result['status_code']} - {result['response_time_ms']:.0f}ms"
            
            print(f"   Iteration {i+1}: {status}")
            
            # Small delay between requests
            time.sleep(0.5)
        
        # Calculate statistics
        if api_times:
            stats = {
                "min": min(api_times),
                "max": max(api_times),
                "avg": statistics.mean(api_times),
                "median": statistics.median(api_times),
                "stdev": statistics.stdev(api_times) if len(api_times) > 1 else 0,
                "success_rate": len(api_times) / TEST_ITERATIONS * 100,
                "first_request": api_times[0] if api_times else 0,
                "subsequent_avg": statistics.mean(api_times[1:]) if len(api_times) > 1 else 0
            }
            all_results[api_name] = stats
            
            print(f"\n   📈 Statistics for {api_name}:")
            print(f"      Min: {stats['min']:.0f}ms")
            print(f"      Max: {stats['max']:.0f}ms")
            print(f"      Avg: {stats['avg']:.0f}ms")
            print(f"      First Request: {stats['first_request']:.0f}ms")
            if stats['subsequent_avg'] > 0:
                print(f"      Subsequent Avg: {stats['subsequent_avg']:.0f}ms")
                penalty = stats['first_request'] - stats['subsequent_avg']
                if penalty > 300:
                    print(f"      ⚠️ First Request Penalty: +{penalty:.0f}ms")
        else:
            all_results[api_name] = {"error": "All requests failed"}
            print(f"\n   ❌ All requests failed for {api_name}")
    
    # Summary
    print()
    print("=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print()
    print(f"{'API Name':<35} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'Success':<10}")
    print("-" * 70)
    
    for api_name, stats in all_results.items():
        if "error" in stats:
            print(f"{api_name:<35} {'FAILED':<12} {'-':<12} {'-':<12} {'0%':<10}")
        else:
            print(f"{api_name:<35} {stats['avg']:<12.0f} {stats['min']:<12.0f} {stats['max']:<12.0f} {stats['success_rate']:.0f}%")
    
    print()
    print("=" * 70)
    print("🎯 RECOMMENDATIONS")
    print("=" * 70)
    
    # Analyze results and give recommendations
    slow_apis = []
    for api_name, stats in all_results.items():
        if "error" not in stats and stats["avg"] > 2000:
            slow_apis.append((api_name, stats["avg"]))
    
    if slow_apis:
        print("\n⚠️ SLOW APIs DETECTED (>2 seconds average):")
        for api, avg_time in sorted(slow_apis, key=lambda x: x[1], reverse=True):
            print(f"   - {api}: {avg_time:.0f}ms average")
        print("\nPossible causes:")
        print("   1. Slow internet connection on Raspberry Pi")
        print("   2. High latency to Vercel servers (consider CDN/region)")
        print("   3. Server-side processing time")
        print("   4. DNS resolution delays")
    else:
        print("\n✅ All APIs are responding within acceptable limits (<2 seconds)")
    
    # QR Generation specific recommendation
    qr_api_stats = all_results.get("Direct Payment (QR Generation)")
    if qr_api_stats and "error" not in qr_api_stats:
        if qr_api_stats["avg"] > 3000:
            print(f"\n⚠️ QR Generation is slow ({qr_api_stats['avg']:.0f}ms average)")
            print("   Consider implementing:")
            print("   1. Pre-generation of QR codes")
            print("   2. Connection pooling (already implemented)")
            print("   3. Caching machine status responses")
        elif qr_api_stats["avg"] > 1500:
            print(f"\n⚡ QR Generation is acceptable but could be faster ({qr_api_stats['avg']:.0f}ms)")
    
    print()
    print(f"Benchmark completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Save results to file
    output_file = f"api_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "network_info": net_info,
            "dns_times": dns_times,
            "api_results": all_results
        }, f, indent=2)
    print(f"\n📁 Results saved to: {output_file}")


if __name__ == "__main__":
    run_benchmark()

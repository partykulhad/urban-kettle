#!/usr/bin/env python3
"""
Real-time Performance Monitor for Urban Kettle
===============================================
A lightweight script that shows live performance metrics.

Usage:
    python live_monitor.py           # Run with default settings
    python live_monitor.py --compact # Compact single-line output
"""

import os
import sys
import time
import psutil
import requests
import threading
from datetime import datetime
from collections import deque

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'

# Configuration
POLLING_SERVER = 'http://localhost:5001'
REFRESH_RATE = 1.0  # seconds

class LiveMonitor:
    def __init__(self):
        self.api_times = {}  # endpoint -> deque of times
        self.cpu_history = deque(maxlen=60)
        self.mem_history = deque(maxlen=60)
        self.network_latency = deque(maxlen=60)  # Network latency history
        self.running = True
        
    def get_temp(self):
        """Get Raspberry Pi temperature"""
        try:
            temp_file = '/sys/class/thermal/thermal_zone0/temp'
            if os.path.exists(temp_file):
                with open(temp_file, 'r') as f:
                    return float(f.read().strip()) / 1000.0
        except:
            pass
        return None
    
    def get_process_stats(self, name_pattern):
        """Get stats for a process by name pattern"""
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info.get('cmdline', []))
                if name_pattern in cmdline:
                    return {
                        'pid': proc.info['pid'],
                        'cpu': proc.cpu_percent(interval=0.1),
                        'mem_mb': proc.memory_info().rss / (1024 * 1024),
                        'threads': proc.num_threads()
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def test_api(self, endpoint):
        """Test API response time"""
        try:
            start = time.perf_counter()
            resp = requests.get(f'{POLLING_SERVER}{endpoint}', timeout=5)
            duration = (time.perf_counter() - start) * 1000
            return {'ms': duration, 'ok': resp.status_code == 200, 'status': resp.status_code}
        except requests.exceptions.Timeout:
            return {'ms': 5000, 'ok': False, 'error': 'Timeout'}
        except requests.exceptions.ConnectionError:
            return {'ms': 0, 'ok': False, 'error': 'Connection refused'}
        except Exception as e:
            return {'ms': 0, 'ok': False, 'error': str(e)[:30]}
    
    def colorize(self, value, thresholds, unit=''):
        """Colorize a value based on thresholds (good, warning, bad)"""
        good, warning = thresholds
        if value < good:
            color = Colors.GREEN
        elif value < warning:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        return f"{color}{value:.1f}{unit}{Colors.RESET}"
    
    def status_icon(self, ok):
        return f"{Colors.GREEN}✓{Colors.RESET}" if ok else f"{Colors.RED}✗{Colors.RESET}"
    
    def draw_bar(self, value, max_val=100, width=20):
        """Draw a simple progress bar"""
        filled = int((value / max_val) * width)
        filled = min(filled, width)
        
        if value < 50:
            color = Colors.GREEN
        elif value < 80:
            color = Colors.YELLOW
        else:
            color = Colors.RED
            
        bar = '█' * filled + '░' * (width - filled)
        return f"{color}{bar}{Colors.RESET}"
    
    def clear_screen(self):
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def run_compact(self):
        """Run in compact single-line mode"""
        print(f"{Colors.CYAN}Live Monitor (Compact) - Press Ctrl+C to exit{Colors.RESET}")
        
        while self.running:
            try:
                # Gather metrics
                cpu = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory().percent
                temp = self.get_temp()
                
                # API test
                api = self.test_api('/api/status')
                
                # Process stats
                app = self.get_process_stats('main_app.py')
                
                # Build line
                parts = [
                    f"{datetime.now().strftime('%H:%M:%S')}",
                    f"CPU:{self.colorize(cpu, (50, 80), '%')}",
                    f"MEM:{self.colorize(mem, (60, 85), '%')}",
                ]
                
                if temp:
                    parts.append(f"TEMP:{self.colorize(temp, (60, 75), '°C')}")
                
                parts.append(f"API:{self.status_icon(api['ok'])} {api['ms']:.0f}ms")
                
                if app:
                    parts.append(f"APP:{app['mem_mb']:.0f}MB/{app['threads']}t")
                else:
                    parts.append(f"APP:{Colors.RED}OFF{Colors.RESET}")
                
                # Print on same line
                line = ' | '.join(parts)
                sys.stdout.write(f"\r{line}    ")
                sys.stdout.flush()
                
                time.sleep(REFRESH_RATE)
                
            except KeyboardInterrupt:
                self.running = False
                print("\n")
    
    def run_full(self):
        """Run with full dashboard display"""
        while self.running:
            try:
                self.clear_screen()
                
                # Header
                print(f"{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.CYAN}║     URBAN KETTLE LIVE PERFORMANCE MONITOR                    ║{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.CYAN}╠══════════════════════════════════════════════════════════════╣{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                Press Ctrl+C to exit     {Colors.CYAN}║{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.CYAN}╚══════════════════════════════════════════════════════════════╝{Colors.RESET}")
                
                # System Resources
                cpu = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                temp = self.get_temp()
                
                self.cpu_history.append(cpu)
                self.mem_history.append(mem.percent)
                
                print(f"\n{Colors.BOLD}📊 SYSTEM RESOURCES{Colors.RESET}")
                print(f"   CPU:    {self.draw_bar(cpu)} {self.colorize(cpu, (50, 80), '%')}")
                print(f"   Memory: {self.draw_bar(mem.percent)} {self.colorize(mem.percent, (60, 85), '%')} ({mem.used//(1024**2)}MB/{mem.total//(1024**2)}MB)")
                print(f"   Disk:   {self.draw_bar(disk.percent)} {disk.percent:.1f}% ({disk.free//(1024**3)}GB free)")
                
                if temp:
                    print(f"   Temp:   {self.draw_bar(temp, 85)} {self.colorize(temp, (60, 75), '°C')}")
                
                # Average stats
                if len(self.cpu_history) > 5:
                    avg_cpu = sum(self.cpu_history) / len(self.cpu_history)
                    avg_mem = sum(self.mem_history) / len(self.mem_history)
                    print(f"   {Colors.CYAN}Avg (last {len(self.cpu_history)}s): CPU {avg_cpu:.1f}% | Mem {avg_mem:.1f}%{Colors.RESET}")
                
                # Process Stats
                print(f"\n{Colors.BOLD}🔄 PROCESSES{Colors.RESET}")
                
                app = self.get_process_stats('main_app.py')
                if app:
                    print(f"   main_app.py    PID:{app['pid']:5d}  CPU:{app['cpu']:5.1f}%  Mem:{app['mem_mb']:6.1f}MB  Threads:{app['threads']}")
                else:
                    print(f"   main_app.py    {Colors.RED}NOT RUNNING{Colors.RESET}")
                
                srv = self.get_process_stats('polling_server')
                if srv:
                    print(f"   polling_server PID:{srv['pid']:5d}  CPU:{srv['cpu']:5.1f}%  Mem:{srv['mem_mb']:6.1f}MB  Threads:{srv['threads']}")
                else:
                    print(f"   polling_server {Colors.RED}NOT RUNNING{Colors.RESET}")
                
                # API Tests
                print(f"\n{Colors.BOLD}🌐 API RESPONSE TIMES (Polling Server :5001){Colors.RESET}")
                
                endpoints = [
                    '/api/status',
                    '/api/devices',
                    '/api/device/commands/pending',
                    '/api/device/sensor/pump_status',
                ]
                
                all_valid_times = []
                for endpoint in endpoints:
                    # Initialize history for this endpoint if needed
                    if endpoint not in self.api_times:
                        self.api_times[endpoint] = deque(maxlen=10)  # Last 10 samples
                    
                    result = self.test_api(endpoint)
                    
                    # Store result
                    if result['ok']:
                        self.api_times[endpoint].append(result['ms'])
                        all_valid_times.append(result['ms'])
                    
                    # Calculate average for this endpoint
                    endpoint_times = [t for t in self.api_times[endpoint] if t > 0]
                    
                    status = self.status_icon(result['ok'])
                    if result['ok']:
                        current_time = self.colorize(result['ms'], (100, 500), 'ms')
                        if len(endpoint_times) > 1:
                            avg = sum(endpoint_times) / len(endpoint_times)
                            time_str = f"{current_time} (avg: {avg:.0f}ms)"
                        else:
                            time_str = current_time
                    else:
                        error_msg = result.get('error', 'FAIL')
                        time_str = f"{Colors.RED}{error_msg}{Colors.RESET}"
                    
                    print(f"   {status} {endpoint:38s} {time_str}")
                
                # Overall API stats (10-second average)
                if all_valid_times:
                    avg_api = sum(all_valid_times) / len(all_valid_times)
                    min_api = min(all_valid_times)
                    max_api = max(all_valid_times)
                    
                    # Get all historical samples
                    all_history = []
                    for ep_times in self.api_times.values():
                        all_history.extend([t for t in ep_times if t > 0])
                    
                    if len(all_history) > 1:
                        hist_avg = sum(all_history) / len(all_history)
                        print(f"   {Colors.CYAN}10-sec Average: {hist_avg:.1f}ms | Current: Min {min_api:.0f}ms, Max {max_api:.0f}ms{Colors.RESET}")
                    else:
                        print(f"   {Colors.CYAN}Current: Avg {avg_api:.1f}ms | Min {min_api:.0f}ms | Max {max_api:.0f}ms{Colors.RESET}")
                else:
                    print(f"   {Colors.RED}All API tests failed - check if polling_server2.py is running{Colors.RESET}")
                
                # Network Status
                print(f"\n{Colors.BOLD}📡 NETWORK LATENCY{Colors.RESET}")
                import socket
                
                network_tests = [
                    ('google.com', 443, 'Internet (Google)'),
                    ('app.urbankettle.in', 443, 'API Server'),
                ]
                
                current_latencies = []
                for hostname, port, label in network_tests:
                    try:
                        start = time.perf_counter()
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(3)
                        sock.connect((hostname, port))
                        sock.close()
                        latency = (time.perf_counter() - start) * 1000
                        current_latencies.append(latency)
                        self.network_latency.append(latency)
                        
                        latency_str = self.colorize(latency, (100, 300), 'ms')
                        print(f"   {label:20s} {self.status_icon(True)} {latency_str}")
                    except Exception as e:
                        print(f"   {label:20s} {self.status_icon(False)} {Colors.RED}UNREACHABLE{Colors.RESET}")
                
                # Show network average
                if len(self.network_latency) > 1:
                    net_history = [l for l in self.network_latency if l > 0]
                    if net_history:
                        avg_latency = sum(net_history) / len(net_history)
                        min_latency = min(net_history)
                        max_latency = max(net_history)
                        print(f"   {Colors.CYAN}Network Avg (last {len(net_history)} tests): {avg_latency:.1f}ms | Range: {min_latency:.0f}-{max_latency:.0f}ms{Colors.RESET}")
                
                # Warnings
                warnings = []
                if cpu > 80:
                    warnings.append(f"High CPU usage ({cpu:.1f}%)")
                if mem.percent > 85:
                    warnings.append(f"High memory usage ({mem.percent:.1f}%)")
                if temp and temp > 75:
                    warnings.append(f"High temperature ({temp:.1f}°C)")
                # Check all endpoint histories for slow responses
                all_api_times = []
                for ep_times in self.api_times.values():
                    all_api_times.extend([t for t in ep_times if t > 0])
                if len(all_api_times) > 5:
                    avg_api_time = sum(all_api_times) / len(all_api_times)
                    if avg_api_time > 200:
                        warnings.append(f"Slow API responses (avg {avg_api_time:.0f}ms)")
                
                if warnings:
                    print(f"\n{Colors.BOLD}{Colors.YELLOW}⚠️  WARNINGS{Colors.RESET}")
                    for w in warnings:
                        print(f"   {Colors.YELLOW}• {w}{Colors.RESET}")
                
                print(f"\n{Colors.CYAN}─" * 64 + Colors.RESET)
                print(f"  Refresh: {REFRESH_RATE}s | Press Ctrl+C to exit")
                
                time.sleep(REFRESH_RATE)
                
            except KeyboardInterrupt:
                self.running = False
                self.clear_screen()
                print(f"\n{Colors.GREEN}Monitor stopped.{Colors.RESET}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Urban Kettle Live Performance Monitor')
    parser.add_argument('--compact', '-c', action='store_true', 
                        help='Run in compact single-line mode')
    parser.add_argument('--refresh', '-r', type=float, default=1.0,
                        help='Refresh rate in seconds (default: 1.0)')
    
    args = parser.parse_args()
    
    global REFRESH_RATE
    REFRESH_RATE = args.refresh
    
    monitor = LiveMonitor()
    
    try:
        if args.compact:
            monitor.run_compact()
        else:
            monitor.run_full()
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == '__main__':
    main()

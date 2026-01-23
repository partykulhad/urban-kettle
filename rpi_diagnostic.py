#!/usr/bin/env python3
"""
Raspberry Pi + Kivy UI Comprehensive Diagnostic Tool
=====================================================
Records ALL system metrics to find root cause of UI lag:
- CPU, Memory, Disk I/O, SD Card performance
- GPU memory, display driver, touch input latency
- Process scheduling, interrupts, context switches
- Network activity, file handles, kernel buffers
- Kivy frame timing, event loop delays
- Touch input events and response times

Run this WHILE using the kiosk app to capture lag events.

Usage:
    python rpi_diagnostic.py                    # Start recording
    python rpi_diagnostic.py --duration 300     # Record for 5 minutes
    python rpi_diagnostic.py --analyze          # Analyze saved data
"""

import os
import sys
import time
import json
import signal
import subprocess
import threading
import statistics
from datetime import datetime
from collections import deque, defaultdict
from pathlib import Path

try:
    import psutil
except ImportError:
    print("Installing psutil...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'psutil'])
    import psutil

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    'log_dir': 'diagnostics',
    'sample_interval': 0.5,  # Sample every 500ms
    'high_res_interval': 0.1,  # High-res sampling for critical metrics
    'lag_threshold_ms': 100,  # Consider >100ms as lag
    'record_duration': 300,  # Default 5 minutes
    'polling_server_port': 5001,
    'main_app_pattern': 'main_app.py',
}

# ============================================================================
# DATA COLLECTORS
# ============================================================================

class SystemCollector:
    """Collects system-level metrics"""
    
    @staticmethod
    def get_cpu_detailed():
        """Get detailed CPU metrics"""
        cpu_times = psutil.cpu_times_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        load = os.getloadavg()
        
        # Per-core usage
        per_cpu = psutil.cpu_percent(percpu=True)
        
        return {
            'percent': psutil.cpu_percent(),
            'per_core': per_cpu,
            'user': cpu_times.user,
            'system': cpu_times.system,
            'iowait': getattr(cpu_times, 'iowait', 0),
            'irq': getattr(cpu_times, 'irq', 0),
            'softirq': getattr(cpu_times, 'softirq', 0),
            'freq_current': cpu_freq.current if cpu_freq else 0,
            'freq_max': cpu_freq.max if cpu_freq else 0,
            'load_1m': load[0],
            'load_5m': load[1],
            'load_15m': load[2],
        }
    
    @staticmethod
    def get_memory_detailed():
        """Get detailed memory metrics"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            'percent': mem.percent,
            'total_mb': mem.total / (1024**2),
            'available_mb': mem.available / (1024**2),
            'used_mb': mem.used / (1024**2),
            'cached_mb': getattr(mem, 'cached', 0) / (1024**2),
            'buffers_mb': getattr(mem, 'buffers', 0) / (1024**2),
            'swap_percent': swap.percent,
            'swap_used_mb': swap.used / (1024**2),
        }
    
    @staticmethod
    def get_disk_io():
        """Get disk I/O metrics (critical for SD card lag)"""
        try:
            io = psutil.disk_io_counters()
            return {
                'read_bytes': io.read_bytes,
                'write_bytes': io.write_bytes,
                'read_count': io.read_count,
                'write_count': io.write_count,
                'read_time_ms': io.read_time,
                'write_time_ms': io.write_time,
                'busy_time_ms': getattr(io, 'busy_time', 0),
            }
        except:
            return {}
    
    @staticmethod
    def get_temperature():
        """Get RPi temperature"""
        try:
            # Method 1: thermal_zone
            temp_file = '/sys/class/thermal/thermal_zone0/temp'
            if os.path.exists(temp_file):
                with open(temp_file, 'r') as f:
                    return float(f.read().strip()) / 1000.0
        except:
            pass
        
        try:
            # Method 2: vcgencmd
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                    capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                # Parse "temp=45.0'C"
                temp_str = result.stdout.strip()
                return float(temp_str.split('=')[1].replace("'C", ""))
        except:
            pass
        
        return None
    
    @staticmethod
    def get_throttling():
        """Check if RPi is throttled (critical for lag)"""
        try:
            result = subprocess.run(['vcgencmd', 'get_throttled'], 
                                    capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                # Parse "throttled=0x0"
                hex_val = result.stdout.strip().split('=')[1]
                val = int(hex_val, 16)
                return {
                    'raw': hex_val,
                    'under_voltage_now': bool(val & 0x1),
                    'freq_capped_now': bool(val & 0x2),
                    'throttled_now': bool(val & 0x4),
                    'soft_temp_limit_now': bool(val & 0x8),
                    'under_voltage_occurred': bool(val & 0x10000),
                    'freq_capped_occurred': bool(val & 0x20000),
                    'throttled_occurred': bool(val & 0x40000),
                    'soft_temp_limit_occurred': bool(val & 0x80000),
                }
        except:
            pass
        return None
    
    @staticmethod
    def get_gpu_memory():
        """Get GPU memory allocation"""
        try:
            result = subprocess.run(['vcgencmd', 'get_mem', 'gpu'], 
                                    capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                # Parse "gpu=128M"
                return result.stdout.strip().split('=')[1]
        except:
            pass
        return None
    
    @staticmethod
    def get_interrupts():
        """Get interrupt counts (high can cause lag)"""
        try:
            with open('/proc/interrupts', 'r') as f:
                lines = f.readlines()
            
            total_irq = 0
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) > 1:
                    for p in parts[1:]:
                        if p.isdigit():
                            total_irq += int(p)
                        else:
                            break
            return total_irq
        except:
            return 0
    
    @staticmethod
    def get_context_switches():
        """Get context switch count"""
        try:
            with open('/proc/stat', 'r') as f:
                for line in f:
                    if line.startswith('ctxt '):
                        return int(line.split()[1])
        except:
            pass
        return 0


class DisplayCollector:
    """Collects display and GPU metrics"""
    
    @staticmethod
    def get_display_info():
        """Get display configuration"""
        info = {}
        
        try:
            # Check display resolution
            result = subprocess.run(['xdpyinfo'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'dimensions:' in line:
                        info['resolution'] = line.split(':')[1].strip().split()[0]
        except:
            pass
        
        try:
            # Check for KMS/DRM
            result = subprocess.run(['cat', '/proc/device-tree/soc/gpu/status'], 
                                    capture_output=True, text=True, timeout=1)
            info['gpu_status'] = result.stdout.strip() if result.returncode == 0 else 'unknown'
        except:
            pass
        
        try:
            # Get framebuffer info
            if os.path.exists('/dev/fb0'):
                result = subprocess.run(['fbset', '-s'], capture_output=True, text=True, timeout=1)
                if result.returncode == 0:
                    info['framebuffer'] = result.stdout.strip()[:200]
        except:
            pass
        
        return info
    
    @staticmethod
    def get_vsync_info():
        """Get VSync/display timing info"""
        try:
            # Check display refresh
            result = subprocess.run(['vcgencmd', 'measure_clock', 'pixel'], 
                                    capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None


class TouchInputCollector:
    """Collects touch input metrics"""
    
    def __init__(self):
        self.touch_device = self._find_touch_device()
        self.last_touch_time = 0
        self.touch_events = deque(maxlen=100)
    
    def _find_touch_device(self):
        """Find the touch input device"""
        try:
            result = subprocess.run(['cat', '/proc/bus/input/devices'], 
                                    capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                content = result.stdout
                # Look for touch device
                if 'waveshare' in content.lower() or 'touch' in content.lower():
                    for line in content.split('\n'):
                        if 'Handlers=' in line and 'event' in line:
                            # Extract event number
                            for part in line.split():
                                if part.startswith('event'):
                                    return f'/dev/input/{part}'
        except:
            pass
        
        # Default paths to try
        for path in ['/dev/input/event0', '/dev/input/event1', '/dev/input/touchscreen']:
            if os.path.exists(path):
                return path
        return None
    
    def get_input_devices(self):
        """List all input devices"""
        devices = []
        try:
            result = subprocess.run(['cat', '/proc/bus/input/devices'], 
                                    capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                current_device = {}
                for line in result.stdout.split('\n'):
                    if line.startswith('N: Name='):
                        current_device['name'] = line.split('=')[1].strip('"')
                    elif line.startswith('H: Handlers='):
                        current_device['handlers'] = line.split('=')[1]
                        devices.append(current_device)
                        current_device = {}
        except:
            pass
        return devices
    
    def get_touch_stats(self):
        """Get touch input statistics"""
        return {
            'device': self.touch_device,
            'recent_events': len(self.touch_events),
            'avg_latency_ms': statistics.mean(self.touch_events) if self.touch_events else 0,
        }


class ProcessCollector:
    """Collects process-level metrics"""
    
    def __init__(self, app_pattern='main_app.py'):
        self.app_pattern = app_pattern
        self.app_process = None
    
    def find_app_process(self):
        """Find the main app process"""
        for proc in psutil.process_iter(['pid', 'cmdline', 'name']):
            try:
                cmdline = ' '.join(proc.info.get('cmdline', []))
                if self.app_pattern in cmdline:
                    self.app_process = proc
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def get_app_metrics(self):
        """Get detailed metrics for the app process"""
        if not self.app_process:
            self.find_app_process()
        
        if not self.app_process:
            return {'running': False}
        
        try:
            proc = self.app_process
            
            # Memory details
            mem_info = proc.memory_info()
            mem_maps = None
            try:
                mem_maps = proc.memory_maps(grouped=True)
            except:
                pass
            
            # I/O counters
            io = None
            try:
                io = proc.io_counters()
            except:
                pass
            
            # Context switches
            ctx = None
            try:
                ctx = proc.num_ctx_switches()
            except:
                pass
            
            # Open files
            open_files = 0
            try:
                open_files = len(proc.open_files())
            except:
                pass
            
            # Threads
            threads = []
            try:
                for t in proc.threads():
                    threads.append({
                        'id': t.id,
                        'user_time': t.user_time,
                        'system_time': t.system_time,
                    })
            except:
                pass
            
            return {
                'running': True,
                'pid': proc.pid,
                'cpu_percent': proc.cpu_percent(),
                'memory_rss_mb': mem_info.rss / (1024**2),
                'memory_vms_mb': mem_info.vms / (1024**2),
                'memory_percent': proc.memory_percent(),
                'num_threads': proc.num_threads(),
                'num_fds': proc.num_fds() if hasattr(proc, 'num_fds') else 0,
                'open_files': open_files,
                'io_read_bytes': io.read_bytes if io else 0,
                'io_write_bytes': io.write_bytes if io else 0,
                'ctx_voluntary': ctx.voluntary if ctx else 0,
                'ctx_involuntary': ctx.involuntary if ctx else 0,
                'threads': threads[:10],  # Top 10 threads
            }
        except psutil.NoSuchProcess:
            self.app_process = None
            return {'running': False, 'error': 'Process died'}
        except Exception as e:
            return {'running': False, 'error': str(e)}
    
    def get_top_processes(self, n=10):
        """Get top N processes by CPU/memory"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'][:20],
                    'cpu': proc.info['cpu_percent'],
                    'mem': proc.info['memory_percent'],
                })
            except:
                continue
        
        # Sort by CPU
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        return processes[:n]


class NetworkCollector:
    """Collects network metrics"""
    
    @staticmethod
    def get_network_io():
        """Get network I/O counters"""
        try:
            net = psutil.net_io_counters()
            return {
                'bytes_sent': net.bytes_sent,
                'bytes_recv': net.bytes_recv,
                'packets_sent': net.packets_sent,
                'packets_recv': net.packets_recv,
                'errin': net.errin,
                'errout': net.errout,
                'dropin': net.dropin,
                'dropout': net.dropout,
            }
        except:
            return {}
    
    @staticmethod
    def get_connections():
        """Get active network connections"""
        try:
            conns = psutil.net_connections(kind='inet')
            return {
                'total': len(conns),
                'established': len([c for c in conns if c.status == 'ESTABLISHED']),
                'listen': len([c for c in conns if c.status == 'LISTEN']),
                'time_wait': len([c for c in conns if c.status == 'TIME_WAIT']),
            }
        except:
            return {}


class SDCardCollector:
    """Collects SD card specific metrics"""
    
    @staticmethod
    def get_sd_health():
        """Get SD card health indicators"""
        info = {}
        
        try:
            # Check mount options
            result = subprocess.run(['mount'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if '/dev/mmcblk0' in line or '/dev/root' in line:
                        info['mount_info'] = line[:200]
                        break
        except:
            pass
        
        try:
            # Check for pending writes
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'Dirty:' in line:
                        info['dirty_pages_kb'] = int(line.split()[1])
                    elif 'Writeback:' in line:
                        info['writeback_kb'] = int(line.split()[1])
        except:
            pass
        
        return info
    
    @staticmethod
    def benchmark_io(test_size_kb=1024):
        """Quick I/O benchmark"""
        test_file = '/tmp/io_test_diagnostic'
        results = {}
        
        try:
            # Write test
            data = b'x' * (test_size_kb * 1024)
            start = time.perf_counter()
            with open(test_file, 'wb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            write_time = time.perf_counter() - start
            results['write_speed_mbps'] = (test_size_kb / 1024) / write_time
            
            # Read test
            start = time.perf_counter()
            with open(test_file, 'rb') as f:
                _ = f.read()
            read_time = time.perf_counter() - start
            results['read_speed_mbps'] = (test_size_kb / 1024) / read_time
            
            # Cleanup
            os.remove(test_file)
        except Exception as e:
            results['error'] = str(e)
        
        return results


class KernelCollector:
    """Collects kernel-level metrics"""
    
    @staticmethod
    def get_kernel_info():
        """Get kernel version and config"""
        info = {}
        
        try:
            info['version'] = os.uname().release
            info['machine'] = os.uname().machine
        except:
            pass
        
        try:
            # Scheduler info
            with open('/proc/sys/kernel/sched_latency_ns', 'r') as f:
                info['sched_latency_ns'] = int(f.read().strip())
        except:
            pass
        
        try:
            # Check for preempt
            with open('/proc/sys/kernel/sched_min_granularity_ns', 'r') as f:
                info['sched_min_granularity_ns'] = int(f.read().strip())
        except:
            pass
        
        return info
    
    @staticmethod
    def get_vmstat():
        """Get virtual memory statistics"""
        stats = {}
        try:
            with open('/proc/vmstat', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 2:
                        key = parts[0]
                        if key in ['pgfault', 'pgmajfault', 'pswpin', 'pswpout', 
                                   'pgpgin', 'pgpgout', 'allocstall_dma', 'allocstall_normal']:
                            stats[key] = int(parts[1])
        except:
            pass
        return stats


# ============================================================================
# MAIN DIAGNOSTIC RECORDER
# ============================================================================

class DiagnosticRecorder:
    """Main class that records all diagnostics"""
    
    def __init__(self):
        self.running = False
        self.data = []
        self.lag_events = []
        self.start_time = None
        
        # Collectors
        self.system = SystemCollector()
        self.display = DisplayCollector()
        self.touch = TouchInputCollector()
        self.process = ProcessCollector(CONFIG['main_app_pattern'])
        self.network = NetworkCollector()
        self.sdcard = SDCardCollector()
        self.kernel = KernelCollector()
        
        # Delta tracking for rates
        self.last_disk_io = None
        self.last_net_io = None
        self.last_interrupts = 0
        self.last_ctx_switches = 0
        self.last_sample_time = None
        
        # Create log directory
        self.log_dir = Path(CONFIG['log_dir'])
        self.log_dir.mkdir(exist_ok=True)
    
    def collect_sample(self):
        """Collect a single sample of all metrics"""
        now = time.time()
        sample = {
            'timestamp': now,
            'datetime': datetime.now().isoformat(),
        }
        
        # System metrics
        sample['cpu'] = self.system.get_cpu_detailed()
        sample['memory'] = self.system.get_memory_detailed()
        sample['temperature'] = self.system.get_temperature()
        sample['throttling'] = self.system.get_throttling()
        
        # Disk I/O (calculate rates)
        disk_io = self.system.get_disk_io()
        if disk_io and self.last_disk_io and self.last_sample_time:
            dt = now - self.last_sample_time
            if dt > 0:
                sample['disk_io'] = {
                    'read_mbps': (disk_io['read_bytes'] - self.last_disk_io['read_bytes']) / (1024**2) / dt,
                    'write_mbps': (disk_io['write_bytes'] - self.last_disk_io['write_bytes']) / (1024**2) / dt,
                    'read_iops': (disk_io['read_count'] - self.last_disk_io['read_count']) / dt,
                    'write_iops': (disk_io['write_count'] - self.last_disk_io['write_count']) / dt,
                    'io_wait_ms': disk_io.get('busy_time_ms', 0) - self.last_disk_io.get('busy_time_ms', 0),
                }
        self.last_disk_io = disk_io
        
        # Network I/O (calculate rates)
        net_io = self.network.get_network_io()
        if net_io and self.last_net_io and self.last_sample_time:
            dt = now - self.last_sample_time
            if dt > 0:
                sample['network'] = {
                    'recv_kbps': (net_io['bytes_recv'] - self.last_net_io['bytes_recv']) / 1024 / dt,
                    'sent_kbps': (net_io['bytes_sent'] - self.last_net_io['bytes_sent']) / 1024 / dt,
                    'errors': net_io['errin'] + net_io['errout'],
                    'drops': net_io['dropin'] + net_io['dropout'],
                }
        self.last_net_io = net_io
        sample['connections'] = self.network.get_connections()
        
        # Interrupts and context switches (rates)
        interrupts = self.system.get_interrupts()
        ctx_switches = self.system.get_context_switches()
        if self.last_sample_time:
            dt = now - self.last_sample_time
            if dt > 0:
                sample['interrupts_per_sec'] = (interrupts - self.last_interrupts) / dt
                sample['ctx_switches_per_sec'] = (ctx_switches - self.last_ctx_switches) / dt
        self.last_interrupts = interrupts
        self.last_ctx_switches = ctx_switches
        
        # Process metrics
        sample['app'] = self.process.get_app_metrics()
        sample['top_processes'] = self.process.get_top_processes(5)
        
        # SD card metrics
        sample['sd_card'] = self.sdcard.get_sd_health()
        
        # VMstat
        sample['vmstat'] = self.kernel.get_vmstat()
        
        self.last_sample_time = now
        
        # Detect potential lag indicators
        self.detect_lag_indicators(sample)
        
        return sample
    
    def detect_lag_indicators(self, sample):
        """Detect conditions that might cause UI lag"""
        indicators = []
        
        # High CPU iowait (waiting for disk)
        if sample['cpu'].get('iowait', 0) > 20:
            indicators.append(f"High I/O wait: {sample['cpu']['iowait']:.1f}%")
        
        # CPU throttling
        if sample.get('throttling') and sample['throttling'].get('throttled_now'):
            indicators.append("CPU is THROTTLED")
        
        # High temperature
        if sample.get('temperature') and sample['temperature'] > 75:
            indicators.append(f"High temperature: {sample['temperature']:.1f}°C")
        
        # Low memory
        if sample['memory']['percent'] > 85:
            indicators.append(f"Low memory: {sample['memory']['percent']:.1f}% used")
        
        # Swap usage (very bad for performance)
        if sample['memory']['swap_percent'] > 10:
            indicators.append(f"Swap in use: {sample['memory']['swap_percent']:.1f}%")
        
        # High disk write (SD card bottleneck)
        if 'disk_io' in sample and sample['disk_io'].get('write_mbps', 0) > 5:
            indicators.append(f"High disk write: {sample['disk_io']['write_mbps']:.1f} MB/s")
        
        # Page faults
        if 'vmstat' in sample:
            if sample['vmstat'].get('pgmajfault', 0) > 0:
                indicators.append("Major page faults occurring")
        
        # App using high CPU
        if sample['app'].get('running') and sample['app'].get('cpu_percent', 0) > 80:
            indicators.append(f"App high CPU: {sample['app']['cpu_percent']:.1f}%")
        
        # High context switching
        if sample.get('ctx_switches_per_sec', 0) > 50000:
            indicators.append(f"High context switches: {sample['ctx_switches_per_sec']:.0f}/s")
        
        if indicators:
            self.lag_events.append({
                'timestamp': sample['timestamp'],
                'datetime': sample['datetime'],
                'indicators': indicators,
            })
    
    def get_static_info(self):
        """Collect static system information once"""
        info = {
            'hostname': os.uname().nodename,
            'kernel': self.kernel.get_kernel_info(),
            'display': self.display.get_display_info(),
            'gpu_memory': self.system.get_gpu_memory(),
            'input_devices': self.touch.get_input_devices(),
            'cpu_count': psutil.cpu_count(),
            'total_memory_mb': psutil.virtual_memory().total / (1024**2),
        }
        
        # Python and package versions
        info['python_version'] = sys.version.split()[0]
        
        try:
            import kivy
            info['kivy_version'] = kivy.__version__
        except:
            info['kivy_version'] = 'not found'
        
        return info
    
    def start_recording(self, duration=None):
        """Start recording diagnostics"""
        self.running = True
        self.start_time = time.time()
        self.data = []
        self.lag_events = []
        
        duration = duration or CONFIG['record_duration']
        
        print(f"\n{'='*60}")
        print("  RASPBERRY PI DIAGNOSTIC RECORDER")
        print(f"{'='*60}")
        print(f"  Recording for {duration} seconds...")
        print(f"  Sample interval: {CONFIG['sample_interval']}s")
        print(f"  Press Ctrl+C to stop early")
        print(f"{'='*60}\n")
        
        # Collect static info
        static_info = self.get_static_info()
        print("📋 System Info:")
        print(f"   Kernel: {static_info['kernel'].get('version', 'unknown')}")
        print(f"   CPU cores: {static_info['cpu_count']}")
        print(f"   Memory: {static_info['total_memory_mb']:.0f} MB")
        print(f"   GPU Memory: {static_info['gpu_memory']}")
        print(f"   Kivy: {static_info['kivy_version']}")
        
        # Run initial SD card benchmark
        print("\n⚡ SD Card Benchmark:")
        sd_bench = self.sdcard.benchmark_io(512)  # 512KB test
        if 'write_speed_mbps' in sd_bench:
            print(f"   Write: {sd_bench['write_speed_mbps']:.1f} MB/s")
            print(f"   Read:  {sd_bench['read_speed_mbps']:.1f} MB/s")
        
        print("\n📊 Recording metrics...")
        print("-" * 40)
        
        sample_count = 0
        end_time = self.start_time + duration
        
        def handle_interrupt(sig, frame):
            self.running = False
            print("\n\n⏹️  Recording stopped by user")
        
        signal.signal(signal.SIGINT, handle_interrupt)
        
        try:
            while self.running and time.time() < end_time:
                sample = self.collect_sample()
                self.data.append(sample)
                sample_count += 1
                
                # Progress display
                elapsed = time.time() - self.start_time
                remaining = duration - elapsed
                
                # Show current status
                cpu = sample['cpu']['percent']
                mem = sample['memory']['percent']
                temp = sample.get('temperature', 0) or 0
                app_cpu = sample['app'].get('cpu_percent', 0) if sample['app'].get('running') else 0
                
                throttle = ""
                if sample.get('throttling', {}).get('throttled_now'):
                    throttle = " ⚠️ THROTTLED"
                
                sys.stdout.write(f"\r  [{elapsed:5.1f}s] CPU:{cpu:5.1f}% | Mem:{mem:5.1f}% | "
                               f"Temp:{temp:4.1f}°C | App:{app_cpu:5.1f}%{throttle}   ")
                sys.stdout.flush()
                
                time.sleep(CONFIG['sample_interval'])
        
        except Exception as e:
            print(f"\n\nError during recording: {e}")
        
        finally:
            self.running = False
        
        # Save data
        self.save_data(static_info)
        
        # Generate and print analysis
        print("\n")
        self.analyze_and_print()
    
    def save_data(self, static_info):
        """Save recorded data to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save full data as JSON
        data_file = self.log_dir / f'diagnostic_{timestamp}.json'
        full_data = {
            'static_info': static_info,
            'samples': self.data,
            'lag_events': self.lag_events,
            'recording_duration': time.time() - self.start_time,
            'sample_count': len(self.data),
        }
        
        with open(data_file, 'w') as f:
            json.dump(full_data, f, indent=2, default=str)
        
        print(f"\n💾 Data saved to: {data_file}")
        
        # Save CSV for easy analysis
        csv_file = self.log_dir / f'diagnostic_{timestamp}.csv'
        with open(csv_file, 'w') as f:
            # Header
            f.write("timestamp,cpu_percent,cpu_iowait,memory_percent,swap_percent,")
            f.write("temperature,throttled,disk_write_mbps,disk_read_mbps,")
            f.write("app_cpu,app_mem_mb,ctx_switches,interrupts\n")
            
            # Data
            for s in self.data:
                f.write(f"{s.get('datetime', '')},")
                f.write(f"{s['cpu'].get('percent', 0):.1f},")
                f.write(f"{s['cpu'].get('iowait', 0):.1f},")
                f.write(f"{s['memory'].get('percent', 0):.1f},")
                f.write(f"{s['memory'].get('swap_percent', 0):.1f},")
                f.write(f"{s.get('temperature', 0) or 0:.1f},")
                f.write(f"{1 if s.get('throttling', {}).get('throttled_now') else 0},")
                f.write(f"{s.get('disk_io', {}).get('write_mbps', 0):.2f},")
                f.write(f"{s.get('disk_io', {}).get('read_mbps', 0):.2f},")
                f.write(f"{s.get('app', {}).get('cpu_percent', 0):.1f},")
                f.write(f"{s.get('app', {}).get('memory_rss_mb', 0):.1f},")
                f.write(f"{s.get('ctx_switches_per_sec', 0):.0f},")
                f.write(f"{s.get('interrupts_per_sec', 0):.0f}\n")
        
        print(f"📈 CSV saved to: {csv_file}")
    
    def analyze_and_print(self):
        """Analyze recorded data and print findings"""
        if not self.data:
            print("No data to analyze")
            return
        
        print(f"\n{'='*60}")
        print("  ANALYSIS RESULTS")
        print(f"{'='*60}")
        print(f"  Samples collected: {len(self.data)}")
        print(f"  Duration: {(self.data[-1]['timestamp'] - self.data[0]['timestamp']):.1f}s")
        
        # CPU Analysis
        print(f"\n📊 CPU ANALYSIS")
        print("-" * 40)
        cpu_values = [s['cpu']['percent'] for s in self.data]
        iowait_values = [s['cpu'].get('iowait', 0) for s in self.data]
        
        print(f"  Average: {statistics.mean(cpu_values):.1f}%")
        print(f"  Max:     {max(cpu_values):.1f}%")
        print(f"  Min:     {min(cpu_values):.1f}%")
        print(f"  I/O Wait Avg: {statistics.mean(iowait_values):.1f}%")
        print(f"  I/O Wait Max: {max(iowait_values):.1f}%")
        
        high_cpu = len([v for v in cpu_values if v > 80])
        if high_cpu > 0:
            print(f"  ⚠️  High CPU (>80%): {high_cpu} samples ({100*high_cpu/len(cpu_values):.1f}%)")
        
        high_iowait = len([v for v in iowait_values if v > 20])
        if high_iowait > 0:
            print(f"  ⚠️  High I/O Wait (>20%): {high_iowait} samples - SD CARD BOTTLENECK!")
        
        # Memory Analysis
        print(f"\n💾 MEMORY ANALYSIS")
        print("-" * 40)
        mem_values = [s['memory']['percent'] for s in self.data]
        swap_values = [s['memory']['swap_percent'] for s in self.data]
        
        print(f"  Average: {statistics.mean(mem_values):.1f}%")
        print(f"  Max:     {max(mem_values):.1f}%")
        
        if max(swap_values) > 0:
            print(f"  ⚠️  Swap Used! Max: {max(swap_values):.1f}% - MAJOR LAG SOURCE")
        
        # App memory trend
        if self.data[0]['app'].get('running'):
            app_mem_start = self.data[0]['app'].get('memory_rss_mb', 0)
            app_mem_end = self.data[-1]['app'].get('memory_rss_mb', 0)
            mem_change = app_mem_end - app_mem_start
            print(f"  App Memory: {app_mem_start:.1f}MB → {app_mem_end:.1f}MB ({mem_change:+.1f}MB)")
            if mem_change > 50:
                print(f"  ⚠️  Memory leak detected! Growing {mem_change:.1f}MB")
        
        # Temperature & Throttling
        print(f"\n🌡️  TEMPERATURE & THROTTLING")
        print("-" * 40)
        temps = [s.get('temperature', 0) or 0 for s in self.data]
        print(f"  Average: {statistics.mean(temps):.1f}°C")
        print(f"  Max:     {max(temps):.1f}°C")
        
        throttled_samples = len([s for s in self.data if s.get('throttling', {}).get('throttled_now')])
        if throttled_samples > 0:
            print(f"  ⚠️  CPU THROTTLED in {throttled_samples} samples ({100*throttled_samples/len(self.data):.1f}%)")
            print(f"      This causes MAJOR UI lag! Add cooling or reduce load.")
        
        undervolt = len([s for s in self.data if s.get('throttling', {}).get('under_voltage_now')])
        if undervolt > 0:
            print(f"  ⚠️  UNDER-VOLTAGE detected! Use a better power supply!")
        
        # Disk I/O
        print(f"\n💿 DISK I/O (SD CARD)")
        print("-" * 40)
        write_values = [s.get('disk_io', {}).get('write_mbps', 0) for s in self.data if 'disk_io' in s]
        if write_values:
            print(f"  Write Avg: {statistics.mean(write_values):.2f} MB/s")
            print(f"  Write Max: {max(write_values):.2f} MB/s")
            
            high_write = len([v for v in write_values if v > 5])
            if high_write > 0:
                print(f"  ⚠️  High write activity in {high_write} samples - check logging!")
        
        # Context Switches
        print(f"\n🔄 CONTEXT SWITCHES")
        print("-" * 40)
        ctx_values = [s.get('ctx_switches_per_sec', 0) for s in self.data if s.get('ctx_switches_per_sec')]
        if ctx_values:
            print(f"  Average: {statistics.mean(ctx_values):.0f}/sec")
            print(f"  Max:     {max(ctx_values):.0f}/sec")
            if max(ctx_values) > 50000:
                print(f"  ⚠️  Very high context switching - check thread count")
        
        # Lag Events Summary
        print(f"\n⚡ LAG EVENTS DETECTED")
        print("-" * 40)
        if self.lag_events:
            print(f"  Total events: {len(self.lag_events)}")
            
            # Count by type
            indicator_counts = defaultdict(int)
            for event in self.lag_events:
                for ind in event['indicators']:
                    # Extract type
                    ind_type = ind.split(':')[0] if ':' in ind else ind.split()[0]
                    indicator_counts[ind_type] += 1
            
            print(f"\n  By type:")
            for ind_type, count in sorted(indicator_counts.items(), key=lambda x: -x[1]):
                print(f"    {count:4d}x {ind_type}")
        else:
            print(f"  ✅ No obvious lag indicators detected")
        
        # Root Cause Summary
        print(f"\n{'='*60}")
        print("  🔍 LIKELY ROOT CAUSES OF LAG")
        print(f"{'='*60}")
        
        causes = []
        
        # Priority order of causes
        if throttled_samples > 0:
            causes.append(("HIGH", "CPU Throttling", "Add heatsink/fan, check power supply"))
        
        if undervolt > 0:
            causes.append(("HIGH", "Under-voltage", "Use official 5V 3A power supply"))
        
        if max(swap_values) > 5:
            causes.append(("HIGH", "Swap Usage", "Reduce memory usage, add swap to USB"))
        
        if high_iowait > len(self.data) * 0.1:
            causes.append(("HIGH", "SD Card Bottleneck", "Use faster SD card, reduce logging"))
        
        if max(iowait_values) > 30:
            causes.append(("MEDIUM", "High I/O Wait Spikes", "Check what's writing to SD"))
        
        if mem_change > 50 if 'mem_change' in dir() else False:
            causes.append(("MEDIUM", "Memory Leak", "Check for unreleased objects in app"))
        
        if max(cpu_values) > 95:
            causes.append(("MEDIUM", "CPU Saturation", "Optimize heavy operations"))
        
        if max(temps) > 80:
            causes.append(("MEDIUM", "High Temperature", "Improve cooling"))
        
        if not causes:
            print("  ✅ No obvious performance issues found in this recording.")
            print("  The lag might be caused by:")
            print("    - Kivy rendering issues (check GPU driver)")
            print("    - Touch input driver latency")
            print("    - Specific operations not captured in this test")
        else:
            for priority, cause, fix in causes:
                icon = "🔴" if priority == "HIGH" else "🟡"
                print(f"\n  {icon} [{priority}] {cause}")
                print(f"     Fix: {fix}")
        
        print(f"\n{'='*60}")


def analyze_existing_file(filepath):
    """Analyze an existing diagnostic JSON file"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    recorder = DiagnosticRecorder()
    recorder.data = data['samples']
    recorder.lag_events = data.get('lag_events', [])
    recorder.start_time = recorder.data[0]['timestamp'] if recorder.data else 0
    
    print(f"\n📂 Analyzing: {filepath}")
    recorder.analyze_and_print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Raspberry Pi Diagnostic Tool for UI Lag Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rpi_diagnostic.py                   # Record for 5 minutes
  python rpi_diagnostic.py --duration 60     # Record for 1 minute
  python rpi_diagnostic.py --analyze FILE    # Analyze saved JSON file
        """
    )
    
    parser.add_argument('--duration', '-d', type=int, default=300,
                        help='Recording duration in seconds (default: 300)')
    parser.add_argument('--analyze', '-a', type=str, metavar='FILE',
                        help='Analyze an existing diagnostic file')
    parser.add_argument('--interval', '-i', type=float, default=0.5,
                        help='Sample interval in seconds (default: 0.5)')
    
    args = parser.parse_args()
    
    if args.analyze:
        analyze_existing_file(args.analyze)
    else:
        CONFIG['sample_interval'] = args.interval
        recorder = DiagnosticRecorder()
        recorder.start_recording(args.duration)


if __name__ == '__main__':
    main()

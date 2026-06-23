"""Pi system health snapshot (CPU/memory/disk) for remote monitoring.

Piggybacks on the existing 60s Kulhad heartbeat (get_machine_data) rather
than adding a new polling cycle — see main_app.py's _refresh_machine_config_cache.
"""

try:
    import psutil
except ImportError:
    psutil = None


def get_system_health():
    """Returns {cpu_percent, mem_percent, disk_percent}, or {} if psutil is
    unavailable or any reading fails — never raises, since this rides along
    with a config fetch that must not be blocked by a monitoring side-feature.
    """
    if psutil is None:
        return {}
    try:
        import subprocess
        # Ping 8.8.8.8 (Google DNS) once with a 1-second timeout
        # Expected output includes something like 'time=14.2 ms'
        ping_out = subprocess.check_output(
            ["ping", "-c", "1", "-W", "1", "8.8.8.8"],
            stderr=subprocess.STDOUT,
            text=True
        )
        latency_ms = None
        for line in ping_out.split('\n'):
            if 'time=' in line:
                # '64 bytes from 8.8.8.8: icmp_seq=1 ttl=116 time=14.2 ms'
                time_str = line.split('time=')[1].split(' ')[0]
                latency_ms = float(time_str)
                break
    except Exception:
        latency_ms = None

    try:
        health_data = {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
            "mem_percent": round(psutil.virtual_memory().percent, 1),
            "disk_percent": round(psutil.disk_usage('/').percent, 1),
        }
        if latency_ms is not None:
            health_data["latency_ms"] = latency_ms
        return health_data
    except Exception as e:
        print(f"⚠️ [SystemHealth] Could not read system health: {e}")
        return {}

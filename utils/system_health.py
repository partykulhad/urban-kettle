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
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
            "mem_percent": round(psutil.virtual_memory().percent, 1),
            "disk_percent": round(psutil.disk_usage('/').percent, 1),
        }
    except Exception as e:
        print(f"⚠️ [SystemHealth] Could not read system health: {e}")
        return {}

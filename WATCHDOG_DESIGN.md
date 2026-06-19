# Watchdog / Reliability Design (not currently enabled)

This documents a watchdog design that was built and then deliberately removed
from the live app (2026-06-19) so it doesn't ship before it's wanted. Kept here
so it can be re-added later without re-deriving the approach.

## Problem

"Watchdog" usually means a hardware timer that reboots the Pi if it isn't
fed periodically. That alone only catches a fully locked-up kernel — it does
**not** catch a Kivy/payment freeze, because in that failure mode the Python
*process* is still alive and the OS is still scheduling it fine; only the
app's own event loop is stuck. A bare `kill -0` / "is the process running"
check also can't tell the difference, for the same reason.

## Design that was implemented

**1. App-side heartbeat, tied to the Kivy event loop itself**

In `ChaiOrderingApp.build()`:

```python
self._watchdog_heartbeat_event = Clock.schedule_interval(self._write_watchdog_heartbeat, 15)
self._write_watchdog_heartbeat(0)

def _write_watchdog_heartbeat(self, dt):
    try:
        with open("/tmp/urban_kettle_heartbeat", "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        print(f"⚠️ [Watchdog] Could not write heartbeat file: {e}")
```

Because this runs as a `Clock.schedule_interval` callback, it only keeps
firing while Kivy's main loop is actually pumping events. A real UI/payment
freeze (stuck callback, blocked main-thread network call, deadlock) stops
this file from updating — even though the process is still running and
`systemctl status` / `kill -0` would report it as healthy.

**2. Hardware watchdog configured to watch that file (`setup_watchdog.sh`, one-time per machine)**

- `sudo apt install watchdog`
- `dtparam=watchdog=on` in `/boot/firmware/config.txt` (or `/boot/config.txt`
  on older Pi OS) — enables the BCM hardware watchdog chip.
- `/etc/watchdog.conf`:
  ```
  watchdog-device = /dev/watchdog
  watchdog-timeout = 15
  realtime = yes
  priority = 1
  file = /tmp/urban_kettle_heartbeat
  change = 60
  ```
  The `file`/`change` directives are a *built-in* feature of the `watchdog`
  daemon — it watches the file's content checksum and reboots if it hasn't
  changed in `change` seconds. No custom polling/glue code needed on top.
- A full **reboot** (not `systemctl restart`) on timeout, because a wedged
  Kivy/X11 session often doesn't recover from a service restart alone.

**3. Why not use systemd's native `WatchdogSec=` + `sd_notify`?**

Considered and rejected for this app's process topology: `urban-kettle.service`
is `Type=simple` with `launch_pi.sh` as MAINPID, which then backgrounds
`polling_server2.py` and `main_app.py` as child processes. systemd's watchdog
notify protocol expects `WATCHDOG=1` pings from the unit's main process (or
needs `NotifyAccess=all` to accept them from children), and even then a ping
from `main_app.py` only proves the *process* called `sd_notify`, not that
Kivy's event loop specifically is unstuck, unless the call site is itself
gated by a `Clock.schedule_interval` exactly like the file-heartbeat above —
at which point the systemd-notify path adds protocol complexity for no extra
benefit over a plain file mtime check. The file-based approach was simpler
and reused the `watchdog` package's existing feature instead of new code.

## Bundled SD-card-wear fixes (kept — unrelated to the watchdog itself)

These shipped in the same change and were **not** reverted:

- `launch_pi.sh`: `backend.log`/`frontend.log` moved from the repo directory
  (SD card) to `/tmp`.
- `update.sh`: `update.log` capped to the last 1000 lines instead of growing
  forever (it appends a few lines every 5 minutes, indefinitely).

If `setup_watchdog.sh` is reinstated, it should also re-add the tmpfs
`/etc/fstab` entries for `/tmp` and `/var/log`, and the daily 1 AM reboot
cron line (`0 1 * * * /sbin/reboot`, installed into root's crontab) — both
were part of that script and were removed along with it.

## Re-enabling later

1. Restore `_write_watchdog_heartbeat` + the `Clock.schedule_interval` call
   in `main_app.py` (`ChaiOrderingApp.build()`).
2. Restore `setup_watchdog.sh` (see git history around the commit that added
   it, or rebuild from this doc).
3. Push the `main_app.py` change — it auto-deploys via the 5-minute cron pull.
4. SSH into each machine and run `./setup_watchdog.sh` once, then `sudo reboot`
   to apply `dtparam=watchdog=on` and the tmpfs mounts. This step does **not**
   happen automatically — the auto-update pipeline only pulls repo files and
   restarts the app service, it never touches `/boot`, `/etc/fstab`, or cron.

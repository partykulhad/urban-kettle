"""
brightness_manager.py — Screen Brightness Controller for Urban Kettle Kiosk
=============================================================================

Manages three brightness levels for the RPi touchscreen:
  • ACTIVE  (80%)  — normal working brightness
  • DIM     (50%)  — after INACTIVITY_TIMEOUT_MINUTES of no touch
  • NIGHT   (0%)   — outside operating hours (start/end time from Kulhad)

On any touch event → always restores to ACTIVE (80%).

Works by writing to the RPi official DSI display brightness file:
  /sys/class/backlight/10-0045/brightness  (RPi official 7" touchscreen)
  or falls back to:
  /sys/class/backlight/rpi_backlight/brightness  (older kernel path)

The manager is a singleton — import and use `brightness_manager` anywhere.

Usage (inside main_app.py build(), after existing setup):
    from utils.brightness_manager import brightness_manager
    brightness_manager.start(app=self)

Usage (on every touch/tap — add to Window.bind or on_touch_down):
    brightness_manager.on_user_activity()

Usage (update operating hours from Kulhad config):
    brightness_manager.set_operating_hours("07:00", "22:00")
"""

import os
import time
import threading
import datetime
import logging

from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.clock import mainthread

logger = logging.getLogger(__name__)

# ─── Brightness constants (0-255 scale for RPi backlight) ──────────────────
_MAX_BRIGHTNESS   = 255
BRIGHTNESS_ACTIVE = int(_MAX_BRIGHTNESS * 0.80)   # 80%  → 204
BRIGHTNESS_DIM    = int(_MAX_BRIGHTNESS * 0.50)   # 50%  → 127
BRIGHTNESS_NIGHT  = 0                              # 0%   →   0

INACTIVITY_TIMEOUT_MINUTES = 5
INACTIVITY_TIMEOUT_SECONDS = INACTIVITY_TIMEOUT_MINUTES * 60

# ─── Poll interval for the background checker ──────────────────────────────
_POLL_INTERVAL_SECONDS = 30   # Check every 30 seconds is enough

# ─── RPi backlight sysfs paths (tried in order) ────────────────────────────
_BACKLIGHT_PATHS = [
    "/sys/class/backlight/10-0045/brightness",         # RPi OS Bookworm (new)
    "/sys/class/backlight/rpi_backlight/brightness",   # Older RPi OS / Buster
    "/sys/class/backlight/backlight/brightness",       # Generic fallback
]


def _find_backlight_path() -> str | None:
    """Return the first writable backlight path, or None if not on RPi."""
    for path in _BACKLIGHT_PATHS:
        if os.path.exists(path):
            return path
    return None


def _write_brightness(path: str, value: int) -> bool:
    """Write brightness value (0-255) to the sysfs file. Returns True on success."""
    value = max(0, min(255, value))
    try:
        with open(path, "w") as f:
            f.write(str(value))
        return True
    except PermissionError:
        logger.warning(
            f"[Brightness] PermissionError writing to {path}. "
            "Run: sudo chmod a+w %s", path
        )
        return False
    except Exception as e:
        logger.error(f"[Brightness] Failed to write brightness: {e}")
        return False


class BrightnessManager:
    """
    Singleton brightness manager. Safe to import and call from any thread.
    Uses a dedicated background thread for inactivity + night-mode checking.
    All sysfs writes happen in that thread to avoid blocking the Kivy UI.
    """

    def __init__(self):
        self._backlight_path: str | None = None
        self._current_brightness: int = BRIGHTNESS_ACTIVE

        # Operating hours set from Kulhad config
        self._op_start: datetime.time | None = None
        self._op_end:   datetime.time | None = None

        # Inactivity tracking
        self._last_activity_ts: float = time.monotonic()
        self._is_night_mode: bool = False
        self._is_dimmed: bool = False

        # Threading
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stopped = False  # BUG-014: guard against double stop() calls
        self._app = None       # BUG-011: app reference to check screensaver_active
        
        # Software Fallback Overlay
        self._overlay_color = None
        self._overlay_rect = None

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def start(self, app=None):
        """
        Call once from main_app.py build() (or on_start()).
        Finds the backlight path, sets initial brightness, and starts the
        background monitoring thread.

        app: Kivy App instance, stored for screensaver state checks (BUG-011).
        """
        self._app = app  # BUG-011: store for screensaver_active checks in _tick
        self._backlight_path = _find_backlight_path()

        if self._backlight_path:
            logger.info(f"[Brightness] Backlight path: {self._backlight_path}")
            self._set_brightness(BRIGHTNESS_ACTIVE)
        else:
            logger.info("[Brightness] No hardware backlight path found. Using Kivy software overlay fallback.")
            self._setup_software_overlay()
            self._set_brightness(BRIGHTNESS_ACTIVE)

        self._stop_event.clear()
        
        # Guarantee we wake the screen up even if the app crashes or user hits Ctrl+C
        import atexit
        atexit.register(self.stop)
        
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="BrightnessMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"[Brightness] Started — Active={BRIGHTNESS_ACTIVE}, "
            f"Dim={BRIGHTNESS_DIM}, Night={BRIGHTNESS_NIGHT}, "
            f"Inactivity timeout={INACTIVITY_TIMEOUT_MINUTES}m"
        )

    def stop(self):
        """Call from app on_stop() or atexit. Idempotent — safe to call multiple times."""
        # BUG-014: prevent double execution (atexit fires even when on_stop() called stop())
        if self._stopped:
            return
        self._stopped = True
        self._stop_event.set()

        # We bypass _set_brightness and Kivy entirely here because during an atexit
        # shutdown, Python has already started tearing down the logging module and
        # the Kivy window.
        try:
            import os
            os.system("wlr-randr --output HDMI-A-2 --on >/dev/null 2>&1 || WAYLAND_DISPLAY=wayland-1 wlr-randr --output HDMI-A-2 --on >/dev/null 2>&1")
        except:
            pass

    def on_user_activity(self, *args, **kwargs):
        """
        Call this on every touch/tap event in the Kivy app.
        Resets the inactivity timer and restores active brightness immediately.
        Safe to call from any thread (Kivy main thread or otherwise).

        Kivy Window.bind(on_touch_down=brightness_manager.on_user_activity)
        also works directly.
        """
        with self._lock:
            self._last_activity_ts = time.monotonic()
            # Wake immediately if dimmed or in night mode
            if self._is_dimmed or self._is_night_mode:
                self._is_dimmed = False
                self._is_night_mode = False
                self._set_brightness(BRIGHTNESS_ACTIVE)
                logger.info("[Brightness] ✋ Touch detected — restored to ACTIVE (80%)")

    def set_operating_hours(self, start_str: str | None, end_str: str | None):
        """
        Update operating hours used for night-mode detection.
        Call whenever the Kulhad heartbeat returns startTime / endTime.

        Args:
            start_str: e.g. "07:00" or "07:00 AM"
            end_str:   e.g. "22:00" or "10:00 PM"
        """
        with self._lock:
            self._op_start = self._parse_time(start_str)
            self._op_end   = self._parse_time(end_str)
        if self._op_start and self._op_end:
            logger.info(
                f"[Brightness] Operating hours set: "
                f"{self._op_start.strftime('%H:%M')} – {self._op_end.strftime('%H:%M')}"
            )

    @property
    def current_level(self) -> str:
        """Return human-readable current level: 'active', 'dim', or 'night'."""
        if self._is_night_mode:
            return "night"
        if self._is_dimmed:
            return "dim"
        return "active"

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _set_brightness(self, value: int):
        """Write brightness. Logs only on change. Thread-safe (caller holds lock)."""
        if value == self._current_brightness:
            return
        self._current_brightness = value
        percent = round(value / _MAX_BRIGHTNESS * 100)
        
        if self._backlight_path:
            ok = _write_brightness(self._backlight_path, value)
            status = "✅ (hardware)" if ok else "⚠️ (write failed)"
        else:
            status = "💻 (software overlay)"
            self._apply_software_brightness(value)
            
        logger.info(f"[Brightness] {status} → {value}/255 ({percent}%)")

    @mainthread
    def _setup_software_overlay(self):
        """Create a full-screen black rectangle over the entire Kivy UI to simulate dimming."""
        with Window.canvas.after:
            self._overlay_color = Color(0, 0, 0, 0)
            self._overlay_rect = Rectangle(pos=(0, 0), size=Window.size)
        Window.bind(size=self._on_window_resize)

    def _on_window_resize(self, instance, size):
        if self._overlay_rect:
            self._overlay_rect.size = size

    def _apply_software_brightness(self, value: int):
        """
        Since the goal is to increase physical display lifespan, a black Kivy rectangle 
        isn't enough (the backlight stays on). Instead, we use DPMS to physically put the 
        monitor to sleep.
        """
        import os
        if value == 0:
            # 0% (Night Mode) - Physically turn OFF the monitor via Wayland (HDMI-A-2)
            logger.info("[Brightness] Sending wlr-randr OFF signal to HDMI-A-2...")
            os.system("wlr-randr --output HDMI-A-2 --off >/dev/null 2>&1 || WAYLAND_DISPLAY=wayland-1 wlr-randr --output HDMI-A-2 --off >/dev/null 2>&1")
        else:
            # > 0% (Wake Up) - Physically turn ON the monitor
            os.system("wlr-randr --output HDMI-A-2 --on >/dev/null 2>&1 || WAYLAND_DISPLAY=wayland-1 wlr-randr --output HDMI-A-2 --on >/dev/null 2>&1")
            
        # Dispatch the UI overlay safely to the main thread
        self._apply_kivy_overlay(value)

    @mainthread
    def _apply_kivy_overlay(self, value: int):
        # We still apply the black box as a fallback just in case hardware control fails
        if self._overlay_color:
            alpha = 1.0 - (value / float(_MAX_BRIGHTNESS))
            self._overlay_color.a = alpha

    def _is_within_operating_hours(self) -> bool:
        """Return True if current time is within operating hours."""
        with self._lock:
            start = self._op_start
            end   = self._op_end

        if start is None or end is None:
            # No hours configured yet → assume always open (never dim to night)
            return True

        now = datetime.datetime.now().time()

        if start <= end:
            # Normal window: e.g. 07:00 – 22:00
            return start <= now <= end
        else:
            # Overnight window: e.g. 22:00 – 06:00
            return now >= start or now <= end

    def _seconds_since_activity(self) -> float:
        with self._lock:
            return time.monotonic() - self._last_activity_ts

    def _monitor_loop(self):
        """
        Background thread: checks inactivity and operating hours every
        _POLL_INTERVAL_SECONDS seconds and adjusts brightness accordingly.
        """
        logger.info("[Brightness] Monitor thread started.")
        while not self._stop_event.wait(timeout=_POLL_INTERVAL_SECONDS):
            try:
                self._tick()
            except Exception as e:
                logger.error(f"[Brightness] Monitor tick error: {e}")
        logger.info("[Brightness] Monitor thread stopped.")

    def _tick(self):
        """Single evaluation cycle."""
        in_hours = self._is_within_operating_hours()
        idle_secs = self._seconds_since_activity()

        with self._lock:
            currently_night  = self._is_night_mode
            currently_dimmed = self._is_dimmed

        if not in_hours and idle_secs >= INACTIVITY_TIMEOUT_SECONDS:
            # ── NIGHT MODE ───────────────────────────────────────────────
            if not currently_night:
                with self._lock:
                    self._is_night_mode = True
                    self._is_dimmed = False
                    self._set_brightness(BRIGHTNESS_NIGHT)
                logger.info("[Brightness] 🌙 Outside operating hours & idle → NIGHT (0%)")

        elif in_hours and idle_secs >= INACTIVITY_TIMEOUT_SECONDS:
            # ── DIM (inactivity) ─────────────────────────────────────────
            # Screensaver page SHOULD dim — the video is just a visual; dimming
            # saves the display and is the correct progression of the idle state.
            #
            # We skip dimming ONLY on staff/maintenance pages where the screensaver
            # is intentionally suppressed and staff are physically present:
            #   machine_empty (offline/refill mode), admin_login, diagnostics, rfid_assign.
            # Dimming there makes the screen look dead and confuses maintenance staff.
            on_staff_page = False
            try:
                app = self._app
                if app is not None:
                    _STAFF_PAGES = {
                        'machine_empty', 'admin_login',
                        'diagnostics', 'rfid_assign', 'maintenance'
                    }
                    current_page = getattr(app, '_current_page', '')
                    on_staff_page = current_page in _STAFF_PAGES
            except Exception:
                pass

            if not currently_dimmed and not currently_night and not on_staff_page:
                with self._lock:
                    self._is_dimmed = True
                    self._is_night_mode = False
                    self._set_brightness(BRIGHTNESS_DIM)
                logger.info(
                    f"[Brightness] 💤 Idle {idle_secs/60:.1f}m → DIM (50%)"
                )

        else:
            # ── ACTIVE ───────────────────────────────────────────────────
            if currently_night or currently_dimmed:
                # Entered operating hours after night → wake up
                with self._lock:
                    self._is_night_mode = False
                    self._is_dimmed = False
                    self._set_brightness(BRIGHTNESS_ACTIVE)
                logger.info("[Brightness] ☀️  Entered operating hours → ACTIVE (80%)")

    @staticmethod
    def _parse_time(time_str: str | None) -> datetime.time | None:
        """Parse '07:00', '07:00 AM', '7:00 AM' → datetime.time."""
        if not time_str:
            return None
        time_str = time_str.strip()
        for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
            try:
                return datetime.datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        logger.warning(f"[Brightness] Could not parse time: {time_str!r}")
        return None


# ── Singleton ────────────────────────────────────────────────────────────────
brightness_manager = BrightnessManager()

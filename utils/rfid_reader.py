#!/usr/bin/env python3
"""
RFID Reader Module — Sycreader HID keyboard mode

Primary path: raw evdev input from /dev/input/event* (no package required,
no Kivy focus dependency).  Works on any Linux kernel ≥ 2.6 including RPi.

Fallback: Kivy Window on_key_down / on_textinput events (used when the
evdev device cannot be opened, e.g. permission error before adding the
user to the 'input' group).

If the evdev path is blocked by permissions, fix it once with:
  sudo usermod -a -G input $(whoami)   # then log out and back in
"""

import threading
import time
import os
import struct
from kivy.clock import Clock
from kivy.core.window import Window


# ── evdev raw-input constants ─────────────────────────────────────────────────
# input_event struct: struct timeval (sec + usec), __u16 type, __u16 code, __s32 value
# '@' = native byte order + native size  →  handles both 32-bit (16B) and 64-bit (24B) ARM
_INPUT_EVENT_FORMAT = '@llHHi'
_INPUT_EVENT_SIZE   = struct.calcsize(_INPUT_EVENT_FORMAT)
_EV_KEY    = 1
_KEY_DOWN  = 1
# Linux input keycodes for digits and Enter
_KEY_DIGITS = {2:'1',3:'2',4:'3',5:'4',6:'5',7:'6',8:'7',9:'8',10:'9',11:'0'}
_KEY_ENTER  = 28


def _find_sycreader_event_path():
    """
    Parse /proc/bus/input/devices to locate the /dev/input/eventN node for
    the Sycreader RFID reader (USB ID ffff:0035).
    Returns the path string (e.g. '/dev/input/event3') or None if not found.
    """
    try:
        with open('/proc/bus/input/devices') as f:
            content = f.read()
        for block in content.strip().split('\n\n'):
            lines = block.split('\n')
            is_rfid = any(
                ('ffff' in ln and '0035' in ln) or
                'sycreader' in ln.lower() or
                'sycid' in ln.lower()
                for ln in lines
            )
            if is_rfid:
                for ln in lines:
                    if ln.startswith('H: Handlers='):
                        for token in ln.split():
                            if token.startswith('event'):
                                path = f'/dev/input/{token}'
                                if os.path.exists(path):
                                    return path
    except Exception:
        pass
    return None


class RFIDReader:
    """RFID Reader — Sycreader HID keyboard mode."""

    def __init__(self):
        self.is_listening = False
        self.callback = None
        self.last_card_time = 0
        self.card_buffer = ""
        self.last_key_time = 0
        self.card_input_timeout = 0.1   # 100 ms inter-digit gap (Kivy path)
        self._evdev_thread = None
        self._using_evdev = False

    # ── public API ────────────────────────────────────────────────────────────

    def start_listening(self, callback):
        self.callback = callback
        self.is_listening = True

        device_path = _find_sycreader_event_path()
        if device_path:
            self._using_evdev = True
            self._evdev_thread = threading.Thread(
                target=self._evdev_reader_loop,
                args=(device_path,),
                daemon=True
            )
            self._evdev_thread.start()
            print(f"🏷️ RFID Reader started — evdev {device_path}")
        else:
            # Fallback: Kivy keyboard events (requires Kivy window focus)
            self._using_evdev = False
            Window.bind(on_key_down=self.on_key_down)
            Window.bind(on_textinput=self.on_text_input)
            print("🏷️ RFID Reader started — Kivy keyboard fallback "
                  "(evdev device not found; check USB connection)")

    def stop_listening(self):
        self.is_listening = False
        self.callback = None
        if not self._using_evdev:
            Window.unbind(on_key_down=self.on_key_down)
            Window.unbind(on_textinput=self.on_text_input)
        print("🏷️ RFID Reader stopped")

    def simulate_card_tap(self, card_number):
        if self.callback:
            print(f"🏷️ Simulating RFID Card: {card_number}")
            Clock.schedule_once(lambda dt: self.callback(card_number))

    # ── evdev path ────────────────────────────────────────────────────────────

    def _evdev_reader_loop(self, device_path):
        """
        Read raw input_event structs from the Sycreader's evdev node.
        Accumulates digit key-down events and fires the callback on Enter
        (or on inter-character timeout via a watchdog approach).
        No third-party package required — only Python's struct module.
        """
        buf = ""
        last_digit_time = time.time()

        try:
            fd = open(device_path, 'rb')
        except PermissionError:
            print(f"⚠️ RFID evdev: permission denied on {device_path}")
            print(f"   Fix: sudo usermod -a -G input {os.environ.get('USER', 'urbanketl4')}")
            print(f"   Then log out and back in.  Falling back to Kivy keyboard.")
            self._using_evdev = False
            # Switch to Kivy keyboard fallback without restarting start_listening
            try:
                Window.bind(on_key_down=self.on_key_down)
                Window.bind(on_textinput=self.on_text_input)
            except Exception:
                pass
            return
        except Exception as e:
            print(f"⚠️ RFID evdev: cannot open {device_path}: {e}")
            return

        print(f"🏷️ RFID evdev: reader loop started ({_INPUT_EVENT_SIZE}B events)")
        with fd:
            while self.is_listening:
                try:
                    data = fd.read(_INPUT_EVENT_SIZE)
                except Exception:
                    break
                if not data or len(data) < _INPUT_EVENT_SIZE:
                    break
                try:
                    _, _, evtype, code, value = struct.unpack(_INPUT_EVENT_FORMAT, data)
                except struct.error:
                    continue

                if evtype != _EV_KEY or value != _KEY_DOWN:
                    continue

                now = time.time()
                if now - last_digit_time > 0.3:
                    buf = ""   # gap too long → new card

                if code in _KEY_DIGITS:
                    buf += _KEY_DIGITS[code]
                    last_digit_time = now
                elif code == _KEY_ENTER:
                    if len(buf) >= 6:
                        captured = buf
                        Clock.schedule_once(lambda dt, c=captured: self._process_card_input(c), 0)
                    buf = ""

        print(f"🏷️ RFID evdev: reader loop ended")

    # ── Kivy keyboard fallback ────────────────────────────────────────────────

    def on_text_input(self, window, text):
        if not self.is_listening:
            return False
        if text and text.isdigit() and len(text) >= 8:
            self._process_card_input(text)
            return True
        return False

    def on_key_down(self, window, key, scancode, codepoint, modifier):
        if not self.is_listening:
            return False
        current_time = time.time()
        if codepoint and codepoint.isdigit():
            if current_time - self.last_key_time > self.card_input_timeout:
                self.card_buffer = ""
            self.card_buffer += codepoint
            self.last_key_time = current_time
            Clock.schedule_once(self.check_card_complete, self.card_input_timeout)
            return True
        elif key == 13:  # Enter
            if self.card_buffer and len(self.card_buffer) >= 8:
                self._process_card_input(self.card_buffer)
            self.card_buffer = ""
            return True
        return False

    def check_card_complete(self, dt):
        current_time = time.time()
        if (current_time - self.last_key_time >= self.card_input_timeout and
                self.card_buffer and len(self.card_buffer) >= 8):
            self._process_card_input(self.card_buffer)
            self.card_buffer = ""

    # ── shared processing ─────────────────────────────────────────────────────

    def _process_card_input(self, card_number):
        current_time = time.time()
        if current_time - self.last_card_time < 0.5:
            print(f"🏷️ Duplicate scan ignored (debounce): {card_number}")
            return
        self.last_card_time = current_time
        print(f"🏷️ RFID Card Detected: {card_number}")
        if self.callback:
            Clock.schedule_once(lambda dt: self.callback(card_number))


# Global RFID reader instance
rfid_reader = RFIDReader()

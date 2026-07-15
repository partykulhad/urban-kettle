from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock
import os
import math
import threading


class MachineEmptyPage(Screen):
    """Page displayed when machine has 0 cups available"""
    
    def __init__(self, **kwargs):
        super(MachineEmptyPage, self).__init__(**kwargs)
        
        # Animation variables
        self.dots_animation_state = 0
        self.dots_timer = None

        # Track which mode we're in so screensaver logic can read it
        self.current_mode = 'empty'  # 'empty' or 'offline'

        # Cups check timer
        self.cups_check_timer = None
        self.cups_check_interval = 3  # Check every 3 seconds
        self._refill_confirm_count = 0  # consecutive cups>0 reads — debounce flaky/stale reads
        
        # Main layout with clean background - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=15)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top spacer
        main_layout.add_widget(Widget(size_hint_y=0.08))
        
        # Urban Ketl logo section - standardized
        logo_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.25)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                allow_stretch=True,
                keep_ratio=True
            )
            logo_section.add_widget(logo_image)
        else:
            # Fallback to text if image not found
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='40sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
                halign='center'
            )
            logo_section.add_widget(fallback_logo)
        
        main_layout.add_widget(logo_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # Main message section
        message_section = BoxLayout(orientation='vertical', size_hint_y=0.30, spacing=10)
        
        # Main title
        self.title_label = Label(
            text="We'll be back soon!",
            font_size='28sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        message_section.add_widget(self.title_label)

        # Subtitle
        self.subtitle_label = Label(
            text="Refill on its way",
            font_size='22sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center'
        )
        message_section.add_widget(self.subtitle_label)

        # Info message
        self.info_label = Label(
            text="Please try again later",
            font_size='20sp',
            color=(0.6, 0.6, 0.6, 1),
            halign='center'
        )
        message_section.add_widget(self.info_label)
        
        main_layout.add_widget(message_section)
        
        # Animated dots for loading effect
        dots_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.10)
        self.dots_label = Label(
            text='●●●',
            font_size='28sp',
            color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
            halign='center'
        )
        dots_section.add_widget(self.dots_label)
        main_layout.add_widget(dots_section)
        
        # Bottom spacer
        main_layout.add_widget(Widget(size_hint_y=0.14))
        
        self.add_widget(main_layout)
    
    def set_mode(self, mode, refill_label=None):
        """Switch between 'empty', 'offline', 'water_low', 'service_refill', and 'closed_hours'.

        'offline'/'water_low' are genuine hardware/connectivity problems → "Under Maintenance".
        'empty' is a normal low-stock refill → reassuring "Refill on its way" message.
        'service_refill' is a scheduled refill window → shows when the refill is coming.
        'closed_hours' is for non-operating hours → "next tea service will start @XX:XX".
        """
        self.current_mode = mode
        if mode == 'offline' or mode == 'water_low':
            self.title_label.text = "Under Maintenance"
            self.subtitle_label.text = "We'll be back soon!"
            self.info_label.text = "Sorry for the inconvenience\nPlease check back shortly"
        elif mode == 'closed_hours':
            # refill_label contains the dynamic start time (e.g., "7:00 AM")
            self.title_label.text = f"Next tea service will start @{refill_label}" if refill_label else "Next tea service starting soon"
            self.title_label.font_size = '22sp'  # Make title slightly smaller to fit the long sentence
            self.subtitle_label.text = ""
            self.info_label.text = "See you then!"
        elif mode == 'service_refill':
            self.title_label.text = f"Next tea service will start @{refill_label}" if refill_label else "Next tea service starting soon"
            self.title_label.font_size = '22sp'  # Make title slightly smaller to fit the long sentence
            self.subtitle_label.text = ""
            self.info_label.text = "See you then!"
        else:
            self.title_label.text = "We'll be back soon!"
            self.subtitle_label.text = "Refill on its way"
            self.info_label.text = "Please try again later"

    def _update_rect(self, instance, value):
        """Update background rectangle"""
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def on_enter(self):
        """Start animations when page becomes active"""
        self.start_dots_animation()
        self._refill_confirm_count = 0  # fresh start — don't trust a stale count from before

        # Start periodic cups check
        self.start_cups_check_timer()
    
    def on_leave(self):
        """Stop animations when leaving page"""
        self.stop_dots_animation()
        
        # Stop periodic cups check
        self.stop_cups_check_timer()
    
    def start_dots_animation(self):
        """Start the animated dots effect"""
        self.dots_animation_state = 0
        self.dots_timer = Clock.schedule_interval(self.update_dots, 0.5)
    
    def update_dots(self, dt):
        """Update the dots animation"""
        dots_states = ['●●●', '○●●', '○○●', '○○○', '●○○', '●●○']
        self.dots_animation_state = (self.dots_animation_state + 1) % len(dots_states)
        self.dots_label.text = dots_states[self.dots_animation_state]
    
    def stop_dots_animation(self):
        """Stop the dots animation"""
        if self.dots_timer:
            self.dots_timer.cancel()
            self.dots_timer = None
    
    def start_cups_check_timer(self):
        """Start periodic timer to check if cups become available"""
        # Stop any existing timer first
        self.stop_cups_check_timer()
        
        # Schedule periodic check
        self.cups_check_timer = Clock.schedule_interval(
            lambda dt: self.check_cups_availability(), 
            self.cups_check_interval
        )
        print(f"Started cups availability check timer (every {self.cups_check_interval} seconds)")
    
    def stop_cups_check_timer(self):
        """Stop the periodic cups check timer"""
        if self.cups_check_timer:
            self.cups_check_timer.cancel()
            self.cups_check_timer = None
            print("Stopped cups availability check timer")
    
    def check_cups_availability(self):
        """Check if cups are available and return to payment method page if so.
        Guarded against overlapping calls: if a slow network response makes one
        check still running when the next 3s tick fires, _refill_confirm_count
        (and the cups/online navigation decisions below) could be mutated from
        two threads at once.
        """
        if getattr(self, '_checking_cups_availability', False):
            return
        self._checking_cups_availability = True
        threading.Thread(target=self._fetch_cups_count_guarded, daemon=True).start()

    def _fetch_cups_count_guarded(self):
        try:
            self.fetch_cups_count()
        finally:
            self._checking_cups_availability = False

    def fetch_cups_count(self):
        """Check ESP32 machineState + cups count; navigate home if machine is back online with cups."""
        from kivy.app import App
        app = App.get_running_app()

        # Water-level-low mode has its own recovery condition (waterLevelLow
        # clearing) — it is NOT driven by ESP32 online state or cups count,
        # so it's checked separately and skips the rest of this method.
        if self.current_mode == 'water_low':
            threading.Thread(target=self._check_water_level_recovery, daemon=True).start()
            return

        try:
            from config import DEVICE_ID, POLLING_SERVER_URL
            from utils.api_client import get_localhost_session

            # ── 1. Check ESP32 machineState from local polling server ──────────
            is_online = False  # default: assume offline until confirmed
            try:
                import time as _time
                r = get_localhost_session().get(
                    f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                    timeout=2
                )
                if r.status_code == 200:
                    data = r.json()
                    machine_state = data.get('machineState', 'UNKNOWN').upper()
                    ts = data.get('timestamp')
                    # Also treat as offline if last health POST is more than 90s old
                    if ts:
                        from datetime import datetime as _dt
                        age = _time.time() - _dt.fromisoformat(ts).timestamp()
                        if age > 90:
                            machine_state = 'OFFLINE'
                    is_online = machine_state != 'OFFLINE'
                    print(f"[MachineEmpty] ESP32 machineState={machine_state}, is_online={is_online}")
                else:
                    # 404 = no health POSTs received yet → ESP32 not connected
                    print(f"[MachineEmpty] Polling server returned {r.status_code} — ESP32 not connected")
            except Exception as poll_err:
                print(f"[MachineEmpty] Polling server unreachable: {poll_err} — staying offline")

            if not is_online:
                print("[MachineEmpty] Machine still OFFLINE — staying on page")
                return

            # ── Machine came back online ───────────────────────────────────────
            if hasattr(app, 'previous_machine_state') and app.previous_machine_state == "offline":
                print("🟢 Machine back ONLINE (detected from machine_empty page)")
                app.previous_machine_state = "online"
                # Notify kulhad that machine is back online
                threading.Thread(
                    target=lambda: app.api_client.report_machine_status(app.MACHINE_ID, 'online'),
                    daemon=True
                ).start()

            # ── 2. Check cups count ────────────────────────────────────────────
            if hasattr(app, 'api_client') and hasattr(app, 'MACHINE_ID'):
                cups_data = app.api_client.get_remaining_cups(app.MACHINE_ID)
                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    from config import MACHINE_EMPTY_THRESHOLD

                    if cups_count > MACHINE_EMPTY_THRESHOLD:
                        # Require 2 consecutive confirmed-restocked reads (~6s apart)
                        # before acting — a single flaky/stale read from get_remaining_cups
                        # (which reads via a reduce-by-0 call, not a dedicated read
                        # endpoint) shouldn't bounce the screen back to selection only
                        # to find it's still at/below the empty threshold.
                        self._refill_confirm_count += 1
                        if self._refill_confirm_count < 2:
                            print(f"[MachineEmpty] cups={cups_count} (unconfirmed, "
                                  f"{self._refill_confirm_count}/2) — waiting for confirmation")
                            return
                        Clock.schedule_once(lambda dt, c=cups_count: app.set_local_cups_count(c))
                        if self.current_mode == 'empty':
                            # Cups genuinely hit the empty threshold → restocked — run the refill flush.
                            print(f"[MachineEmpty] Cups refilled ({MACHINE_EMPTY_THRESHOLD} or below → {cups_count}) — returning home via refill flush")
                            Clock.schedule_once(lambda dt: self.return_to_payment_method())
                        else:
                            # 'offline' mode (ESP32 connectivity blip) — cups never hit the
                            # threshold, so this is not a refill. Go home directly, skip the flush.
                            print(f"[MachineEmpty] Machine online, cups={cups_count} — returning home (no refill flush, was never empty)")
                            Clock.schedule_once(lambda dt: app.show_payment_method_page(fetch_cups=True))
                    else:
                        # Online but at/below the empty threshold — switch to the 'empty' message
                        self._refill_confirm_count = 0
                        Clock.schedule_once(lambda dt, c=cups_count: app.set_local_cups_count(c))
                        print(f"[MachineEmpty] Machine online but cups={cups_count} (<= {MACHINE_EMPTY_THRESHOLD}) — switching to empty mode")
                        Clock.schedule_once(lambda dt: self.set_mode('empty'), 0)
                else:
                    # Kulhad API unreachable — still go home; cups will be re-fetched there
                    print("[MachineEmpty] Cups API failed — navigating home anyway (machine is online)")
                    Clock.schedule_once(lambda dt: self.return_to_payment_method())
        except Exception as e:
            print(f"Error checking machine availability: {e}")
    
    def _check_water_level_recovery(self):
        """While in 'water_low' mode, poll the ESP32's waterLevelLow flag and
        return to selection once it clears (e.g. tank was refilled).
        """
        from kivy.app import App
        from utils.hardware_monitor import hardware_monitor
        app = App.get_running_app()
        try:
            still_low = hardware_monitor.get_water_level_low()
            if not still_low:
                print("🟢 [MachineEmpty] waterLevelLow cleared — returning to selection")
                if hasattr(app, 'clear_water_level_low'):
                    Clock.schedule_once(lambda dt: app.clear_water_level_low(), 0)
        except Exception as e:
            print(f"[MachineEmpty] water level recovery check error: {e}")

    def return_to_payment_method(self):
        """Cups were just refilled — hand off to handle_cups_refill() which runs
        a temp check then the water×2 + tea flush before going to selection.
        """
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, 'handle_cups_refill'):
            app.handle_cups_refill()
        else:
            app.show_payment_method_page(fetch_cups=True)

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
import threading
import time
import os
from config import MACHINE_ID, RFID_MACHINE_ID

# Import utility modules
from utils.api_client import ApiClient, get_localhost_session
from utils.qr_utils import QRUtils
from utils.hardware_monitor import hardware_monitor
from utils.screensaver_manager import ScreensaverVideoManager

# Import page modules
from ui_pages.payment_method_page import PaymentMethodPage
from ui_pages.selection_page import SelectionPage
from ui_pages.payment_page import PaymentPage
from ui_pages.loading_page import LoadingPage
# from ui_pages.transaction_processing_page import TransactionProcessingPage  # Commented out - not used
from ui_pages.dispensing_page import DispensingPage
from ui_pages.place_cup_page import PlaceCupPage
from ui_pages.thank_you_page import ThankYouPage
from ui_pages.screensaver_page import ScreensaverPage
from ui_pages.qr_expired_page import QRExpiredPage
from ui_pages.machine_empty_page import MachineEmptyPage
from ui_pages.rfid_auth_page import RFIDAuthPage
from ui_pages.hardware_error_page import HardwareErrorPage
from ui_pages.heating_page import HeatingPage
from ui_pages.flush_page import FlushPage


class ChaiOrderingApp(App):

    # =========================================================================
    # Device ID auto-detection (Option B)
    # =========================================================================

    def _auto_detect_device_id(self, timeout_seconds: int = 30) -> str:
        """Query the polling server and return the first connected ESP32 device ID.
        Returns empty string if no device is found within timeout_seconds.
        """
        from config import POLLING_SERVER_URL
        import requests

        print(f"🔍 [Setup] DEVICE_ID is empty — scanning for connected ESP32 "
              f"(timeout {timeout_seconds}s)...")
        deadline = time.time() + timeout_seconds

        while time.time() < deadline:
            try:
                r = requests.get(f"{POLLING_SERVER_URL}/api/devices", timeout=2)
                if r.status_code == 200:
                    devices = r.json().get("devices", [])
                    if devices:
                        device_id = devices[0].get("deviceId", "")
                        if device_id:
                            print(f"✅ [Setup] ESP32 found: {device_id}")
                            return device_id
                        print("⚠️ [Setup] Device entry has no deviceId — waiting...")
                    else:
                        print("⏳ [Setup] Polling server running but no ESP32 connected yet...")
            except Exception as e:
                print(f"⏳ [Setup] Polling server not ready ({e}) — retrying...")
            time.sleep(2)

        print("❌ [Setup] Auto-detection timed out — no ESP32 found")
        return ""

    def _save_device_id_to_config(self, device_id: str) -> None:
        """Write device_id into the DEVICE_ID line of config.py using regex."""
        import re
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
        try:
            with open(config_path, "r") as f:
                content = f.read()
            new_content = re.sub(
                r'(DEVICE_ID\s*=\s*")[^"]*(")',
                f'\\g<1>{device_id}\\2',
                content
            )
            with open(config_path, "w") as f:
                f.write(new_content)
            print(f"✅ [Setup] config.py updated — DEVICE_ID = \"{device_id}\"")
        except Exception as e:
            print(f"❌ [Setup] Could not write DEVICE_ID to config.py: {e}")

    def _auto_detect_and_update_device_id(self, current_id: str) -> None:
        """Background: detect connected ESP32 and update config.py if ID changed.

        Runs on every startup so a replaced ESP32 board is picked up automatically
        without any manual config edit.
        """
        detected_id = self._auto_detect_device_id(timeout_seconds=60)
        import config as _cfg

        if not detected_id:
            if current_id:
                print(f"⚠️ [Setup] ESP32 not detected within 60s — continuing with existing ID: {current_id}")
            else:
                print("❌ [Setup] No ESP32 detected — hardware commands will fail")
            return

        if detected_id == current_id:
            print(f"✅ [Setup] ESP32 ID confirmed: {detected_id}")
            return

        # ID changed — update config.py and in-memory config
        print(f"🔄 [Setup] ESP32 ID changed: '{current_id}' → '{detected_id}' — updating config.py")
        self._save_device_id_to_config(detected_id)
        _cfg.DEVICE_ID = detected_id
        hardware_monitor.device_id = detected_id
        print(f"✅ [Setup] config.py updated automatically — no manual edit needed")

    # =========================================================================

    def build(self):
        self.title = "Urban Kettle"

        # ── Device ID setup ──────────────────────────────────────────────────
        # DEVICE_ID in config.py is auto-managed — no manual editing needed.
        #
        # First boot (DEVICE_ID = ""):  block here and wait for ESP32 to connect
        #                               so the rest of build() has a valid ID.
        # Subsequent boots (ID stored): use it immediately (no delay), then
        #                               check in background and auto-update if
        #                               the ESP32 board was ever replaced.
        import config as _cfg
        if not _cfg.DEVICE_ID:
            # First-time setup: show a splash screen so the user sees something
            # while we wait for the ESP32 (up to 30s). build() hasn't returned
            # yet so the Kivy loop hasn't started — we build a minimal window manually.
            from kivy.core.window import Window as _Win
            from kivy.uix.label import Label as _Label
            from kivy.uix.floatlayout import FloatLayout as _FL
            splash = _FL()
            splash.add_widget(_Label(
                text='Urban Kettle\nConnecting to hardware...',
                font_size='28sp',
                bold=True,
                halign='center',
                color=(0.714, 0.478, 0.176, 1)
            ))
            # Briefly show window so user sees progress
            _Win.size = (881, 661)

            detected_id = self._auto_detect_device_id(timeout_seconds=30)
            if detected_id:
                self._save_device_id_to_config(detected_id)
                _cfg.DEVICE_ID = detected_id
                hardware_monitor.device_id = detected_id
                print(f"✅ [Setup] First-time setup complete — DEVICE_ID = {detected_id}")
            else:
                print("❌ [Setup] No ESP32 detected — hardware will not function. "
                      "Check ESP32 is powered and polling server is running.")
        else:
            # Existing ID — use immediately, verify / auto-update in background
            hardware_monitor.device_id = _cfg.DEVICE_ID
            print(f"✅ [Setup] Using stored DEVICE_ID: {_cfg.DEVICE_ID}")
            threading.Thread(
                target=lambda: self._auto_detect_and_update_device_id(_cfg.DEVICE_ID),
                daemon=True
            ).start()

        # Constants
        self.MACHINE_ID = MACHINE_ID
        self.INACTIVE_TIMEOUT = 30  # 30 seconds

        # Create API client
        self.api_client = ApiClient()
        
        # Variables
        self.screensaver_active = False
        self.last_activity_time = time.time()
        self.video_path = "input.mp4"  # Default video path
        self.current_qr_code_id = ""  # Store the current QR code ID
        self.status_check_event = None  # For tracking the status check timer
        
        # Cache for machine status (reduce API calls)
        self._machine_status_cache = None
        self._machine_status_cache_time = 0
        self._machine_status_cache_ttl = 10  # Cache for 10 seconds
        self._cups_count_cache = None
        self._cups_count_cache_time = 0
        
        # *** LOCAL CUPS COUNTER - Fetch from API only on state transitions ***
        self.local_cups_count = None  # Store cups count locally
        self.cups_count_initialized = False  # Track if we've fetched initial count
        
        # *** Canister level alert tracking ***
        self.canister_alert_sent = False  # Track if alert has been sent for cups = 5
        
        # *** Global machine status monitoring ***
        self.global_status_monitor_event = None
        self.global_status_check_interval = 10  # Check every 10 seconds
        self.previous_machine_state = None  # Track previous state for transition detection
        
        # *** Activity and hardware error monitoring ***
        self.activity_monitor_event = None
        self.hardware_error_monitor_event = None
        
        # *** NEW: Cup management variables ***
        self.selected_cups = 1  # Default number of cups
        self.current_cup_number = 1  # Current cup being dispensed

        # *** Dispense volume (from Kulhad getMachineData) ***
        self.ml_to_dispense = 100   # Default ml per cup; overridden by API on startup

        # *** Auto flush after inactivity ***
        # The Kulhad API exposes exactly ONE flush setting: flushTimeMinutes.
        # That is the idle time (in minutes) after the last dispense before the
        # machine runs its cleaning cycle.  Pump run-durations are fixed in
        # firmware — 20 s each — and are NOT configurable via the API.
        self.flush_timer_event = None           # Kivy Clock event for the idle flush
        self.flush_time_minutes = 40            # Default; overridden by Kulhad flushTimeMinutes on startup
        self.scheduled_flush_check_event = None # Kivy Clock: refresh flush_time_minutes every 5 min

        # *** Flush-in-progress state (drives flush page UI) ***
        self.flush_in_progress = False          # True while water+tea flush is running

        # --- Strategy 1: Multi-Prefetch State ---
        self._prefetches = {}           # dict: {cup_count: {'data': qr_data, 'image': PIL_img}}
        self._prefetch_lock = threading.Lock()
        self._prefetching_counts = set()  # counts currently being fetched
        self._prefetch_abandoned = set()  # in-flight counts that must cancel on completion
        
        # Create screen manager with no transition for faster page changes
        # SlideTransition can cause perceived lag, NoTransition is instant
        self.screen_manager = ScreenManager(transition=NoTransition())
        
        # Initialize pages
        self.payment_method_page = PaymentMethodPage(name='payment_method')
        self.selection_page = SelectionPage(name='selection')
        self.payment_page = PaymentPage(name='payment')
        self.loading_page = LoadingPage(name='loading')
        # self.transaction_processing_page = TransactionProcessingPage(name='transaction_processing')  # Commented out - not used
        self.dispensing_page = DispensingPage(name='dispensing')
        self.place_cup_page = PlaceCupPage(name='place_cup')  # *** NEW: Place cup page ***
        self.thank_you_page = ThankYouPage(name='thank_you')
        self.screensaver_page = ScreensaverPage(name='screensaver')
        self.qr_expired_page = QRExpiredPage(name='qr_expired')
        self.machine_empty_page = MachineEmptyPage(name='machine_empty')
        self.rfid_auth_page = RFIDAuthPage(name='rfid_auth')  # RFID authentication page
        self.hardware_error_page = HardwareErrorPage(name='hardware_error')
        self.heating_page = HeatingPage(name='heating')
        self.flush_page = FlushPage(name='flush')
        
        # Add screens to screen manager
        self.screen_manager.add_widget(self.payment_method_page)
        self.screen_manager.add_widget(self.selection_page)
        self.screen_manager.add_widget(self.payment_page)
        self.screen_manager.add_widget(self.loading_page)
        # self.screen_manager.add_widget(self.transaction_processing_page)  # Commented out - not used
        self.screen_manager.add_widget(self.dispensing_page)
        self.screen_manager.add_widget(self.place_cup_page)  # *** NEW: Add place cup page ***
        self.screen_manager.add_widget(self.thank_you_page)
        self.screen_manager.add_widget(self.screensaver_page)
        self.screen_manager.add_widget(self.qr_expired_page)
        self.screen_manager.add_widget(self.machine_empty_page)
        self.screen_manager.add_widget(self.rfid_auth_page)  # Add RFID auth page
        self.screen_manager.add_widget(self.hardware_error_page)
        self.screen_manager.add_widget(self.heating_page)
        self.screen_manager.add_widget(self.flush_page)
        
        # Set initial screen to payment method selection
        self.screen_manager.current = 'payment_method'
        self._current_page = 'payment_method'  # thread-safe mirror of screen_manager.current
        
        # Setup screensaver monitoring
        self.setup_screensaver_monitoring()
        
        # Setup hardware error monitoring
       #self.setup_hardware_error_monitoring()
        
        # Set exact 7-inch tablet dimensions (7 inches diagonal)
        # Standard 7-inch tablet: 1024x600 pixels at ~170 PPI
        # Physical size: 6.1" x 3.6" = 7" diagonal
        Window.size = (881, 661)
        Window.minimum_width = 881
        Window.minimum_height = 661
        Window.maximum_width = 881
        Window.maximum_height = 661
        # Lock to exact 7-inch tablet size
        Window.resizable = False
        Window.fullscreen = 'auto'
        Window.rotation = 180  # Physical screen is mounted upside-down
        # Start hardware monitoring service
        hardware_monitor.start()
        
        # Initialize RFID Auth Handler early (at app startup)
        print("🔐 Initializing RFID AES Auth Handler at startup...")
        try:
            from utils.rfid_aes_auth import RFIDAESAuth
            self.rfid_auth_handler = RFIDAESAuth(
                base_url="https://www.ukteawallet.com",
                machine_id=RFID_MACHINE_ID
            )
            if self.rfid_auth_handler.reader_active:
                print("✅ RFID Auth Handler initialized successfully at startup")
            else:
                print("⚠️ RFID reader not active at startup - will retry when entering payment page")
        except Exception as e:
            print(f"❌ Failed to initialize RFID Auth Handler at startup: {e}")
            self.rfid_auth_handler = None
        
        # Warm up API connections (background)
        self.api_client.warmup_apis()

        # Populate both cached config values from Kulhad on startup.
        # The same function is called every 5 min by the scheduled monitor
        # to pick up any changes made on the Kulhad backend.
        threading.Thread(target=self._refresh_machine_config_cache, daemon=True).start()

        # ── OPT 2: Pre-warm PIL image plugins in a background thread.
        # PIL lazy-loads ~40 plugins on first use, adding ~0.15s to the
        # first QR generation.  Pre-loading them at startup costs nothing.
        def _prewarm_pil():
            try:
                from PIL import Image
                Image.init()   # Forces all image plugins to load now
                print("✅ PIL image plugins pre-warmed")
            except Exception:
                pass
        threading.Thread(target=_prewarm_pil, daemon=True).start()

        # Start global machine status monitoring
        self.start_global_status_monitoring()
        
        # Start scheduled flush monitor — polls Kulhad API every 5 min and triggers
        # water + tea flush when a scheduled time arrives or interval elapses.
        self.start_scheduled_flush_monitor()

        # Check if tea is heating up (schedule check after 1.5 seconds to allow hardware monitor to start)
        Clock.schedule_once(lambda dt: self.check_heating_on_startup(), 1.5)
        
        # Setup idle temperature monitoring (checks every 5s on payment_method or screensaver page)
        self.setup_idle_temperature_monitoring()
        
        # Initialize and start screensaver video manager
        self.screensaver_video_manager = ScreensaverVideoManager(machine_id=self.MACHINE_ID)
        
        # Update screensaver video in background thread
        def on_video_ready(video_path):
            """Callback when video is ready - update screensaver page"""
            print(f"📹 Screensaver video ready: {video_path}")
            self.video_path = video_path
            # Update screensaver page on main thread
            Clock.schedule_once(lambda dt: self.screensaver_page.set_video_path(video_path))
        
        self.screensaver_video_manager.update_video_async(callback=on_video_ready)
        
        return self.screen_manager
    
    def show_page(self, page_name):
        """Show a page by name"""
        self.screen_manager.current = page_name
        # Keep a plain Python string mirror for safe reading from background threads.
        # screen_manager.current is a Kivy property — reading it off the main thread
        # is not officially supported. This attribute is always written here (main thread).
        self._current_page = page_name
        if page_name != 'screensaver':
            self.reset_activity_timer()
    
    def show_payment_method_page(self, fetch_cups=False):
        """Show the payment method page — or the flush page if a flush is running.

        Any navigation that ends on the home screen (screensaver wake, heating done,
        etc.) goes through here, so a single guard is enough to block orders while
        the machine is cleaning itself.
        """
        if self.flush_in_progress:
            self.flush_page.show_waiting()
            self.show_page('flush')
            return

        self.show_page('payment_method')
        if fetch_cups:
            self.fetch_and_store_cups_count()
    
    def show_selection_page(self):
        """Show the selection page"""
        self.show_page('selection')
    
    def show_payment_page(self, number_of_cups=None):
        """Show the payment page with QR code generation (using Multi-Prefetch)"""
        if number_of_cups is None:
            number_of_cups = self.selection_page.get_cup_count()

        # New order started — cancel any pending auto flush
        self.cancel_auto_flush()

        self.set_selected_cups(number_of_cups)
        self.show_loading_page()
        self.loading_timeout_event = Clock.schedule_once(self.on_loading_timeout, 15)
        
        # --- STRATEGY 1: Check Multi-Prefetch Cache ---
        # needs_fallback is determined INSIDE the lock so no other thread can race
        # between releasing the lock and the check below.
        needs_fallback = False
        with self._prefetch_lock:
            cached = self._prefetches.get(number_of_cups)
            if cached and cached.get('data') and cached.get('image'):
                print(f"⚡ MULTI-PREFETCH: Instant reveal for {number_of_cups} cups!")
                data = cached['data']
                image = cached['image']

                # Cancel every OTHER cached QR before clearing — no leaks
                others = {k: v for k, v in self._prefetches.items() if k != number_of_cups}
                self._prefetches = {}

                # Mark every OTHER in-flight prefetch as abandoned so it cancels on completion
                for count in self._prefetching_counts:
                    if count != number_of_cups:
                        self._prefetch_abandoned.add(count)

                Clock.schedule_once(lambda dt: self.update_payment_page(image, data))

            elif number_of_cups in self._prefetching_counts:
                # Prefetch for this count is in flight — mark all others abandoned, wait
                print(f"⌛ MULTI-PREFETCH: Already fetching {number_of_cups} cups. Loading screen will wait.")
                for count in self._prefetching_counts:
                    if count != number_of_cups:
                        self._prefetch_abandoned.add(count)
                # Cancel other cached QRs too
                others = {k: v for k, v in self._prefetches.items() if k != number_of_cups}
                self._prefetches = {number_of_cups: self._prefetches[number_of_cups]} if number_of_cups in self._prefetches else {}
                # needs_fallback stays False — worker will deliver result
            else:
                others = dict(self._prefetches)
                self._prefetches = {}
                for count in self._prefetching_counts:
                    self._prefetch_abandoned.add(count)
                needs_fallback = True  # nothing in cache or in-flight

        # Cancel any stale cached QRs outside the lock (avoids holding lock during network call)
        for cup_count, entry in others.items():
            qr_id = entry.get('data', {}).get('id', '')
            if qr_id:
                print(f"🗑️ Cancelling stale cached QR {qr_id} ({cup_count} cups)")
                threading.Thread(
                    target=lambda qid=qr_id: self.api_client.cancel_payment(qid),
                    daemon=True
                ).start()

        if cached:
            return

        if needs_fallback:
            print(f"🔄 MULTI-PREFETCH: Result for {number_of_cups} not in cache/loading, using fallback.")
            threading.Thread(target=lambda: self.generate_qr_code(number_of_cups), daemon=True).start()

    def trigger_qr_prefetch(self, number_of_cups):
        """Pre-generate a unique QR for a specific cup count in the background"""
        def _prefetch_worker():
            with self._prefetch_lock:
                if number_of_cups in self._prefetches or number_of_cups in self._prefetching_counts:
                    return
                self._prefetching_counts.add(number_of_cups)

            print(f"🛰️ MULTI-PREFETCH: Starting background request for {number_of_cups} cups...")
            qr_data = self.api_client.generate_payment_qr(self.MACHINE_ID, number_of_cups)

            # Check abandoned BEFORE touching cache — must happen while lock is held
            with self._prefetch_lock:
                abandoned = number_of_cups in self._prefetch_abandoned
                self._prefetching_counts.discard(number_of_cups)
                self._prefetch_abandoned.discard(number_of_cups)

            if abandoned:
                # User moved on — cancel this QR immediately, never cache it
                qr_id = (qr_data or {}).get('id', '')
                if qr_id:
                    print(f"🗑️ PREFETCH ABANDONED: cancelling {qr_id} ({number_of_cups} cups)")
                    threading.Thread(
                        target=lambda qid=qr_id: self.api_client.cancel_payment(qid),
                        daemon=True
                    ).start()
                return

            if qr_data and qr_data.get("imageContent"):
                img = QRUtils.generate_qr_from_content(qr_data["imageContent"])
                print(f"✅ MULTI-PREFETCH: {number_of_cups} cups is READY in cache.")

                # User is on loading screen waiting for this exact count — deliver now
                if self._current_page == 'loading' and self.selected_cups == number_of_cups:
                    print(f"🎯 MULTI-PREFETCH: Delivered just-in-time for {number_of_cups} cups!")
                    Clock.schedule_once(lambda dt: self.update_payment_page(img, qr_data))
                    return

                # User is on loading screen but waiting for a DIFFERENT count — cancel this one
                if self._current_page == 'loading' and self.selected_cups != number_of_cups:
                    qr_id = qr_data.get('id', '')
                    if qr_id:
                        print(f"🗑️ STALE PREFETCH: cancelling {qr_id} ({number_of_cups} cups, user wants {self.selected_cups})")
                        threading.Thread(
                            target=lambda qid=qr_id: self.api_client.cancel_payment(qid),
                            daemon=True
                        ).start()
                    return

                # Store in cache for when user confirms
                with self._prefetch_lock:
                    self._prefetches[number_of_cups] = {'data': qr_data, 'image': img}
            else:
                print(f"❌ MULTI-PREFETCH: Background request failed for {number_of_cups} cups.")
                if self._current_page == 'loading' and self.selected_cups == number_of_cups:
                    print("⚠️ User was waiting for this prefetch - showing error fallback")
                    Clock.schedule_once(lambda dt: self.show_error_fallback())

        threading.Thread(target=_prefetch_worker, daemon=True).start()

    def cancel_prefetched_qrs(self):
        """Cancel all cached and in-flight prefetch QRs.
        Called when user backs out of selection page or inactivity timeout fires."""
        with self._prefetch_lock:
            cached = dict(self._prefetches)
            self._prefetches = {}
            # Mark every in-flight count as abandoned — they will cancel themselves on completion
            self._prefetch_abandoned.update(self._prefetching_counts)
            self._prefetching_counts.clear()

        for cup_count, entry in cached.items():
            qr_id = entry.get('data', {}).get('id', '')
            if qr_id:
                print(f"🗑️ Cancelling prefetched QR {qr_id} ({cup_count} cups)")
                threading.Thread(
                    target=lambda qid=qr_id: self.api_client.cancel_payment(qid),
                    daemon=True
                ).start()

    def trigger_early_prefetch(self):
        """Strategic batch prefetch for 1, 2, and 3 cups to mask API latency"""
        for count in [1, 2, 3]:
            self.trigger_qr_prefetch(count)
    
    def on_loading_timeout(self, dt):
        """Called if loading page takes too long - prevents hanging"""
        if self.screen_manager.current == 'loading':
            print("⚠️ Loading page timeout (15s) - QR generation took too long")
            self.show_error_fallback()
    
    def cancel_loading_timeout(self):
        """Cancel the loading timeout"""
        if hasattr(self, 'loading_timeout_event') and self.loading_timeout_event:
            self.loading_timeout_event.cancel()
            self.loading_timeout_event = None
    
    def show_loading_page(self, message=None):
        """Show the loading page"""
        # Pause RF keep-alive to prevent GIL contention during animations
        if hasattr(self, 'rfid_auth_handler') and self.rfid_auth_handler:
            self.rfid_auth_handler.pause_keepalive()
        
        if message:
            self.loading_page.update_message(message)
        else:
            self.loading_page.update_message("Generating QR code for payment")
        self.show_page('loading')
        self.loading_page.start_animation()
    
    # def show_transaction_processing_page(self):
    #     """Show the transaction processing page"""
    #     self.show_page('transaction_processing')
    
    def show_dispensing_page(self):
        """Show the dispensing page - MODIFIED to start dispensing process"""
        # *** MODIFIED: Start the dispensing process instead of directly showing dispensing page ***
        self.start_dispensing_process()
    
    def show_thank_you_page(self):
        """Show the thank you page"""
        self.show_page('thank_you')
    
    # *** NEW: Cup management methods ***
    def set_selected_cups(self, num_cups):
        """Called when user selects number of cups"""
        self.selected_cups = num_cups
        self.current_cup_number = 1
        print(f"Selected {num_cups} cups for dispensing")
    
    def start_dispensing_process(self):
        """Start the dispensing process for multiple cups"""
        self.current_cup_number = 1
        print(f"Starting dispensing process for {self.selected_cups} cups")
        self.show_place_cup_page()
    
    def show_place_cup_page(self):
        """Show the place cup page"""
        print(f"Showing place cup page for cup {self.current_cup_number} of {self.selected_cups}")
        
        # Check if we're already on the place_cup page
        already_on_page = self.screen_manager.current == 'place_cup'
        
        # Show the page
        self.show_page('place_cup')
        
        # Only call on_enter manually if we were already on this page
        # (Kivy calls it automatically when changing screens)
        if already_on_page:
            print("📋 Manually calling on_enter() to reset page for next cup")
            self.place_cup_page.on_enter()
    
    def start_dispensing_current_cup(self):
        """Start dispensing for the current cup"""
        print(f"Starting dispensing for cup {self.current_cup_number} of {self.selected_cups}")
        self.dispensing_page.set_cup_info(self.current_cup_number, self.selected_cups)
        self.show_page('dispensing')
    
    def handle_cup_completion(self):
        """Handle completion of a single cup"""
        print(f"Cup {self.current_cup_number} of {self.selected_cups} completed")
        
        if self.current_cup_number < self.selected_cups:
            # More cups to dispense
            self.current_cup_number += 1
            print(f"Moving to cup {self.current_cup_number} of {self.selected_cups}")
            # Show place cup page for next cup
            self.show_place_cup_page()
        else:
            # All cups completed
            print("All cups completed! Showing thank you page")
            # Refresh cups count after all dispensing is complete
            self.refresh_cups_count()
            self.show_thank_you_page()
            # Schedule auto water flush if no new order within flushTimeMinutes
            self.schedule_auto_flush()
    
    def refresh_cups_count(self):
        """Refresh the cups count on payment method page"""
        if hasattr(self.payment_method_page, 'refresh_cups_count'):
            self.payment_method_page.refresh_cups_count()

    # *** AUTO FLUSH METHODS ***
    def schedule_auto_flush(self):
        """After a dispense, fetch the latest flushTimeMinutes from Kulhad then
        arm the idle-flush timer.  If a new order arrives before the timer fires,
        cancel_auto_flush() resets everything.
        """
        self.cancel_auto_flush()
        threading.Thread(target=self._fetch_flush_timing_and_schedule, daemon=True).start()

    def _refresh_machine_config_cache(self):
        """Fetch flushTimeMinutes and mlToDispense from Kulhad and update the local cache.

        Called once at startup and every 5 minutes by the scheduled monitor.
        If either value changed since the last refresh, the ESP32 is re-synced
        automatically.  All other code (dispense, flush arming) reads from
        self.flush_time_minutes / self.ml_to_dispense — no extra API calls.
        """
        try:
            from config import DEVICE_ID, ml_to_pump_ms

            result = self.api_client.get_machine_data(self.MACHINE_ID)
            if not result or not result.get("success"):
                print("⚠️ [Config] Could not fetch machine config from Kulhad — using cached values")
                return

            data = result.get("data", {})
            updated = []

            # ── flushTimeMinutes ─────────────────────────────────────────────
            flush_mins = data.get("flushTimeMinutes")
            if flush_mins and flush_mins != "N/A":
                new_flush = float(flush_mins)
                if new_flush <= 0:
                    print(f"⚠️ [Config] flushTimeMinutes={new_flush} is invalid — "
                          f"keeping {self.flush_time_minutes} min")
                elif new_flush != self.flush_time_minutes:
                    self.flush_time_minutes = new_flush
                    updated.append(f"flushTimeMinutes={new_flush} min")

            # ── mlToDispense → pump duration ─────────────────────────────────
            ml_raw = data.get("mlToDispense")
            if ml_raw and ml_raw != "N/A":
                new_ml = float(ml_raw)
                if new_ml < 50:
                    # Sanity check: Kulhad may have test data (e.g. 5 ml).
                    # A real dispense volume should be 50–200 ml.
                    print(f"⚠️ [Config] mlToDispense={new_ml} ml is too low — "
                          f"looks like test data, keeping {self.ml_to_dispense} ml")
                    new_ml = self.ml_to_dispense  # ignore bad value
                ml_changed = (new_ml != self.ml_to_dispense)
                self.ml_to_dispense = new_ml

                if ml_changed:
                    duration_ms = ml_to_pump_ms(new_ml)
                    updated.append(f"mlToDispense={new_ml} ml → {duration_ms} ms")

                    # Sync the new duration to the ESP32 in its own thread
                    # so this config thread is never blocked by the 35 s
                    # polling-server → ESP32 round-trip.
                    if DEVICE_ID:
                        threading.Thread(
                            target=lambda d=duration_ms: (
                                self.api_client.update_pump_settings(DEVICE_ID, d),
                                print(f"📡 [Config] ESP32 pump duration updated: {d} ms")
                            ),
                            daemon=True
                        ).start()

            if updated:
                print(f"🔄 [Config] Cache updated from Kulhad: {', '.join(updated)}")
            else:
                print(f"✅ [Config] Cache up to date "
                      f"(flush={self.flush_time_minutes} min, ml={self.ml_to_dispense} ml)")

        except Exception as e:
            print(f"❌ [Config] Cache refresh error: {e}")

    def _fetch_flush_timing_and_schedule(self):
        """Arm the flush idle timer using flushTimeMinutes from Kulhad.
        Falls back to 40 minutes if the cached value hasn't been fetched yet.
        """
        delay_seconds = self.flush_time_minutes * 60
        print(f"💧 [Flush] Idle timer armed: {self.flush_time_minutes} min ({delay_seconds:.0f}s)")
        Clock.schedule_once(lambda dt: self._arm_flush_timer(delay_seconds), 0)

    def _arm_flush_timer(self, delay_seconds):
        """Arm the Clock timer (main thread only)."""
        if self.flush_timer_event is not None:
            return  # new order already cancelled this while we were fetching
        self.flush_timer_event = Clock.schedule_once(self._trigger_auto_flush, delay_seconds)

    def cancel_auto_flush(self):
        """Cancel a pending auto flush (called when a new order starts)."""
        if self.flush_timer_event:
            self.flush_timer_event.cancel()
            self.flush_timer_event = None
            print("💧 [Flush] Timer cancelled — new order started")

    def _trigger_auto_flush(self, dt):
        """Called by Kivy Clock when the idle timer fires — set state and start flush."""
        self.flush_timer_event = None
        self.flush_in_progress = True

        # Navigate to flush page only from pages where no active order is running
        safe_to_redirect = {
            'payment_method', 'machine_empty', 'screensaver',
            'selection', 'qr_expired', 'thank_you'
        }
        if self.screen_manager.current in safe_to_redirect:
            self.flush_page.show_waiting()
            self.show_page('flush')

        print("💧 [Flush] Idle timer fired — launching water flush followed by tea flush...")
        threading.Thread(target=self._run_auto_flush, daemon=True).start()

    def _run_auto_flush(self):
        """Execute maintenance flush — waits for ESP32 success on each step."""
        from config import DEVICE_ID
        try:
            # ── Step 1: Water flush — wait for ESP32 success ─────────────────
            print(f"💧 [Flush] Sending water flush → {DEVICE_ID}...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('water'), 0)
            water_result = self.api_client.water_flush(DEVICE_ID)

            if water_result:
                print(f"✅ [Flush] Water flush complete: {water_result}")
            else:
                print("❌ [Flush] Water flush command failed — continuing to tea flush")

            # ── Step 2: Tea flush — wait for ESP32 success ──────────────────
            print(f"🍵 [Flush] Sending tea flush → {DEVICE_ID}...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('tea'), 0)
            tea_result = self.api_client.tea_flush(DEVICE_ID)

            if tea_result:
                print(f"✅ [Flush] Tea flush complete: {tea_result}")
            else:
                print("❌ [Flush] Tea flush command failed — check polling server")

        except Exception as e:
            print(f"❌ [Flush] Error during flush: {e}")
        finally:
            self.flush_in_progress = False
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('done'), 0)
            print("✅ [Flush] Auto flush cycle complete — returning to payment page")
            Clock.schedule_once(
                lambda dt: self.show_payment_method_page(fetch_cups=True), 1
            )

    # *** SCHEDULED FLUSH MONITOR (Kulhad API-driven) ***

    def start_scheduled_flush_monitor(self):
        """Start a 5-minute periodic check that polls the Kulhad API for the flush
        schedule and triggers water + tea flush when a configured time arrives.
        """
        self.stop_scheduled_flush_monitor()
        # Run the first check after 60 s (let the app finish startup first)
        self.scheduled_flush_check_event = Clock.schedule_interval(
            self._check_scheduled_flush, 300  # every 5 minutes
        )
        print("🕐 Scheduled flush monitor started (check every 5 min)")

    def stop_scheduled_flush_monitor(self):
        """Stop the scheduled flush monitor."""
        if self.scheduled_flush_check_event:
            self.scheduled_flush_check_event.cancel()
            self.scheduled_flush_check_event = None
            print("🛑 Scheduled flush monitor stopped")

    def _check_scheduled_flush(self, dt):
        """Kivy Clock callback — offload the actual check to a background thread."""
        threading.Thread(target=self._do_scheduled_flush_check, daemon=True).start()

    def _do_scheduled_flush_check(self):
        """Every 5 minutes: refresh both flushTimeMinutes and mlToDispense from Kulhad.
        Uses the unified cache refresh so any Kulhad change is picked up automatically
        and the ESP32 is re-synced if mlToDispense changed.
        """
        self._refresh_machine_config_cache()

    # *** LOCAL CUPS COUNTER METHODS ***
    def get_local_cups_count(self):
        """Get the locally stored cups count"""
        return self.local_cups_count if self.local_cups_count is not None else 0
    
    def set_local_cups_count(self, count):
        """Set the local cups count and update UI"""
        self.local_cups_count = count
        self.cups_count_initialized = True
        print(f"📦 Local cups count set to: {count}")
        
        # Check if cups are exactly 5 and alert hasn't been sent
        print(f"🔍 DEBUG: count={count}, canister_alert_sent={self.canister_alert_sent}")
        if count == 5 and not self.canister_alert_sent:
            print(f"🔔 Cups are at 5! Sending canister alert...")
            self.send_canister_alert()
            self.canister_alert_sent = True
        # Reset alert flag if cups go above 5 (refilled)
        elif count > 5:
            if self.canister_alert_sent:
                print(f"🔄 Cups refilled to {count}, resetting alert flag")
            self.canister_alert_sent = False
        
        # Update payment method page display
        if hasattr(self.payment_method_page, 'update_cups_display'):
            Clock.schedule_once(lambda dt: self.payment_method_page.update_cups_display(count))
    
    def decrement_local_cups(self, num_cups=1):
        """Decrement local cups count (when dispensing)"""
        if self.local_cups_count is not None:
            self.local_cups_count = max(0, self.local_cups_count - num_cups)
            print(f"📦 Local cups decremented by {num_cups}, new count: {self.local_cups_count}")
            
            # Check if cups reached exactly 5 and alert hasn't been sent
            print(f"🔍 DEBUG: after decrement count={self.local_cups_count}, canister_alert_sent={self.canister_alert_sent}")
            if self.local_cups_count == 5 and not self.canister_alert_sent:
                print(f"🔔 Cups reached 5 after dispensing! Sending canister alert...")
                self.send_canister_alert()
                self.canister_alert_sent = True
            
            # Reset alert flag if cups go above 5 (refilled)
            elif self.local_cups_count > 5:
                if self.canister_alert_sent:
                    print(f"🔄 Cups refilled to {self.local_cups_count} after dispensing, resetting alert flag")
                self.canister_alert_sent = False
            
            # Update payment method page display
            if hasattr(self.payment_method_page, 'update_cups_display'):
                Clock.schedule_once(lambda dt: self.payment_method_page.update_cups_display(self.local_cups_count))
        else:
            print("⚠️ Cannot decrement cups - local count not initialized")
    
    def fetch_and_store_cups_count(self):
        """Fetch cups count from API and store locally (called on state transitions)"""
        def fetch_in_background():
            try:
                print("🔄 Fetching cups count from API...")
                cups_data = self.api_client.get_remaining_cups(self.MACHINE_ID)
                
                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    Clock.schedule_once(lambda dt: self.set_local_cups_count(cups_count))
                    print(f"✅ Fetched and stored cups count: {cups_count}")
                    
                    # Reset alert flag if cups are refilled (> 5)
                    if cups_count > 5:
                        self.canister_alert_sent = False
                else:
                    print("❌ Failed to fetch cups count from API")
            except Exception as e:
                print(f"❌ Error fetching cups count: {e}")
        
        # Run in background thread
        threading.Thread(target=fetch_in_background, daemon=True).start()
    
    def send_canister_alert(self):
        """Send canister level alert when cups reach 5"""
        print(f"🔔 DEBUG: send_canister_alert() called for machine {self.MACHINE_ID}")
        
        def send_alert_in_background():
            try:
                print(f"🔔 DEBUG: Calling API check_canister_level()...")
                result = self.api_client.check_canister_level(self.MACHINE_ID, canister_level=5)
                if result:
                    print(f"✅ DEBUG: Canister alert API call successful")
                else:
                    print(f"❌ DEBUG: Canister alert API call failed - no result")
            except Exception as e:
                print(f"❌ DEBUG: Error sending canister alert: {e}")
        
        # Run in background thread
        print(f"🔔 DEBUG: Starting background thread for canister alert...")
        threading.Thread(target=send_alert_in_background, daemon=True).start()
        print(f"🔔 DEBUG: Background thread started")
    
    def handle_dispense_error(self, status_code):
        """Route ESP32 dispense error codes to the appropriate page.
        Called from place_cup_page when ESP32 returns a non-200 status code.
        """
        print(f"⚠️ [Dispense] ESP32 error code: {status_code}")
        if status_code == 700:
            # Water temperature too low — show heating page
            print("🔥 [Dispense] Temperature low (700) — redirecting to heating page")
            temp = hardware_monitor.get_pt100_temperature()
            Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
        elif status_code == 701:
            print("🌡️ [Dispense] Temperature critical (701) — showing hardware error")
            Clock.schedule_once(
                lambda dt: self.show_hardware_error("Temperature critical — contact support"), 0
            )
        else:
            # All other error codes stay on place_cup_page for retry
            pass

    def reduce_cups_after_payment(self):
        """DEPRECATED: Do not use. Cups should only be reduced when user clicks 'Confirm to Dispense' button.
        Kept for backward compatibility but should not be called.
        Use reduce_one_cup() from place_cup_page instead."""
        print("⚠️ WARNING: reduce_cups_after_payment() called - this should not happen!")
        print("⚠️ Cups should only reduce when 'Confirm to Dispense' is clicked")
        # Don't reduce cups here
        pass
    
    def reduce_one_cup(self):
        """Reduce 1 cup count when user clicks 'Confirm to Dispense' button"""
        # Call reduce cups API in a separate thread to avoid blocking UI
        threading.Thread(target=lambda: self.call_reduce_cups_api(cups_to_reduce=1), daemon=True).start()
    
    def call_reduce_cups_api(self, cups_to_reduce=None):
        """Call the reduce cups API in background thread
        Args:
            cups_to_reduce: Number of cups to reduce. If None, uses self.selected_cups
        """
        if cups_to_reduce is None:
            cups_to_reduce = self.selected_cups
            
        try:
            # Snapshot the count BEFORE decrementing so we can restore on failure
            count_before = self.local_cups_count

            # Decrement local counter IMMEDIATELY for instant UI update
            self.decrement_local_cups(cups_to_reduce)
            
            print(f"🔄 Sending cups reduction to backend: {cups_to_reduce} cup(s) from machine {self.MACHINE_ID}")
            
            # Call API to reduce cups (for backend sync)
            result = self.api_client.reduce_cups(self.MACHINE_ID, cups_to_reduce)
            
            if result and result.get("success", False):
                print(f"✅ Backend synced - reduced {cups_to_reduce} cup(s)")
                print(f"   Previous cups: {result.get('previousCups')}")
                print(f"   New cups: {result.get('newCups')}")
                print(f"   Message: {result.get('message')}")
            else:
                print("❌ Failed to sync cups reduction to backend — retrying once...")
                print(f"   API Response: {result}")
                # Retry once
                result = self.api_client.reduce_cups(self.MACHINE_ID, cups_to_reduce)
                if result and result.get("success", False):
                    print(f"✅ Retry succeeded — backend synced {cups_to_reduce} cup(s)")
                else:
                    # Both attempts failed — restore local counter to prevent divergence
                    print("❌ Retry also failed — restoring local counter to avoid UI divergence")
                    if count_before is not None:
                        Clock.schedule_once(lambda dt: self.set_local_cups_count(count_before))
                    
        except Exception as e:
            print(f"❌ Error calling reduce cups API: {e}")
    
    def generate_qr_code(self, number_of_cups):
        """⚡ Generate QR code — OPT 1: skip redundant machine status HTTP call.

        The global monitor (check_global_machine_status) already hits the
        MachinesStatus endpoint every 10 seconds and stores the result in
        self.previous_machine_state.  Re-checking it here costs an extra
        ~2s HTTP round-trip that runs IN PARALLEL but still holds a
        connection-pool slot and clutters the logs.

        We use the cached state instead.  If the cached state has never been
        set (app just started), we fall back to a direct API call so we
        never skip the check on the very first request.
        """
        import time
        start_time = time.time()
        try:
            print(f"🚀 Starting QR generation for {number_of_cups} cups...")

            # ── OPT 1: Use cached machine status from global monitor ──
            cached_state = getattr(self, 'previous_machine_state', None)

            if cached_state is None:
                # First request ever — no cache yet, do a real check
                print("🔄 No cached machine state — doing direct status check")
                status_data = self.api_client.check_machine_status(self.MACHINE_ID)
                if not status_data or not status_data.get("success", False):
                    print(f"❌ Machine status check failed: {status_data}")
                    Clock.schedule_once(lambda dt: self.show_error_fallback())
                    return
                machine_status = status_data.get("data", {}).get("status", "").lower()
                if machine_status != "online":
                    print(f"❌ Machine is {machine_status} during QR generation")
                    Clock.schedule_once(lambda dt: self.show_error_fallback())
                    return
            else:
                # Use cached result — saves one full HTTP round-trip
                if cached_state != "online":
                    print(f"❌ Cached machine state is '{cached_state}' — aborting QR generation")
                    Clock.schedule_once(lambda dt: self.show_error_fallback())
                    return
                print(f"✅ Machine status OK (cached: {cached_state}) — skipping status API call")

            # ── Now only run the QR generation call ──
            qr_data = self.api_client.generate_payment_qr(self.MACHINE_ID, number_of_cups)
            api_time = time.time() - start_time
            print(f"⏱️ QR API call completed in {api_time:.2f}s")
            
            # Machine is online, process QR generation result
            if qr_data:
                # NEW: Use imageContent directly to generate QR code
                image_content = qr_data.get("imageContent")
                
                if image_content:
                    print(f"⚡ Generating QR code from imageContent ({len(image_content)} chars)...")
                    qr_gen_start = time.time()
                    # Generate QR code directly from UPI string
                    qr_image = QRUtils.generate_qr_from_content(image_content)
                    qr_gen_time = time.time() - qr_gen_start
                    
                    if qr_image:
                        total_time = time.time() - start_time
                        print(f"✅ QR generation complete! Total: {total_time:.2f}s (QR image: {qr_gen_time:.3f}s)")
                        # Update payment page in main thread
                        Clock.schedule_once(lambda dt: self.update_payment_page(qr_image, qr_data))
                        return
                    else:
                        print("❌ QRUtils.generate_qr_from_content returned None")
                else:
                    # Fallback: Use old method with imageUrl (deprecated)
                    print("⚠️ imageContent not found in API response, falling back to imageUrl...")
                    print(f"   Available keys: {list(qr_data.keys())}")
                    image_url = qr_data.get("imageUrl")
                    
                    if image_url:
                        print(f"📥 Loading QR from URL: {image_url[:50]}...")
                        # Load QR image from URL
                        qr_image = QRUtils.load_qr_from_url(image_url)
                        
                        if qr_image:
                            # Detect and crop QR code
                            qr_image = QRUtils.detect_and_crop_qr(qr_image)
                            
                            total_time = time.time() - start_time
                            print(f"✅ QR from URL complete! Total: {total_time:.2f}s")
                            # Update payment page in main thread
                            Clock.schedule_once(lambda dt: self.update_payment_page(qr_image, qr_data))
                            return
                        else:
                            print("❌ Failed to load QR from URL")
                    else:
                        print("❌ No imageUrl available either")
            else:
                print("❌ qr_data is None - API call failed")
            
            # If we get here, there was an error
            total_time = time.time() - start_time
            print(f"❌ QR generation failed after {total_time:.2f}s - showing fallback")
            Clock.schedule_once(lambda dt: self.show_error_fallback())
        except Exception as e:
            total_time = time.time() - start_time
            print(f"❌ Error generating QR code after {total_time:.2f}s: {e}")
            import traceback
            traceback.print_exc()
            Clock.schedule_once(lambda dt: self.show_error_fallback())
    
    def update_payment_page(self, qr_image, data):
        """Update payment page with QR code and show it"""
        # Guard against double-delivery race: if a QR is already showing,
        # cancel the incoming duplicate so it is never orphaned on the backend.
        incoming_id = data.get('id', '') if data else ''
        if self.current_qr_code_id and self.current_qr_code_id != incoming_id:
            stale_id = incoming_id
            if stale_id:
                threading.Thread(
                    target=lambda qid=stale_id: self.api_client.cancel_payment(qid),
                    daemon=True
                ).start()
                print(f"🗑️ Duplicate QR delivery — cancelling stale {stale_id}")
            return

        # Cancel loading timeout since we successfully generated QR
        self.cancel_loading_timeout()

        # Resume RF keep-alive now that loading animation is done
        if hasattr(self, 'rfid_auth_handler') and self.rfid_auth_handler:
            self.rfid_auth_handler.resume_keepalive()

        # Update payment page with QR data
        self.payment_page.update(qr_image, data)

        # Get the QR code ID for status checking
        self.current_qr_code_id = self.payment_page.get_qr_code_id()

        # Set timer expiration callback
        self.payment_page.set_timer_callback(self.on_timer_expired)

        # Show the payment page
        self.show_page('payment')

        # Start payment status checking
        self.start_payment_status_check()
    
    def show_error_fallback(self, is_retry=False):
        """Show an error popup when QR generation fails with retry option"""
        # Cancel loading timeout
        self.cancel_loading_timeout()
        
        # Stop loading animation
        self.loading_page.stop_animation()
        
        # Resume RF keep-alive now that loading animation is done
        if hasattr(self, 'rfid_auth_handler') and self.rfid_auth_handler:
            self.rfid_auth_handler.resume_keepalive()
        
        # If this is a retry attempt that failed, go directly to home
        if is_retry:
            print("⚠️ Retry also failed - going to home screen")
            self.show_selection_page()
            return
        
        # Show error popup with Retry button
        from ui_pages.error_popup import QRErrorPopup
        
        def on_retry():
            """Called when user clicks Retry"""
            print(f"🔄 Retrying QR generation for {self.selected_cups} cups...")
            # Show loading page and retry with stored cup count
            self.show_loading_page()
            self.loading_timeout_event = Clock.schedule_once(
                lambda dt: self.show_error_fallback(is_retry=True), 15
            )
            # Retry QR generation in background thread
            import threading
            threading.Thread(
                target=lambda: self.generate_qr_code(self.selected_cups), 
                daemon=True
            ).start()
        
        def on_cancel():
            """Called when popup auto-dismisses (8 seconds timeout)"""
            print("⚠️ Retry not clicked - going to home screen")
            self.show_selection_page()
        
        popup = QRErrorPopup(
            on_retry_callback=on_retry,
            on_cancel_callback=on_cancel
        )
        popup.open()
    
    def start_payment_status_check(self):
        """Start checking payment status at regular intervals"""
        # Cancel any existing timer
        if self.status_check_event:
            self.status_check_event.cancel()
            self.status_check_event = None
        
        # Only start checking if we have a QR code ID
        if self.current_qr_code_id:
            # Schedule the first status check
            self.status_check_event = Clock.schedule_once(self.check_payment_status, 2)
    
    def check_payment_status(self, dt=None):
        """Check the payment status with the API — runs HTTP call in background thread"""
        # Only proceed if we have a QR code ID and current page is payment page
        if not self.current_qr_code_id or self.screen_manager.current != 'payment':
            return

        qr_id = self.current_qr_code_id

        def _do_check():
            status_data = self.api_client.check_payment_status(qr_id)
            Clock.schedule_once(lambda dt: self._handle_payment_status(status_data), 0)

        threading.Thread(target=_do_check, daemon=True).start()

    def _handle_payment_status(self, status_data):
        """Process payment status result on the main thread"""
        # Guard: page may have changed while the HTTP request was in flight
        if self.screen_manager.current != 'payment':
            return

        if status_data:
            status_message = status_data.get("message", "").lower()
            print(f"Payment status: {status_message}")

            if status_message == "active":
                self.status_check_event = Clock.schedule_once(self.check_payment_status, 2)

            elif status_message == "paid":
                self.payment_page.update_status("Payment received!")
                # Don't reduce cups here - will reduce when user clicks dispense
                Clock.schedule_once(lambda dt: self.show_dispensing_page(), 1.5)

            elif status_message == "expired":
                print("Payment expired, cancelling automatically")
                self.payment_page.update_status("Payment expired!")
                Clock.schedule_once(lambda dt: self.cancel_payment(auto_cancel=True), 1)

            else:  # Unknown status
                self.status_check_event = Clock.schedule_once(self.check_payment_status, 2)
        else:
            # Try again after 2 seconds if API call failed
            self.status_check_event = Clock.schedule_once(self.check_payment_status, 2)
    
    def cancel_payment(self, auto_cancel=False, timer_expired=False):
        """Cancel the current payment"""
        # Stop status checking
        if self.status_check_event:
            self.status_check_event.cancel()
            self.status_check_event = None

        # Discard all prefetched / in-flight QRs so no stale QR can appear
        # if the user immediately tries to pay again after cancelling.
        self.cancel_prefetched_qrs()

        # Navigate immediately (don't wait for API)
        if timer_expired:
            # Show QR expired page when timer expires
            self.show_page('qr_expired')
        else:
            # Always go back to home (payment_method) on cancel — not selection.
            # Going to selection left the prefetch cache intact, so pressing
            # Confirm immediately would serve the old (now-cancelled) QR.
            self.show_payment_method_page()

        # Call API to cancel payment in background (non-blocking)
        if self.current_qr_code_id:
            qr_id = self.current_qr_code_id
            self.current_qr_code_id = ""  # Reset immediately

            def cancel_in_background():
                self.api_client.cancel_payment(qr_id)
            threading.Thread(target=cancel_in_background, daemon=True).start()
    
    def select_video_file(self):
        """Allow user to select a video file for screensaver"""
        def on_selection(chooser, selection):
            if selection:
                self.video_path = selection[0]
                self.screensaver_page.set_video_path(selection[0])
                popup.dismiss()
        
        def on_cancel(instance):
            popup.dismiss()
        
        # Create modern file chooser layout
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        file_chooser = FileChooserListView(
            filters=['*.mp4', '*.avi', '*.mov', '*.mkv', '*.webm'],
            path=os.path.expanduser('~')
        )
        file_chooser.bind(on_submit=on_selection)
        
        # Button layout
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, 
                                height=50, spacing=10)
        
        cancel_btn = Button(text='Cancel', size_hint_x=0.5)
        cancel_btn.bind(on_press=on_cancel)
        
        select_btn = Button(text='Select', size_hint_x=0.5)
        select_btn.bind(on_press=lambda x: on_selection(file_chooser, file_chooser.selection))
        
        button_layout.add_widget(cancel_btn)
        button_layout.add_widget(select_btn)
        
        content.add_widget(file_chooser)
        content.add_widget(button_layout)
        
        popup = Popup(title='Select Video File for Screensaver',
                     content=content,
                     size_hint=(0.9, 0.9))
        popup.open()
    
    def setup_screensaver_monitoring(self):
        """Setup monitoring for user inactivity to trigger screensaver"""
        # Register user activity events
        Window.bind(on_motion=self.reset_activity_timer)
        Window.bind(on_key_down=self.on_key_press)  # Handle ESC key for exit
        Window.bind(on_touch_down=self.reset_activity_timer)
        
        # Start monitoring for inactivity (store reference for cleanup)
        self.activity_monitor_event = Clock.schedule_interval(self.monitor_activity, 1)
    
    def reset_activity_timer(self, *args):
        """Reset the activity timer when user interacts with the app"""
        self.last_activity_time = time.time()
        
        # If screensaver is active, deactivate it
        if self.screensaver_active:
            self.deactivate_screensaver()
    
    def monitor_activity(self, dt):
        """Monitor for user inactivity to trigger screensaver"""
        current_time = time.time()
        elapsed = current_time - self.last_activity_time
        
        # Activate screensaver on payment method page or machine empty page
        current_page = self.screen_manager.current
        is_screensaver_eligible_page = current_page in ['payment_method', 'machine_empty']
        
        if elapsed >= self.INACTIVE_TIMEOUT and not self.screensaver_active and is_screensaver_eligible_page:
            if self.video_path and os.path.exists(self.video_path):
                self.activate_screensaver()
            else:
                print(f"Video file not found: {self.video_path}")
    
    def activate_screensaver(self):
        """Activate the screensaver"""
        print("Activating screensaver...")
        # Remember which page we were on before screensaver
        self.previous_page_before_screensaver = self.screen_manager.current
        self.screensaver_active = True
        self.show_page('screensaver')
            
    def deactivate_screensaver(self):
        """Deactivate the screensaver - navigate immediately using local cups count"""
        self.screensaver_active = False
        print("⚡ Deactivating screensaver - navigating immediately...")
        
        # INSTANT NAVIGATION - show home page immediately with local cups count
        self.show_payment_method_page()
        
        # No API call needed - local cups count is already available
        print(f"📦 Using local cups count: {self.local_cups_count}")
    
    def check_machine_status_background(self):
        """Check machine status in background with parallel API calls and fetch cups count"""
        try:
            # Wait a moment to let home page render first
            time.sleep(0.3)
            
            print("🔄 Fetching machine status and cups count (transition to home)...")
            
            status_result = [None]
            cups_result = [None]
            
            def fetch_status():
                """Parallel thread 1: Get machine status"""
                try:
                    status_result[0] = self.api_client.check_machine_status(self.MACHINE_ID)
                except Exception as e:
                    print(f"Status check error: {e}")
            
            def fetch_cups():
                """Parallel thread 2: Get cups count"""
                try:
                    cups_result[0] = self.api_client.get_remaining_cups(self.MACHINE_ID)
                except Exception as e:
                    print(f"Cups check error: {e}")
            
            # Run both API calls in parallel
            t1 = threading.Thread(target=fetch_status, daemon=True)
            t2 = threading.Thread(target=fetch_cups, daemon=True)
            
            t1.start()
            t2.start()
            
            # Wait for both (max 3 seconds)
            t1.join(timeout=3)
            t2.join(timeout=3)
            
            # Process results
            is_online = True
            cups_count = 0
            
            if status_result[0] and status_result[0].get("success", False):
                data = status_result[0].get("data", {})
                machine_status = data.get("status", "offline")
                is_online = machine_status.lower() == "online"
            
            if cups_result[0] and cups_result[0].get("success", False):
                cups_count = cups_result[0].get("cups", 0)
                # Store locally for future use
                Clock.schedule_once(lambda dt: self.set_local_cups_count(cups_count))
            
            # Navigate based on results
            if not is_online:
                print("⚠️ Machine offline detected - switching to machine empty page")
                Clock.schedule_once(lambda dt: self.show_page('machine_empty'), 0)
            elif cups_count <= 0:
                print("⚠️ No cups available - switching to machine empty page")
                Clock.schedule_once(lambda dt: self.show_page('machine_empty'), 0)
            else:
                print(f"✅ Machine online with {cups_count} cups - staying on home page")
        
        except Exception as e:
            print(f"Background status check error: {e}")
            # Stay on home page if check fails
    
    def on_timer_expired(self):
        """Handle payment timer expiration"""
        print("Timer expired - cancelling payment and showing expiration page")
        # Cancel payment with timer_expired flag
        self.cancel_payment(timer_expired=True)
    
    def setup_hardware_error_monitoring(self):
        """Setup monitoring for hardware errors"""
        # Check for errors every 2 seconds (store reference for cleanup)
        self.hardware_error_monitor_event = Clock.schedule_interval(self.check_hardware_errors, 2)
        
    def check_hardware_errors(self, dt):
        """Check for hardware errors and navigate to error page if needed"""
        current_screen = self.screen_manager.current
        
        # Don't check during critical operations to avoid interrupting them
        critical_screens = ['dispensing', 'place_cup', 'payment', 'thank_you', 'heating']  # Removed 'transaction_processing'
        if current_screen in critical_screens:
            # Skip error checking during critical operations
            return
        
        error_msg = hardware_monitor.get_latest_error()
        
        # Only show error page if we're not already on it and there's an error
        if error_msg and current_screen != 'hardware_error':
            print(f"Hardware error detected: {error_msg} - Navigating to error page")
            self.show_hardware_error(error_msg)
    
    def show_hardware_error(self, error_message):
        """Navigate to hardware error page with a custom error message"""
        print(f"Showing hardware error page: {error_message}")
        if hasattr(self.hardware_error_page, 'set_error_message'):
            self.hardware_error_page.set_error_message(error_message)
        self.show_page('hardware_error')
    
    def check_heating_on_startup(self):
        """Check temperature on startup. Always mandatory — no bypass exists.
        Shows heating page if temp < SERVING_TEMP; navigates to home once ready.
        """
        from config import SERVING_TEMP
        def check_temp_background():
            try:
                # Check PT100 temperature
                temp = hardware_monitor.get_pt100_temperature()

                # Reject readings outside valid water range (open-circuit PT100
                # can spike to 300-400°C; short-circuit reads near -10°C or 0°C).
                if temp is not None and (temp < -10 or temp > 120):
                    print(f"⚠️ PT100 startup read {temp}°C — out of range, treating as sensor error")
                    temp = None

                if temp is None:
                    print("⚠️ Can't read temperature at startup — showing heating page as safe default")
                    Clock.schedule_once(lambda dt: self.show_heating_page(None), 0)
                elif temp < SERVING_TEMP:
                    print(f"🔥 Tea is heating: {temp:.1f}°C (target: {SERVING_TEMP}°C)")
                    Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
                else:
                    print(f"✅ Tea is ready: {temp:.1f}°C")
                    Clock.schedule_once(lambda dt: self.show_payment_method_page(fetch_cups=True), 0)

            except Exception as e:
                print(f"Heating check error: {e}")
                # On exception also default to heating page — safer than assuming ready
                Clock.schedule_once(lambda dt: self.show_heating_page(None), 0)
        
        # Run in background thread
        threading.Thread(target=check_temp_background, daemon=True).start()
    
    def setup_idle_temperature_monitoring(self):
        """Monitor temperature when the app is on payment_method or screensaver page.
        If the temperature falls below 80°C, it automatically redirects to the heating page.
        """
        self._idle_temp_checking = False
        self._idle_temp_event = Clock.schedule_interval(self.check_idle_temperature, 5.0)  # Check every 5 seconds

    def check_idle_temperature(self, dt):
        current_page = self.screen_manager.current
        # Only check on payment_method or screensaver screens
        if current_page not in ['payment_method', 'screensaver']:
            return

        # Avoid overlapping read threads
        if hasattr(self, '_idle_temp_checking') and self._idle_temp_checking:
            return

        self._idle_temp_checking = True

        def _do_check():
            try:
                temp = hardware_monitor.get_pt100_temperature()
                # Reject invalid readings (out of bounds)
                if temp is not None and (temp < -10 or temp > 120):
                    temp = None

                from config import SERVING_TEMP
                if temp is not None and temp < SERVING_TEMP:
                    print(f"🔥 Idle temp check: temperature is low ({temp:.1f}°C < {SERVING_TEMP}°C). Redirecting to heating page.")
                    # Transition to heating page on the Kivy main thread
                    Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
            except Exception as e:
                print(f"Error in idle temperature check: {e}")
            finally:
                self._idle_temp_checking = False

        threading.Thread(target=_do_check, daemon=True).start()

    def show_heating_page(self, current_temp):
        """Show heating page and start temperature monitoring"""
        # Enable fast polling mode in hardware monitor
        hardware_monitor.enable_heating_mode()
        
        # Update temperature
        self.heating_page.update_temperature(current_temp)
        
        # Navigate to heating page
        self.show_page('heating')
        
        # Start fast polling (every 1 second)
        self.start_heating_monitor()
    
    def start_heating_monitor(self):
        """Monitor temperature every 1 second until ready.

        The hardware I2C read runs in a background thread so it never blocks
        the Kivy main thread (which caused the page to stutter / 'come and go').
        A poll-running guard prevents multiple concurrent reads if a read takes
        longer than 1 second. All UI updates and navigation are marshalled back
        to the main thread via Clock.schedule_once.
        """
        print("🔥 Starting heating monitor (checking every 1 second)")

        self.heating_temp_error_count = 0
        self.heating_ready_count = 0       # consecutive readings >= 80°C required
        self._heating_poll_running = False  # guard: only one read in flight at a time
        self.heating_start_time = time.time()  # used to detect a never-responding sensor

        def _handle_result(temp, exc):
            """Process result on the Kivy main thread."""
            # Page-guard: if we already left heating (e.g. RFID maintenance),
            # discard stale results — never navigate based on them.
            if self.screen_manager.current != 'heating':
                return

            # Reject temperatures outside the physically valid water range.
            # < -10°C: clearly disconnected/short. > 120°C: open-circuit spike
            # (water can't exceed ~100°C at atmospheric pressure; 384°C is a
            # known artifact when the PT100 wire loses contact).
            if temp is not None and (temp < -10 or temp > 120):
                print(f"⚠️ PT100 returned {temp}°C — treating as sensor error (out of range)")
                exc = Exception(f"PT100 invalid reading: {temp}°C")
                temp = None

            # Real exception from the read attempt → count as hardware error
            if exc is not None:
                self.heating_temp_error_count += 1
                print(f"⚠️ Temperature read error ({self.heating_temp_error_count}/3): {exc}")
                if self.heating_temp_error_count >= 3:
                    print("❌ Multiple temperature read failures - showing hardware error page")
                    self.stop_heating_monitor()
                    self.show_hardware_error("Temperature sensor error")
                return

            # temp is None but no exception — _temperature_loop hasn't returned a
            # reading yet (ESP32 poll cycle takes a few seconds).  Show placeholder
            # and keep waiting.  Only escalate if no data arrives within 120 s.
            if temp is None:
                elapsed = time.time() - self.heating_start_time
                if elapsed > 300:
                    print("❌ No temperature data after 300 s — sensor not responding")
                    self.stop_heating_monitor()
                    self.show_hardware_error("Temperature sensor not responding")
                else:
                    self.heating_page.update_temperature(None)
                return

            # Good read — reset error streak and update display
            self.heating_temp_error_count = 0
            self.heating_page.update_temperature(temp)

            from config import SERVING_TEMP
            if temp >= SERVING_TEMP:
                self.heating_ready_count += 1
                print(f"🌡️ Above target: {temp:.1f}°C (confirm {self.heating_ready_count}/3)")
                if self.heating_ready_count < 3:
                    return
                print(f"✅ Tea ready at {temp:.1f}°C - navigating to home")
                self.stop_heating_monitor()
                self.show_payment_method_page(fetch_cups=True)
            else:
                self.heating_ready_count = 0
                print(f"🔥 Heating: {temp:.1f}°C / {SERVING_TEMP}°C")

        def _read_temp_background():
            """Run in a background daemon thread — never on the main thread."""
            temp, exc = None, None
            try:
                # Call _fetch_temperature() directly so the heating page always
                # gets a fresh reading from ESP32, not a possibly-stale cache.
                temp = hardware_monitor._fetch_temperature()
                if temp is not None:
                    hardware_monitor.last_temperature = temp
            except Exception as e:
                exc = e
            finally:
                self._heating_poll_running = False
            Clock.schedule_once(lambda dt: _handle_result(temp, exc), 0)

        def _trigger_read(dt):
            """Called by Clock every second. Skips tick if previous read still running."""
            if self._heating_poll_running:
                return  # previous read hasn't finished — skip this tick
            if self.screen_manager.current != 'heating':
                return  # already navigated away — interval will be cancelled shortly
            self._heating_poll_running = True
            threading.Thread(target=_read_temp_background, daemon=True).start()

        # Schedule tick every 1 second (reads happen in background threads)
        self.heating_check_event = Clock.schedule_interval(_trigger_read, 1)
    
    def stop_heating_monitor(self):
        """Stop heating temperature monitoring"""
        # Disable fast polling mode in hardware monitor
        hardware_monitor.disable_heating_mode()
        
        if hasattr(self, 'heating_check_event') and self.heating_check_event:
            self.heating_check_event.cancel()
            self.heating_check_event = None
            print("⏹️ Stopped heating monitor")
    
    def on_key_press(self, window, key, *args):
        """Handle keyboard events"""
        # ESC key = 27
        if key == 27:
            # SAFETY: Only allow ESC exit from home/screensaver pages.
            # Pressing ESC mid-dispense was killing the app abruptly.
            safe_exit_pages = ['payment_method', 'screensaver', 'machine_empty', 'hardware_error']
            current_page = self.screen_manager.current
            if current_page in safe_exit_pages:
                print("\n🚶 ESC key pressed on home screen - Shutting down gracefully...")
                self.stop()
            else:
                print(f"\n⚠️ ESC key pressed on '{current_page}' - IGNORED (use Back button to navigate)")
            return True
        
        # F11 key = 292
        if key == 292:
            print("\n📺 F11 pressed - Toggling Fullscreen")
            Window.fullscreen = not Window.fullscreen
            return True
        
        # Reset activity timer for any other key
        self.reset_activity_timer(window, key, *args)
        return False
    
    def on_stop(self):
        """Called when app is closing"""
        print("\n🛑 Application closing - Cleaning up...")
        
        try:
            # Stop heating monitor if running
            self.stop_heating_monitor()

            # Stop idle temperature monitoring if running
            if hasattr(self, '_idle_temp_event') and self._idle_temp_event:
                self._idle_temp_event.cancel()
                self._idle_temp_event = None

            # Stop scheduled flush monitor
            self.stop_scheduled_flush_monitor()

            # Stop global status monitoring
            self.stop_global_status_monitoring()
            
            # Stop payment status checking
            if hasattr(self, 'status_check_event') and self.status_check_event:
                self.status_check_event.cancel()
                self.status_check_event = None
            
            # Stop any ongoing loading timeout
            if hasattr(self, 'loading_timeout_event') and self.loading_timeout_event:
                self.loading_timeout_event.cancel()
                self.loading_timeout_event = None
            
            # Stop activity monitor if running
            if hasattr(self, 'activity_monitor_event') and self.activity_monitor_event:
                self.activity_monitor_event.cancel()
                self.activity_monitor_event = None
            
            # Stop hardware error monitor if running
            if hasattr(self, 'hardware_error_monitor_event') and self.hardware_error_monitor_event:
                self.hardware_error_monitor_event.cancel()
                self.hardware_error_monitor_event = None
            
            # Stop RFID monitoring if running
            if hasattr(self, 'rfid_auth_handler') and self.rfid_auth_handler:
                try:
                    self.rfid_auth_handler.stop()
                except Exception as e:
                    print(f"Error stopping RFID handler: {e}")
            
            # Unbind window events
            try:
                Window.unbind(on_motion=self.reset_activity_timer)
                Window.unbind(on_key_down=self.on_key_press)
                Window.unbind(on_touch_down=self.reset_activity_timer)
            except Exception as e:
                print(f"Error unbinding window events: {e}")
            
            # Stop hardware monitoring (this will also stop polling_server2.py)
            hardware_monitor.stop()
            
            print("✓ Cleanup complete. Goodbye!\n")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        # Conditional force-exit: only triggers if the process truly hangs.
        # Previously this ALWAYS called os._exit(0) after 2 seconds, which
        # killed the app even during normal dispense flows if on_stop was
        # invoked prematurely (e.g. by an accidental ESC keypress).
        # Now we give 8 seconds for daemon threads to finish naturally.
        def force_exit(dt):
            print("⚡ Process did not exit cleanly - forcing exit now...")
            import os
            os._exit(0)
        
        Clock.schedule_once(force_exit, 8)  # Only fires if process hangs
        
        return super().on_stop()
    
    def start_global_status_monitoring(self):
        """Start global machine status monitoring that runs on all pages"""
        # Stop any existing monitoring first
        self.stop_global_status_monitoring()

        # Delay the first check by 30s so the network and Vercel API are settled
        # at boot before we start reading machine status. An immediate check at
        # autostart boot caused transient "offline" readings → heater cycling.
        def _start_interval(dt):
            self.check_global_machine_status(0)
            self.global_status_monitor_event = Clock.schedule_interval(
                self.check_global_machine_status,
                self.global_status_check_interval
            )
            print(f"🌐 Started GLOBAL machine status monitoring (every {self.global_status_check_interval} seconds)")

        Clock.schedule_once(_start_interval, 30)
        print("🌐 Global status monitoring will begin in 30s (network settle time)")
    
    def stop_global_status_monitoring(self):
        """Stop global machine status monitoring"""
        if self.global_status_monitor_event:
            self.global_status_monitor_event.cancel()
            self.global_status_monitor_event = None
            print("🛑 Stopped GLOBAL machine status monitoring")
    
    def check_global_machine_status(self, dt):
        """Check machine status in background - runs on all pages.
        screen_manager.current is read here (main thread) and passed to the
        background thread — Kivy properties are not thread-safe to read from
        OS threads.
        """
        current_page = self.screen_manager.current  # safe: called on main thread

        skip_pages = [
            'machine_empty',      # Already on offline page
            'screensaver',        # Screensaver active
            'place_cup',          # User placing cup
            'dispensing',         # Actively dispensing
            'thank_you',          # Showing thank you
            'rfid_auth',          # RFID authentication
            'heating',            # Tea heating
            'flush'               # Maintenance flush in progress
        ]

        if current_page in skip_pages:
            return

        if hasattr(self, '_checking_global_status') and self._checking_global_status:
            return

        self._checking_global_status = True
        threading.Thread(
            target=lambda: self._do_global_status_check(current_page),
            daemon=True
        ).start()

    def _do_global_status_check(self, current_page):
        """Perform global machine status check - only on home/selection/payment pages.
        current_page is passed in from the main thread to avoid unsafe cross-thread
        reads of screen_manager.current.
        """
        try:
            check_pages = ['payment_method', 'selection', 'payment', 'loading']

            if current_page not in check_pages:
                return
            
            # Check machine status
            status_data = self.api_client.check_machine_status(self.MACHINE_ID)
            
            if status_data and status_data.get("success", False):
                data = status_data.get("data", {})
                machine_status = data.get("status", "offline")
                is_online = machine_status.lower() == "online"
                
                # Track state for logging only — do NOT send set_state to ESP32.
                # Sending OFFLINE causes ESP32 firmware to shut down the heater,
                # which causes temperature cycling when cloud API has transient blips.
                if self.previous_machine_state is not None:
                    if self.previous_machine_state == "online" and not is_online:
                        print("🔴 Machine state changed: ONLINE → OFFLINE (UI only)")
                    elif self.previous_machine_state == "offline" and is_online:
                        print("🟢 Machine state changed: OFFLINE → ONLINE (UI only)")

                # Update previous state
                self.previous_machine_state = "online" if is_online else "offline"
                
                if not is_online:
                    # Machine went offline - navigate to machine empty page
                    print("⚠️ GLOBAL CHECK: Machine went OFFLINE - navigating to machine empty page")
                    Clock.schedule_once(lambda dt: self.show_page('machine_empty'), 0)
                    return
            
            # Also check cups count
            cups_data = self.api_client.get_remaining_cups(self.MACHINE_ID)
            if cups_data and cups_data.get("success", False):
                cups_count = cups_data.get("cups", 0)
                
                # Update local count
                Clock.schedule_once(lambda dt: self.set_local_cups_count(cups_count))
                
                if cups_count <= 0:
                    # Cups ran out - navigate to machine empty page
                    print("⚠️ GLOBAL CHECK: Cups = 0 - navigating to machine empty page")
                    Clock.schedule_once(lambda dt: self.show_page('machine_empty'), 0)
                    return
                    
        except Exception as e:
            print(f"Global status check error: {e}")
        finally:
            self._checking_global_status = False

    def send_machine_state_to_esp32(self, state, reason=None):
        """Send machine state change command to ESP32 device
        Args:
            state: "ONLINE" or "OFFLINE"
            reason: Optional reason for offline state (e.g., "malfunction", "status_check_offline")
        """
        def send_in_background():
            try:
                import uuid
                from config import DEVICE_ID
                
                command_id = f"cmd_set_{state.lower()}_{uuid.uuid4().hex[:6]}"
                
                payload = {
                    "messageType": "command",
                    "commandType": "control",
                    "version": "1.0",
                    "commandId": command_id,
                    "deviceId": DEVICE_ID,
                    "command": {
                        "action": "set_state",
                        "parameters": {
                            "machineState": state
                        }
                    }
                }
                
                # Add reason if offline
                if state == "OFFLINE" and reason:
                    payload["command"]["parameters"]["reason"] = reason
                
                print(f"📡 Sending {state} state to ESP32...")
                url = "http://localhost:5000/api/device/command"
                
                session = get_localhost_session()
                response = session.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    print(f"✅ ESP32 notified: Machine state set to {state}")
                else:
                    print(f"⚠️ Failed to notify ESP32: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error sending state to ESP32: {e}")
        
        # Send in background thread to avoid blocking
        threading.Thread(target=send_in_background, daemon=True).start()

    # def setup_automated_flushes(self):
    #     """
    #     Sets up periodic maintenance flushes.
    #     (Currently commented out for manual control)
    #     """
    #     from kivy.clock import Clock
    #     # # Schedule a water flush every 4 hours (14400 seconds)
    #     Clock.schedule_interval(self.trigger_periodic_flush, 14400)

    # def trigger_periodic_flush(self, dt):
    #     """
    #     Executes a periodic water flush.
    #     (Currently commented out for manual control)
    #     """
    #     print("🔄 SYSTEM: Triggering automated maintenance flush...")
    #     from config import DEVICE_ID
    #     self.api_client.water_flush(DEVICE_ID)
    #     self.api_client.tea_flush(DEVICE_ID)


if __name__ == "__main__":
    ChaiOrderingApp().run()

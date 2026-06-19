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

    def build(self):
        self.title = "Urban Kettle"

        # ── Device ID setup ──────────────────────────────────────────────────
        # DEVICE_ID is set manually in config.py — no auto-detection.
        import config as _cfg
        hardware_monitor.device_id = _cfg.DEVICE_ID
        print(f"✅ [Setup] Using DEVICE_ID: {_cfg.DEVICE_ID}")

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
        self.previous_machine_state = None  # Track previous state for logging
        self._offline_confirm_count = 0    # consecutive OFFLINE reads — debounce transient blips
        
        # *** Activity and hardware error monitoring ***
        self.activity_monitor_event = None
        self.hardware_error_monitor_event = None
        
        # *** NEW: Cup management variables ***
        self.selected_cups = 1  # Default number of cups
        self.current_cup_number = 1  # Current cup being dispensed
        self._dispensing_cups = False  # True while a multi-cup order is actively dispensing
        # Set to cup count when user confirmed order but temp is low — heating page
        # should generate QR and show payment page when done, not go home.
        self._pending_cups_after_heating = None
        # True when an RFID customer authenticated but temp was low — heating page
        # should go straight to dispensing (place_cup) when done, not a payment page.
        self._pending_rfid_dispense_after_heating = False

        # *** Dispense volume (from Kulhad getMachineData) ***
        self.ml_to_dispense = 100   # Default ml per cup; overridden by API on startup

        # *** Auto flush after inactivity ***
        # The Kulhad API exposes exactly ONE flush setting: flushTimeMinutes.
        # That is the idle time (in minutes) after the last dispense before the
        # machine runs its cleaning cycle.  Pump run-durations are fixed in
        # firmware — 20 s each — and are NOT configurable via the API.
        self.flush_timer_event = None           # Kivy Clock event for the idle flush
        self.flush_time_minutes = 40            # Default; overridden by Kulhad flushTimeMinutes on startup
        self.flush_duration_seconds = 20        # Seconds the pump runs per flush (fixed in firmware)
        self.scheduled_flush_check_event = None # Kivy Clock: refresh flush_time_minutes every 5 min

        # *** Flush-in-progress state (drives flush page UI) ***
        self.flush_in_progress = False          # True while water+tea flush is running
        self._flush_cancelled = True            # Prevents spurious timer arming at startup
        self._pending_refill_flush = False      # True when cups refilled — triggers refill flush before going home

        # *** Operating hours (from Kulhad startTime / endTime) ***
        self._operating_start  = None           # datetime.time — machine open time
        self._operating_end    = None           # datetime.time — machine close time
        self._operating_timers = []             # threading.Timer instances (cancelled on stop)

        # *** Water level low (ESP32 health_check → waterLevelLow) ***
        self._water_level_low_active = False    # True while showing the water-low maintenance page

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
        
        # Set initial screen to cup selection (home page)
        self.screen_manager.current = 'selection'
        self._current_page = 'selection'  # thread-safe mirror of screen_manager.current
        
        # Setup screensaver monitoring
        self.setup_screensaver_monitoring()
        
        # Setup hardware error monitoring
       #self.setup_hardware_error_monitoring()
        
        # Window setup — production vs test mode
        # Set UK_TEST_MODE=1 to run windowed on a desktop for development.
        import os as _os
        if _os.environ.get("UK_TEST_MODE"):
            # Desktop testing: windowed, no rotation, resizable
            Window.size = (881, 661)
            Window.resizable = True
            Window.fullscreen = False
            Window.rotation = 0
        else:
            # Production: lock to 7-inch tablet, fullscreen, upside-down mount
            Window.size = (881, 661)
            Window.minimum_width = 881
            Window.minimum_height = 661
            Window.maximum_width = 881
            Window.maximum_height = 661
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
                print("⚠️ RFID reader not active in PC/SC mode - HID keyboard fallback active")
        except Exception as e:
            print(f"❌ Failed to initialize RFID Auth Handler at startup: {e}")
            self.rfid_auth_handler = None

        # HID keyboard fallback — catches card numbers typed by readers
        # configured in USB HID mode (outputs decimal card number as keystrokes)
        try:
            from utils.rfid_reader import rfid_reader as _hid_reader
            _hid_reader.start_listening(self._on_hid_rfid_card)
            self._hid_rfid_reader = _hid_reader
            print("🏷️ HID RFID keyboard listener started")
        except Exception as e:
            print(f"⚠️ HID RFID listener failed to start: {e}")
        
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

        # Start always-on RFID monitor (handles pages without per-page polling)
        Clock.schedule_once(lambda dt: self._start_global_rfid_monitor(), 3)
        
        # flushTimeMinutes/mlToDispense/operatingHours load once at boot (line above),
        # then every 1 min via this monitor — needed so manual online/offline toggles
        # in Kulhad (and any other config change) are picked up without restarting.
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

        # Watchdog heartbeat: touch a file every 15s from a Clock callback, so it
        # only keeps updating while Kivy's main event loop is actually pumping —
        # a real UI/payment freeze stops this even though the process stays alive.
        # /etc/watchdog.conf on the Pi watches this file's mtime and reboots if it
        # goes stale (see setup_watchdog.sh).
        self._watchdog_heartbeat_event = Clock.schedule_interval(self._write_watchdog_heartbeat, 15)
        self._write_watchdog_heartbeat(0)

        return self.screen_manager

    def _write_watchdog_heartbeat(self, dt):
        try:
            with open("/tmp/urban_kettle_heartbeat", "w") as f:
                f.write(str(time.time()))
        except Exception as e:
            print(f"⚠️ [Watchdog] Could not write heartbeat file: {e}")
    
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
        self._pending_cups_after_heating = None  # safety reset
        self._pending_rfid_dispense_after_heating = False  # safety reset

        # Cups were just refilled — run refill flush before going to selection.
        if getattr(self, '_pending_refill_flush', False):
            self._pending_refill_flush = False
            Clock.schedule_once(lambda dt: self._trigger_refill_flush(), 0)
            return

        if self.flush_in_progress:
            self.flush_page.show_waiting()
            self.show_page('flush')
            return

        self.show_page('selection')
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

        # Clear any QR ID from a previous payment cycle so the duplicate-delivery
        # guard in update_payment_page() doesn't reject the incoming QR.
        self.current_qr_code_id = ""

        self.set_selected_cups(number_of_cups)
        self.show_loading_page()
        self.loading_timeout_event = Clock.schedule_once(self.on_loading_timeout, 30)
        
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
                pil_img = QRUtils.generate_qr_from_content(qr_data["imageContent"])
                # Pre-encode to PNG bytes here in the background thread so the
                # main thread only needs CoreImage(buf) — no PIL.save() on UI thread.
                import io as _io
                buf = _io.BytesIO()
                pil_img.save(buf, format='PNG')
                img = buf  # pass BytesIO to cache; update_qr_code() accepts both
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
        """Background QR prefetch for every achievable cup count (max 3).
        Only spawns workers for counts ≤ current stock so we never create
        Razorpay QRs that can never be used."""
        cups = self.local_cups_count
        max_cups = min(cups, 3) if cups is not None else 3
        if max_cups < 1:
            return
        print(f"🚀 PREFETCH: Starting background QR generation for 1–{max_cups} cups")
        for count in range(1, max_cups + 1):
            self.trigger_qr_prefetch(count)
    
    def on_loading_timeout(self, dt):
        """Called if loading page takes too long - prevents hanging"""
        if self.screen_manager.current == 'loading':
            print("⚠️ Loading page timeout (30s) - QR generation took too long")
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
        """Start the dispensing process for multiple cups."""
        self.current_cup_number = 1
        self._dispensing_cups = True  # guard: block machine_empty navigation mid-order
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
            self._dispensing_cups = False  # order done — machine_empty can show now if count=0
            # Refresh cups count after all dispensing is complete
            self.refresh_cups_count()
            self.show_thank_you_page()
            # Navigate to machine_empty if cups hit the empty threshold during the last dispense
            from config import MACHINE_EMPTY_THRESHOLD
            if self.local_cups_count is not None and self.local_cups_count <= MACHINE_EMPTY_THRESHOLD:
                def _show_empty_after_thankyou(dt):
                    self.machine_empty_page.set_mode('empty')
                    self.show_page('machine_empty')
                Clock.schedule_once(_show_empty_after_thankyou, 3.0)
            # Schedule auto water flush if no new order within flushTimeMinutes
            self.schedule_auto_flush()
    
    def refresh_cups_count(self):
        """Refresh the cups count on home pages"""
        if hasattr(self.payment_method_page, 'refresh_cups_count'):
            self.payment_method_page.refresh_cups_count()
        if hasattr(self.selection_page, 'refresh_cups_count'):
            self.selection_page.refresh_cups_count()

    # *** AUTO FLUSH METHODS ***
    def schedule_auto_flush(self):
        """After a dispense, arm the idle-flush timer.  If a new order arrives
        before the timer fires, cancel_auto_flush() resets everything.
        """
        self.cancel_auto_flush()       # cancel any previous timer first
        self._flush_cancelled = False  # then allow the new timer to be armed
        threading.Thread(target=self._fetch_flush_timing_and_schedule, daemon=True).start()

    def _refresh_machine_config_cache(self):
        """Fetch flushTimeMinutes and mlToDispense from Kulhad and update the local cache.

        Called once at startup and every 1 minute by the scheduled monitor.
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

            # ── Operating hours (startTime / endTime) ────────────────────────
            # Sourced from Kulhad only — no local fallback, so a missing/cleared
            # value on the machine record simply leaves the scheduler un-armed
            # rather than silently running a stale test window.
            start_str = (data.get("startTime") or data.get("openTime")
                         or data.get("start_time") or data.get("StartTime"))
            end_str   = (data.get("endTime")   or data.get("closeTime")
                         or data.get("end_time") or data.get("EndTime"))

            if start_str and end_str:
                new_start = self._parse_operating_time(str(start_str))
                new_end   = self._parse_operating_time(str(end_str))
                if new_start and new_end:
                    hours_changed = (new_start != self._operating_start
                                     or new_end != self._operating_end
                                     or not self._operating_timers)
                    if hours_changed:
                        updated.append(f"operatingHours={start_str}–{end_str}")
                        Clock.schedule_once(
                            lambda dt, s=str(start_str), e=str(end_str):
                                self._schedule_operating_hours(s, e), 0
                        )
            else:
                print("⚠️ [Config] No startTime/endTime in Kulhad — "
                      "operating hours scheduler not active")

            # ── Kulhad-commanded online/offline (manual dashboard toggle) ────
            # previous_machine_state reflects the Pi's own last-known real-world
            # state (from ESP32 health checks). If Kulhad's status disagrees with
            # it, an admin manually toggled the switch — apply that command.
            # Skipped on the very first call (previous_machine_state is still None
            # at startup, before the global status check has run even once).
            kulhad_status = str(data.get("status") or "").strip().lower()
            current_state = getattr(self, 'previous_machine_state', None)
            if kulhad_status in ("online", "offline") and current_state is not None \
                    and kulhad_status != current_state:
                print(f"📡 [Kulhad] Manual status change detected: {current_state} → {kulhad_status}")
                updated.append(f"kulhadCommand={kulhad_status}")
                if kulhad_status == "offline":
                    threading.Thread(target=self._operating_go_offline, daemon=True).start()
                else:
                    self.send_machine_state_to_esp32("ONLINE", None)
                    threading.Thread(
                        target=lambda: self.api_client.report_machine_status(self.MACHINE_ID, 'online'),
                        daemon=True
                    ).start()
                    Clock.schedule_once(lambda dt: self.check_heating_on_startup(), 0)

            if updated:
                print(f"🔄 [Config] Cache updated from Kulhad: {', '.join(updated)}")
            else:
                print(f"✅ [Config] Cache up to date "
                      f"(flush={self.flush_time_minutes} min, ml={self.ml_to_dispense} ml)")

        except Exception as e:
            print(f"❌ [Config] Cache refresh error: {e}")

    # =========================================================================
    # Operating hours — auto OFFLINE at close, auto ONLINE 40 min before open
    # =========================================================================

    @staticmethod
    def _parse_operating_time(time_str):
        """Parse Kulhad time strings → datetime.time or None.
        Kulhad stores times from an HTML <input type='time'> which always
        produces HH:MM 24-hour format (e.g. '09:00', '22:00').
        AM/PM variants are also accepted as a fallback.
        """
        if not time_str:
            return None
        from datetime import datetime as _dt
        for fmt in ('%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M%p', '%I %p'):
            try:
                return _dt.strptime(str(time_str).strip(), fmt).time()
            except ValueError:
                continue
        print(f"⚠️ [OperatingHours] Cannot parse time: '{time_str}'")
        return None

    def _schedule_operating_hours(self, start_str, end_str):
        """Schedule daily close (OFFLINE at end_str) and pre-start (ONLINE 40 min before start_str).
        Also immediately goes offline if the app starts inside a closed window.
        Called on the Kivy main thread so show_page() is safe to call.
        """
        from datetime import datetime as _dt, timedelta as _td

        start_t = self._parse_operating_time(start_str)
        end_t   = self._parse_operating_time(end_str)
        if not start_t or not end_t:
            print(f"⚠️ [OperatingHours] Invalid times — skipping scheduler")
            return

        # Cancel previous timers before rescheduling
        for t in self._operating_timers:
            t.cancel()
        self._operating_timers.clear()

        self._operating_start = start_t
        self._operating_end   = end_t
        PRE_MINUTES = 40

        now       = _dt.now()
        now_t     = now.time()
        prestart_t = (_dt.combine(now.date(), start_t) - _td(minutes=PRE_MINUTES)).time()

        print(f"🕐 [OperatingHours] Open {start_t.strftime('%I:%M %p')} → "
              f"Close {end_t.strftime('%I:%M %p')} | "
              f"Pre-start ONLINE at {prestart_t.strftime('%I:%M %p')}")

        # ── Are we currently in the closed window? ──────────────────────────
        # Open window: prestart_t … (end_t + 30 min grace)
        POST_MINUTES = 30
        offline_t = (_dt.combine(now.date(), end_t) + _td(minutes=POST_MINUTES)).time()
        if prestart_t < offline_t:
            in_open = prestart_t <= now_t < offline_t
        else:  # window crosses midnight
            in_open = now_t >= prestart_t or now_t < offline_t

        if not in_open and self.previous_machine_state != "offline":
            print("🔴 [OperatingHours] App started inside closed window — going offline now")
            threading.Thread(target=self._operating_go_offline, daemon=True).start()

        # ── Schedule end-of-day OFFLINE trigger ─────────────────────────────
        # OFFLINE fires 30 min AFTER end_t (grace window for in-flight customers).
        POST_MINUTES = 30
        end_dt = _dt.combine(now.date(), end_t) + _td(minutes=POST_MINUTES)
        if end_dt <= now:
            end_dt += _td(days=1)
        t_end = threading.Timer((end_dt - now).total_seconds(), self._on_operating_end)
        t_end.daemon = True
        t_end.start()
        self._operating_timers.append(t_end)
        print(f"⏰ [OperatingHours] OFFLINE at {end_dt.strftime('%Y-%m-%d %I:%M %p')} "
              f"(end_time + {POST_MINUTES} min grace, in {(end_dt - now).total_seconds() / 3600:.1f}h)")

        # ── Schedule pre-start ONLINE trigger ───────────────────────────────
        prestart_dt = _dt.combine(now.date(), start_t) - _td(minutes=PRE_MINUTES)
        if prestart_dt <= now:
            prestart_dt += _td(days=1)
        t_pre = threading.Timer((prestart_dt - now).total_seconds(), self._on_operating_prestart)
        t_pre.daemon = True
        t_pre.start()
        self._operating_timers.append(t_pre)
        print(f"⏰ [OperatingHours] ONLINE cmd at {prestart_dt.strftime('%Y-%m-%d %I:%M %p')} "
              f"(in {(prestart_dt - now).total_seconds() / 3600:.1f}h)")

    def _operating_go_offline(self):
        """Send OFFLINE to ESP32 and switch UI to machine_empty (background-safe)."""
        self.send_machine_state_to_esp32("OFFLINE", "operating_hours")
        try:
            self.api_client.report_machine_status(self.MACHINE_ID, 'offline')
        except Exception:
            pass
        def _ui(dt):
            self.machine_empty_page.set_mode('offline')
            self.show_page('machine_empty')
            self.previous_machine_state = "offline"
            print("🔴 [OperatingHours] UI → machine_empty (closed hours)")
        Clock.schedule_once(_ui, 0)

    # *** WATER LEVEL LOW (ESP32 health_check → waterLevelLow) ***

    def show_water_level_low(self):
        """ESP32 reported waterLevelLow=True — show maintenance page and alert Kulhad."""
        self.machine_empty_page.set_mode('water_low')
        self.show_page('machine_empty')
        threading.Thread(
            target=lambda: self.api_client.report_water_level(self.MACHINE_ID, True),
            daemon=True
        ).start()

    def clear_water_level_low(self):
        """waterLevelLow cleared (tank refilled) — return to selection and clear Kulhad's flag."""
        self.show_payment_method_page(fetch_cups=True)
        threading.Thread(
            target=lambda: self.api_client.report_water_level(self.MACHINE_ID, False),
            daemon=True
        ).start()

    def _on_operating_end(self):
        """Fires at closing time every day — sends OFFLINE and reschedules for tomorrow.
        Runs on a threading.Timer thread, so the actual offline decision is handed
        to the main thread (Kivy properties like screen_manager.current aren't
        thread-safe to read from here).
        """
        print("🔴 [OperatingHours] Closing time reached — checking before sending OFFLINE")
        Clock.schedule_once(self._operating_end_check, 0)
        # Reschedule 1 second later so "now" is clearly past the trigger point
        if self._operating_start and self._operating_end:
            Clock.schedule_once(
                lambda dt: self._schedule_operating_hours(
                    self._operating_start.strftime('%I:%M %p'),
                    self._operating_end.strftime('%I:%M %p')
                ), 1
            )

    def _operating_end_check(self, dt=None):
        """Main-thread check: defer going offline if a customer is mid-transaction,
        retrying every 30s instead of interrupting them — mirrors the skip_pages
        list in check_global_machine_status. These pages are all bounded by their
        own timeouts (payment QR ~10min, place_cup auto-dispense 30s, etc.), so this
        cannot defer forever.
        """
        critical_pages = ['place_cup', 'dispensing', 'payment', 'loading', 'rfid_auth']
        current = self.screen_manager.current
        if current in critical_pages:
            print(f"🟡 [OperatingHours] Closing deferred — customer mid-transaction ({current}), retrying in 30s")
            Clock.schedule_once(self._operating_end_check, 30)
            return
        self._operating_go_offline()

    def _on_operating_prestart(self):
        """Fires 40 min before opening — sends ONLINE so ESP32 starts heating.
        The machine_empty page's 3-second recovery timer will detect the ONLINE
        state and call check_heating_on_startup(), which navigates to the heating
        page. Tea will be ready by the time the machine officially opens.
        """
        print("🟢 [OperatingHours] Pre-start — sending ONLINE (40 min before open)")
        self.send_machine_state_to_esp32("ONLINE", None)
        threading.Thread(
            target=lambda: self.api_client.report_machine_status(self.MACHINE_ID, 'online'),
            daemon=True
        ).start()
        print("🟢 [OperatingHours] ESP32 ONLINE sent — machine will heat up before opening")
        # Reschedule for tomorrow
        if self._operating_start and self._operating_end:
            Clock.schedule_once(
                lambda dt: self._schedule_operating_hours(
                    self._operating_start.strftime('%I:%M %p'),
                    self._operating_end.strftime('%I:%M %p')
                ), 1
            )

    def _fetch_flush_timing_and_schedule(self):
        """Arm the flush idle timer using flushTimeMinutes from Kulhad.
        Falls back to 40 minutes if the cached value hasn't been fetched yet.
        """
        delay_seconds = self.flush_time_minutes * 60
        print(f"💧 [Flush] Idle timer armed: {self.flush_time_minutes} min ({delay_seconds:.0f}s)")
        Clock.schedule_once(lambda dt: self._arm_flush_timer(delay_seconds), 0)

    def _arm_flush_timer(self, delay_seconds):
        """Arm the Clock timer (main thread only)."""
        if getattr(self, '_flush_cancelled', False):
            print("💧 [Flush] Arming aborted — flush was cancelled")
            return
        if self.flush_timer_event is not None:
            return  # already armed
        self.flush_timer_event = Clock.schedule_once(self._trigger_auto_flush, delay_seconds)

    def cancel_auto_flush(self):
        """Cancel a pending auto flush (called when a new order starts)."""
        self._flush_cancelled = True  # Tell background arming to abort
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
        """Execute maintenance flush: water → 10 s wait → tea → done."""
        import time as _time
        from config import DEVICE_ID
        try:
            # ── Step 1: Water flush ───────────────────────────────────────────
            print(f"💧 [Flush] Sending water flush → {DEVICE_ID}...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('water'), 0)
            water_result = self.api_client.water_flush(DEVICE_ID)

            if water_result:
                if water_result.get('dispatched'):
                    print(f"⚠️ [Flush] Water flush dispatched but NOT confirmed by ESP32 "
                          f"(server timed out waiting for result) — raw: {water_result}")
                else:
                    print(f"✅ [Flush] Water flush confirmed by ESP32 — raw: {water_result}")
            else:
                print("❌ [Flush] Water flush command failed — skipping tea flush")
                return

            # ── 10 s pause (show live countdown on flush page) ───────────────
            print("⏳ [Flush] Waiting 10 s before tea flush...")
            Clock.schedule_once(
                lambda dt: self.flush_page.start_wait_countdown(4), 0
            )
            _time.sleep(4)

            # ── Step 2: Tea flush ─────────────────────────────────────────────
            print(f"🍵 [Flush] Sending tea flush → {DEVICE_ID}...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('tea'), 0)
            tea_result = self.api_client.tea_flush(DEVICE_ID)

            if tea_result:
                resp = tea_result if isinstance(tea_result, dict) else {}
                nested = resp.get('response', {})
                status = nested.get('status', 'unknown')
                code   = nested.get('statusCode', 0)
                if status == 'success' or code == 200:
                    print("✅ [Flush] Tea flush succeeded")
                else:
                    print(f"⚠️ [Flush] Tea flush returned non-success: {tea_result}")
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
            # Re-arm for the next idle interval — without this, the machine only
            # ever flushes once (after the dispense that triggered it) and then
            # never again no matter how much longer it sits idle. A real new
            # order (show_payment_page) still cancels this via cancel_auto_flush().
            Clock.schedule_once(lambda dt: self.schedule_auto_flush(), 1.1)

    # *** REFILL FLUSH (triggered when cups restocked from 0) ***

    def handle_cups_refill(self):
        """Called when machine_empty detects cups refilled (0 → N).
        Sets the refill-flush pending flag then runs temp check.
        If temp is already ready, show_payment_method_page intercepts and starts the flush.
        If temp is low, the heating page shows first; once hot, the same interception happens.
        """
        print("🔄 [RefillFlush] Cups restocked — setting pending refill flush flag")
        self._pending_refill_flush = True
        self.check_heating_on_startup()

    def _trigger_refill_flush(self):
        """Navigate to flush page and launch refill flush thread.
        Guard: if another flush (e.g. the idle auto-flush, armed right after the
        last dispense — which is exactly when cups hit 0) is already running,
        defer and retry shortly instead of dropping the refill flush entirely.
        Both flush paths reset flush_in_progress in a finally block, so this
        always resolves within one flush cycle (~20-30s), never indefinitely.
        """
        if getattr(self, 'flush_in_progress', False):
            print("⚠️ [RefillFlush] Another flush already in progress — deferring, retrying in 5s")
            self._pending_refill_flush = True  # don't lose the request
            # A flush IS actively running right now — show the flush page during
            # the wait too, instead of leaving the user looking at machine_empty
            # while the pump is audibly running.
            self.flush_page.set_note('Waiting for current flush to finish...')
            self.flush_page.show_waiting()
            self.show_page('flush')
            Clock.schedule_once(lambda dt: self._trigger_refill_flush(), 5)
            return

        # Cancel any pending (not-yet-fired) idle-flush timer — refill flush takes priority.
        self.cancel_auto_flush()

        self.flush_in_progress = True
        self.flush_page.set_note('Refill flush: Step 1/3')
        self.flush_page.show_waiting()
        self.show_page('flush')
        print("💧 [RefillFlush] Launching water × 2 → tea flush sequence...")
        threading.Thread(target=self._run_refill_flush, daemon=True).start()

    def _run_refill_flush(self):
        """Execute refill flush: water → 10 s → water → 10 s → tea → done."""
        import time as _time
        from config import DEVICE_ID
        try:
            # ── Step 1/3: First water flush ──────────────────────────────────
            print("💧 [RefillFlush] Step 1/3 — water flush...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('water'), 0)
            Clock.schedule_once(lambda dt: self.flush_page.set_note('Refill flush: Step 1/3'), 0)
            w1 = self.api_client.water_flush(DEVICE_ID)
            if not w1:
                print("❌ [RefillFlush] Step 1 water flush failed — aborting")
                return
            if w1.get('dispatched'):
                print(f"⚠️ [RefillFlush] Step 1 water flush dispatched but NOT confirmed by ESP32 — raw: {w1}")
            else:
                print(f"✅ [RefillFlush] Step 1 confirmed by ESP32 — raw: {w1}")
            Clock.schedule_once(lambda dt: self.flush_page.start_wait_countdown(4), 0)
            _time.sleep(4)

            # ── Step 2/3: Second water flush ─────────────────────────────────
            print("💧 [RefillFlush] Step 2/3 — water flush (2nd)...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('water'), 0)
            Clock.schedule_once(lambda dt: self.flush_page.set_note('Refill flush: Step 2/3'), 0)
            w2 = self.api_client.water_flush(DEVICE_ID)
            if not w2:
                print("❌ [RefillFlush] Step 2 water flush failed — aborting")
                return
            if w2.get('dispatched'):
                print(f"⚠️ [RefillFlush] Step 2 water flush dispatched but NOT confirmed by ESP32 — raw: {w2}")
            else:
                print(f"✅ [RefillFlush] Step 2 confirmed by ESP32 — raw: {w2}")
            Clock.schedule_once(lambda dt: self.flush_page.start_wait_countdown(4), 0)
            _time.sleep(4)

            # ── Step 3/3: Tea flush ───────────────────────────────────────────
            print("🍵 [RefillFlush] Step 3/3 — tea flush...")
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('tea'), 0)
            Clock.schedule_once(lambda dt: self.flush_page.set_note('Refill flush: Step 3/3'), 0)
            t1 = self.api_client.tea_flush(DEVICE_ID)
            if t1:
                print("✅ [RefillFlush] Tea flush complete")
            else:
                print("❌ [RefillFlush] Tea flush failed — continuing to selection anyway")

        except Exception as e:
            print(f"❌ [RefillFlush] Error: {e}")
        finally:
            self.flush_in_progress = False
            Clock.schedule_once(lambda dt: self.flush_page.set_phase('done'), 0)
            Clock.schedule_once(lambda dt: self.flush_page.set_note(''), 0)
            print("✅ [RefillFlush] Complete — going to selection")
            Clock.schedule_once(lambda dt: self.show_payment_method_page(fetch_cups=True), 1)

    # *** SCHEDULED FLUSH MONITOR (Kulhad API-driven) ***

    def start_scheduled_flush_monitor(self):
        """Start a periodic check that polls the Kulhad API for the flush schedule,
        operating hours, and manual online/offline commands, applying any changes.
        """
        self.stop_scheduled_flush_monitor()
        self.scheduled_flush_check_event = Clock.schedule_interval(
            self._check_scheduled_flush, 60  # every 1 minute — keeps manual Kulhad toggles responsive
        )
        print("🕐 Scheduled flush monitor started (check every 1 min)")

    def stop_scheduled_flush_monitor(self):
        """Stop the scheduled flush monitor."""
        if self.scheduled_flush_check_event:
            self.scheduled_flush_check_event.cancel()
            self.scheduled_flush_check_event = None
            print("🛑 Scheduled flush monitor stopped")

    def _check_scheduled_flush(self, dt):
        """Kivy Clock callback — offload the actual check to a background thread.
        Skips if the previous check is still running (e.g. Kulhad responding slowly)
        so overlapping requests never run concurrently.
        """
        if getattr(self, '_scheduled_flush_check_running', False):
            return
        self._scheduled_flush_check_running = True
        threading.Thread(target=self._do_scheduled_flush_check, daemon=True).start()

    def _do_scheduled_flush_check(self):
        """Every 1 minute: refresh flushTimeMinutes, mlToDispense, operating hours, and
        the manual online/offline command from Kulhad. Uses the unified cache refresh so
        any Kulhad change is picked up automatically and the ESP32 is re-synced if needed.
        """
        try:
            self._refresh_machine_config_cache()
        finally:
            self._scheduled_flush_check_running = False

    # *** LOCAL CUPS COUNTER METHODS ***
    def get_local_cups_count(self):
        """Get the locally stored cups count"""
        return self.local_cups_count if self.local_cups_count is not None else 0
    
    def set_local_cups_count(self, count):
        """Set the local cups count and update UI.

        This is the single place cups land after any fresh fetch (startup, page
        entry, screensaver wake, refill checks) — so it's also the right place to
        redirect to machine_empty on 0, instead of only catching it reactively
        when the user clicks Proceed on the selection page.
        """
        self.local_cups_count = count
        self.cups_count_initialized = True
        print(f"📦 Local cups count set to: {count}")

        # Check if cups are at the canister-low alert threshold and alert hasn't been sent
        from config import CANISTER_ALERT_THRESHOLD, MACHINE_EMPTY_THRESHOLD
        print(f"🔍 DEBUG: count={count}, canister_alert_sent={self.canister_alert_sent}")
        if count <= CANISTER_ALERT_THRESHOLD and not self.canister_alert_sent:
            print(f"🔔 Cups are at {CANISTER_ALERT_THRESHOLD}! Sending canister alert...")
            self.send_canister_alert()
            self.canister_alert_sent = True
        # Reset alert flag if cups go above the threshold (refilled)
        elif count > CANISTER_ALERT_THRESHOLD:
            if self.canister_alert_sent:
                print(f"🔄 Cups refilled to {count}, resetting alert flag")
            self.canister_alert_sent = False

        # Update cups display on both pages
        if hasattr(self.payment_method_page, 'update_cups_display'):
            Clock.schedule_once(lambda dt: self.payment_method_page.update_cups_display(count))
        if hasattr(self.selection_page, 'update_cups_display'):
            Clock.schedule_once(lambda dt: self.selection_page.update_cups_display(count))

        # Redirect straight to machine_empty if we're sitting on the selection
        # page at or below the empty threshold — don't wait for the user to
        # click Proceed to find out. Skip during critical in-flight pages and
        # while machine_empty already owns the screen (avoids restarting its
        # animation/timers redundantly).
        in_flight_pages = ('place_cup', 'dispensing', 'payment', 'loading',
                            'heating', 'rfid_auth', 'thank_you', 'flush')
        current_page = self.screen_manager.current
        if (count <= MACHINE_EMPTY_THRESHOLD
                and not getattr(self, '_dispensing_cups', False)
                and current_page not in in_flight_pages
                and current_page != 'machine_empty'):
            print(f"📦 set_local_cups_count: {count} cups (<= {MACHINE_EMPTY_THRESHOLD}) on a live page — navigating to machine_empty")
            def _show_empty(dt):
                self.machine_empty_page.set_mode('empty')
                self.show_page('machine_empty')
            Clock.schedule_once(_show_empty, 0)

    def decrement_local_cups(self, num_cups=1):
        """Decrement local cups count (when dispensing)"""
        if self.local_cups_count is not None:
            from config import CANISTER_ALERT_THRESHOLD, MACHINE_EMPTY_THRESHOLD
            self.local_cups_count = max(0, self.local_cups_count - num_cups)
            count = self.local_cups_count  # snapshot for lambdas — avoids stale-reference bug
            print(f"📦 Local cups decremented by {num_cups}, new count: {count}")

            # Only navigate to machine_empty if no order is actively in progress.
            # During a multi-cup order the count can legitimately hit the empty
            # threshold mid-dispense (user ordered the last N cups). Interrupting
            # that with machine_empty would cut off the dispensing animation and
            # skip the thank-you page.
            if count <= MACHINE_EMPTY_THRESHOLD and not getattr(self, '_dispensing_cups', False):
                print(f"📦 Cups at {count} (<= {MACHINE_EMPTY_THRESHOLD}, no active order) — navigating to machine_empty")
                def _show_empty(dt):
                    self.machine_empty_page.set_mode('empty')
                    self.show_page('machine_empty')
                Clock.schedule_once(_show_empty, 2.0)  # small delay so thank_you can show first

            # Check if cups reached the canister-low alert threshold and alert hasn't been sent
            print(f"🔍 DEBUG: after decrement count={count}, canister_alert_sent={self.canister_alert_sent}")
            if count <= CANISTER_ALERT_THRESHOLD and not self.canister_alert_sent:
                print(f"🔔 Cups reached {CANISTER_ALERT_THRESHOLD} after dispensing! Sending canister alert...")
                self.send_canister_alert()
                self.canister_alert_sent = True

            # Reset alert flag if cups go above the threshold (refilled)
            elif count > CANISTER_ALERT_THRESHOLD:
                if self.canister_alert_sent:
                    print(f"🔄 Cups refilled to {count} after dispensing, resetting alert flag")
                self.canister_alert_sent = False

            # Update cups display on both pages (use snapshot to avoid stale reference)
            if hasattr(self.payment_method_page, 'update_cups_display'):
                Clock.schedule_once(lambda dt, c=count: self.payment_method_page.update_cups_display(c))
            if hasattr(self.selection_page, 'update_cups_display'):
                Clock.schedule_once(lambda dt, c=count: self.selection_page.update_cups_display(c))
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
                    
                    # Reset alert flag if cups are refilled (> threshold)
                    from config import CANISTER_ALERT_THRESHOLD
                    if cups_count > CANISTER_ALERT_THRESHOLD:
                        self.canister_alert_sent = False
                else:
                    print("❌ Failed to fetch cups count from API")
            except Exception as e:
                print(f"❌ Error fetching cups count: {e}")
        
        # Run in background thread
        threading.Thread(target=fetch_in_background, daemon=True).start()
    
    def send_canister_alert(self):
        """Send canister level alert when cups reach the alert threshold"""
        from config import CANISTER_ALERT_THRESHOLD
        print(f"🔔 DEBUG: send_canister_alert() called for machine {self.MACHINE_ID}")

        def send_alert_in_background():
            try:
                print(f"🔔 DEBUG: Calling API check_canister_level()...")
                result = self.api_client.check_canister_level(self.MACHINE_ID, canister_level=CANISTER_ALERT_THRESHOLD)
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
            # Water temperature too low — show heating page with fresh temp from cache
            print("🔥 [Dispense] Temperature low (700) — redirecting to heating page")
            temp = hardware_monitor._fetch_cached_temperature()
            Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
        elif status_code == 701:
            # Temperature ABOVE critical threshold — the PT100 is reading garbage
            # (open circuit / disconnected sensor).  Show a persistent hardware error;
            # the hardware_error page will now detect the out-of-range reading and
            # keep displaying the error rather than auto-clearing.
            print("🌡️ [Dispense] Temperature critical / sensor error (701) — showing hardware error")
            Clock.schedule_once(
                lambda dt: self.show_hardware_error(
                    "PT100 Sensor Error: temperature above critical threshold\n"
                    "Check sensor connection and restart machine."
                ), 0
            )
        elif status_code == 704:
            # Cup removed mid-dispense (schema §7.2) — resumable, send user back to place cup
            print("🥛 [Dispense] Cup removed (704) — returning to place cup page")
            Clock.schedule_once(lambda dt: self.show_place_cup_page(), 0)
        elif status_code in [705, 706, 707, 708, 711]:
            # Hardware fault (flow, pump, heater, water level, timeout)
            error_messages = {
                705: "Flow Failure\nPlease contact support",
                706: "Pump Fault\nPlease contact support",
                707: "Heater Fault\nPlease contact support",
                708: "Low Water Level\nFill tank and retry",
                711: "Pump Timeout\nPlease contact support",
            }
            msg = error_messages.get(status_code, f"Hardware Error (code {status_code})")
            print(f"🔧 [Dispense] Hardware fault ({status_code}) — showing hardware error page")
            Clock.schedule_once(lambda dt: self.show_hardware_error(msg), 0)
        else:
            # Unrecognised code — stay on current page; ESP32 may recover
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
            # Only block QR generation if machine is EXPLICITLY "offline".
            # Kulhad API returns various strings ("active", "online", etc.) — reject
            # only on a literal "offline" response, not on any non-"online" value.
            cached_state = getattr(self, 'previous_machine_state', None)

            if cached_state is None:
                # First request — no cache yet; check ESP32 machineState from local
                # polling server (instant, no internet required).
                print("🔄 No cached machine state — checking ESP32 directly")
                try:
                    from config import DEVICE_ID, POLLING_SERVER_URL
                    esp_r = get_localhost_session().get(
                        f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                        timeout=2
                    )
                    if esp_r.status_code == 200:
                        esp_state = esp_r.json().get('machineState', 'UNKNOWN').upper()
                        if esp_state == 'OFFLINE':
                            print("❌ ESP32 machineState is OFFLINE — aborting QR generation")
                            Clock.schedule_once(lambda dt: self.show_error_fallback())
                            return
                        print(f"✅ ESP32 machineState = '{esp_state}' — proceeding with QR")
                    else:
                        # Polling server unavailable — proceed; physical machine ready
                        print("⚠️ Polling server unavailable for state check — proceeding with QR generation")
                except Exception:
                    print("⚠️ ESP32 state check failed — proceeding with QR generation")
            else:
                # Use cached result — saves one full HTTP round-trip
                if cached_state == "offline":
                    print(f"❌ Cached machine state is 'offline' — aborting QR generation")
                    Clock.schedule_once(lambda dt: self.show_error_fallback())
                    return
                print(f"✅ Machine status OK (cached: '{cached_state}') — skipping status API call")

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
                    qr_pil = QRUtils.generate_qr_from_content(image_content)
                    qr_gen_time = time.time() - qr_gen_start

                    if qr_pil:
                        # Pre-encode to PNG bytes here in background thread to keep
                        # the main thread fast (no PIL.save on UI thread).
                        import io as _io
                        qr_buf = _io.BytesIO()
                        qr_pil.save(qr_buf, format='PNG')
                        total_time = time.time() - start_time
                        print(f"✅ QR generation complete! Total: {total_time:.2f}s (QR image: {qr_gen_time:.3f}s)")
                        Clock.schedule_once(lambda dt: self.update_payment_page(qr_buf, qr_data))
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
        incoming_id = data.get('id', '') if data else ''

        # Guard: only accept QR delivery while user is still on the loading screen.
        # generate_qr_code() and _prefetch_worker run in background threads — they
        # can complete AFTER the user has cancelled and navigated away.  Without this
        # check the payment page would re-appear over the selection page.
        if self._current_page != 'loading':
            if incoming_id:
                print(f"🗑️ QR arrived but page is '{self._current_page}' (not loading) — cancelling {incoming_id}")
                threading.Thread(
                    target=lambda qid=incoming_id: self.api_client.cancel_payment(qid),
                    daemon=True
                ).start()
            return

        # Guard against double-delivery race: if a QR is already showing,
        # cancel the incoming duplicate so it is never orphaned on the backend.
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
            """Called when user clicks Try Again"""
            print(f"🔄 Retrying QR generation for {self.selected_cups} cups...")
            self.show_loading_page()
            # Shorter timeout on retry — if it fails again, bail fast
            self.loading_timeout_event = Clock.schedule_once(
                lambda dt: self.show_error_fallback(is_retry=True), 8
            )
            threading.Thread(
                target=lambda: self.generate_qr_code(self.selected_cups),
                daemon=True
            ).start()

        def on_cancel():
            """Called when user clicks Go Back or popup auto-dismisses"""
            print("⚠️ Going back to home screen")
            self.show_payment_method_page()
        
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
                # Guard: user may have navigated away in the 1.5s window (e.g. cancel tap)
                Clock.schedule_once(
                    lambda dt: self.show_dispensing_page() if self.screen_manager.current == 'payment' else None,
                    1.5
                )

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
            # Always go back to home (selection) on cancel — not staying on payment.
            # Going to selection resets the flow so the next Confirm gets a fresh QR.
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
        
        # Activate screensaver on home/idle pages.
        # machine_empty in 'offline' mode shows the "Under Maintenance" message —
        # that must stay visible, so the screensaver is blocked in that state.
        current_page = self.screen_manager.current
        machine_empty_is_offline = (
            current_page == 'machine_empty'
            and getattr(self.machine_empty_page, 'current_mode', 'empty') == 'offline'
        )
        is_screensaver_eligible_page = (
            current_page in ['payment_method', 'selection', 'machine_empty']
            and not machine_empty_is_offline
        )
        
        if elapsed >= self.INACTIVE_TIMEOUT and not self.screensaver_active and is_screensaver_eligible_page:
            if self.video_path and os.path.exists(self.video_path):
                self.activate_screensaver()
            else:
                print(f"Video file not found: {self.video_path}")
    
    def activate_screensaver(self):
        """Activate the screensaver"""
        print("Activating screensaver...")
        # User walked away — cancel any pre-generated QRs so they don't expire in cache
        self.cancel_prefetched_qrs()
        # Remember which page we were on before screensaver
        self.previous_page_before_screensaver = self.screen_manager.current
        self.screensaver_active = True
        self.show_page('screensaver')
            
    def deactivate_screensaver(self):
        """Deactivate the screensaver - navigate immediately using local cups count"""
        self.screensaver_active = False
        print("⚡ Deactivating screensaver - navigating immediately...")

        # If machine went offline during the screensaver (or was already offline when
        # it activated), return to the maintenance page instead of the home page so
        # the user can't attempt an order while the ESP32 is unreachable.
        if getattr(self, 'previous_machine_state', None) == 'offline':
            print("🔴 Machine still OFFLINE — returning to maintenance page")
            self.machine_empty_page.set_mode('offline')
            self.show_page('machine_empty')
            return

        # The global 10s monitor skips itself while the screensaver is showing
        # (to avoid fighting over screen state), so waterLevelLow could have
        # gone True during that idle period without being caught yet. Check it
        # here too, same as the offline check above, before letting the user
        # start an order on a machine that's actually out of water.
        if hardware_monitor.get_water_level_low():
            print("🔴 Machine water level LOW (caught on screensaver wake) — showing maintenance page")
            self._water_level_low_active = True
            self.show_water_level_low()
            return

        # INSTANT NAVIGATION - show home page immediately with local cups count
        self.show_payment_method_page()
        
        # No API call needed - local cups count is already available
        print(f"📦 Using local cups count: {self.local_cups_count}")
    
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
        """Check for hardware errors and navigate to error page if needed.

        Runs the actual check in a background thread. get_latest_error() can
        block for up to 35s (its fast cached-history path sometimes misses and
        falls back to sending a slow health_check command) — and this function
        is a Clock.schedule_interval callback firing every 2s on the MAIN UI
        thread. Without offloading it, the entire app would freeze solid for
        up to 35s every time that cache misses.
        """
        current_screen = self.screen_manager.current

        # Don't check during critical operations to avoid interrupting them
        critical_screens = ['dispensing', 'place_cup', 'payment', 'thank_you', 'heating']  # Removed 'transaction_processing'
        if current_screen in critical_screens:
            # Skip error checking during critical operations
            return

        # Guard against overlapping checks — if get_latest_error() is still
        # running (e.g. mid-35s health_check call) when the next 2s tick fires,
        # skip rather than stacking up concurrent calls.
        if getattr(self, '_checking_hardware_errors', False):
            return
        self._checking_hardware_errors = True

        def _check_in_background():
            error_msg = None
            try:
                error_msg = hardware_monitor.get_latest_error()
            except Exception as e:
                print(f"⚠️ check_hardware_errors background error: {e}")
            finally:
                self._checking_hardware_errors = False
            Clock.schedule_once(lambda dt: _handle_result(error_msg), 0)

        def _handle_result(error_msg):
            # Re-check current screen — by the time this background check
            # resolves (up to 35s later), the user may have since started a
            # critical operation that shouldn't be interrupted.
            current = self.screen_manager.current
            if error_msg and current != 'hardware_error' and current not in critical_screens:
                print(f"Hardware error detected: {error_msg} - Navigating to error page")
                self.show_hardware_error(error_msg)

        threading.Thread(target=_check_in_background, daemon=True).start()
    
    def show_hardware_error(self, error_message):
        """Navigate to hardware error page with a custom error message"""
        print(f"Showing hardware error page: {error_message}")
        # Stop heating monitor so it doesn't call show_heating_page after we navigate away
        self.stop_heating_monitor()
        # Clear the QR ID so the next payment cycle isn't blocked by the
        # duplicate-delivery guard in update_payment_page().
        self.current_qr_code_id = ""
        self._dispensing_cups = False  # order aborted
        if hasattr(self.hardware_error_page, 'set_error_message'):
            self.hardware_error_page.set_error_message(error_message)
        self.show_page('hardware_error')
    
    def check_heating_on_startup(self):
        """Check temperature on startup. Uses only the fast cached path (GET /temperature).
        If no cached data is available yet, defaults immediately to the heating page —
        the heating monitor will navigate home once temperature is confirmed ready.
        The slow health_check command path is intentionally skipped here because it can
        block for 30-60 s (one ESP32 poll cycle), leaving the user on the selection page
        with no feedback and allowing them to start an order before heating is confirmed.
        """
        from config import SERVING_TEMP, DEVICE_ID, POLLING_SERVER_URL
        def check_temp_background():
            temp = None
            raw_reading = None  # track raw value before range-filter
            try:
                # Fast path only: read last health POST from the polling server cache.
                # This returns 404 if ESP32 hasn't sent a health POST yet (first boot).
                r = get_localhost_session().get(
                    f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                    timeout=2
                )
                if r.status_code == 200:
                    data = r.json()
                    # If ESP32 says OFFLINE (e.g. operating hours end, maintenance)
                    # skip the heating check — the operating hours scheduler or global
                    # status monitor will navigate to machine_empty instead.
                    if data.get('machineState', '').upper() == 'OFFLINE':
                        print("⚠️ Startup: ESP32 machineState=OFFLINE — skipping heating check")
                        return
                    raw = data.get('pt100_temperature')
                    if raw is not None:
                        raw_reading = float(raw)
                        # Reject out-of-range (open-circuit / short-circuit artifacts)
                        if -10 <= raw_reading <= 120:
                            temp = raw_reading
            except Exception as e:
                print(f"Startup temp cache read error: {e}")

            # If raw reading is >120°C the sensor is disconnected (open circuit artifact).
            # Show hardware error immediately — no retry, no heating page loop.
            if raw_reading is not None and raw_reading > 120:
                msg = f"PT100 Sensor Error: reading {raw_reading:.0f}°C (sensor disconnected?)"
                print(f"⚠️ Startup: {msg}")
                Clock.schedule_once(lambda dt: self.show_hardware_error(msg), 0)
                return

            if temp is None:
                # No cached data yet — the ESP32 may not have sent its first health
                # POST in the 1.5 s since app start.  Retry once with a short delay
                # before defaulting to the heating page so we avoid a false redirect.
                import time as _t
                _t.sleep(3)  # wait 3 s for the first health POST to arrive
                try:
                    r2 = get_localhost_session().get(
                        f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                        timeout=2
                    )
                    if r2.status_code == 200:
                        raw2 = r2.json().get('pt100_temperature')
                        if raw2 is not None:
                            raw_reading = float(raw2)
                            if raw_reading > 120:
                                msg = f"PT100 Sensor Error: reading {raw_reading:.0f}°C (sensor disconnected?)"
                                print(f"⚠️ Startup retry: {msg}")
                                Clock.schedule_once(lambda dt: self.show_hardware_error(msg), 0)
                                return
                            if -10 <= raw_reading <= 120:
                                temp = raw_reading
                                print(f"✅ Startup retry: got temp {temp:.1f}°C")
                except Exception:
                    pass

            if temp is None:
                print("⚠️ No cached temperature after retry — defaulting to heating page")
                Clock.schedule_once(lambda dt: self.show_heating_page(None), 0)
            elif temp < SERVING_TEMP:
                print(f"🔥 Tea is heating: {temp:.1f}°C (target: {SERVING_TEMP}°C)")
                Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
            else:
                print(f"✅ Tea is ready: {temp:.1f}°C")
                Clock.schedule_once(lambda dt: self.show_payment_method_page(fetch_cups=True), 0)

        threading.Thread(target=check_temp_background, daemon=True).start()
    
    def setup_idle_temperature_monitoring(self):
        """Monitor temperature when the app is on payment_method or screensaver page.
        If the temperature falls below 80°C, it automatically redirects to the heating page.
        """
        self._idle_temp_checking = False
        self._idle_temp_event = Clock.schedule_interval(self.check_idle_temperature, 5.0)  # Check every 5 seconds

    def check_idle_temperature(self, dt):
        # Never interrupt an active flush with a heating page redirect.
        if getattr(self, 'flush_in_progress', False):
            return

        current_page = self.screen_manager.current
        # Check ONLY on true idle/waiting screens — NEVER during active dispense/delivery.
        # 'place_cup' is intentionally excluded: the user is mid-dispensing and
        # a low temp reading here must NOT hijack the screen to the heating page.
        # 'dispensing' and 'thank_you' are also excluded for the same reason.
        if current_page not in ['payment_method', 'selection', 'screensaver', 'qr_expired']:
            return

        # Avoid overlapping read threads
        if hasattr(self, '_idle_temp_checking') and self._idle_temp_checking:
            return

        self._idle_temp_checking = True

        def _do_check():
            try:
                # Fast path: read from polling server cache (ESP32 health POST data).
                # Avoids the 35 s slow-path health_check round-trip which would hold
                # _idle_temp_checking=True for up to 35 s, effectively making this
                # 5 s interval check run only once every ~40 s.
                temp = hardware_monitor._fetch_cached_temperature()
                # Fallback: use last_temperature if the cache just expired
                if temp is None and hardware_monitor.last_temperature is not None:
                    temp = float(hardware_monitor.last_temperature)
                    print(f"🔥 Idle temp: cache stale, using last known {temp:.1f}°C")

                # Reject out-of-range and glitch readings.
                # 0.0 °C is a common ESP32 sensor glitch; realistic minimum
                # for an installed machine is ~10 °C.
                if temp is not None and (temp < 10 or temp > 120):
                    if temp is not None:
                        print(f"🔥 Idle temp: ignoring glitch reading {temp}°C")
                    temp = None

                from config import SERVING_TEMP
                if temp is not None and temp < SERVING_TEMP:
                    print(f"🔥 Idle temp check: {temp:.1f}°C < {SERVING_TEMP}°C — redirecting to heating page")
                    Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
            except Exception as e:
                print(f"Error in idle temperature check: {e}")
            finally:
                self._idle_temp_checking = False

        threading.Thread(target=_do_check, daemon=True).start()

    def show_heating_page(self, current_temp):
        """Show heating page and start temperature monitoring"""
        hardware_monitor.enable_heating_mode()

        # If caller didn't have a temp reading, pull one from the polling server
        # cache immediately so the page never opens with "--°C" (live data is always
        # fresher than waiting for the first 1-second tick in start_heating_monitor).
        if current_temp is None:
            try:
                from config import DEVICE_ID, POLLING_SERVER_URL
                _r = get_localhost_session().get(
                    f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                    timeout=2
                )
                if _r.status_code == 200:
                    _t = _r.json().get('pt100_temperature')
                    if _t is not None and -10 <= float(_t) <= 120:
                        current_temp = float(_t)
            except Exception:
                pass

        self.heating_page.update_temperature(current_temp)
        self.show_page('heating')
        self.start_heating_monitor()

        # Pre-generate QR while heating — skip if we already know the exact cup count
        # since we'll generate the right QR when heating completes.
        if getattr(self, '_pending_cups_after_heating', None) is None:
            self.trigger_qr_prefetch(1)
    
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

            # temp is None but no exception — health_check command pending or no data yet.
            # Only escalate after 300 s of nothing.
            if temp is None:
                elapsed = time.time() - self.heating_start_time
                if elapsed > 300:
                    print("❌ No temperature data after 300 s — sensor not responding")
                    self.stop_heating_monitor()
                    self.show_hardware_error("Temperature sensor not responding")
                else:
                    # Keep the last known reading on screen — never overwrite a valid
                    # temperature with "--°C" just because a command is still in flight.
                    fallback = hardware_monitor.last_temperature
                    self.heating_page.update_temperature(fallback)
                return

            # Good read — reset error streak and update display
            self.heating_temp_error_count = 0
            self.heating_page.update_temperature(temp)

            from config import SERVING_TEMP
            if temp >= SERVING_TEMP:
                self.stop_heating_monitor()
                pending_cups = getattr(self, '_pending_cups_after_heating', None)
                pending_rfid = getattr(self, '_pending_rfid_dispense_after_heating', False)
                if pending_rfid:
                    print(f"✅ Tea ready at {temp:.1f}°C - RFID customer already authenticated, proceeding to dispensing")
                    self._pending_rfid_dispense_after_heating = False
                    self.show_dispensing_page()
                elif pending_cups is not None:
                    print(f"✅ Tea ready at {temp:.1f}°C - proceeding to QR for {pending_cups} cups")
                    self._pending_cups_after_heating = None
                    self.show_payment_page(pending_cups)
                else:
                    print(f"✅ Tea ready at {temp:.1f}°C - navigating to home")
                    self.show_payment_method_page(fetch_cups=True)
            else:
                print(f"🔥 Heating: {temp:.1f}°C / {SERVING_TEMP}°C")

        def _read_temp_background():
            """Run in a background daemon thread — never on the main thread."""
            temp, exc = None, None
            try:
                # force_fresh=True: bypasses cache and sends a health_check command so
                # the displayed temperature reflects the actual PT100 reading now, not
                # a 30-second-old health POST.
                temp = hardware_monitor._fetch_temperature(force_fresh=True)
                # If the health_check command is already in flight (_slow_path_lock busy),
                # _fetch_temperature returns last_temperature (may be None on first poll).
                # Fall back to the ESP32 health POST cache to avoid showing "--°C" while
                # the first command round-trip is pending.
                if temp is None:
                    temp = hardware_monitor._fetch_cached_temperature()
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
            print("\n🚶 ESC key pressed - Shutting down gracefully...")
            self.stop()
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

            # Cancel operating hours timers
            for t in getattr(self, '_operating_timers', []):
                t.cancel()
            self._operating_timers = []

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
        
        # threading.Timer fires independently of Kivy's Clock (which may stop
        # during shutdown), guaranteeing the force-exit fires even after Kivy stops.
        # daemon=True: if the process exits cleanly on its own, this thread is killed
        # automatically so it doesn't hold up shutdown for 8s unnecessarily.
        _t = threading.Timer(8, force_exit)
        _t.daemon = True
        _t.start()
        
        return super().on_stop()
    
    def start_global_status_monitoring(self):
        """Start global machine status monitoring that runs on all pages"""
        # Stop any existing monitoring first
        self.stop_global_status_monitoring()

        # A short delay so the ESP32 has sent at least one health POST before the
        # first check. Transient "offline" readings at boot (which previously
        # caused heater cycling with no delay at all) are now filtered by the
        # 2-consecutive-reads debounce in _do_global_status_check instead of a
        # blanket 30s wait — so a genuine offline/water-low state at boot is no
        # longer invisible to the user for half a minute.
        def _start_interval(dt):
            self._global_status_start_event = None
            self.check_global_machine_status(0)
            self.global_status_monitor_event = Clock.schedule_interval(
                self.check_global_machine_status,
                self.global_status_check_interval
            )
            print(f"🌐 Started GLOBAL machine status monitoring (every {self.global_status_check_interval} seconds)")

        import os as _os
        startup_delay = 3 if _os.environ.get("UK_TEST_MODE") else 5
        self._global_status_start_event = Clock.schedule_once(_start_interval, startup_delay)
        print(f"🌐 Global status monitoring will begin in {startup_delay}s")
    
    def stop_global_status_monitoring(self):
        """Stop global machine status monitoring"""
        if hasattr(self, '_global_status_start_event') and self._global_status_start_event:
            self._global_status_start_event.cancel()
            self._global_status_start_event = None
        if self.global_status_monitor_event:
            self.global_status_monitor_event.cancel()
            self.global_status_monitor_event = None
            print("🛑 Stopped GLOBAL machine status monitoring")
    
    # ── Global RFID monitor ───────────────────────────────────────────────────
    # Pages whose own on_enter/on_leave hooks manage RFID polling — skip them
    # so the global monitor doesn't double-process cards on those pages.
    _GRF_OWN_PAGES = frozenset({'payment_method', 'selection', 'heating', 'hardware_error', 'rfid_auth'})
    # Pages where an RFID tap has no useful action (mid-dispense or wrap-up)
    _GRF_SKIP_PAGES = frozenset({'dispensing', 'place_cup', 'thank_you', 'flush'})

    def _start_global_rfid_monitor(self):
        """Start the always-on RFID monitor that handles every page not already
        covered by a per-page RFID polling loop."""
        self._grf_busy = False
        self._grf_last_uid = None
        self._grf_last_scan_time = 0.0
        Clock.schedule_interval(self._grf_tick, 0.5)
        print("🏷️ Global RFID monitor started (covers all pages without per-page polling)")

    def _grf_tick(self, dt):
        current = self._current_page
        if current in self._GRF_OWN_PAGES or current in self._GRF_SKIP_PAGES:
            return
        if self._grf_busy:
            return
        # If PC/SC gave up (HID-only reader like Sycreader), skip silently.
        # The HID keyboard path (rfid_reader) handles cards via on_key_down events.
        if getattr(self, '_grf_pc_sc_gave_up', False):
            return
        handler = getattr(self, 'rfid_auth_handler', None)
        if not handler or not getattr(handler, 'reader_active', False):
            # Reader not ready — attempt re-init at most once every 30 s
            now = time.time()
            if now - getattr(self, '_grf_last_reinit', 0) > 30 and not getattr(self, '_grf_reinit_busy', False):
                self._grf_last_reinit = now
                self._grf_reinit_busy = True
                threading.Thread(target=self._grf_reinit_reader, daemon=True).start()
            return
        self._grf_busy = True
        threading.Thread(target=self._grf_check_card, args=(current,), daemon=True).start()

    def _grf_reinit_reader(self):
        """Re-initialize the PC/SC RFID reader if it wasn't ready at startup.
        Gives up after 3 consecutive failures — for HID-only readers (Sycreader)
        PC/SC will never succeed, and the HID path handles cards via rfid_reader."""
        try:
            handler = getattr(self, 'rfid_auth_handler', None)
            if handler is None:
                from utils.rfid_aes_auth import RFIDAESAuth
                from config import RFID_MACHINE_ID
                self.rfid_auth_handler = RFIDAESAuth(
                    base_url="https://www.ukteawallet.com",
                    machine_id=RFID_MACHINE_ID
                )
                if not self.rfid_auth_handler.reader_active:
                    self._grf_pc_sc_failures = getattr(self, '_grf_pc_sc_failures', 0) + 1
                else:
                    self._grf_pc_sc_failures = 0
                print(f"🔐 Global RFID: handler created, reader_active={self.rfid_auth_handler.reader_active}")
            elif not handler.reader_active:
                handler._init_reader()
                failures = getattr(self, '_grf_pc_sc_failures', 0) + 1
                self._grf_pc_sc_failures = failures
                if failures >= 3:
                    print("🔐 Global RFID: PC/SC reader unavailable after 3 attempts — "
                          "HID keyboard path (rfid_reader) handles cards. Stopping PC/SC reinit.")
                    self._grf_pc_sc_gave_up = True
                # Only log first failure to avoid spam
                elif failures == 1:
                    print(f"🔐 Global RFID: reader re-init, reader_active={handler.reader_active}")
        except Exception as e:
            print(f"🔐 Global RFID: re-init error: {e}")
        finally:
            self._grf_reinit_busy = False

    def _grf_check_card(self, page_at_start):
        try:
            uid = self.rfid_auth_handler.get_card_uid()
            if uid and uid != self._grf_last_uid:
                self._grf_last_uid = uid
                Clock.schedule_once(lambda dt: self._grf_on_new_card(uid, page_at_start), 0)
            elif not uid:
                self._grf_last_uid = None
        except Exception as e:
            print(f"🏷️ Global RFID monitor error: {e}")
        finally:
            self._grf_busy = False

    def _grf_on_new_card(self, uid, source_page):
        now = time.time()
        if now - self._grf_last_scan_time < 3:
            return
        self._grf_last_scan_time = now

        # Re-check page — navigation may have happened between thread dispatch and now
        current = self.screen_manager.current
        if current in self._GRF_OWN_PAGES or current in self._GRF_SKIP_PAGES:
            return

        print(f"🏷️ Global RFID: card detected on page '{current}'")

        # Delegate to payment_method_page's full RFID handler (auth, maintenance,
        # balance check, navigate-to-dispensing).  Re-enable rfid_listening first
        # because it may have been cleared by a prior per-page session.
        pmp = self.payment_method_page
        pmp.rfid_listening = True
        pmp.handle_rfid_card_detected(uid)

    def _on_hid_rfid_card(self, card_number):
        """Handle an RFID card number received via HID keyboard mode.

        Some ACR122U readers are configured to output the card ID as decimal
        keystrokes (USB HID keyboard mode) instead of exposing themselves as a
        PC/SC smartcard reader.  This callback receives those keystrokes and
        routes them through the same authentication flow as the PC/SC path.
        """
        skip_pages = {'rfid_auth', 'dispensing', 'place_cup', 'thank_you', 'flush'}
        current = self.screen_manager.current
        if current in skip_pages:
            return

        print(f"🏷️ HID RFID: card number '{card_number}' on page '{current}'")

        # Store card number so process_card() can use it when pyscard returns None
        if getattr(self, 'rfid_auth_handler', None):
            self.rfid_auth_handler.last_card_uid = str(card_number)

        pmp = self.payment_method_page
        pmp.rfid_listening = True
        pmp.handle_rfid_card_detected(str(card_number))

    # ─────────────────────────────────────────────────────────────────────────

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
            'flush'               # Maintenance flush in progress
            # 'heating' intentionally NOT skipped — OFFLINE must override heating
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
            check_pages = ['payment_method', 'selection', 'payment', 'loading', 'heating']

            if current_page not in check_pages:
                return

            # Use ESP32's machineState from the local polling server — no internet
            # dependency, real-time, and the ground-truth source for physical readiness.
            # Kulhad is NOT used here; its status strings are unreliable ("active",
            # "Active", "online", etc.) and require an external HTTP call.
            try:
                from config import DEVICE_ID, POLLING_SERVER_URL
                esp32_resp = get_localhost_session().get(
                    f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                    timeout=2
                )
                if esp32_resp.status_code == 200:
                    esp32_data = esp32_resp.json()
                    machine_state = esp32_data.get('machineState', 'UNKNOWN')
                    ts = esp32_data.get('timestamp')
                    # If last health POST is more than 90 s old the ESP32 stopped
                    # communicating — treat as hardware offline regardless of machineState.
                    if ts:
                        from datetime import datetime as _dt
                        age = time.time() - _dt.fromisoformat(ts).timestamp()
                        if age > 90:
                            print(f"🔴 ESP32 health POST is {age:.0f}s old — treating as hardware offline")
                            machine_state = 'OFFLINE'
                    is_online = machine_state.upper() != 'OFFLINE'
                elif esp32_resp.status_code == 404:
                    # No health POSTs received since server start → ESP32 not connected
                    print("🔴 GLOBAL CHECK: No ESP32 health data (404) — hardware offline")
                    machine_state = 'OFFLINE'
                    is_online = False
                else:
                    print(f"🌐 GLOBAL CHECK: Polling server returned {esp32_resp.status_code} — skipping state update")
                    self._checking_global_status = False
                    return

                if not is_online:
                    # Require 2 consecutive OFFLINE reads (~10-20s apart) before
                    # acting — filters out a single transient blip (e.g. right
                    # after boot, before the network/ESP32 has settled) without
                    # needing to blanket-delay the whole monitor by 30s.
                    self._offline_confirm_count += 1
                else:
                    self._offline_confirm_count = 0

                confirmed_offline = self._offline_confirm_count >= 2

                if confirmed_offline and self.previous_machine_state != "offline":
                    # Covers two cases:
                    # 1. previous_machine_state is None (first check) and machine is already offline
                    # 2. previous_machine_state == "online" and machine just went offline (ONLINE→OFFLINE)
                    print("🔴 Machine state changed: → OFFLINE (ESP32, confirmed)")
                    def _show_offline(dt):
                        self.machine_empty_page.set_mode('offline')
                        self.show_page('machine_empty')
                    Clock.schedule_once(_show_offline, 0)
                    # Notify kulhad backend
                    threading.Thread(
                        target=self.api_client.report_machine_status,
                        args=(self.MACHINE_ID, 'offline'),
                        daemon=True
                    ).start()
                elif is_online and self.previous_machine_state == "offline":
                    print("🟢 Machine state changed: OFFLINE → ONLINE (ESP32)")
                    Clock.schedule_once(lambda dt: self.check_heating_on_startup(), 0)
                    # Notify kulhad backend
                    threading.Thread(
                        target=self.api_client.report_machine_status,
                        args=(self.MACHINE_ID, 'online'),
                        daemon=True
                    ).start()

                # Only update previous_machine_state from a CONFIRMED offline read or
                # an online read — a single unconfirmed offline blip (count==1) must
                # not flip this yet, or the debounce above could never reach count>=2
                # with previous_machine_state still "online".
                if confirmed_offline:
                    self.previous_machine_state = "offline"
                elif is_online:
                    self.previous_machine_state = "online"
                print(f"🌐 GLOBAL CHECK: ESP32 machineState = '{machine_state}' → is_online={is_online}")

                # ── Water level low (ESP32 health_check → waterLevelLow) ────────
                if is_online:
                    water_low = hardware_monitor.get_water_level_low()
                    if water_low and not self._water_level_low_active:
                        print("🔴 GLOBAL CHECK: waterLevelLow=True — showing maintenance page")
                        self._water_level_low_active = True
                        Clock.schedule_once(lambda dt: self.show_water_level_low(), 0)
                    elif not water_low and self._water_level_low_active:
                        print("🟢 GLOBAL CHECK: waterLevelLow cleared — returning to selection")
                        self._water_level_low_active = False
                        Clock.schedule_once(lambda dt: self.clear_water_level_low(), 0)
            except Exception as esp_err:
                print(f"🌐 GLOBAL CHECK: ESP32 state check failed: {esp_err}")

            # Machine_empty is NOT triggered by status check.
            # machine_empty is only shown by decrement_local_cups() hitting 0
            # or check_machine_availability() confirming 0 cups from the API.

            # Sync cups count from cloud for refill detection only.
            # Never write 0 to local here — cloud lags after a dispense and a stale 0
            # would make check_machine_availability() show machine_empty on next page entry.
            # decrement_local_cups() is the only authoritative zero signal.
            cups_data = self.api_client.get_remaining_cups(self.MACHINE_ID)
            if cups_data and cups_data.get("success", False):
                cups_count = cups_data.get("cups", 0)
                if cups_count > 0:
                    Clock.schedule_once(lambda dt: self.set_local_cups_count(cups_count))
                    print(f"🌐 GLOBAL CHECK: Cloud cups = {cups_count} (local synced)")
                else:
                    print(f"🌐 GLOBAL CHECK: Cloud cups = 0 (skipping local sync — may be post-dispense lag)")
                    
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

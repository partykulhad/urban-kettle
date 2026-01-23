from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition, NoTransition
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
import threading
import time
import os

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
from ui_pages.transaction_processing_page import TransactionProcessingPage
from ui_pages.dispensing_page import DispensingPage
from ui_pages.place_cup_page import PlaceCupPage
from ui_pages.thank_you_page import ThankYouPage
from ui_pages.screensaver_page import ScreensaverPage
from ui_pages.qr_expired_page import QRExpiredPage
from ui_pages.machine_empty_page import MachineEmptyPage
from ui_pages.rfid_auth_page import RFIDAuthPage
from ui_pages.hardware_debug_page import HardwareDebugPage
from ui_pages.hardware_error_page import HardwareErrorPage
from ui_pages.heating_page import HeatingPage


class ChaiOrderingApp(App):
    def build(self):
        self.title = "Urban Kettle"
        
        # Constants
        self.MACHINE_ID = "KH-01"
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
        self.global_status_check_interval = 5  # Check every 5 seconds
        self.previous_machine_state = None  # Track previous state for transition detection
        
        # *** Activity and hardware error monitoring ***
        self.activity_monitor_event = None
        self.hardware_error_monitor_event = None
        
        # *** NEW: Cup management variables ***
        self.selected_cups = 1  # Default number of cups
        self.current_cup_number = 1  # Current cup being dispensed
        
        # Create screen manager with no transition for faster page changes
        # SlideTransition can cause perceived lag, NoTransition is instant
        self.screen_manager = ScreenManager(transition=NoTransition())
        
        # Initialize pages
        self.payment_method_page = PaymentMethodPage(name='payment_method')
        self.selection_page = SelectionPage(name='selection')
        self.payment_page = PaymentPage(name='payment')
        self.loading_page = LoadingPage(name='loading')
        self.transaction_processing_page = TransactionProcessingPage(name='transaction_processing')
        self.dispensing_page = DispensingPage(name='dispensing')
        self.place_cup_page = PlaceCupPage(name='place_cup')  # *** NEW: Place cup page ***
        self.thank_you_page = ThankYouPage(name='thank_you')
        self.screensaver_page = ScreensaverPage(name='screensaver')
        self.qr_expired_page = QRExpiredPage(name='qr_expired')
        self.machine_empty_page = MachineEmptyPage(name='machine_empty')
        self.rfid_auth_page = RFIDAuthPage(name='rfid_auth')  # RFID authentication page
        self.hardware_debug_page = HardwareDebugPage(name='hardware_debug')  # Hardware debug page
        self.hardware_error_page = HardwareErrorPage(name='hardware_error')
        self.heating_page = HeatingPage(name='heating')  # Heating up page
        
        # Add screens to screen manager
        self.screen_manager.add_widget(self.payment_method_page)
        self.screen_manager.add_widget(self.selection_page)
        self.screen_manager.add_widget(self.payment_page)
        self.screen_manager.add_widget(self.loading_page)
        self.screen_manager.add_widget(self.transaction_processing_page)
        self.screen_manager.add_widget(self.dispensing_page)
        self.screen_manager.add_widget(self.place_cup_page)  # *** NEW: Add place cup page ***
        self.screen_manager.add_widget(self.thank_you_page)
        self.screen_manager.add_widget(self.screensaver_page)
        self.screen_manager.add_widget(self.qr_expired_page)
        self.screen_manager.add_widget(self.machine_empty_page)
        self.screen_manager.add_widget(self.rfid_auth_page)  # Add RFID auth page
        self.screen_manager.add_widget(self.hardware_debug_page)  # Add hardware debug page
        self.screen_manager.add_widget(self.hardware_error_page)
        self.screen_manager.add_widget(self.heating_page)  # Add heating page
        
        # Set initial screen to payment method selection
        self.screen_manager.current = 'payment_method'
        
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
        #Window.fullscreen = 'auto'
        # Start hardware monitoring service
        hardware_monitor.start()
        
        # Initialize RFID Auth Handler early (at app startup)
        print("🔐 Initializing RFID AES Auth Handler at startup...")
        try:
            from utils.rfid_aes_auth import RFIDAESAuth
            self.rfid_auth_handler = RFIDAESAuth(
                base_url="https://www.ukteawallet.com",
                machine_id="UK_0007"
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
        
        # Start global machine status monitoring
        self.start_global_status_monitoring()
        
        # Check if tea is heating up (schedule check after 1.5 seconds to allow hardware monitor to start)
        Clock.schedule_once(lambda dt: self.check_heating_on_startup(), 1.5)
        
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
        # Don't reset activity timer when showing screensaver
        if page_name != 'screensaver':
            self.reset_activity_timer()
    
    def show_payment_method_page(self, fetch_cups=False):
        """Show the payment method selection page
        Args:
            fetch_cups: If True, fetch cups count from API (for state transitions)
        """
        self.show_page('payment_method')
        
        # Fetch cups count if requested (for transitions from heating/hardware_error/screensaver)
        if fetch_cups:
            self.fetch_and_store_cups_count()
    
    def show_selection_page(self):
        """Show the selection page"""
        self.show_page('selection')
    
    def show_payment_page(self, number_of_cups=None):
        """Show the payment page with QR code generation"""
        # If number_of_cups is not provided, use the value from selection page
        if number_of_cups is None:
            number_of_cups = self.selection_page.get_cup_count()
        
        # *** NEW: Store selected cups ***
        self.set_selected_cups(number_of_cups)
        
        # Show loading page first
        self.show_loading_page()
        
        # Generate QR code in a separate thread to keep UI responsive
        threading.Thread(target=lambda: self.generate_qr_code(number_of_cups), daemon=True).start()
    
    def show_loading_page(self, message=None):
        """Show the loading page"""
        if message:
            self.loading_page.update_message(message)
        else:
            self.loading_page.update_message("Generating QR code for payment")
        self.show_page('loading')
        self.loading_page.start_animation()
    
    def show_transaction_processing_page(self):
        """Show the transaction processing page"""
        self.show_page('transaction_processing')
    
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
    
    def refresh_cups_count(self):
        """Refresh the cups count on payment method page"""
        if hasattr(self.payment_method_page, 'refresh_cups_count'):
            self.payment_method_page.refresh_cups_count()
    
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
                print("❌ Failed to sync cups reduction to backend")
                print(f"   API Response: {result}")
                # Note: Local counter already decremented, so UI is updated
                
        except Exception as e:
            print(f"❌ Error calling reduce cups API: {e}")
            # Note: Local counter already decremented, so UI is updated
    
    def generate_qr_code(self, number_of_cups):
        """Generate QR code with parallel API calls for faster response"""
        try:
            # Run machine status check and QR generation in parallel
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both API calls simultaneously
                status_future = executor.submit(self.api_client.check_machine_status, self.MACHINE_ID)
                qr_future = executor.submit(self.api_client.generate_payment_qr, self.MACHINE_ID, number_of_cups)
                
                # Wait for both to complete
                status_data = status_future.result()
                qr_data = qr_future.result()
            
            # Check machine status first
            if not status_data or not status_data.get("success", False):
                print("Machine status check failed during QR generation")
                Clock.schedule_once(lambda dt: self.show_error_fallback())
                return
            
            machine_status = status_data.get("data", {}).get("status", "").lower()
            if machine_status != "online":
                print(f"Machine is {machine_status} during QR generation")
                Clock.schedule_once(lambda dt: self.show_error_fallback())
                return
            
            # Machine is online, process QR generation result
            if qr_data:
                # NEW: Use imageContent directly to generate QR code
                image_content = qr_data.get("imageContent")
                
                if image_content:
                    print("⚡ Generating QR code from imageContent (fast method)...")
                    # Generate QR code directly from UPI string
                    qr_image = QRUtils.generate_qr_from_content(image_content)
                    
                    if qr_image:
                        # Update payment page in main thread
                        Clock.schedule_once(lambda dt: self.update_payment_page(qr_image, qr_data))
                        return
                else:
                    # Fallback: Use old method with imageUrl (deprecated)
                    print("⚠️ imageContent not found, falling back to imageUrl...")
                    image_url = qr_data.get("imageUrl")
                    
                    if image_url:
                        # Load QR image from URL
                        qr_image = QRUtils.load_qr_from_url(image_url)
                        
                        if qr_image:
                            # Detect and crop QR code
                            qr_image = QRUtils.detect_and_crop_qr(qr_image)
                            
                            # Update payment page in main thread
                            Clock.schedule_once(lambda dt: self.update_payment_page(qr_image, qr_data))
                            return
            
            # If we get here, there was an error
            Clock.schedule_once(lambda dt: self.show_error_fallback())
        except Exception as e:
            print(f"Error generating QR code: {e}")
            Clock.schedule_once(lambda dt: self.show_error_fallback())
    
    def update_payment_page(self, qr_image, data):
        """Update payment page with QR code and show it"""
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
    
    def show_error_fallback(self):
        """Show an error fallback QR code"""
        qr_image = QRUtils.create_qr_placeholder(300, 300)
        
        # Create a simple data object for the payment page
        error_data = {
            "amount": 0,
            "id": "",
            "transactionId": ""
        }
        
        # Update payment page with error QR
        self.payment_page.update(qr_image, error_data)
        
        # Show payment page with error QR
        self.show_page('payment')
    
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
        """Check the payment status with the API"""
        # Only proceed if we have a QR code ID and current page is payment page
        if not self.current_qr_code_id or self.screen_manager.current != 'payment':
            return
        
        # Call API to check status
        status_data = self.api_client.check_payment_status(self.current_qr_code_id)
        
        if status_data:
            status_message = status_data.get("message", "").lower()
            print(f"Payment status: {status_message}")
            
            # Update status based on message
            if status_message == "active":
                # Don't update status text when timer is running - let timer handle the display
                # Just schedule the next check
                self.status_check_event = Clock.schedule_once(self.check_payment_status, 2)
                
            elif status_message == "paid":
                self.payment_page.update_status("Payment received!")
                # Don't reduce cups here - will reduce when user clicks dispense
                # Show transaction processing page immediately, then move to dispensing
                Clock.schedule_once(lambda dt: self.show_transaction_processing_page(), 0.5)
                Clock.schedule_once(lambda dt: self.show_dispensing_page(), 4)
                
            elif status_message == "expired":
                print("Payment expired, cancelling automatically")
                self.payment_page.update_status("Payment expired!")
                # Auto cancel and go back to selection page
                Clock.schedule_once(lambda dt: self.cancel_payment(auto_cancel=True), 1)
            
            else:  # Unknown status
                # Schedule another check after 2 seconds
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
        
        # Navigate immediately (don't wait for API)
        if timer_expired:
            # Show QR expired page when timer expires
            self.show_page('qr_expired')
        elif not auto_cancel or (auto_cancel and self.screen_manager.current == 'payment'):
            # Return to selection page for normal cancellation
            self.show_selection_page()
        
        # Call API to cancel payment in background (non-blocking)
        if self.current_qr_code_id:
            qr_id = self.current_qr_code_id
            self.current_qr_code_id = ""  # Reset immediately
            
            # Cancel API call in background thread
            import threading
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
        critical_screens = ['dispensing', 'place_cup', 'payment', 'transaction_processing', 'thank_you', 'heating']
        if current_screen in critical_screens:
            # Skip error checking during critical operations
            return
        
        error_msg = hardware_monitor.get_latest_error()
        
        # Only show error page if we're not already on it and there's an error
        if error_msg and current_screen != 'hardware_error':
            print(f"Hardware error detected: {error_msg} - Navigating to error page")
            self.screen_manager.current = 'hardware_error'
            if hasattr(self.hardware_error_page, 'set_error_message'):
                self.hardware_error_page.set_error_message(error_msg)
    
    def check_heating_on_startup(self):
        """Check if tea is heating up on app startup"""
        def check_temp_background():
            try:
                # Check PT100 temperature
                temp = hardware_monitor.get_pt100_temperature()
                
                if temp is None:
                    # Can't get temperature, fetch cups and show home
                    print("⚠️ Can't get temperature, assuming ready")
                    Clock.schedule_once(lambda dt: self.show_payment_method_page(fetch_cups=True), 0)
                elif temp < 83:
                    # Tea is heating up
                    print(f"🔥 Tea is heating: {temp:.1f}°C (target: 83°C)")
                    Clock.schedule_once(lambda dt: self.show_heating_page(temp), 0)
                else:
                    # Tea is ready, fetch cups and show home
                    print(f"✅ Tea is ready: {temp:.1f}°C")
                    Clock.schedule_once(lambda dt: self.show_payment_method_page(fetch_cups=True), 0)
            
            except Exception as e:
                print(f"Heating check error: {e}")
                Clock.schedule_once(lambda dt: self.show_payment_method_page(fetch_cups=True), 0)
        
        # Run in background thread
        threading.Thread(target=check_temp_background, daemon=True).start()
    
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
        """Monitor temperature every 1 second until ready"""
        print("🔥 Starting heating monitor (checking every 1 second)")
        
        def check_temp():
            try:
                temp = hardware_monitor.get_pt100_temperature()
                
                if temp is None:
                    # Can't get temperature, assume ready, fetch cups and navigate
                    print("⚠️ Can't get temperature during heating, assuming ready")
                    self.stop_heating_monitor()
                    self.show_payment_method_page(fetch_cups=True)
                    return False
                
                # Update display
                self.heating_page.update_temperature(temp)
                
                if temp >= 83:
                    # Tea is ready! Fetch cups and navigate to home
                    print(f"✅ Tea ready at {temp:.1f}°C - navigating to home")
                    self.stop_heating_monitor()
                    self.show_payment_method_page(fetch_cups=True)
                    return False
                else:
                    # Still heating
                    print(f"🔥 Heating: {temp:.1f}°C / 83°C")
                    return True  # Continue checking
            
            except Exception as e:
                print(f"Heating monitor error: {e}")
                self.stop_heating_monitor()
                self.show_payment_method_page(fetch_cups=True)
                return False
        
        # Schedule check every 1 second
        self.heating_check_event = Clock.schedule_interval(lambda dt: check_temp(), 1)
    
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
            print("\n🚪 ESC key pressed - Shutting down gracefully...")
            self.stop()
            return True
        
        # Reset activity timer for any other key
        self.reset_activity_timer(window, key, *args)
        return False
    
    def on_stop(self):
        """Called when app is closing"""
        print("\n🛑 Application closing - Cleaning up...")
        
        # Stop heating monitor if running
        self.stop_heating_monitor()
        
        # Stop global status monitoring
        self.stop_global_status_monitoring()
        
        # Stop activity monitor if running
        if self.activity_monitor_event:
            self.activity_monitor_event.cancel()
            self.activity_monitor_event = None
        
        # Stop hardware error monitor if running
        if self.hardware_error_monitor_event:
            self.hardware_error_monitor_event.cancel()
            self.hardware_error_monitor_event = None
        
        # Stop hardware monitoring (this will also stop polling_server2.py)
        hardware_monitor.stop()
        
        print("✓ Cleanup complete. Goodbye!\n")
        return super().on_stop()
    
    def start_global_status_monitoring(self):
        """Start global machine status monitoring that runs on all pages"""
        # Stop any existing monitoring first
        self.stop_global_status_monitoring()
        
        # Schedule periodic check every 5 seconds
        self.global_status_monitor_event = Clock.schedule_interval(
            self.check_global_machine_status, 
            self.global_status_check_interval
        )
        print(f"🌐 Started GLOBAL machine status monitoring (every {self.global_status_check_interval} seconds)")
    
    def stop_global_status_monitoring(self):
        """Stop global machine status monitoring"""
        if self.global_status_monitor_event:
            self.global_status_monitor_event.cancel()
            self.global_status_monitor_event = None
            print("🛑 Stopped GLOBAL machine status monitoring")
    
    def check_global_machine_status(self, dt):
        """Check machine status in background - runs on all pages"""
        # Don't check if we're on certain pages where interruption would be bad
        current_page = self.screen_manager.current
        
        # Skip checking on these pages (user is in active flow)
        skip_pages = [
            'machine_empty',      # Already on offline page
            'screensaver',        # Screensaver active
            'place_cup',          # User placing cup
            'dispensing',         # Actively dispensing
            'thank_you',          # Showing thank you
            'transaction_processing',  # Processing payment
            'rfid_auth',          # RFID authentication
            'heating'             # Tea heating
        ]
        
        if current_page in skip_pages:
            return
        
        # Run check in background thread
        threading.Thread(target=self._do_global_status_check, daemon=True).start()
    
    def _do_global_status_check(self):
        """Perform global machine status check - only on home/selection/payment pages"""
        try:
            # Only check on pages where user is selecting/paying (not in dispensing flow)
            current_page = self.screen_manager.current
            check_pages = ['payment_method', 'selection', 'payment', 'loading']
            
            if current_page not in check_pages:
                return
            
            # Check machine status
            status_data = self.api_client.check_machine_status(self.MACHINE_ID)
            
            if status_data and status_data.get("success", False):
                data = status_data.get("data", {})
                machine_status = data.get("status", "offline")
                is_online = machine_status.lower() == "online"
                
                # Detect state transition and notify ESP32
                if self.previous_machine_state is not None:
                    if self.previous_machine_state == "online" and not is_online:
                        # Transition: Online → Offline
                        print("🔴 Machine state changed: ONLINE → OFFLINE")
                        self.send_machine_state_to_esp32("OFFLINE", "status_check_offline")
                    elif self.previous_machine_state == "offline" and is_online:
                        # Transition: Offline → Online
                        print("🟢 Machine state changed: OFFLINE → ONLINE")
                        self.send_machine_state_to_esp32("ONLINE", None)
                
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
                response = session.post(url, json=payload, timeout=5)
                
                if response.status_code == 200:
                    print(f"✅ ESP32 notified: Machine state set to {state}")
                else:
                    print(f"⚠️ Failed to notify ESP32: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error sending state to ESP32: {e}")
        
        # Send in background thread to avoid blocking
        threading.Thread(target=send_in_background, daemon=True).start()


if __name__ == "__main__":
    ChaiOrderingApp().run()

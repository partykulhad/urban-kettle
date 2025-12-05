from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
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
from utils.api_client import ApiClient
from utils.qr_utils import QRUtils
from utils.hardware_monitor import hardware_monitor
from utils.screensaver_manager import ScreensaverVideoManager

# Import page modules
from ui_pages.payment_method_page import PaymentMethodPage
from ui_pages.selection_page import SelectionPage
from ui_pages.payment_page import PaymentPage
from ui_pages.loading_page import LoadingPage
from ui_pages.transaction_processing_page import TransactionProcessingPage
from ui_pages.dispensing_page import DispensingPage, PlaceCupPage  # Added PlaceCupPage import
from ui_pages.thank_you_page import ThankYouPage
from ui_pages.screensaver_page import ScreensaverPage
from ui_pages.qr_expired_page import QRExpiredPage
from ui_pages.machine_empty_page import MachineEmptyPage
from ui_pages.rfid_auth_page import RFIDAuthPage
from ui_pages.hardware_debug_page import HardwareDebugPage
from ui_pages.hardware_error_page import HardwareErrorPage


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
        
        # *** NEW: Cup management variables ***
        self.selected_cups = 1  # Default number of cups
        self.current_cup_number = 1  # Current cup being dispensed
        
        # Create screen manager with slide transition
        self.screen_manager = ScreenManager(transition=SlideTransition())
        
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
        self.screen_manager.add_widget(self.rfid_auth_page)  # RFID authentication page
        self.screen_manager.add_widget(self.hardware_debug_page)  # Hardware debug page
        self.screen_manager.add_widget(self.hardware_error_page)
        
        # Set initial screen to payment method selection
        self.screen_manager.current = 'payment_method'
        
        # Setup screensaver monitoring
        self.setup_screensaver_monitoring()
        
        # Setup hardware error monitoring
        self.setup_hardware_error_monitoring()
        
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
        
        # Start hardware monitoring service
        hardware_monitor.start()
        
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
    
    def show_payment_method_page(self):
        """Show the payment method selection page"""
        self.show_page('payment_method')
    
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
        self.place_cup_page.update_cup_info(self.current_cup_number, self.selected_cups)
        self.show_page('place_cup')
    
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
    
    def reduce_cups_after_payment(self):
        """Reduce cups count after successful payment"""
        # Call reduce cups API in a separate thread to avoid blocking UI
        threading.Thread(target=self.call_reduce_cups_api, daemon=True).start()
    
    def call_reduce_cups_api(self):
        """Call the reduce cups API in background thread"""
        try:
            print(f"🔄 PAYMENT SUCCESSFUL - Reducing {self.selected_cups} cups from machine {self.MACHINE_ID}")
            
            # Call API to reduce cups
            result = self.api_client.reduce_cups(self.MACHINE_ID, self.selected_cups)
            
            if result and result.get("success", False):
                print(f"✅ Successfully reduced {self.selected_cups} cups")
                print(f"   Previous cups: {result.get('previousCups')}")
                print(f"   New cups: {result.get('newCups')}")
                print(f"   Message: {result.get('message')}")
                
                # Schedule cups count refresh on main thread
                Clock.schedule_once(lambda dt: self.refresh_cups_count(), 0.5)
            else:
                print("❌ Failed to reduce cups count")
                print(f"   API Response: {result}")
                
        except Exception as e:
            print(f"❌ Error calling reduce cups API: {e}")
    
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
            if qr_data and qr_data.get("success", False):
                # Get QR image URL from the response
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
            self.status_check_event = Clock.schedule_once(self.check_payment_status, 1)
    
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
                self.status_check_event = Clock.schedule_once(self.check_payment_status, 1)
                
            elif status_message == "paid":
                self.payment_page.update_status("Payment received!")
                # Reduce cups count when payment is successful
                self.reduce_cups_after_payment()
                # Show transaction processing page immediately, then move to dispensing
                Clock.schedule_once(lambda dt: self.show_transaction_processing_page(), 0.5)
                Clock.schedule_once(lambda dt: self.show_dispensing_page(), 4)
                
            elif status_message == "expired":
                print("Payment expired, cancelling automatically")
                self.payment_page.update_status("Payment expired!")
                # Auto cancel and go back to selection page
                Clock.schedule_once(lambda dt: self.cancel_payment(auto_cancel=True), 1)
            
            else:  # Unknown status
                # Schedule another check after 1 second
                self.status_check_event = Clock.schedule_once(self.check_payment_status, 1)
        else:
            # Try again after 1 second if API call failed
            self.status_check_event = Clock.schedule_once(self.check_payment_status, 1)
    
    def cancel_payment(self, auto_cancel=False, timer_expired=False):
        """Cancel the current payment"""
        # Stop status checking
        if self.status_check_event:
            self.status_check_event.cancel()
            self.status_check_event = None
        
        # Call API to cancel payment
        if self.current_qr_code_id:
            self.api_client.cancel_payment(self.current_qr_code_id)
            
            # Reset QR code ID
            self.current_qr_code_id = ""
        
        # Navigate based on cancellation reason
        if timer_expired:
            # Show QR expired page when timer expires
            self.show_page('qr_expired')
        elif not auto_cancel or (auto_cancel and self.screen_manager.current == 'payment'):
            # Return to selection page for normal cancellation
            self.show_selection_page()
    
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
        Window.bind(on_key_down=self.reset_activity_timer)
        Window.bind(on_touch_down=self.reset_activity_timer)
        
        # Start monitoring for inactivity
        Clock.schedule_interval(self.monitor_activity, 1)
    
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
        """Deactivate the screensaver - check machine status and navigate appropriately"""
        self.screensaver_active = False
        print("Deactivating screensaver - checking machine status...")
        
        # Check machine status and cups availability in background thread
        threading.Thread(target=self.check_machine_and_navigate, daemon=True).start()
    
    def check_machine_and_navigate(self):
        """Check machine status and cups, then navigate to appropriate page"""
        try:
            # Check machine status
            status_data = self.api_client.check_machine_status(self.MACHINE_ID)
            
            if status_data and status_data.get("success", False):
                # Get status from nested data object
                data = status_data.get("data", {})
                machine_status = data.get("status", "offline")
                is_online = machine_status.lower() == "online"
                
                print(f"Machine status: {machine_status}, is_online: {is_online}")
                
                if not is_online:
                    # Machine is offline, go to machine empty page
                    print("Machine is offline - navigating to machine empty page")
                    Clock.schedule_once(lambda dt: self.show_page('machine_empty'))
                    return
                
                # Machine is online, check cups availability
                cups_data = self.api_client.get_remaining_cups(self.MACHINE_ID)
                
                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    print(f"Cups available: {cups_count}")
                    
                    if cups_count > 0:
                        # Machine is online and has cups, go to payment method page
                        print("Machine is online with cups - navigating to payment method page")
                        Clock.schedule_once(lambda dt: self.show_payment_method_page())
                    else:
                        # Machine is online but no cups, go to machine empty page
                        print("Machine is online but no cups - navigating to machine empty page")
                        Clock.schedule_once(lambda dt: self.show_page('machine_empty'))
                else:
                    # Failed to get cups data, fallback to payment method page
                    print("Failed to get cups data - navigating to payment method page")
                    Clock.schedule_once(lambda dt: self.show_payment_method_page())
            else:
                # Failed to get machine status, fallback to payment method page
                print("Failed to get machine status - navigating to payment method page")
                Clock.schedule_once(lambda dt: self.show_payment_method_page())
                
        except Exception as e:
            print(f"Error checking machine status: {e}")
            # On error, fallback to payment method page
            Clock.schedule_once(lambda dt: self.show_payment_method_page())
    
    def on_timer_expired(self):
        """Handle payment timer expiration"""
        print("Timer expired - cancelling payment and showing expiration page")
        # Cancel payment with timer_expired flag
        self.cancel_payment(timer_expired=True)
    
    def setup_hardware_error_monitoring(self):
        """Setup monitoring for hardware errors"""
        # Check for errors every 2 seconds
        Clock.schedule_interval(self.check_hardware_errors, 2)
        
    def check_hardware_errors(self, dt):
        """Check for hardware errors and navigate to error page if needed"""
        error_msg = hardware_monitor.get_latest_error()
        
        current_screen = self.screen_manager.current
        
        # Only show error page if we're not already on it and there's an error
        if error_msg and current_screen != 'hardware_error':
            print(f"Hardware error detected: {error_msg} - Navigating to error page")
            self.screen_manager.current = 'hardware_error'
            if hasattr(self.hardware_error_page, 'set_error_message'):
                self.hardware_error_page.set_error_message(error_msg)
    
    def on_stop(self):
        """Called when app is closing"""
        # Stop hardware monitoring
        hardware_monitor.stop()
        return super().on_stop()


if __name__ == "__main__":
    ChaiOrderingApp().run()

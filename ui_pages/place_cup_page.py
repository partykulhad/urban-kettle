from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
import os
import threading
import uuid
from utils.api_client import get_localhost_session


class PlaceCupPage(Screen):
    """Simple page to instruct user to place cup - matching the design"""
    
    def __init__(self, **kwargs):
        super(PlaceCupPage, self).__init__(**kwargs)
        
        # Main layout - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=10)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top section with logo on left - matching other pages
        from kivy.uix.floatlayout import FloatLayout
        top_section = BoxLayout(orientation='vertical', size_hint_y=0.18, padding=[10, 5])
        
        # Logo on the left
        logo_float = FloatLayout(size_hint_y=0.6)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                pos_hint={'x': -0.05, 'top': 1.3},
                allow_stretch=True,
                keep_ratio=True
            )
            logo_float.add_widget(logo_image)
        else:
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='28sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='left'
            )
            logo_float.add_widget(fallback_logo)
        
        top_section.add_widget(logo_float)
        
        # "PAYMENT RECEIVED" text - reduced font
        payment_label = Label(
            text='PAYMENT RECEIVED',
            font_size='28sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.5
        )
        top_section.add_widget(payment_label)
        
        # Cup counter label (e.g., "Cup 1 of 3")
        self.cup_counter_label = Label(
            text='Cup 1 of 1',
            font_size='20sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            size_hint_y=0.5
        )
        top_section.add_widget(self.cup_counter_label)
        
        main_layout.add_widget(top_section)
        
        # Place cup image section
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.40)
        
        placecup_image = Image(
            source=os.path.join('assets', 'placecup.png'),
            size_hint=(None, None),
            size=(300, 240),
            allow_stretch=True,
            keep_ratio=True
        )
        
        image_section.add_widget(placecup_image)
        main_layout.add_widget(image_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # "Please place your cup in the holder." text - bigger fonts
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.12, spacing=5)
        
        place_label = Label(
            text='Please place your cup',
            font_size='28sp',  # Increased from 24sp
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(place_label)
        
        holder_label = Label(
            text='in the holder.',
            font_size='28sp',  # Increased from 24sp
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(holder_label)
        
        main_layout.add_widget(instruction_section)
        
        # Spacing before button - move button down
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Continue button - bigger with proper text fit
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.11)
        
        # Simple button class for this page
        class SimpleButton(Button):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.background_color = (0, 0, 0, 0)
                self.background_normal = ''
                self.bind(size=self.update_graphics, pos=self.update_graphics)
            
            def update_graphics(self, *args):
                self.canvas.before.clear()
                with self.canvas.before:
                    Color(0.949, 0.6, 0.0, 1)
                    RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
        
        self.continue_button = SimpleButton(
            text='Continue Dispensing',
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(380, 65)
        )
        self.continue_button.bind(on_press=self.on_continue_pressed)
        self.continue_button.disabled = True
        self.continue_button.opacity = 0.5
        
        button_section.add_widget(self.continue_button)
        main_layout.add_widget(button_section)
        
        # Cup status label - bigger font
        self.cup_status_label = Label(
            text='Waiting for cup...',
            font_size='20sp',  # Increased from 16sp
            color=(0.906, 0.298, 0.235, 1),
            size_hint_y=0.06,
            halign='center'
        )
        main_layout.add_widget(self.cup_status_label)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        self.add_widget(main_layout)
        
        # Cup sensor checking with timeout
        self.cup_check_event = None
        self.page_timeout_event = None
        self.page_entered_time = 0
        self.cup_detected_time = None
        self.testing_mode_enabled = False  # Flag for testing mode
        self.error_popup_count = 0  # Track number of error popups shown
        
        # PRODUCTION FIX: Button debouncing to prevent multiple dispenses
        self.button_pressed = False  # Track if button already pressed
        self.dispense_in_progress = False  # Track if dispense command sent
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def update_cup_info(self, current_cup, total_cups):
        """Update the cup information display"""
        self.cup_counter_label.text = f'Cup {current_cup} of {total_cups}'
        print(f"📋 Updated cup counter: Cup {current_cup} of {total_cups}")
    
    def send_dispense_command(self):
        """Send dispense command to ESP32 via polling server
        Returns: (success, status_code, response_data)
        """
        try:
            # Generate unique job ID
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            command_id = f"cmd_dispense_{int(threading.get_ident()) % 1000000}"
            
            print("="*80)
            print("🚀 DISPENSE COMMAND - SENDING TO ESP32")
            print("="*80)
            # Get device ID from central config
            from config import DEVICE_ID
            
            print(f"🔧 Job ID: {job_id}")
            print(f"🔧 Command ID: {command_id}")
            print(f"🔧 Device ID: {DEVICE_ID}")
            
            # API endpoint
            url = "http://localhost:5000/api/device/command"
            
            # Prepare the request payload
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": command_id,
                "deviceId": DEVICE_ID,
                "command": {
                    "action": "start_dispense",
                    "parameters": {
                        "jobId": job_id
                    }
                }
            }
            
            print(f"🔧 API Endpoint: {url}")
            print(f"🔧 Payload:")
            import json
            print(json.dumps(payload, indent=2))
            print("="*80)
            print("⏳ Sending request to polling server...")
            print("="*80)
            
            # Send POST request with longer timeout for ESP32 response (using pooled session)
            session = get_localhost_session()
            response = session.post(url, json=payload, timeout=30)
            
            print("="*80)
            print("📥 RESPONSE RECEIVED")
            print("="*80)
            print(f"✓ HTTP Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Response JSON:")
                print(json.dumps(result, indent=2))
                
                # Get the status code from ESP32 response
                esp_status_code = result.get('response', {}).get('statusCode', 200)
                status = result.get('response', {}).get('status')
                
                print(f"\n✅ DISPENSE COMMAND SUCCESSFUL!")
                print(f"   Response Status: {status}")
                print(f"   ESP32 Status Code: {esp_status_code}")
                print(f"   Command ID: {result.get('commandId')}")
                print("="*80)
                
                return (True, esp_status_code, result)
            else:
                print(f"❌ DISPENSE COMMAND FAILED")
                print(f"   HTTP Status Code: {response.status_code}")
                print(f"   Response: {response.text}")
                print("="*80)
                return (False, response.status_code, None)
                
        except Exception as e:
            print("="*80)
            print(f"❌ ERROR SENDING DISPENSE COMMAND")
            print("="*80)
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            print("="*80)
            return (False, None, None)
    
    def show_technical_error_popup(self, status_code):
        """Show popup for machine technical issues"""
        # Increment error popup count
        self.error_popup_count += 1
        
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # Error icon/message
        error_label = Label(
            text='⚠️',
            font_size='60sp',
            size_hint_y=0.3
        )
        content.add_widget(error_label)
        
        # Specific error messages based on status code
        error_messages = {
            700: 'Temperature Low\\nWaiting for water to heat up',
            701: 'Temperature Critical\\nPlease contact support',
            704: 'Cup Not Detected\\nPlease place cup properly',
            705: 'Flow Failure\\nPlease contact support',
            706: 'Pump Fault\\nPlease contact support',
            707: 'Heater Fault\\nPlease contact support',
            711: 'Pump Timeout\\nPlease contact support'
        }
        
        error_text = error_messages.get(status_code, 'Machine has some technical issue\\nPlease wait for some time')
        
        # Error message
        message_label = Label(
            text=error_text,
            font_size='20sp',
            halign='center',
            valign='middle',
            size_hint_y=0.4
        )
        message_label.bind(size=message_label.setter('text_size'))
        content.add_widget(message_label)
        
        # Status code info with attempt counter
        code_label = Label(
            text=f'Error Code: {status_code}\\nAttempt {self.error_popup_count} of 3',
            font_size='16sp',
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=0.2,
            halign='center'
        )
        code_label.bind(size=code_label.setter('text_size'))
        content.add_widget(code_label)
        
        # OK button
        ok_button = Button(
            text='OK',
            size_hint_y=0.3,
            font_size='18sp',
            background_color=(0.851, 0.647, 0.125, 1)
        )
        content.add_widget(ok_button)
        
        # Create popup
        popup = Popup(
            title='Technical Issue',
            content=content,
            size_hint=(0.7, 0.5),
            auto_dismiss=False
        )
        
        # Bind OK button to close popup
        def on_ok_press(instance):
            popup.dismiss()
            
            if self.error_popup_count >= 3:
                # Third error - go to home page
                print(f"❌ Third error popup - returning to home page")
                app = App.get_running_app()
                Clock.schedule_once(lambda dt: app.show_page('payment_method'), 0.5)
            else:
                # First or second error - stay on page, reset timer, allow retry
                print(f"⚠️ Error popup {self.error_popup_count}/3 - staying on page, resetting timer")
                
                # Reset the 10-second timeout to give more time
                self.stop_page_timeout()
                import time
                self.page_entered_time = time.time()
                self.start_page_timeout()
                
                # Re-enable cup sensor checking if it was stopped
                if not self.cup_check_event:
                    self.start_cup_sensor_check()
        
        ok_button.bind(on_press=on_ok_press)
        popup.open()
    
    def start_page_timeout(self):
        """Start 10-second timeout - return to home if no cup or no action"""
        print("⏱️ Starting 10-second page timeout...")
        self.page_timeout_event = Clock.schedule_once(self.on_page_timeout, 20.0)
    
    def stop_page_timeout(self):
        """Stop page timeout"""
        if self.page_timeout_event:
            self.page_timeout_event.cancel()
            self.page_timeout_event = None
    
    def on_page_timeout(self, dt):
        """Called when 20 seconds elapsed"""
        import time
        elapsed = time.time() - self.page_entered_time
        
        app = App.get_running_app()
        
        if self.cup_detected_time is None:
            # No cup detected in 20 seconds
            print(f"⏰ Timeout: No cup detected after {elapsed:.1f}s")
        else:
            # Cup detected but button not clicked in 20 seconds
            cup_detected_duration = time.time() - self.cup_detected_time
            print(f"⏰ Timeout: Cup detected but no action for {cup_detected_duration:.1f}s")
        
        # Stop sensors and timeout
        self.stop_cup_sensor_check()
        self.stop_page_timeout()
        
        # Reset debouncing flags for next action
        self.button_pressed = False
        self.dispense_in_progress = False
        
        # Check if this is the final cup (with safety checks for testing)
        if hasattr(app, 'current_cup_number') and hasattr(app, 'selected_cups'):
            if app.current_cup_number >= app.selected_cups:
                # Final cup - go to home screen (all cups completed/skipped)
                print(f"🏠 Final cup (Cup {app.current_cup_number} of {app.selected_cups}) timed out - returning to home screen")
                self.return_to_home("Timeout on final cup")
            else:
                # Not final cup - skip and move to next
                print(f"⏩ Skipping cup {app.current_cup_number} of {app.selected_cups} and moving to next cup")
                Clock.schedule_once(lambda dt: app.handle_cup_completion(), 0.5)
        else:
            # No cup tracking (test mode or standalone) - just go home
            print("🏠 Timeout - returning to home (no multi-cup tracking)")
            self.return_to_home("Timeout - no cup tracking")
    
    def return_to_home(self, reason):
        """Return to home page with message"""
        print(f"🏠 Returning to home: {reason}")
        self.stop_cup_sensor_check()
        self.stop_page_timeout()
        
        # Reset debouncing flags
        self.button_pressed = False
        self.dispense_in_progress = False
        
        app = App.get_running_app()
        Clock.schedule_once(lambda dt: app.show_payment_method_page(), 0)
    
    def on_continue_pressed(self, instance):
        """Handle continue button press - PRODUCTION: Debounced to prevent multiple dispenses"""
        
        # PRODUCTION FIX: Prevent multiple rapid taps
        if self.button_pressed or self.dispense_in_progress:
            print("⚠️ Button already pressed - ignoring duplicate tap")
            return
        
        # Mark button as pressed immediately
        self.button_pressed = True
        self.dispense_in_progress = True
        
        # Disable button immediately to prevent further taps
        self.continue_button.disabled = True
        self.continue_button.opacity = 0.5
        
        print("\n" + "="*80)
        print("🎯 CONFIRM TO DISPENSE BUTTON PRESSED")
        print("="*80)
        
        # Stop timeout and polling
        self.stop_cup_sensor_check()
        self.stop_page_timeout()
        
        # Reduce 1 cup count when user confirms dispensing
        app = App.get_running_app()
        print("🔄 Reducing 1 cup from machine count...")
        app.reduce_one_cup()
        
        # COMMENTED OUT: Navigate to dispensing page immediately (onclick approach)
        # Uncomment below if you want immediate navigation without waiting for status code
        # print("✅ Navigating to dispensing page immediately")
        # Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)
        
        # STATUS CODE APPROACH: Send dispense command and wait for 200 status code
        def send_command_and_wait():
            print("🔄 Sending dispense command and waiting for status code...")
            success, status_code, response_data = self.send_dispense_command()
            
            if success and status_code == 200:
                # Status code 200 - navigate to dispensing page
                print("✅ Status code 200 received - navigating to dispensing page")
                Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)
            elif status_code in [700, 701, 704, 705, 706, 707, 711]:
                # Technical error - show popup and reset button state
                print(f"⚠️ Technical error {status_code} - showing popup")
                Clock.schedule_once(lambda dt: self.show_technical_error_popup(status_code), 0)
                # Reset button state on error
                self.button_pressed = False
                self.dispense_in_progress = False
            else:
                # Other error - show generic error and reset
                print(f"❌ Error status code {status_code} - showing error popup")
                Clock.schedule_once(lambda dt: self.show_technical_error_popup(status_code or 999), 0)
                # Reset button state on error
                self.button_pressed = False
                self.dispense_in_progress = False
        
        threading.Thread(target=send_command_and_wait, daemon=True).start()
        print("="*80 + "\n")

    
    def on_enter(self):
        """Called when page is entered"""
        import time
        # Reset state (but not if dispense is in progress)
        if not hasattr(self, 'dispense_in_progress'):
            self.dispense_in_progress = False
        
        if self.dispense_in_progress:
            print("⏸️ Dispense in progress - skipping timeout initialization")
            return
        
        # Reset debouncing flags for fresh page entry (new payment or next cup)
        self.button_pressed = False
        
        self.page_entered_time = time.time()
        self.cup_detected_time = None
        self.testing_mode_enabled = False  # Reset testing mode flag
        self.error_popup_count = 0  # Reset error counter on page entry
        self.continue_button.disabled = True
        self.continue_button.opacity = 0.5
        self.cup_status_label.text = 'Waiting for cup...'
        
        # Update cup counter display
        app = App.get_running_app()
        if hasattr(app, 'current_cup_number') and hasattr(app, 'selected_cups'):
            self.update_cup_info(app.current_cup_number, app.selected_cups)
        self.cup_status_label.color = (0.906, 0.298, 0.235, 1)  # Red
        
        # No video to start - using static image
        
        # Start checking for cup sensor (every 1 second)
        self.start_cup_sensor_check()
        
        # Start 10-second timeout
        self.start_page_timeout()
        
        # TESTING: Auto-enable button after 5 seconds (remove this later)
       #print("⏱️ TESTING MODE: Button will auto-enable after 5 seconds")
       #Clock.schedule_once(self.auto_enable_button_for_testing, 5)
    
    def on_leave(self):
        """Called when page is left"""
        # No video to stop - using static image
        
        # Reset dispense and button flags when leaving
        self.dispense_in_progress = False
        self.button_pressed = False
        
        # Stop checking cup sensor
        self.stop_cup_sensor_check()
        # Stop timeout
        self.stop_page_timeout()
    
    def start_cup_sensor_check(self):
        """Start cup sensor checking using a single background thread"""
        print("🔍 Starting cup detection polling (background thread)...")
        self._cup_check_running = True
        self._cup_check_thread = threading.Thread(target=self._cup_check_loop, daemon=True)
        self._cup_check_thread.start()
    
    def stop_cup_sensor_check(self):
        """Stop checking cup sensor"""
        self._cup_check_running = False
        # Thread will exit on next iteration
    
    def _cup_check_loop(self):
        """Background thread loop for cup detection - runs every 1 second"""
        import time
        while self._cup_check_running:
            self._do_cup_check()
            # Sleep for 1 second before next check
            time.sleep(1.0)
    
    def _do_cup_check(self):
        """Poll request_cup API"""
        try:
            from config import DEVICE_ID
            
            url = "http://localhost:5000/api/device/command"
            payload = {
                "messageType": "request_cup",
                "commandType": "request",
                "version": "1.0",
                "deviceId": DEVICE_ID
            }
            
            # Use pooled session for connection reuse
            session = get_localhost_session()
            response = session.post(url, json=payload, timeout=2)
            
            if response.status_code == 200:
                result = response.json()
                status_code = result.get('statusCode')
                
                # Status 200 = Cup detected
                # Status 704 = No cup
                cup_detected = (status_code == 200)
                
                # Update UI on main thread
                Clock.schedule_once(lambda dt: self._update_cup_status(cup_detected, status_code), 0)
            else:
                # API failed, assume no cup
                Clock.schedule_once(lambda dt: self._update_cup_status(False, None), 0)
                
        except Exception as e:
            print(f"Cup detection error: {e}")
            # Keep button disabled on error
            Clock.schedule_once(lambda dt: self._update_cup_status(False, None), 0)
    
    def auto_enable_button_for_testing(self, dt):
        """TESTING ONLY: Auto-enable button after 5 seconds
        TODO: Remove this method when cup sensor is working properly
        """
        print("🧪 TESTING: Auto-enabling dispense button (cup sensor bypass)")
        
        # Set testing mode flag to prevent cup sensor from disabling button
        self.testing_mode_enabled = True
        
        # Stop cup sensor polling to prevent it from disabling the button
        self.stop_cup_sensor_check()
        print("🧪 TESTING: Stopped cup sensor polling")
        
        # Enable the button
        self.cup_status_label.text = ''
        self.cup_status_label.color = (0.298, 0.686, 0.314, 1)  # Green
        self.continue_button.disabled = False
        self.continue_button.opacity = 1.0
        
        import time
        if self.cup_detected_time is None:
            self.cup_detected_time = time.time()
    
    def _update_cup_status(self, cup_detected, status_code):
        """Update cup status UI based on API response"""
        import time
        
        # If testing mode is enabled, don't update status (keep button enabled)
        if hasattr(self, 'testing_mode_enabled') and self.testing_mode_enabled:
            print("🧪 TESTING: Ignoring cup status update - testing mode active")
            return
        
        if cup_detected:
            # Cup detected (status 200)
            print(f"✅ Cup detected! (Status: {status_code})")
            self.cup_status_label.text = '✓ Cup detected - Ready to dispense'
            self.cup_status_label.color = (0.298, 0.686, 0.314, 1)  # Green
            self.continue_button.disabled = False
            self.continue_button.opacity = 1.0
            
            # Track when cup was first detected
            if self.cup_detected_time is None:
                self.cup_detected_time = time.time()
        else:
            # No cup (status 704 or error)
            if status_code == 704:
                print(f"⏳ Waiting for cup... (Status: {status_code})")
            self.cup_status_label.text = 'Waiting for cup...'
            self.cup_status_label.color = (0.906, 0.298, 0.235, 1)  # Red
            self.continue_button.disabled = True
            self.continue_button.opacity = 0.5
            self.cup_detected_time = None

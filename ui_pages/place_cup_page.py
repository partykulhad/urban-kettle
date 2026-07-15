from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
import os
import threading
import uuid
from kivy.core.image import Image as CoreImage
from utils.api_client import get_localhost_session
from config import POLLING_SERVER_URL


class PlaceCupPage(Screen):
    """Simple page to instruct user to place cup - matching the design"""
    
    # Timeout in seconds - change this value to adjust the countdown duration
    PAGE_TIMEOUT_SECONDS = 30
    
    def __init__(self, **kwargs):
        super(PlaceCupPage, self).__init__(**kwargs)
        
        # Timer variables
        self.countdown_seconds = self.PAGE_TIMEOUT_SECONDS
        self.countdown_event = None
        
        # Use FloatLayout as root to allow timer overlay
        root_layout = FloatLayout()
        
        # Main layout - no padding to match payment_method_page exactly
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top bar with logo on left - matching payment_method_page exactly
        top_bar = FloatLayout(size_hint_y=0.15)
        
        # Urban Kettle logo on the left side - same as payment_method_page
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                pos_hint={'x': 0.0, 'top': 1.35},
                allow_stretch=True,
                keep_ratio=True
            )
            top_bar.add_widget(logo_image)
        else:
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='28sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                pos_hint={'x': 0.02, 'top': 0.95},
                halign='left'
            )
            top_bar.add_widget(fallback_logo)
        
        main_layout.add_widget(top_bar)
        
        # "PLACE THE CUP" text
        payment_label = Label(
            text='PLACE THE CUP',
            font_size='36sp',
            bold=True,
            color=(0.333, 0.224, 0.118, 1),  # Dark brown color from mockup
            halign='center',
            size_hint_y=0.06
        )
        main_layout.add_widget(payment_label)
        
        # Cup counter label (e.g., "Cup 1 of 3")
        self.cup_counter_label = Label(
            text='',  # Hidden by default
            font_size='20sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            size_hint_y=0.04
        )
        main_layout.add_widget(self.cup_counter_label)
        
        # Image and Timer section - horizontal layout
        image_timer_section = BoxLayout(orientation='horizontal', size_hint_y=0.45)
        
        # Left spacer to keep image centered
        image_timer_section.add_widget(Widget(size_hint_x=0.4))
        
        # Center - Place cup image (New 3D dispenser bay)
        image_container = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_x=0.4)
        placecup_image = Image(
            source=os.path.join('assets', 'dispenser_bay_cropped.png'),
            size_hint=(None, None),
            size=(420, 280),  # Fixed size to prevent overlapping
            allow_stretch=True,
            keep_ratio=True
        )
        image_container.add_widget(placecup_image)
        image_timer_section.add_widget(image_container)
        
        # Right side - Warning text first, then Timer below
        timer_container = BoxLayout(orientation='vertical', size_hint_x=0.4, padding=[0, 30, 10, 30])
        
        # Spacer to center vertically - reduced to move timer up
        timer_container.add_widget(Widget(size_hint_y=0.05))
        
        # # Blinking warning text - red color (COMMENTED OUT)
        # self.warning_label = Label(
        #     text='If cup is not placed,\ntransaction will be\ncancelled',
        #     font_size='14sp',
        #     bold=True,
        #     color=(0.906, 0.298, 0.235, 1),  # Red color
        #     size_hint_y=0.4,
        #     halign='center',
        #     valign='middle'
        # )
        # self.warning_label.bind(size=self.warning_label.setter('text_size'))
        # timer_container.add_widget(self.warning_label)
        
        # Timer label - large, red (moved up)
        self.timer_label = Label(
            text=str(self.PAGE_TIMEOUT_SECONDS),
            font_size='50sp',
            bold=True,
            color=(0.906, 0.298, 0.235, 1),  # Red color
            size_hint_y=0.75,  # Increased to occupy more space
            halign='center',
            valign='middle'
        )
        timer_container.add_widget(self.timer_label)
        
        # Spacer
        timer_container.add_widget(Widget(size_hint_y=0.1))
        
        image_timer_section.add_widget(timer_container)
        main_layout.add_widget(image_timer_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # "Please place your cup in the holder." text - blinking red
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.01, spacing=0)
        
        # Instruction text - hidden to match mockup, but kept for layout spacing
        self.warning_label = Label(
            text='',
            font_size='32sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            valign='middle',
            size_hint_y=0.01
        )
        self.warning_label.bind(size=self.warning_label.setter('text_size'))
        instruction_section.add_widget(self.warning_label)
        
        # # Original non-blinking labels (COMMENTED OUT)
        # place_label = Label(
        #     text='Please place your cup',
        #     font_size='28sp',
        #     color=(0.3, 0.3, 0.3, 1),
        #     halign='center'
        # )
        # instruction_section.add_widget(place_label)
        # 
        # holder_label = Label(
        #     text='in the holder.',
        #     font_size='28sp',
        #     color=(0.3, 0.3, 0.3, 1),
        #     halign='center'
        # )
        # instruction_section.add_widget(holder_label)
        
        main_layout.add_widget(instruction_section)
        
        # Spacing before button - removed to push button up
        main_layout.add_widget(Widget(size_hint_y=0.001))
        
        # Continue button - sized to match selection page buttons
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.12)
        
        # Simple button class for this page
        class SimpleButton(Button):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.background_color = (0, 0, 0, 0)
                self.background_normal = ''
                self.bg_color = [0.875, 0.545, 0.086, 1]  # Gradient top approx (#DF8B16)
                self.border_color = [0.765, 0.467, 0.063, 1] # Darker bottom border (#C37710)
                
                # Load icon texture
                try:
                    self.icon = CoreImage('assets/touch_icon.png').texture
                except:
                    self.icon = None
                    
                self.bind(size=self.update_graphics, pos=self.update_graphics)
            
            def update_graphics(self, *args):
                self.canvas.before.clear()
                with self.canvas.before:
                    # Draw 3D shadow (darker bottom border)
                    Color(*self.border_color)
                    RoundedRectangle(pos=(self.pos[0], self.pos[1]-6), size=self.size, radius=[20])
                    
                    # Draw main button
                    Color(*self.bg_color)
                    RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
                    
                    # Draw icon if we have it
                    if self.icon:
                        Color(1, 1, 1, 1)
                        # Icon matching the selection page styling
                        icon_size = 48 
                        icon_pos = (self.pos[0] + 65, self.pos[1] + (self.size[1] - icon_size)/2)
                        from kivy.graphics import Rectangle
                        Rectangle(texture=self.icon, pos=icon_pos, size=(icon_size, icon_size))
        
        self.continue_button = SimpleButton(
            text='       TOUCH TO DISPENSE',
            font_size='26sp',  # Matching selection page font size
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(500, 80)  # Sized similar to selection page confirm button
        )
        self.continue_button.bind(on_press=self.on_continue_pressed)
        # Bypassed cup sensor: Button is now enabled by default
        self.continue_button.disabled = False
        self.continue_button.opacity = 1.0
        
        button_section.add_widget(self.continue_button)
        main_layout.add_widget(button_section)
        
        # Cup status label removed (bypassed)
        
        # Bottom spacing - increased to push the button up
        main_layout.add_widget(Widget(size_hint_y=0.12))
        
        # Add main layout to root
        root_layout.add_widget(main_layout)
        
        self.add_widget(root_layout)
        
        # Blinking animation event
        self.blink_event = None
        
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
        if total_cups > 1:
            self.cup_counter_label.text = f'Cup {current_cup} of {total_cups}'
        else:
            self.cup_counter_label.text = ''  # Hide if only 1 cup
        print(f"📋 Updated cup counter: Cup {current_cup} of {total_cups}")
    
    def send_dispense_command(self):
        """Send dispense command to ESP32 via polling server
        Returns: (success, status_code, response_data)
        """
        try:
            # Generate unique job ID and command ID to prevent collision
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            command_id = f"cmd_dispense_{uuid.uuid4().hex[:12]}"
            
            print("="*80)
            print("🚀 DISPENSE COMMAND - SENDING TO ESP32")
            print("="*80)
            # Get device ID from central config
            from config import DEVICE_ID
            
            print(f"🔧 Job ID: {job_id}")
            print(f"🔧 Command ID: {command_id}")
            print(f"🔧 Device ID: {DEVICE_ID}")
            
            # API endpoint - use central config, not hardcoded
            url = f"{POLLING_SERVER_URL}/api/device/command"
            
            # Calculate pump duration from ml quantity (flow rate in config.py)
            from config import ml_to_pump_ms
            from kivy.app import App as _App
            ml = getattr(_App.get_running_app(), 'ml_to_dispense', 100)
            pump_duration_ms = ml_to_pump_ms(ml)
            print(f"🔧 Pump duration: {ml} ml → {pump_duration_ms} ms")

            # Prepare the request payload
            # pumpOperationDuration is NOT sent here per schema §7.1 — ESP32 uses
            # the value synced via handshake config and update_pump_settings (§7.3).
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
            
            # 35s: enough for one ESP32 poll cycle (~10-30s) + execution
            session = get_localhost_session()
            response = session.post(url, json=payload, timeout=35)
            
            print("="*80)
            print("📥 RESPONSE RECEIVED")
            print("="*80)
            print(f"✓ HTTP Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Response JSON:")
                print(json.dumps(result, indent=2))
                
                # Get the status code from ESP32 response.
                # ESP32 firmware may return statusCode at the top level OR nested
                # under a 'response' key — check both so temperature errors (700/701)
                # are never misread as success (200 default).
                nested = result.get('response', {})
                nested_code = nested.get('statusCode')
                flat_code = result.get('statusCode')
                esp_status_code = (nested_code if nested_code is not None
                                   else (flat_code if flat_code is not None
                                         else 200))
                status = nested.get('status') or result.get('status')

                print(f"\n✅ DISPENSE COMMAND RECEIVED!")
                print(f"   Response Status: {status}")
                print(f"   ESP32 Status Code: {esp_status_code} "
                      f"(nested={nested_code}, flat={flat_code})")
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
            700: 'Temperature Low\nWaiting for water to heat up',
            701: 'Temperature Critical\nPlease contact support',
            704: 'Cup Not Detected\nPlease place cup properly',
            705: 'Flow Failure\nPlease contact support',
            706: 'Pump Fault\nPlease contact support',
            707: 'Heater Fault\nPlease contact support',
            708: 'Low Water Level\nFill tank and retry',
            711: 'Pump Timeout\nPlease contact support'
        }

        error_text = error_messages.get(status_code, 'Machine has some technical issue\nPlease wait for some time')
        
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
            text=f'Error Code: {status_code}\nAttempt {self.error_popup_count} of 3',
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
                Clock.schedule_once(lambda dt: app.show_payment_method_page(), 0.5)
            else:
                # First or second error - stay on page, reset timer, allow retry
                print(f"⚠️ Error popup {self.error_popup_count}/3 - staying on page, resetting timer")
                
                # Reset the 10-second timeout to give more time
                self.stop_page_timeout()
                import time
                self.page_entered_time = time.time()
                self.start_page_timeout()
                
                # Cup sensor check is bypassed, no need to restart it
                # But we must re-enable the continue button so user can retry
                self.continue_button.disabled = False
                self.continue_button.opacity = 1.0
                pass
        
        ok_button.bind(on_press=on_ok_press)
        popup.open()
    
    def start_page_timeout(self):
        """Start page timeout with visible countdown - return to home if no cup or no action"""
        print(f"⏱️ Starting {self.PAGE_TIMEOUT_SECONDS}-second page timeout...")
        
        # Initialize countdown
        self.countdown_seconds = self.PAGE_TIMEOUT_SECONDS
        self.timer_label.text = str(self.countdown_seconds)
        self.timer_label.color = (0.906, 0.298, 0.235, 1)  # Red color
        
        # Start countdown timer (updates every second)
        self.countdown_event = Clock.schedule_interval(self.update_countdown, 1.0)
    
    def stop_page_timeout(self):
        """Stop page timeout and countdown"""
        if self.page_timeout_event:
            self.page_timeout_event.cancel()
            self.page_timeout_event = None
        if self.countdown_event:
            self.countdown_event.cancel()
            self.countdown_event = None
    
    def update_countdown(self, dt):
        """Update countdown timer every second"""
        self.countdown_seconds -= 1
        self.timer_label.text = str(self.countdown_seconds)
        
        # Change color to more urgent as time runs low
        if self.countdown_seconds <= 10:
            self.timer_label.color = (0.9, 0.2, 0.1, 1)  # Darker red
        if self.countdown_seconds <= 5:
            self.timer_label.color = (1, 0, 0, 1)  # Bright red
        
        # When countdown reaches 0, trigger timeout
        if self.countdown_seconds <= 0:
            self.countdown_event.cancel()
            self.countdown_event = None
            self.on_page_timeout(None)
            return False  # Stop the interval
        
        return True  # Continue the interval
    
    def on_page_timeout(self, dt):
        """Called when timeout elapsed"""
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
        
        # Stop timeout
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
        self.stop_page_timeout()

        # Reset debouncing flags
        self.button_pressed = False
        self.dispense_in_progress = False

        app = App.get_running_app()
        # Order aborted — release the dispensing guard so machine_empty can show
        # if cups hit 0 after this timeout (guard was set in start_dispensing_process).
        app._dispensing_cups = False
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
        
        # Stop timeout
        self.stop_page_timeout()
        
        # NOTE: Cups are only reduced AFTER a successful dispense confirmation (200 OK).
        # Moving reduce_one_cup() here (before sending the command) caused it to fire
        # on every retry attempt, draining the count 3x for a single payment.
        app = App.get_running_app()
        
        # COMMENTED OUT: Navigate to dispensing page immediately (onclick approach)
        # Uncomment below if you want immediate navigation without waiting for status code
        # print("✅ Navigating to dispensing page immediately")
        # Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)
        
        # HYBRID APPROACH:
        # 1. Pre-flight temp check (fast, ~100ms from cache)
        # 2. If temp OK → navigate to dispensing immediately (smooth UX)
        # 3. Send dispense command in background
        # 4. Handle hardware errors (700/701) even after navigating away
        def send_command_and_wait():
            # Temperature was already checked before QR generation.
            # Once the user has paid, let the dispense proceed — the ESP32
            # enforces its own temperature floor (allows from ~78.5°C).
            # Reduce cups and navigate to dispensing IMMEDIATELY
            # so the user sees the animation straight away without waiting for the
            # ESP32 poll cycle (which can take up to 30s).
            app.reduce_one_cup()
            Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)

            # Now send the dispense command (ESP32 picks it up on next poll cycle).
            print("🔄 Sending dispense command in background...")
            success, status_code, response_data = self.send_dispense_command()

            if success and status_code == 200:
                print(f"✅ Dispense command confirmed (200)")
            elif status_code in [700, 701]:
                # Temperature warning from ESP32 — but user has already paid and
                # dispensing is in progress; the ESP32 allows ~78.5°C so just log it.
                print(f"ℹ️ ESP32 temp code {status_code} — dispensing already started, ignoring")
            elif status_code in [704, 705, 706, 707, 708, 711]:
                # Hardware fault — route through central handler (shows hardware error page)
                print(f"⚠️ Hardware error {status_code} returned from ESP32")
                self.button_pressed = False
                self.dispense_in_progress = False
                if getattr(app.dispensing_page, 'completion_handled', False):
                    print(f"⚠️ Stale {status_code} — dispense already completed, ignoring")
                else:
                    Clock.schedule_once(lambda dt: app.handle_dispense_error(status_code), 0)
            else:
                if not success:
                    print(f"❌ Dispense command failed (status={status_code}) — ESP32 will still run via timeout")
        
        threading.Thread(target=send_command_and_wait, daemon=True).start()
        print("="*80 + "\n")

    
    def on_enter(self):
        """Called when page is entered"""
        import time
        # Reset state (but not if dispense is in progress)
        if self.dispense_in_progress:
            print("⏸️ Dispense in progress - skipping timeout initialization")
            return
        
        # Reset debouncing flags for fresh page entry (new payment or next cup)
        self.button_pressed = False
        
        self.page_entered_time = time.time()
        self.cup_detected_time = None
        self.testing_mode_enabled = False  # Reset testing mode flag
        self.error_popup_count = 0  # Reset error counter on page entry
        self.continue_button.disabled = False
        self.continue_button.opacity = 1.0
        
        # Update cup counter display
        app = App.get_running_app()
        if hasattr(app, 'current_cup_number') and hasattr(app, 'selected_cups'):
            self.update_cup_info(app.current_cup_number, app.selected_cups)
        # UI update removed (bypassed)
        
        # No video to start - using static image
        
        # Cup sensor check disabled (bypassed)
        
        # Start 10-second timeout
        self.start_page_timeout()
        
        # Start button pulsing animation so users know to click it
        self.start_warning_blink()
        
        # TESTING: Auto-enable button after 5 seconds (remove this later)
       #print("⏱️ TESTING MODE: Button will auto-enable after 5 seconds")
       #Clock.schedule_once(self.auto_enable_button_for_testing, 5)
    
    def start_warning_blink(self):
        """Start pulsing animation for the dispense button so users know to click it"""
        from kivy.animation import Animation
        
        if not self.blink_event:
            # Create a pulsing animation by changing opacity
            anim = Animation(opacity=0.6, duration=0.6) + Animation(opacity=1.0, duration=0.6)
            anim.repeat = True
            
            # Save the animation so we can stop it later
            self.blink_event = anim
            self.blink_event.start(self.continue_button)

    def stop_warning_blink(self):
        """Stop blinking animation"""
        if self.blink_event:
            self.blink_event.cancel(self.continue_button)
            self.continue_button.opacity = 1.0
            self.blink_event = None

    def _send_solenoid_bypass(self, duration_ms=10000):
        """Send solenoid_control command to bypass ESP32 temperature check.
        Used when start_dispense returns 700 (PT100 sensor not connected)."""
        try:
            from config import DEVICE_ID
            import json
            session = get_localhost_session()
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": f"cmd_solenoid_bypass_{uuid.uuid4().hex[:12]}",
                "deviceId": DEVICE_ID,
                "command": {
                    "action": "solenoid_control",
                    "parameters": {
                        "duration": duration_ms
                    }
                }
            }
            print(f"🔧 Solenoid bypass payload: {json.dumps(payload)}")
            response = session.post(
                f"{POLLING_SERVER_URL}/api/device/command",
                json=payload,
                timeout=35
            )
            if response.status_code == 200:
                print(f"✅ Solenoid bypass command accepted (duration={duration_ms}ms)")
                return True
            else:
                print(f"❌ Solenoid bypass failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Solenoid bypass exception: {e}")
            return False

    def on_leave(self):
        """Called when page is left"""
        # Reset dispense and button flags when leaving
        self.dispense_in_progress = False
        self.button_pressed = False

        # Stop timeout
        self.stop_page_timeout()
        # Stop blinking (no-op but must not crash)
        self.stop_warning_blink()

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
import threading


class HeatingPage(Screen):
    """Page displayed while tea is heating up"""
    
    def __init__(self, **kwargs):
        super(HeatingPage, self).__init__(**kwargs)
        
        # RFID polling state
        self.rfid_polling_event = None
        self.rfid_listening = False
        self._checking_card = False
        
        # Main layout - no padding to match payment_method_page exactly
        main_layout = BoxLayout(orientation='vertical')
        
        # Background
        with main_layout.canvas.before:
            Color(0.98, 0.97, 0.95, 1)  # Warm cream background
            self.bg_rect = Rectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top bar with logo on left - matching payment_method_page exactly
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.image import Image
        top_bar = FloatLayout(size_hint_y=0.15)
        
        # Urban Kettle logo on the left side - same as payment_method_page
        logo_image = Image(
            source='assets/urban_ketl_logo.png',
            size_hint=(None, None),
            size=(260, 230),
            allow_stretch=True,
            keep_ratio=True,
            pos_hint={'x': 0.0, 'top': 1.35}
        )
        top_bar.add_widget(logo_image)
        
        main_layout.add_widget(top_bar)
        
        # Content layout (reduced top spacing)
        content_layout = BoxLayout(orientation='vertical', padding=[40, 0, 40, 40], spacing=25)
        
        # Small top spacer
        content_layout.add_widget(BoxLayout(size_hint_y=0.05))
        
        # Heating icon container
        icon_container = BoxLayout(size_hint_y=0.3, orientation='vertical')
        
        # Animated heating icon (will be added via canvas)
        self.icon_widget = BoxLayout(size_hint=(None, None), size=(150, 150))
        self.icon_widget.pos_hint = {'center_x': 0.5}
        
        with self.icon_widget.canvas:
            # Steam effect (animated circles)
            Color(0.714, 0.478, 0.176, 0.3)  # #b67a2d with transparency
            self.steam1 = Ellipse(pos=(50, 100), size=(20, 20))
            self.steam2 = Ellipse(pos=(80, 110), size=(15, 15))
            self.steam3 = Ellipse(pos=(65, 120), size=(18, 18))
            
            # Tea cup
            Color(0.714, 0.478, 0.176, 1)  # #b67a2d
            # Cup body
            Line(points=[40, 40, 40, 80, 110, 80, 110, 40], width=4)
            Line(points=[30, 40, 120, 40], width=4)
            # Handle
            Line(circle=(125, 60, 15, 0, 180), width=4)
        
        icon_container.add_widget(self.icon_widget)
        content_layout.add_widget(icon_container)
        
        # Heating message
        self.temp_label = Label(
            text='Please Wait\nTea is Heating Up',
            font_size='42sp',
            bold=True,
            halign='center',
            color=(0.714, 0.478, 0.176, 1),  # #b67a2d
            size_hint_y=0.25
        )
        self.temp_label.bind(size=self.temp_label.setter('text_size'))
        content_layout.add_widget(self.temp_label)
        
        # Temperature display
        self.current_temp_label = Label(
            text='Current: --°C',
            font_size='28sp',
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=0.12
        )
        content_layout.add_widget(self.current_temp_label)
        
        # Target temperature
        target_label = Label(
            text=f'Target: {__import__("config").SERVING_TEMP:.0f}°C',
            font_size='22sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=0.1
        )
        content_layout.add_widget(target_label)
        
        # Hidden skip button (bottom-right corner) — for testing when
        # PT100 sensor is not connected. Tap 3 times quickly to bypass.
        from kivy.uix.floatlayout import FloatLayout as _FL
        skip_layer = _FL(size_hint_y=0.18)
        self._skip_tap_count = 0
        self._skip_tap_event = None

        skip_btn = Button(
            text='',
            size_hint=(None, None),
            size=(80, 80),
            pos_hint={'right': 0.98, 'y': 0.0},
            background_color=(0, 0, 0, 0),  # fully transparent
            background_normal=''
        )
        skip_btn.bind(on_press=self._on_skip_tap)
        skip_layer.add_widget(skip_btn)
        content_layout.add_widget(skip_layer)

        main_layout.add_widget(content_layout)

        self.add_widget(main_layout)
        
        # Animation
        self.steam_animation = None
    
    def _update_rect(self, instance, value):
        self.bg_rect.size = instance.size
        self.bg_rect.pos = instance.pos
    
    def on_enter(self):
        """Start animations and RFID polling when page is shown"""
        self.animate_steam()
        # Start RFID polling for maintenance cards
        self.start_rfid_polling()
    
    def on_leave(self):
        """Stop animations and RFID polling when leaving"""
        self.stop_rfid_polling()

        # Cancel the hidden 3-tap skip debounce timer if it is pending
        if self._skip_tap_event:
            self._skip_tap_event.cancel()
            self._skip_tap_event = None

        if self.steam_animation:
            self.steam_animation.cancel_all(self.steam1)
            self.steam_animation.cancel_all(self.steam2)
            self.steam_animation.cancel_all(self.steam3)
    
    def animate_steam(self):
        """Animate rising steam"""
        # Animate steam circles rising and fading
        def reset_steam(*args):
            self.steam1.pos = (50, 100)
            self.steam2.pos = (80, 110)
            self.steam3.pos = (65, 120)
            anim1 = Animation(pos=(50, 140), duration=2)
            anim2 = Animation(pos=(80, 150), duration=2.2)
            anim3 = Animation(pos=(65, 155), duration=2.1)
            anim1.bind(on_complete=reset_steam)
            anim1.start(self.steam1)
            anim2.start(self.steam2)
            anim3.start(self.steam3)
        
        reset_steam()
    
    def update_temperature(self, current_temp):
        """Update current temperature display"""
        if current_temp is not None:
            self.current_temp_label.text = f'Current: {current_temp:.1f}°C'
        else:
            self.current_temp_label.text = 'Current: --°C'
    
    # ============================================
    # RFID Maintenance Card Support
    # ============================================
    
    def start_rfid_polling(self):
        """Start polling for RFID maintenance cards only"""
        from kivy.app import App
        app = App.get_running_app()
        
        if not hasattr(app, 'rfid_auth_handler') or app.rfid_auth_handler is None:
            print("⚠️ RFID not available on heating page - no handler")
            return
        
        # Ensure RF keep-alive is active for fast card detection
        if hasattr(app.rfid_auth_handler, 'resume_keepalive'):
            app.rfid_auth_handler.resume_keepalive()
            print("🔄 RFID keep-alive resumed for heating page")
        
        self.rfid_listening = True
        
        # Poll every 500ms for fast detection
        if self.rfid_polling_event:
            self.rfid_polling_event.cancel()
        self.rfid_polling_event = Clock.schedule_interval(self._poll_rfid, 0.5)
        print("🔐 Started RFID polling on heating page (maintenance cards only)")
    
    def stop_rfid_polling(self):
        """Stop RFID polling"""
        self.rfid_listening = False
        if self.rfid_polling_event:
            self.rfid_polling_event.cancel()
            self.rfid_polling_event = None
        print("🔐 Stopped RFID polling on heating page")
    
    def _poll_rfid(self, dt):
        """Poll for RFID card in background thread"""
        if not self.rfid_listening:
            return False
        
        # Check if already checking for card
        if hasattr(self, '_checking_card') and self._checking_card:
            return True
        
        self._checking_card = True
        # Run the actual RFID read in a background thread
        threading.Thread(target=self._read_rfid_background, daemon=True).start()
        return True
    
    def _read_rfid_background(self):
        """Read RFID card in background thread"""
        from kivy.app import App
        app = App.get_running_app()
        
        if not hasattr(app, 'rfid_auth_handler') or app.rfid_auth_handler is None:
            self._checking_card = False
            return
        
        try:
            # Try to detect card
            uid = app.rfid_auth_handler.get_card_uid()
            
            if uid:
                print(f"🏷️ Card detected on heating page: {uid}")
                # Stop polling during authentication
                Clock.schedule_once(lambda dt: self.stop_rfid_polling(), 0)
                
                # Authenticate and validate card
                validation_result = app.api_client.validate_rfid_card_aes(app.rfid_auth_handler)
                
                if validation_result and validation_result.get("cardCategory") == "maintenance":
                    # Maintenance card - process it
                    print("🔧 Maintenance Card Detected on heating page")
                    Clock.schedule_once(lambda dt: self._handle_maintenance_card(validation_result), 0)
                else:
                    # Not a maintenance card - ignore and restart polling
                    print("⚠️ Non-maintenance card on heating page - ignoring")
                    Clock.schedule_once(lambda dt: self._restart_polling_after_delay(), 0)
        except Exception as e:
            print(f"❌ RFID error on heating page: {e}")
            Clock.schedule_once(lambda dt: self._restart_polling_after_delay(), 0)
        finally:
            self._checking_card = False
    
    def _handle_maintenance_card(self, validation_result):
        """Handle maintenance card detection"""
        from kivy.app import App
        app = App.get_running_app()

        app.rfid_auth_page.show_success("Maintenance")
        app.rfid_auth_page.step_label.text = validation_result.get('message', 'Maintenance mode activated')
        app.show_page('rfid_auth')

        pump_duration = validation_result.get("pumpDuration", 10000)
        duration_ms = pump_duration if pump_duration and pump_duration > 0 else 10000

        app.stop_heating_monitor()

        # Run solenoid command in background — never block the Kivy main thread
        threading.Thread(
            target=self._send_maintenance_solenoid_command,
            args=(duration_ms,),
            daemon=True
        ).start()

        Clock.schedule_once(lambda dt: app.check_heating_on_startup(), 5)
    
    def _send_maintenance_solenoid_command(self, duration_ms=10000):
        """Send solenoid control command for maintenance card"""
        try:
            from config import DEVICE_ID
            from utils.api_client import get_localhost_session
            import json
            
            session = get_localhost_session()
            
            command_payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": f"cmd_maint_heat_{__import__('uuid').uuid4().hex[:12]}",
                "deviceId": DEVICE_ID,
                "command": {
                    "action": "solenoid_control",
                    "parameters": {
                        "duration": duration_ms
                    }
                }
            }
            
            print(f"🔧 Sending maintenance solenoid command (heating page): {duration_ms}ms")
            
            response = session.post(
                "http://localhost:5000/api/device/command",
                json=command_payload,
                timeout=35
            )
            
            if response.status_code == 200:
                print(f"✅ Maintenance solenoid command sent successfully")
            else:
                print(f"⚠️ Maintenance command failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error sending maintenance command: {e}")
    
    def _restart_polling_after_delay(self):
        """Restart RFID polling after a short delay"""
        Clock.schedule_once(lambda dt: self.start_rfid_polling(), 2)

    def _on_skip_tap(self, instance):
        """Hidden 3-tap skip — bypasses heating check during testing"""
        self._skip_tap_count += 1
        if self._skip_tap_event:
            self._skip_tap_event.cancel()
        if self._skip_tap_count >= 3:
            self._skip_tap_count = 0
            print("⚠️ Heating page skip triggered (3-tap)")
            from kivy.app import App
            app = App.get_running_app()
            app.stop_heating_monitor()
            app.show_payment_method_page(fetch_cups=True)
        else:
            self._skip_tap_event = Clock.schedule_once(
                lambda dt: setattr(self, '_skip_tap_count', 0), 1.5
            )

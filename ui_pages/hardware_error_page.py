from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from utils.hardware_monitor import hardware_monitor
import threading

class HardwareErrorPage(Screen):
    """Page displayed when a critical hardware error occurs"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Main layout
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        
        # Background
        with layout.canvas.before:
            Color(0.95, 0.95, 0.95, 1)  # Light gray background
            self.rect = RoundedRectangle(size=(800, 480), pos=(0, 0)) # Size will update
        layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Icon
        self.icon_label = Label(
            text="⚠️",
            font_size='96sp',
            color=(0.9, 0.3, 0.2, 1),  # Red/Orange
            size_hint=(1, 0.25)
        )
        layout.add_widget(self.icon_label)
        
        # Title
        self.title_label = Label(
            text="Hardware Alert",
            font_size='40sp',
            bold=True,
            color=(0.2, 0.2, 0.2, 1),
            size_hint=(1, 0.12)
        )
        layout.add_widget(self.title_label)
        
        # Message
        self.message_label = Label(
            text="Connecting to hardware...",
            font_size='24sp',
            color=(0.4, 0.4, 0.4, 1),
            halign='center',
            valign='top',
            size_hint=(1, 0.30)
        )
        self.message_label.bind(size=self.message_label.setter('text_size'))
        layout.add_widget(self.message_label)
        
        # Footer/Status
        self.status_label = Label(
            text="Checking hardware status...",
            font_size='16sp',
            color=(0.6, 0.6, 0.6, 1),
            size_hint=(1, 0.10)
        )
        layout.add_widget(self.status_label)

        # Hidden 5-tap zone for staff override — invisible to customers.
        # Tapping this area 5 times forces navigation home when auto-recovery
        # is stuck (e.g. false-positive error reading).
        from kivy.uix.widget import Widget
        self._staff_tap_count = 0
        self._staff_tap_zone = Widget(size_hint=(1, 0.13))
        self._staff_tap_zone.bind(on_touch_down=self._on_staff_tap)
        layout.add_widget(self._staff_tap_zone)
        
        self.add_widget(layout)
        
        # Monitor event
        self.monitor_event = None
        self._check_in_progress = False  # guard: only one background check at a time
        
        # RFID polling state
        self.rfid_polling_event = None
        self.rfid_listening = False
        self._checking_card = False

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def _on_staff_tap(self, widget, touch):
        """Hidden 5-tap override for staff — navigates home if auto-recovery is stuck."""
        if not widget.collide_point(*touch.pos):
            return False
        self._staff_tap_count += 1
        if self._staff_tap_count >= 5:
            self._staff_tap_count = 0
            print("🔧 Staff override: 5-tap detected — forcing navigation home")
            self._on_go_home(None)
        return True

    def _on_go_home(self, instance):
        """Force navigation back to home — stops monitor so it doesn't re-trigger."""
        from kivy.app import App
        if self.monitor_event:
            self.monitor_event.cancel()
            self.monitor_event = None
        App.get_running_app().show_payment_method_page(fetch_cups=True)

    def on_enter(self):
        """Called when screen is entered"""
        self._check_in_progress = False
        self.status_label.text = "Checking hardware status..."
        # Check every 10 s — was 3 s which caused the blink-and-disappear effect.
        # 10 s gives the user time to read the message before any auto-navigation.
        self.monitor_event = Clock.schedule_interval(self.check_status, 10)
        # First check after 5 s (not immediately) so the error message stays visible.
        Clock.schedule_once(lambda dt: self.check_status(dt), 5)
        # Start RFID polling for maintenance cards
        self.start_rfid_polling()

    def on_leave(self):
        """Called when screen is left"""
        print("🛑 Hardware Error Page: on_leave() called - stopping monitoring")
        if self.monitor_event:
            self.monitor_event.cancel()
            self.monitor_event = None
            print("✅ Hardware Error Page: Monitoring stopped")
        self.stop_rfid_polling()
        self._staff_tap_count = 0  # reset hidden tap counter

    def set_error_message(self, message):
        """Set/update the error message displayed on the page"""
        self.message_label.text = message

    def check_status(self, dt):
        """Kick off a background check — never blocks the Kivy main thread."""
        if self._check_in_progress:
            return
        self._check_in_progress = True
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        """Run get_latest_error() in a background thread, marshal result back."""
        try:
            result = hardware_monitor.get_latest_error(force_fresh=True)
        except Exception as e:
            result = f"Check failed: {e}"
        finally:
            self._check_in_progress = False
        Clock.schedule_once(lambda dt: self._apply_result(result), 0)

    def _apply_result(self, result):
        """Process result on the Kivy main thread. Guard against stale callbacks."""
        from kivy.app import App
        app = App.get_running_app()
        if app.screen_manager.current != self.name:
            return

        if isinstance(result, tuple) and result[0] == 'HEATING':
            temp = result[1]
            print(f"Temperature low ({temp}°C) - Navigating to Heating page")
            app.show_heating_page(temp)
        elif result:
            # Still an error — update the message and keep showing this page
            self.message_label.text = result
            self.status_label.text = "Waiting for sensor to recover..."
        else:
            print("Hardware error cleared - Navigating to Home and fetching cups")
            if hasattr(app, 'previous_machine_state') and app.previous_machine_state == "offline":
                print("🟢 Machine state changed: OFFLINE → ONLINE (detected from hardware_error page)")
                if hasattr(app, 'send_machine_state_to_esp32'):
                    app.send_machine_state_to_esp32("ONLINE", None)
                app.previous_machine_state = "online"
            app.show_payment_method_page(fetch_cups=True)
                
    def update_error(self, message):
        """Update the error message"""
        self.message_label.text = message

    # ============================================
    # RFID Maintenance Card Support on Error Page
    # ============================================

    def start_rfid_polling(self):
        """Start polling for RFID maintenance cards"""
        from kivy.app import App
        app = App.get_running_app()
        
        if not hasattr(app, 'rfid_auth_handler') or app.rfid_auth_handler is None:
            print("⚠️ RFID not available on hardware error page - no handler")
            return
        
        if hasattr(app.rfid_auth_handler, 'resume_keepalive'):
            app.rfid_auth_handler.resume_keepalive()
            print("🔄 RFID keep-alive resumed for hardware error page")
        
        self.rfid_listening = True
        
        if self.rfid_polling_event:
            self.rfid_polling_event.cancel()
        self.rfid_polling_event = Clock.schedule_interval(self._poll_rfid, 0.5)
        print("🔐 Started RFID polling on hardware error page")
    
    def stop_rfid_polling(self):
        """Stop RFID polling"""
        self.rfid_listening = False
        if self.rfid_polling_event:
            self.rfid_polling_event.cancel()
            self.rfid_polling_event = None
        print("🔐 Stopped RFID polling on hardware error page")
    
    def _poll_rfid(self, dt):
        """Poll for RFID card in background thread"""
        if not self.rfid_listening:
            return False
        
        if hasattr(self, '_checking_card') and self._checking_card:
            return True
        
        self._checking_card = True
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
            uid = app.rfid_auth_handler.get_card_uid()
            if uid:
                print(f"🏷️ Card detected on hardware error page: {uid}")
                Clock.schedule_once(lambda dt: self.stop_rfid_polling(), 0)
                
                validation_result = app.api_client.validate_rfid_card_aes(app.rfid_auth_handler)
                
                if validation_result and validation_result.get("cardCategory") == "maintenance":
                    print("🔧 Maintenance Card Detected on hardware error page")
                    Clock.schedule_once(lambda dt: self._handle_maintenance_card(validation_result), 0)
                else:
                    print("⚠️ Non-maintenance card on hardware error page — ignoring")
                    Clock.schedule_once(lambda dt: self._restart_polling_after_delay(), 0)
        except Exception as e:
            print(f"❌ RFID error on hardware error page: {e}")
            Clock.schedule_once(lambda dt: self._restart_polling_after_delay(), 0)
        finally:
            self._checking_card = False

    def _handle_maintenance_card(self, validation_result):
        """Handle maintenance card detection on hardware error page"""
        from kivy.app import App
        app = App.get_running_app()

        app.rfid_auth_page.show_success("Maintenance")
        app.rfid_auth_page.step_label.text = validation_result.get('message', 'Maintenance mode activated')
        app.show_page('rfid_auth')

        pump_duration = validation_result.get("pumpDuration", 10000)
        duration_ms = pump_duration if pump_duration and pump_duration > 0 else 10000

        # Temporarily stop hardware monitor so we don't clear/interrupt maintenance mode
        if self.monitor_event:
            self.monitor_event.cancel()
            self.monitor_event = None

        # Run solenoid command in background — never block the Kivy main thread
        threading.Thread(
            target=self._send_maintenance_solenoid_command,
            args=(duration_ms,),
            daemon=True
        ).start()

        # Resume monitoring and return to hardware error page after some delay
        Clock.schedule_once(lambda dt: self._resume_monitoring_after_maintenance(), 5)

    def _resume_monitoring_after_maintenance(self):
        from kivy.app import App
        app = App.get_running_app()
        current = app.screen_manager.current
        if current == 'rfid_auth':
            # Navigating to hardware_error fires on_enter() via Kivy — don't call it manually.
            app.show_page('hardware_error')
        elif current == 'hardware_error':
            # Already on this page (e.g. user navigated back early) — restart monitor manually.
            # Cancel any existing interval first to avoid duplicates.
            if self.monitor_event:
                self.monitor_event.cancel()
                self.monitor_event = None
            self.on_enter()
        # else: user navigated away from hardware_error entirely — don't interfere.

    def _send_maintenance_solenoid_command(self, duration_ms=10000):
        """Send solenoid control command for maintenance card"""
        try:
            from config import DEVICE_ID, POLLING_SERVER_URL
            from utils.api_client import get_localhost_session
            import uuid
            
            session = get_localhost_session()
            
            # Send both 'solenoid_control' and 'open_solenoid' to guarantee compatibility
            for action in ["solenoid_control", "open_solenoid"]:
                command_payload = {
                    "messageType": "command",
                    "commandType": "control",
                    "version": "1.0",
                    "commandId": f"cmd_maint_err_{uuid.uuid4().hex[:12]}",
                    "deviceId": DEVICE_ID,
                    "command": {
                        "action": action,
                        "parameters": {
                            "duration": duration_ms
                        }
                    }
                }
                
                print(f"🔧 Sending maintenance solenoid command ({action}): {duration_ms}ms")
                try:
                    response = session.post(
                        f"{POLLING_SERVER_URL}/api/device/command",
                        json=command_payload,
                        timeout=15
                    )
                    if response.status_code == 200:
                        print(f"   Success response for action {action}: {response.status_code}")
                    else:
                        print(f"   Failed response for action {action}: {response.status_code}")
                except Exception as ex:
                    print(f"   Exception sending action {action}: {ex}")
                
        except Exception as e:
            print(f"❌ Error sending maintenance command: {e}")

    def _restart_polling_after_delay(self):
        """Restart RFID polling after a short delay"""
        Clock.schedule_once(lambda dt: self.start_rfid_polling(), 2)


"""
Hardware Debug Page - Testing/Monitoring UI
Shows real-time hardware status, handshake info, and sensor data
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from utils.hardware_monitor import hardware_monitor
import requests


class HardwareDebugPage(Screen):
    """Debug page to monitor hardware status in real-time"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'hardware_debug'
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # Title
        title = Label(
            text='Hardware Monitor Debug',
            font_size='32sp',
            size_hint=(1, 0.08),
            color=(1, 1, 1, 1),
            bold=True
        )
        main_layout.add_widget(title)
        
        # Status container
        self.status_layout = BoxLayout(orientation='vertical', spacing=10, size_hint=(1, 0.75))
        
        # Server Status
        self.server_status = Label(
            text='Server: Checking...',
            font_size='20sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        self.server_status.bind(size=self.server_status.setter('text_size'))
        self.status_layout.add_widget(self.server_status)
        
        # Handshake Status
        self.handshake_status = Label(
            text='Handshake: Waiting...',
            font_size='20sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        self.handshake_status.bind(size=self.handshake_status.setter('text_size'))
        self.status_layout.add_widget(self.handshake_status)
        
        # Device ID
        self.device_id_label = Label(
            text='Device ID: Not detected',
            font_size='20sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        self.device_id_label.bind(size=self.device_id_label.setter('text_size'))
        self.status_layout.add_widget(self.device_id_label)
        
        # Temperature
        self.temp_label = Label(
            text='Temperature: --°C',
            font_size='24sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top',
            bold=True
        )
        self.temp_label.bind(size=self.temp_label.setter('text_size'))
        self.status_layout.add_widget(self.temp_label)
        
        # Cup Sensor
        self.cup_label = Label(
            text='Cup Sensor: --',
            font_size='20sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        self.cup_label.bind(size=self.cup_label.setter('text_size'))
        self.status_layout.add_widget(self.cup_label)
        
        # Cups Remaining
        self.cups_remaining_label = Label(
            text='Cups Remaining: --',
            font_size='20sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        self.cups_remaining_label.bind(size=self.cups_remaining_label.setter('text_size'))
        self.status_layout.add_widget(self.cups_remaining_label)
        
        # Machine State
        self.machine_state_label = Label(
            text='Machine State: --',
            font_size='20sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top'
        )
        self.machine_state_label.bind(size=self.machine_state_label.setter('text_size'))
        self.status_layout.add_widget(self.machine_state_label)
        
        # Last Update
        self.last_update_label = Label(
            text='Last Update: --',
            font_size='16sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='left',
            valign='top'
        )
        self.last_update_label.bind(size=self.last_update_label.setter('text_size'))
        self.status_layout.add_widget(self.last_update_label)
        
        main_layout.add_widget(self.status_layout)
        
        # Buttons
        button_layout = BoxLayout(orientation='horizontal', spacing=20, size_hint=(1, 0.12))
        
        # Refresh button
        refresh_btn = Button(
            text='Refresh Now',
            font_size='20sp',
            background_color=(0.2, 0.6, 1, 1),
            size_hint=(0.4, 1)
        )
        refresh_btn.bind(on_press=self.manual_refresh)
        button_layout.add_widget(refresh_btn)
        
        # Back button
        back_btn = Button(
            text='Back to Home',
            font_size='20sp',
            background_color=(0.3, 0.3, 0.3, 1),
            size_hint=(0.4, 1)
        )
        back_btn.bind(on_press=self.go_back)
        button_layout.add_widget(back_btn)
        
        main_layout.add_widget(button_layout)
        
        # Background
        with main_layout.canvas.before:
            Color(0.1, 0.1, 0.15, 1)
            self.bg_rect = Rectangle(size=main_layout.size, pos=main_layout.pos)
        main_layout.bind(size=self._update_bg, pos=self._update_bg)
        
        self.add_widget(main_layout)
        
        # Update timer
        self.update_event = None
    
    def _update_bg(self, instance, value):
        """Update background rectangle"""
        self.bg_rect.size = instance.size
        self.bg_rect.pos = instance.pos
    
    def on_enter(self):
        """Start updating when page is shown"""
        # Disable screensaver/inactivity timeout while on debug page
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, 'reset_inactivity_timer'):
            # Stop the inactivity monitoring
            if hasattr(app, 'inactivity_event') and app.inactivity_event:
                app.inactivity_event.cancel()
                app.inactivity_event = None
        
        self.update_status()
        # Update every second
        self.update_event = Clock.schedule_interval(lambda dt: self.update_status(), 1.0)
    
    def on_leave(self):
        """Stop updating when leaving page"""
        if self.update_event:
            self.update_event.cancel()
            self.update_event = None
        
        # Re-enable screensaver/inactivity timeout
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, 'setup_screensaver_monitoring'):
            app.setup_screensaver_monitoring()
    
    def update_status(self):
        """Update all status information"""
        from datetime import datetime
        
        # Check server status
        try:
            response = requests.get(f"{hardware_monitor.api_base_url}/test/devices", timeout=1)
            if response.status_code == 200:
                self.server_status.text = f'Server: ✓ Running at {hardware_monitor.api_base_url}'
                self.server_status.color = (0, 1, 0, 1)
                
                # Check devices
                devices = response.json().get('devices', [])
                if devices:
                    self.handshake_status.text = f'Handshake: ✓ Complete ({len(devices)} device(s))'
                    self.handshake_status.color = (0, 1, 0, 1)
                else:
                    self.handshake_status.text = 'Handshake: ⏳ Waiting for ESP32...'
                    self.handshake_status.color = (1, 1, 0, 1)
            else:
                self.server_status.text = f'Server: ⚠️ Responded with status {response.status_code}'
                self.server_status.color = (1, 1, 0, 1)
        except:
            self.server_status.text = 'Server: ❌ Not running'
            self.server_status.color = (1, 0, 0, 1)
            self.handshake_status.text = 'Handshake: ❌ No server'
            self.handshake_status.color = (1, 0, 0, 1)
        
        # Device ID
        if hardware_monitor.device_id:
            self.device_id_label.text = f'Device ID: ✓ {hardware_monitor.device_id}'
            self.device_id_label.color = (0, 1, 0, 1)
        else:
            self.device_id_label.text = 'Device ID: ⏳ Not detected yet'
            self.device_id_label.color = (1, 1, 0, 1)
        
        # Get health data
        health_data = self.get_health_data()
        
        if health_data:
            # Temperature
            temp = health_data.get('temp')
            if temp:
                temp_color = (0, 1, 0, 1) if temp >= 82 else (1, 1, 0, 1)
                self.temp_label.text = f'Temperature: {temp}°C {"✓" if temp >= 82 else "⚠️ Heating..."}'
                self.temp_label.color = temp_color
            
            # Cup sensor
            cup_present = health_data.get('cup_present')
            if cup_present is not None:
                self.cup_label.text = f'Cup Sensor: {"✓ Cup Present" if cup_present else "○ No Cup"}'
                self.cup_label.color = (0, 1, 0, 1) if cup_present else (0.7, 0.7, 0.7, 1)
            
            # Cups remaining
            cups = health_data.get('cups_remaining')
            if cups is not None:
                cups_color = (0, 1, 0, 1) if cups > 3 else (1, 1, 0, 1) if cups > 0 else (1, 0, 0, 1)
                self.cups_remaining_label.text = f'Cups Remaining: {cups}'
                self.cups_remaining_label.color = cups_color
            
            # Machine state
            state = health_data.get('machine_state', 'UNKNOWN')
            state_colors = {
                'ONLINE': (0, 1, 0, 1),
                'DEGRADED': (1, 1, 0, 1),
                'OFFLINE': (1, 0, 0, 1)
            }
            self.machine_state_label.text = f'Machine State: {state}'
            self.machine_state_label.color = state_colors.get(state, (1, 1, 1, 1))
        
        # Last update time
        self.last_update_label.text = f'Last Update: {datetime.now().strftime("%H:%M:%S")}'
    
    def get_health_data(self):
        """Get health data from hardware"""
        try:
            if not hardware_monitor.device_id:
                return None
            
            response = requests.post(
                f"{hardware_monitor.api_base_url}/api/device/health",
                json={
                    "messageType": "health_check",
                    "version": "1.0",
                    "deviceId": hardware_monitor.device_id
                },
                timeout=2
            )
            
            if response.status_code == 200:
                data = response.json()
                checks = data.get('checks', {})
                
                # Extract temperature
                pt100_data = checks.get('sensor:pt100_sensor_01', [{}])[0]
                temp = pt100_data.get('observedValue')
                
                # Extract cup sensor
                cup_data = checks.get('sensor:cup_sensor_01', [{}])
                if isinstance(cup_data, list) and len(cup_data) > 0:
                    cup_data = cup_data[0]
                cup_value = cup_data.get('observedValue', 'no_cup')
                cup_present = cup_value in ['cup_present', 'cup', 'present', 'yes', 'true', '1']
                
                # Extract cups remaining
                ultrasonic_data = checks.get('sensor:ultrasonic_sensor_01', [{}])[0]
                cups_remaining = ultrasonic_data.get('observedValue')
                
                # Machine state
                machine_state = data.get('machineState', 'UNKNOWN')
                
                return {
                    'temp': temp,
                    'cup_present': cup_present,
                    'cups_remaining': cups_remaining,
                    'machine_state': machine_state
                }
        except:
            pass
        
        return None
    
    def manual_refresh(self, instance):
        """Manual refresh button pressed"""
        print("🔄 Manual refresh triggered")
        self.update_status()
    
    def go_back(self, instance):
        """Go back to payment method page"""
        print("⬅️ Returning to payment method page")
        self.manager.current = 'payment_method'

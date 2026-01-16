from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from utils.hardware_monitor import hardware_monitor

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
            size_hint=(1, 0.3)
        )
        layout.add_widget(self.icon_label)
        
        # Title
        self.title_label = Label(
            text="Hardware Alert",
            font_size='40sp',
            bold=True,
            color=(0.2, 0.2, 0.2, 1),
            size_hint=(1, 0.15)
        )
        layout.add_widget(self.title_label)
        
        # Message
        self.message_label = Label(
            text="Connecting to hardware...",
            font_size='24sp',
            color=(0.4, 0.4, 0.4, 1),
            halign='center',
            valign='top',
            size_hint=(1, 0.4)
        )
        self.message_label.bind(size=self.message_label.setter('text_size'))
        layout.add_widget(self.message_label)
        
        # Footer/Status
        self.status_label = Label(
            text="Waiting for resolution...",
            font_size='16sp',
            color=(0.6, 0.6, 0.6, 1),
            size_hint=(1, 0.15)
        )
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
        
        # Monitor event
        self.monitor_event = None
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
        
    def on_enter(self):
        """Called when screen is entered"""
        # Start monitoring error status
        self.monitor_event = Clock.schedule_interval(self.check_status, 1)
        # Initial check
        self.check_status(0)
        
    def on_leave(self):
        """Called when screen is left"""
        print("🛑 Hardware Error Page: on_leave() called - stopping monitoring")
        if self.monitor_event:
            self.monitor_event.cancel()
            self.monitor_event = None
            print("✅ Hardware Error Page: Monitoring stopped")
            
    def check_status(self, dt):
        """Check if error persists"""
        result = hardware_monitor.get_latest_error()
        
        # Result can be: error message string, None (no error), or tuple (status, temp)
        if isinstance(result, tuple) and result[0] == 'HEATING':
            # Temperature is low - navigate to heating page
            temp = result[1]
            print(f"Temperature low ({temp}°C) - Navigating to Heating page")
            from kivy.app import App
            app = App.get_running_app()
            if app.screen_manager.current == self.name:
                app.show_heating_page(temp)
        elif result:
            # Error still present, update message
            self.message_label.text = result
        else:
            # Error cleared! Navigate back to Home with cups fetch
            print("Hardware error cleared - Navigating to Home and fetching cups")
            from kivy.app import App
            app = App.get_running_app()
            # Navigate to payment method page (Home) and fetch cups count
            if app.screen_manager.current == self.name:
                app.show_payment_method_page(fetch_cups=True)
                
    def update_error(self, message):
        """Update the error message"""
        self.message_label.text = message

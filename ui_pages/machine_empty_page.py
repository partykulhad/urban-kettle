from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock
import os
import math
import threading


class MachineEmptyPage(Screen):
    """Page displayed when machine has 0 cups available"""
    
    def __init__(self, **kwargs):
        super(MachineEmptyPage, self).__init__(**kwargs)
        
        # Animation variables
        self.dots_animation_state = 0
        self.dots_timer = None
        
        # Cups check timer
        self.cups_check_timer = None
        self.cups_check_interval = 5  # Check every 5 seconds
        
        # Main layout with clean background - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=15)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top spacer
        main_layout.add_widget(Widget(size_hint_y=0.08))
        
        # Urban Ketl logo section
        logo_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.25)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(250, 225),
                allow_stretch=True,
                keep_ratio=True
            )
            logo_section.add_widget(logo_image)
        else:
            # Fallback to text if image not found
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='40sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
                halign='center'
            )
            logo_section.add_widget(fallback_logo)
        
        main_layout.add_widget(logo_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # Main message section
        message_section = BoxLayout(orientation='vertical', size_hint_y=0.30, spacing=10)
        
        # Main title
        title_label = Label(
            text="We'll be back soon!",
            font_size='28sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        message_section.add_widget(title_label)
        
        # Subtitle
        subtitle_label = Label(
            text="Machine is empty",
            font_size='22sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center'
        )
        message_section.add_widget(subtitle_label)
        
        # Info message
        info_label = Label(
            text="Refiller is on its way\nTry again after some time",
            font_size='20sp',
            color=(0.6, 0.6, 0.6, 1),
            halign='center'
        )
        message_section.add_widget(info_label)
        
        main_layout.add_widget(message_section)
        
        # Animated dots for loading effect
        dots_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.10)
        self.dots_label = Label(
            text='●●●',
            font_size='28sp',
            color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
            halign='center'
        )
        dots_section.add_widget(self.dots_label)
        main_layout.add_widget(dots_section)
        
        # Bottom spacer
        main_layout.add_widget(Widget(size_hint_y=0.14))
        
        self.add_widget(main_layout)
    
    def _update_rect(self, instance, value):
        """Update background rectangle"""
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def on_enter(self):
        """Start animations when page becomes active"""
        self.start_dots_animation()
        
        # Start periodic cups check
        self.start_cups_check_timer()
    
    def on_leave(self):
        """Stop animations when leaving page"""
        self.stop_dots_animation()
        
        # Stop periodic cups check
        self.stop_cups_check_timer()
    
    def start_dots_animation(self):
        """Start the animated dots effect"""
        self.dots_animation_state = 0
        self.dots_timer = Clock.schedule_interval(self.update_dots, 0.5)
    
    def update_dots(self, dt):
        """Update the dots animation"""
        dots_states = ['●●●', '○●●', '○○●', '○○○', '●○○', '●●○']
        self.dots_animation_state = (self.dots_animation_state + 1) % len(dots_states)
        self.dots_label.text = dots_states[self.dots_animation_state]
    
    def stop_dots_animation(self):
        """Stop the dots animation"""
        if self.dots_timer:
            self.dots_timer.cancel()
            self.dots_timer = None
    
    def start_cups_check_timer(self):
        """Start periodic timer to check if cups become available"""
        # Stop any existing timer first
        self.stop_cups_check_timer()
        
        # Schedule periodic check
        self.cups_check_timer = Clock.schedule_interval(
            lambda dt: self.check_cups_availability(), 
            self.cups_check_interval
        )
        print(f"Started cups availability check timer (every {self.cups_check_interval} seconds)")
    
    def stop_cups_check_timer(self):
        """Stop the periodic cups check timer"""
        if self.cups_check_timer:
            self.cups_check_timer.cancel()
            self.cups_check_timer = None
            print("Stopped cups availability check timer")
    
    def check_cups_availability(self):
        """Check if cups are available and return to payment method page if so"""
        threading.Thread(target=self.fetch_cups_count, daemon=True).start()
    
    def fetch_cups_count(self):
        """Fetch cups count and machine status from API in background thread - called once on page enter"""
        from kivy.app import App
        app = App.get_running_app()
        
        try:
            # Call API to check machine status and cups
            if hasattr(app, 'api_client') and hasattr(app, 'MACHINE_ID'):
                # Check machine status first
                status_data = app.api_client.check_machine_status(app.MACHINE_ID)
                
                if status_data and status_data.get("success", False):
                    # Get status from nested data object
                    data = status_data.get("data", {})
                    machine_status = data.get("status", "offline")
                    is_online = machine_status.lower() == "online"
                    
                    print(f"Machine status check: {machine_status}, is_online: {is_online}")
                    
                    if not is_online:
                        # Machine is still offline, stay on this page
                        print("Machine is still offline")
                        return
                    
                    # Machine is now online - notify ESP32 of state change
                    # Check if previous state was offline (we're on machine_empty page, so it was)
                    if hasattr(app, 'previous_machine_state') and app.previous_machine_state == "offline":
                        print("🟢 Machine state changed: OFFLINE → ONLINE (detected from machine_empty page)")
                        if hasattr(app, 'send_machine_state_to_esp32'):
                            app.send_machine_state_to_esp32("ONLINE", None)
                        # Update the tracked state
                        app.previous_machine_state = "online"
                
                # Check cups count and store locally
                cups_data = app.api_client.get_remaining_cups(app.MACHINE_ID)
                
                # Check if cups are now available
                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    
                    # Store locally
                    Clock.schedule_once(lambda dt: app.set_local_cups_count(cups_count))
                    
                    # If machine is online and cups are available, return to payment method page
                    if cups_count > 0:
                        print(f"Machine is online and cups available ({cups_count}), returning to payment method page")
                        Clock.schedule_once(lambda dt: self.return_to_payment_method())
        except Exception as e:
            print(f"Error checking machine availability: {e}")
    
    def return_to_payment_method(self):
        """Return to payment method page and fetch cups count"""
        from kivy.app import App
        app = App.get_running_app()
        # Navigate to home and fetch cups count
        app.show_payment_method_page(fetch_cups=True)

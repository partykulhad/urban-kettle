from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle, Ellipse
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.app import App
import os
import math
import random
import requests
import threading


# ModernSteamEffect removed - not needed since we're using video




class DispensingPage(Screen):
    """Simple dispensing page matching the design with video"""
    
    def __init__(self, **kwargs):
        super(DispensingPage, self).__init__(**kwargs)
        
        # Cup tracking variables
        self.total_cups = 1
        self.current_cup = 1
        
        # Pause state
        self.is_paused = False
        
        # Pump state monitoring
        self.pump_check_event = None
        self.pause_popup = None
        
        # Main layout - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=10)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top section with logo on left - matching other pages
        from kivy.uix.floatlayout import FloatLayout
        top_section = BoxLayout(orientation='vertical', size_hint_y=0.15, padding=[10, 5])
        
        # Logo on the left
        logo_float = FloatLayout(size_hint_y=0.6)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(230, 200),
                pos_hint={'x': -0.05, 'top': 1.2},  # More left
                allow_stretch=True,
                keep_ratio=True
            )
            logo_float.add_widget(logo_image)
        else:
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='32sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='left'
            )
            logo_float.add_widget(fallback_logo)
        
        top_section.add_widget(logo_float)
        
        # "DISPENSING..." text - bigger font
        dispensing_label = Label(
            text='DISPENSING...',
            font_size='40sp',  # Increased from 32sp
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.4
        )
        top_section.add_widget(dispensing_label)
        
        main_layout.add_widget(top_section)
        
        # Cup counter - bigger font
        self.cup_counter_label = Label(
            text='Cup 1 of 1',
            font_size='26sp',  # Increased from 20sp
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.07
        )
        main_layout.add_widget(self.cup_counter_label)
        
        # Small spacing after cup counter
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # Video section using OpenCV (same as screensaver) - optimized size
        video_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.50)
        
        # Import VideoWidget from screensaver
        from ui_pages.screensaver_page import VideoWidget
        
        # Optimized video size - wider but not too tall
        self.video_widget = VideoWidget(size_hint=(None, None), size=(400, 300))
        video_path = os.path.join('assets', 'dispensing.mp4')
        self.video_widget.set_video_path(video_path)
        
        video_section.add_widget(self.video_widget)
        main_layout.add_widget(video_section)
        
        # Small spacing before instruction
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Instruction text - bigger fonts
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.12, spacing=5)
        
        tea_label = Label(
            text='Your tea is being prepared.',
            font_size='26sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(tea_label)
        
        wait_label = Label(
            text='Please wait.',
            font_size='26sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(wait_label)
        
        main_layout.add_widget(instruction_section)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.07))
        
        self.add_widget(main_layout)
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def set_cup_info(self, current_cup, total_cups):
        """Set the cup information for display"""
        self.current_cup = current_cup
        self.total_cups = total_cups
        self.cup_counter_label.text = f'Cup {current_cup} of {total_cups}'
    
    def start_dispensing_animation(self):
        """Start the dispensing animation"""
        # Start video if available
        if hasattr(self, 'video_widget'):
            self.video_widget.start_video()
    
    def on_enter(self):
        """Called when screen is entered"""
        self.last_status_index = -1
        self.start_dispensing_animation()
        # Pump state monitoring commented out - not in use
        # self.start_pump_monitoring()
        
        # Auto-navigate to thank you page after 10 seconds
        print("⏱️ Auto-navigating to thank you page after 10 seconds")
        self.auto_complete_event = Clock.schedule_once(self.auto_complete_for_testing, 10)
    
    def on_leave(self):
        """Called when screen is left"""
        # Stop video when leaving
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()
        
        # Pump monitoring commented out - not in use
        # self.stop_pump_monitoring()
        
        # Cancel auto-complete timer if it exists
        if hasattr(self, 'auto_complete_event') and self.auto_complete_event:
            self.auto_complete_event.cancel()
            self.auto_complete_event = None
    
    # Pump monitoring methods commented out - not in use
    # def start_pump_monitoring(self):
    #     """Start monitoring pump state every 0.5 seconds for smooth response"""
    #     print("🔍 Starting pump state monitoring (every 0.5 seconds)...")
    #     self.pump_check_event = Clock.schedule_interval(self.check_pump_state, 0.5)  # Every 0.5s
    # 
    # def stop_pump_monitoring(self):
    #     """Stop monitoring pump state"""
    #     if self.pump_check_event:
    #         self.pump_check_event.cancel()
    #         self.pump_check_event = None
    # 
    # def check_pump_state(self, dt):
    #     """Poll pump status API every 1 second"""
    #     threading.Thread(target=self._do_pump_check, daemon=True).start()
    # 
    # def _do_pump_check(self):
    #     """Check pump status in background"""
    #     try:
    #         from config import DEVICE_ID
    #         url = f"http://localhost:5000/api/device/sensor/pump_status?deviceId={DEVICE_ID}"
    #         response = requests.get(url, timeout=2)
    #         
    #         if response.status_code == 200:
    #             result = response.json()
    #             pump_data = result.get('response', {}).get('data', {})
    #             pump_state = pump_data.get('pumpState', 'Idle')
    #             
    #             # Update UI on main thread
    #             Clock.schedule_once(lambda dt: self._update_pump_state(pump_state), 0)
    #         else:
    #             print(f"Pump status check failed: {response.status_code}")
    #             
    #     except Exception as e:
    #         print(f"Pump status check error: {e}")
    
    def auto_complete_for_testing(self, dt):
        """Auto-complete dispensing after 10 seconds"""
        print("✅ Auto-completing dispensing after 10 seconds")
        
        # Pump monitoring commented out - not in use
        # self.stop_pump_monitoring()
        
        # Stop video
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()
        
        # Handle cup completion (checks if more cups needed)
        from kivy.app import App
        app = App.get_running_app()
        print("✅ Handling cup completion")
        Clock.schedule_once(lambda dt: app.handle_cup_completion(), 0.3)
    
    # Pump state update method commented out - not in use
    # def _update_pump_state(self, pump_state):
    #     """Update UI based on pump state"""
    #     print(f"📊 Pump State: {pump_state}")
    #     
    #     if pump_state == "success":
    #         # Dispensing complete - stop video and handle cup completion
    #         print("✅ Dispensing complete - stopping video and handling cup completion")
    #         
    #         # Cancel auto-complete timer since real completion happened
    #         if hasattr(self, 'auto_complete_event') and self.auto_complete_event:
    #             self.auto_complete_event.cancel()
    #             self.auto_complete_event = None
    #             print("✅ Cancelled auto-complete timer - real completion detected")
    #         
    #         self.stop_pump_monitoring()
    #         
    #         # Stop video when dispensing is actually complete
    #         if hasattr(self, 'video_widget'):
    #             self.video_widget.stop_video()
    #         
    #         # Handle cup completion (checks if more cups needed)
    #         app = App.get_running_app()
    #         Clock.schedule_once(lambda dt: app.handle_cup_completion(), 0.3)
    #         
    #     elif pump_state == "Paused" and not self.is_paused:
    #         # Cup removed - pause animation
    #         print("⏸️ Cup removed - PAUSING dispensing animation")
    #         self.pause_dispensing()
    #         
    #     elif pump_state == "Ongoing" and self.is_paused:
    #         # Cup replaced - resume animation
    #         print("▶️ Cup replaced - RESUMING dispensing animation")
    #         self.resume_dispensing()
    
    # Pause/Resume methods commented out - not in use
    # def pause_dispensing(self):
    #     """Pause the dispensing animation and show popup"""
    #     self.is_paused = True
    #     
    #     # Pause video
    #     if hasattr(self, 'video_widget'):
    #         self.video_widget.stop_video()
    #     
    #     # Show popup
    #     self.show_pause_popup()
    # 
    # def resume_dispensing(self):
    #     """Resume the dispensing animation and close popup"""
    #     self.is_paused = False
    #     
    #     # Close popup
    #     if self.pause_popup:
    #         self.pause_popup.dismiss()
    #         self.pause_popup = None
    #     
    #     # Resume video
    #     if hasattr(self, 'video_widget'):
    #         self.video_widget.start_video()
    
    # Pause popup method commented out - not in use
    # def show_pause_popup(self):
    #     """Show popup when dispensing is paused"""
    #     content = BoxLayout(orientation='vertical', padding=20, spacing=15)
    #     
    #     # Warning icon
    #     icon_label = Label(
    #         text='⚠️',
    #         font_size='60sp',
    #         size_hint_y=0.3
    #     )
    #     content.add_widget(icon_label)
    #     
    #     # Message
    #     message_label = Label(
    #         text='Place the cup to\\ncontinue dispensing',
    #         font_size='24sp',
    #         bold=True,
    #         halign='center',
    #         valign='middle',
    #         size_hint_y=0.5
    #     )
    #     message_label.bind(size=message_label.setter('text_size'))
    #     content.add_widget(message_label)
    #     
    #     # Info text
    #     info_label = Label(
    #         text='Dispensing will resume automatically',
    #         font_size='16sp',
    #         color=(0.5, 0.5, 0.5, 1),
    #         size_hint_y=0.2
    #     )
    #     content.add_widget(info_label)
    #     
    #     # Create popup
    #     self.pause_popup = Popup(
    #         title='Dispensing Paused',
    #         content=content,
    #         size_hint=(0.7, 0.5),
    #         auto_dismiss=False
    #     )
    #     
    #     self.pause_popup.open()

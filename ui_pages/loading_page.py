from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
import os
import math

class SpinnerWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.angle = 0
        self.size_hint = (None, None)
        self.size = (60, 60)
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(0.714, 0.478, 0.176, 1)  # #b67a2d
            center_x, center_y = self.center
            radius = min(self.width, self.height) / 3
            
            # Draw spinning arcs
            for i in range(8):
                angle = (self.angle + i * 45) % 360
                alpha = 1.0 - (i * 0.1)
                Color(0.714, 0.478, 0.176, alpha)
                
                # Calculate arc position
                start_angle = angle
                end_angle = angle + 30
                
                # Draw arc as lines (simplified spinner)
                x1 = center_x + radius * math.cos(math.radians(start_angle))
                y1 = center_y + radius * math.sin(math.radians(start_angle))
                x2 = center_x + (radius + 10) * math.cos(math.radians(start_angle))
                y2 = center_y + (radius + 10) * math.sin(math.radians(start_angle))
                
                Line(points=[x1, y1, x2, y2], width=3)
    
    def start_spinning(self):
        self.spin_event = Clock.schedule_interval(self.spin, 1/30)
    
    def stop_spinning(self):
        if hasattr(self, 'spin_event'):
            self.spin_event.cancel()
    
    def spin(self, dt):
        self.angle = (self.angle + 10) % 360
        self.update_graphics()

class LoadingPage(Screen):
    """Modern loading page with animated spinner"""
    
    def __init__(self, **kwargs):
        super(LoadingPage, self).__init__(**kwargs)
        
        self.is_animating = False
        
        # Main layout with gradient background
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Top spacing
        main_layout.add_widget(Widget(size_hint_y=0.2))
        
        # Cup image section
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.25)
        
        # Check if image exists, otherwise use placeholder
        image_path = os.path.join('assets', 'cupimage.png')
        if os.path.exists(image_path):
            self.cup_image = Image(source=image_path, size_hint=(None, None), size=(160, 160))
        else:
            # Create a placeholder widget
            self.cup_image = Widget(size_hint=(None, None), size=(120, 120))
            with self.cup_image.canvas:
                Color(0.714, 0.478, 0.176, 1)  # #b67a2d
                Line(circle=(60, 60, 50), width=3)
                Line(points=[110, 60, 130, 60, 130, 40, 120, 20], width=3)  # Handle
        
        image_section.add_widget(self.cup_image)
        main_layout.add_widget(image_section)
        
        # Loading text
        loading_label = Label(
            text='Please wait...',
            font_size='24sp',  # Optimized for 1024x600 (7-inch tablet)
            bold=True,
            color=(0.714, 0.478, 0.176, 1),  # #b67a2d
            size_hint_y=0.1
        )
        main_layout.add_widget(loading_label)
        
        # Spinner section
        spinner_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.15)
        self.spinner = SpinnerWidget()
        spinner_section.add_widget(self.spinner)
        main_layout.add_widget(spinner_section)
        
        # More specific message
        self.loading_detail = Label(
            text='Generating QR code for payment',
            font_size='20sp',  # Optimized for 1024x600 (7-inch tablet)
            color=(0.4, 0.4, 0.4, 1),
            size_hint_y=0.15
        )
        main_layout.add_widget(self.loading_detail)
        
        # Bottom spacing (increased since we removed dots)
        main_layout.add_widget(Widget(size_hint_y=0.15))
        
        self.add_widget(main_layout)
        
        # Animation events
        self.dots_event = None
        self.pulse_animation = None
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def update_message(self, message):
        """Update the loading message"""
        self.loading_detail.text = message

    def start_animation(self):
        """Start the loading animation"""
        self.is_animating = True
        self.spinner.start_spinning()
        self.animate_cup_pulse()

    def stop_animation(self):
        """Stop the loading animation"""
        self.is_animating = False
        self.spinner.stop_spinning()
        if self.pulse_animation:
            self.pulse_animation.cancel(self.cup_image)
    
    def animate_cup_pulse(self):
        """Add a subtle pulse animation to the cup image"""
        if not self.is_animating:
            return
            
        # Create pulsing animation
        pulse_out = Animation(size=(160, 160), duration=1)
        pulse_in = Animation(size=(150, 150), duration=1)
        self.pulse_animation = pulse_out + pulse_in
        self.pulse_animation.repeat = True
        self.pulse_animation.start(self.cup_image)
    
    def on_enter(self):
        """Called when screen is entered"""
        self.start_animation()
    
    def on_leave(self):
        """Called when screen is left"""
        self.stop_animation()

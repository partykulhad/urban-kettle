from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
import os
import math

class ProcessingSpinner(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.angle = 0
        self.size_hint = (None, None)
        self.size = (80, 80)
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.clear()
        with self.canvas:
            center_x, center_y = self.center
            radius = min(self.width, self.height) / 3
            
            # Draw multiple rotating circles for a modern look
            for i in range(3):
                angle = (self.angle + i * 120) % 360
                alpha = 0.8 - (i * 0.2)
                Color(0.18, 0.8, 0.44, alpha)  # Green color with varying alpha
                
                # Calculate circle position
                orbit_radius = radius * 0.6
                x = center_x + orbit_radius * math.cos(math.radians(angle)) - 8
                y = center_y + orbit_radius * math.sin(math.radians(angle)) - 8
                
                Ellipse(pos=(x, y), size=(16, 16))
    
    def start_spinning(self):
        self.spin_event = Clock.schedule_interval(self.spin, 1/30)  # 60 FPS for smooth animation
    
    def stop_spinning(self):
        if hasattr(self, 'spin_event'):
            self.spin_event.cancel()
    
    def spin(self, dt):
        self.angle = (self.angle + 5) % 360
        self.update_graphics()

class TransactionProcessingPage(Screen):
    """Modern transaction processing page with animated elements"""
    
    def __init__(self, **kwargs):
        super(TransactionProcessingPage, self).__init__(**kwargs)
        
        # Main layout with gradient background
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Top spacing
        main_layout.add_widget(Widget(size_hint_y=0.15))
        
        # Success icon section
        icon_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.2)
        
        # Create success checkmark
        success_icon = Widget(size_hint=(None, None), size=(100, 100))
        with success_icon.canvas:
            Color(0.18, 0.8, 0.44, 1)  # Green color
            Line(circle=(50, 50, 45), width=4)
            # Checkmark
            Color(0.18, 0.8, 0.44, 1)
            Line(points=[30, 50, 45, 35, 70, 65], width=6)
        
        icon_section.add_widget(success_icon)
        main_layout.add_widget(icon_section)
        
        # Processing text with animation
        self.processing_label = Label(
            text='Processing Payment...',
            font_size='28sp',
            bold=True,
            color=(0.18, 0.8, 0.44, 1),  # Green color
            size_hint_y=0.1
        )
        main_layout.add_widget(self.processing_label)
        
        # Spinner section
        spinner_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.15)
        self.spinner = ProcessingSpinner()
        spinner_section.add_widget(self.spinner)
        main_layout.add_widget(spinner_section)
        
        # More specific message
        self.processing_detail = Label(
            text='Please wait while we confirm your payment',
            font_size='16sp',
            color=(0.4, 0.4, 0.4, 1),
            size_hint_y=0.1,
            text_size=(None, None),
            halign='center'
        )
        main_layout.add_widget(self.processing_detail)
        
        # Progress steps
        steps_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.15)
        steps_container = BoxLayout(orientation='vertical', size_hint=(None, None), 
                                  size=(300, 80), spacing=5)
        
        self.step1 = Label(text='✓ Payment received', font_size='14sp', 
                          color=(0.18, 0.8, 0.44, 1), size_hint_y=None, height='20sp')
        self.step2 = Label(text='⟳ Verifying transaction...', font_size='14sp', 
                          color=(0.714, 0.478, 0.176, 1), size_hint_y=None, height='20sp')
        self.step3 = Label(text='○ Preparing your order', font_size='14sp', 
                          color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height='20sp')
        
        steps_container.add_widget(self.step1)
        steps_container.add_widget(self.step2)
        steps_container.add_widget(self.step3)
        
        steps_section.add_widget(steps_container)
        main_layout.add_widget(steps_section)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.15))
        
        self.add_widget(main_layout)
        
        # Animation for text pulsing
        self.text_animation = None
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def update_message(self, message):
        """Update the processing message"""
        self.processing_detail.text = message
    
    def animate_steps(self):
        """Animate the processing steps"""
        def update_step2():
            self.step2.text = '✓ Transaction verified'
            self.step2.color = (0.18, 0.8, 0.44, 1)
            self.step3.text = '⟳ Preparing your order'
            self.step3.color = (0.714, 0.478, 0.176, 1)
        
        def update_step3():
            self.step3.text = '✓ Order ready for dispensing'
            self.step3.color = (0.18, 0.8, 0.44, 1)
        
        # Schedule step updates
        Clock.schedule_once(lambda dt: update_step2(), 1.5)
        Clock.schedule_once(lambda dt: update_step3(), 2.5)
    
    def animate_text_pulse(self):
        """Add pulsing animation to processing text"""
        pulse_out = Animation(font_size=32, duration=0.8)
        pulse_in = Animation(font_size=28, duration=0.8)
        self.text_animation = pulse_out + pulse_in
        self.text_animation.repeat = True
        self.text_animation.start(self.processing_label)
    
    def on_enter(self):
        """Called when screen is entered"""
        # Reset steps to initial state
        self.step1.text = '✓ Payment received'
        self.step1.color = (0.18, 0.8, 0.44, 1)
        self.step2.text = '⟳ Verifying transaction...'
        self.step2.color = (0.714, 0.478, 0.176, 1)
        self.step3.text = '○ Preparing your order'
        self.step3.color = (0.7, 0.7, 0.7, 1)
        
        # Start animations
        self.spinner.start_spinning()
        self.animate_text_pulse()
        self.animate_steps()
    
    def on_leave(self):
        """Called when screen is left"""
        self.spinner.stop_spinning()
        if self.text_animation:
            self.text_animation.cancel(self.processing_label)

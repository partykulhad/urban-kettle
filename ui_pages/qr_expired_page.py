from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.app import App
import math


class ModernPremiumButton(Button):
    """Premium modern button with advanced styling"""
    
    def __init__(self, bg_color=(0.2, 0.6, 0.9, 1), text_color=(1, 1, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.bg_color = bg_color
        self.text_color = text_color
        self.is_pressed = False
        self.original_size = None
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Multi-layer shadow for premium look
            Color(0, 0, 0, 0.05)
            RoundedRectangle(pos=(self.pos[0] + 6, self.pos[1] - 6), size=self.size, radius=[25])
            Color(0, 0, 0, 0.08)
            RoundedRectangle(pos=(self.pos[0] + 4, self.pos[1] - 4), size=self.size, radius=[25])
            Color(0, 0, 0, 0.12)
            RoundedRectangle(pos=(self.pos[0] + 2, self.pos[1] - 2), size=self.size, radius=[25])
            
            # Gradient-like effect with multiple layers
            Color(self.bg_color[0] * 1.1, self.bg_color[1] * 1.1, self.bg_color[2] * 1.1, self.bg_color[3])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[25])
            
            # Subtle inner highlight
            Color(1, 1, 1, 0.15)
            RoundedRectangle(
                pos=(self.pos[0] + 2, self.pos[1] + self.size[1] * 0.6), 
                size=(self.size[0] - 4, self.size[1] * 0.3), 
                radius=[20]
            )
        
        # Update text color
        self.color = self.text_color
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_pressed = True
            if not self.original_size:
                self.original_size = self.size[:]
            
            # Premium scale animation
            Animation.cancel_all(self)
            press_size = (self.original_size[0] * 1.08, self.original_size[1] * 1.08)
            Animation(size=press_size, duration=0.15, t='out_quart').start(self)
            
            return super().on_touch_down(touch)
        return False
    
    def on_touch_up(self, touch):
        if self.is_pressed:
            self.is_pressed = False
            
            # Smooth return animation
            if self.original_size:
                Animation.cancel_all(self)
                Animation(size=self.original_size, duration=0.25, t='out_elastic').start(self)
            
            return super().on_touch_up(touch)
        return False


class PremiumIconWidget(Widget):
    """Custom widget for premium expired icon"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        if self.size[0] == 0 or self.size[1] == 0:
            return
            
        self.canvas.clear()
        with self.canvas:
            # Premium circular background with gradient effect
            center_x, center_y = self.center_x, self.center_y
            radius = min(self.width, self.height) * 0.4
            
            # Outer glow
            Color(1, 0.3, 0.3, 0.1)
            Ellipse(pos=(center_x - radius * 1.3, center_y - radius * 1.3), 
                   size=(radius * 2.6, radius * 2.6))
            
            # Main circle with gradient layers
            Color(0.95, 0.25, 0.25, 1)  # Deep red
            Ellipse(pos=(center_x - radius, center_y - radius), 
                   size=(radius * 2, radius * 2))
            
            Color(1, 0.4, 0.4, 0.7)  # Lighter red overlay
            Ellipse(pos=(center_x - radius * 0.8, center_y - radius * 0.8), 
                   size=(radius * 1.6, radius * 1.6))
            
            # Premium X mark
            Color(1, 1, 1, 1)  # White X
            line_width = radius * 0.15
            
            # X lines with rounded ends
            Line(points=[
                center_x - radius * 0.4, center_y - radius * 0.4,
                center_x + radius * 0.4, center_y + radius * 0.4
            ], width=line_width, cap='round')
            
            Line(points=[
                center_x - radius * 0.4, center_y + radius * 0.4,
                center_x + radius * 0.4, center_y - radius * 0.4
            ], width=line_width, cap='round')
            
            # Inner highlight ring
            Color(1, 1, 1, 0.2)
            Line(ellipse=(center_x - radius * 0.9, center_y - radius * 0.9, 
                         radius * 1.8, radius * 1.8), width=2)


class QRExpiredPage(Screen):
    """Premium QR code expiration page with modern design"""
    
    def __init__(self, **kwargs):
        super(QRExpiredPage, self).__init__(**kwargs)
        
        # Main layout with premium background
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            # Consistent background color
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Top spacing
        main_layout.add_widget(Widget(size_hint_y=0.12))
        
        # Premium icon section
        icon_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.25)
        premium_icon = PremiumIconWidget(
            size_hint=(None, None),
            size=(150, 150)
        )
        icon_section.add_widget(premium_icon)
        main_layout.add_widget(icon_section)
        
        # Small spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # Main title with premium styling
        title_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.15)
        title_label = Label(
            text='QR Code Expired',
            font_size='36sp',
            bold=True,
            color=(0.2, 0.2, 0.2, 1),
            halign='center'
        )
        title_section.add_widget(title_label)
        main_layout.add_widget(title_section)
        
        # Subtitle message
        subtitle_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.12)
        subtitle_label = Label(
            text='Generate a new QR code to pay',
            font_size='22sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center'
        )
        subtitle_section.add_widget(subtitle_label)
        main_layout.add_widget(subtitle_section)
        
        # Additional helpful message
        message_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.1)
        message_label = Label(
            text='Your payment session has timed out for security',
            font_size='16sp',
            color=(0.6, 0.6, 0.6, 1),
            halign='center'
        )
        message_section.add_widget(message_label)
        main_layout.add_widget(message_section)
        
        # Spacing before button
        main_layout.add_widget(Widget(size_hint_y=0.08))
        
        # Premium button section
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.12)
        
        self.home_btn = ModernPremiumButton(
            text='🏠 Home Page',
            size_hint=(None, None),
            size=(300, 65),
            font_size='20sp',
            bold=True,
            bg_color=(0.2, 0.6, 0.9, 1),  # Premium blue
            text_color=(1, 1, 1, 1)
        )
        self.home_btn.bind(on_press=self.go_to_home)
        
        button_section.add_widget(self.home_btn)
        main_layout.add_widget(button_section)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.08))
        
        self.add_widget(main_layout)
        
        # Add entrance animation
        self.entrance_animation = None
        
    def _update_rect(self, instance, value):
        """Update background rectangle"""
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def on_enter(self, *args):
        """Called when entering the screen - add entrance animation"""
        # Animate the main content sliding up from bottom
        for child in self.children[0].children:
            if hasattr(child, 'children') and child.children:
                widget = child.children[0] if child.children else child
                # Start from below and animate up
                original_y = widget.y
                widget.y = original_y - 50
                widget.opacity = 0
                
                # Staggered animation for each element
                delay = (len(self.children[0].children) - self.children[0].children.index(child)) * 0.1
                Animation.cancel_all(widget)
                anim = Animation(y=original_y, opacity=1, duration=0.6, t='out_quart')
                anim.start(widget)
    
    def go_to_home(self, instance):
        """Navigate back to selection page (home)"""
        app = App.get_running_app()
        # Navigate to selection page which acts as home
        app.show_selection_page()

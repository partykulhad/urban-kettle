from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock

class ErrorPopup(Popup):
    """Modern styled popup for hardware errors"""
    
    def __init__(self, title_text="Hardware Error", message_text="Unknown Error", **kwargs):
        # Create content layout
        content = FloatLayout()
        
        # Background with rounded corners
        with content.canvas.before:
            Color(0.95, 0.95, 0.95, 0.98)  # Light background
            self.bg_rect = RoundedRectangle(size=(450, 300), pos=(0, 0), radius=[25])
        
        # Close button (X) in top-right corner
        close_btn = Button(
            text='✕',
            size_hint=(None, None),
            size=(40, 40),
            pos_hint={'right': 0.95, 'top': 0.95},
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.6, 1),
            font_size='20sp',
            bold=True
        )
        close_btn.bind(on_press=self.dismiss)
        content.add_widget(close_btn)
        
        # Icon - Warning Symbol
        icon_label = Label(
            text="⚠️",
            font_size='48sp',
            color=(0.9, 0.3, 0.2, 1),  # Red/Orange
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.8},
            size_hint=(None, None),
            size=(100, 60)
        )
        content.add_widget(icon_label)
        
        # Title
        title_label = Label(
            text=title_text,
            font_size='24sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.65},
            size_hint=(None, None),
            size=(400, 40)
        )
        content.add_widget(title_label)
        
        # Message
        message_label = Label(
            text=message_text,
            font_size='18sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.45},
            size_hint=(None, None),
            size=(400, 80)
        )
        content.add_widget(message_label)
        
        # Initialize Popup
        super().__init__(
            title='',
            content=content,
            size_hint=(None, None),
            size=(450, 300),
            auto_dismiss=False,
            separator_height=0,
            **kwargs
        )
        
        # Update background rect when popup size changes
        content.bind(size=self.update_bg_rect, pos=self.update_bg_rect)
        
    def update_bg_rect(self, *args):
        """Update background rectangle size and position"""
        self.bg_rect.size = self.content.size
        self.bg_rect.pos = self.content.pos

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


class QRErrorPopup(Popup):
    """Popup for QR generation errors with Retry button"""
    
    def __init__(self, on_retry_callback=None, on_cancel_callback=None, **kwargs):
        self.on_retry_callback = on_retry_callback
        self.on_cancel_callback = on_cancel_callback
        self.auto_dismiss_event = None
        self.is_retry_clicked = False
        
        # Create content layout
        content = FloatLayout()
        
        # Background with rounded corners
        with content.canvas.before:
            Color(0.95, 0.95, 0.95, 0.98)  # Light background
            self.bg_rect = RoundedRectangle(size=(450, 320), pos=(0, 0), radius=[25])
        
        # Icon - Warning Symbol
        icon_label = Label(
            text="⚠️",
            font_size='48sp',
            color=(0.9, 0.3, 0.2, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.82},
            size_hint=(None, None),
            size=(100, 60)
        )
        content.add_widget(icon_label)
        
        # Title
        title_label = Label(
            text="QR Generation Failed",
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
            text="Connection timeout.\nPlease try again.",
            font_size='18sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.48},
            size_hint=(None, None),
            size=(400, 60)
        )
        content.add_widget(message_label)
        
        # Retry button - Orange
        retry_btn = Button(
            text='Try Again',
            size_hint=(None, None),
            size=(170, 55),
            pos_hint={'center_x': 0.3, 'center_y': 0.22},
            background_color=(0, 0, 0, 0),
            background_normal='',
            color=(1, 1, 1, 1),
            font_size='20sp',
            bold=True
        )
        with retry_btn.canvas.before:
            Color(0.949, 0.6, 0.0, 1)  # Orange
            self.retry_btn_bg = RoundedRectangle(size=retry_btn.size, pos=retry_btn.pos, radius=[15])
        retry_btn.bind(size=self._update_retry_btn, pos=self._update_retry_btn)
        retry_btn.bind(on_press=self._on_retry_pressed)
        content.add_widget(retry_btn)

        # Go Back button - grey
        back_btn = Button(
            text='Go Back',
            size_hint=(None, None),
            size=(170, 55),
            pos_hint={'center_x': 0.7, 'center_y': 0.22},
            background_color=(0, 0, 0, 0),
            background_normal='',
            color=(1, 1, 1, 1),
            font_size='20sp',
            bold=True
        )
        with back_btn.canvas.before:
            Color(0.45, 0.45, 0.45, 1)  # Grey
            self.back_btn_bg = RoundedRectangle(size=back_btn.size, pos=back_btn.pos, radius=[15])
        back_btn.bind(size=self._update_back_btn, pos=self._update_back_btn)
        back_btn.bind(on_press=self._on_back_pressed)
        content.add_widget(back_btn)

        # Initialize Popup
        super().__init__(
            title='',
            content=content,
            size_hint=(None, None),
            size=(450, 320),
            auto_dismiss=False,
            separator_height=0,
            **kwargs
        )
        
        # Update background rect when popup size changes
        content.bind(size=self._update_bg_rect, pos=self._update_bg_rect)
    
    def _update_bg_rect(self, *args):
        """Update background rectangle size and position"""
        self.bg_rect.size = self.content.size
        self.bg_rect.pos = self.content.pos
    
    def _update_retry_btn(self, instance, value):
        self.retry_btn_bg.size = instance.size
        self.retry_btn_bg.pos = instance.pos

    def _update_back_btn(self, instance, value):
        self.back_btn_bg.size = instance.size
        self.back_btn_bg.pos = instance.pos

    def _on_back_pressed(self, instance):
        """Immediately return to home — no retry attempt."""
        if self.auto_dismiss_event:
            self.auto_dismiss_event.cancel()
            self.auto_dismiss_event = None
        self.dismiss()
        if self.on_cancel_callback:
            self.on_cancel_callback()

    def _on_retry_pressed(self, instance):
        """Handle retry button press"""
        self.is_retry_clicked = True
        # Cancel auto-dismiss timer
        if self.auto_dismiss_event:
            self.auto_dismiss_event.cancel()
            self.auto_dismiss_event = None
        self.dismiss()
        if self.on_retry_callback:
            self.on_retry_callback()
    
    def open(self):
        """Open popup and start auto-dismiss timer"""
        super().open()
        # Auto-dismiss after 8 seconds if retry not clicked
        self.auto_dismiss_event = Clock.schedule_once(self._auto_dismiss, 8)
    
    def _auto_dismiss(self, dt):
        """Auto-dismiss and go to home"""
        if not self.is_retry_clicked:
            self.dismiss()
            if self.on_cancel_callback:
                self.on_cancel_callback()
    
    def dismiss(self, *args, **kwargs):
        """Override dismiss to cancel timer"""
        if self.auto_dismiss_event:
            self.auto_dismiss_event.cancel()
            self.auto_dismiss_event = None
        super().dismiss(*args, **kwargs)
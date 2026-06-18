from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.app import App
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
import io
import os
from kivy.core.image import Image as CoreImage


class SimpleButton(Button):
    """Simple button without animations or effects"""
    
    def __init__(self, bg_color=(0.906, 0.298, 0.235, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.bg_color = bg_color
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Simple button background
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[15])


class PaymentPage(Screen):
    def __init__(self, **kwargs):
        super(PaymentPage, self).__init__(**kwargs)
        
        # Store QR code ID and transaction ID
        self.current_qr_code_id = ""
        self.transaction_id = ""
        
        # Timer variables
        self.timer_seconds = 120  # 2 minutes in seconds
        self.timer_event = None
        self.timer_callback = None
        self.timer_running = False
        
        # Cancel button debouncing
        self.cancel_pressed = False
        
        # Main layout - no padding to match payment_method_page exactly
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Top bar with logo on left - matching payment_method_page exactly
        from kivy.uix.floatlayout import FloatLayout
        top_bar = FloatLayout(size_hint_y=0.15)
        
        # Urban Kettle logo on the left side - same as payment_method_page
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                pos_hint={'x': 0.0, 'top': 1.35},
                allow_stretch=True,
                keep_ratio=True
            )
            top_bar.add_widget(logo_image)
        else:
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='28sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                pos_hint={'x': 0.02, 'top': 0.95},
                halign='left'
            )
            top_bar.add_widget(fallback_logo)
        
        main_layout.add_widget(top_bar)
        
        # "SCAN TO PAY" text
        scan_label = Label(
            text='SCAN TO PAY',
            font_size='32sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.08
        )
        main_layout.add_widget(scan_label)
        
        # Spacing after SCAN TO PAY
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # QR code section - increased space
        qr_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.40)
        
        # QR code container - reduced size
        self.qr_container = BoxLayout(
            size_hint=(None, None),
            size=(250, 250),
            padding=10
        )
        
        with self.qr_container.canvas.before:
            # White background
            Color(1, 1, 1, 1)
            self.qr_bg = RoundedRectangle(
                pos=self.qr_container.pos, 
                size=(250, 250), 
                radius=[15]
            )
        
        self.qr_container.bind(pos=self._update_qr_bg, size=self._update_qr_bg)
        
        # QR image widget
        self.qr_image = Image(
            size_hint=(1, 1),
            fit_mode='contain'
        )
        
        self.qr_container.add_widget(self.qr_image)
        qr_section.add_widget(self.qr_container)
        main_layout.add_widget(qr_section)
        
        # Spacing after QR
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Total amount display below QR code - reduced font
        amount_section = AnchorLayout(anchor_x='right', anchor_y='center', size_hint_y=0.07)
        self.amount_label = Label(
            text='Total: ₹0',
            font_size='26sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='right'
        )
        amount_section.add_widget(self.amount_label)
        main_layout.add_widget(amount_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # Instruction text - reduced fonts
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.08, spacing=3)
        
        scan_text_label = Label(
            text='Scan this QR with your UPI',
            font_size='20sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(scan_text_label)
        
        payment_label = Label(
            text='app to make payment.',
            font_size='20sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(payment_label)
        
        main_layout.add_widget(instruction_section)
        
        # Timer display - increased font
        self.payment_status_label = Label(
            text='Pay within 2:30',
            font_size='22sp',  # Increased from 18sp
            bold=True,
            color=(0.906, 0.298, 0.235, 1),
            size_hint_y=0.06,
            halign='center'
        )
        main_layout.add_widget(self.payment_status_label)
        
        # Spacing before button
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Cancel button
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.08)
        
        cancel_btn = SimpleButton(
            text='Cancel',
            size_hint=(None, None),
            size=(150, 55),  # Increased size
            font_size='22sp',  # Increased from 18sp
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=(0.906, 0.298, 0.235, 1)
        )
        cancel_btn.bind(on_press=self.cancel_payment)
        
        button_section.add_widget(cancel_btn)
        main_layout.add_widget(button_section)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        self.add_widget(main_layout)
        
        # Animation for QR code appearance
        self.qr_animation = None
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def _update_qr_bg(self, instance, value):
        self.qr_bg.pos = instance.pos
        self.qr_bg.size = instance.size
    
    def update(self, qr_image, data):
        """Update payment page with generated QR code and payment info"""
        self.update_qr_code(qr_image)
        
        # Store QR code ID and transaction ID
        self.current_qr_code_id = data.get("id", "")
        self.transaction_id = data.get("transactionId", "")
        print(f"Got QR code ID: {self.current_qr_code_id}")
        print(f"Got transaction ID: {self.transaction_id}")
        
        # Update total amount display
        amount = data.get("amount", 0)
        self.amount_label.text = f'Total: ₹{amount}'
        print(f"Total amount: ₹{amount}")
        
        # Start the countdown timer
        self.start_timer()
        
        # Animate QR code appearance
        if self.qr_animation:
            self.qr_animation.cancel(self.qr_image)
        self.qr_image.opacity = 0
        self.qr_animation = Animation(opacity=1, duration=0.5)
        self.qr_animation.start(self.qr_image)
    
    def update_qr_code(self, pil_image):
        """Update QR code image from PIL Image or pre-encoded bytes.

        Accepts either a PIL.Image or an io.BytesIO that already contains
        PNG-encoded bytes (produced in a background thread by the prefetch
        worker to avoid blocking the main thread with PIL.save).
        """
        if isinstance(pil_image, io.BytesIO):
            # Fast path: bytes were encoded in background thread
            buf = pil_image
            buf.seek(0)
        else:
            # Slow path: encode PIL image here on the main thread (fallback)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            buf = io.BytesIO()
            pil_image.save(buf, format='PNG')
            buf.seek(0)

        kivy_image = CoreImage(buf, ext='png')
        self.qr_image.texture = kivy_image.texture
    
    def update_status(self, status):
        """Update the payment status label"""
        if not self.timer_running or 'received' in status.lower() or 'expired' in status.lower():
            if 'received' in status.lower() or 'expired' in status.lower():
                self.stop_timer()
            
            self.payment_status_label.text = status
            
            # Add color coding for different statuses
            if 'received' in status.lower():
                self.payment_status_label.color = (0.18, 0.8, 0.44, 1)  # Green
            elif 'expired' in status.lower():
                self.payment_status_label.color = (0.906, 0.298, 0.235, 1)  # Red
            else:
                self.payment_status_label.color = (0.4, 0.4, 0.4, 1)  # Gray
    
    def cancel_payment(self, instance):
        """Handle cancel button click - with debouncing"""
        # Prevent multiple clicks
        if self.cancel_pressed:
            return
        self.cancel_pressed = True
        
        app = App.get_running_app()
        app.cancel_payment()
    
    def get_qr_code_id(self):
        """Get the current QR code ID"""
        return self.current_qr_code_id
    
    def get_transaction_id(self):
        """Get the current transaction ID"""
        return self.transaction_id
    
    def start_timer(self):
        """Start the 2.5-minute countdown timer"""
        self.timer_seconds = 150
        self.stop_timer()
        self.timer_running = True
        self.timer_event = Clock.schedule_interval(self.update_timer, 1)
        self.update_timer_display()
    
    def stop_timer(self):
        """Stop the countdown timer"""
        self.timer_running = False
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
    
    def update_timer(self, dt):
        """Update the countdown timer every second"""
        self.timer_seconds -= 1
        self.update_timer_display()
        
        if self.timer_seconds <= 0:
            self.timer_expired()
            return False
        
        return True
    
    def update_timer_display(self):
        """Update the timer display text"""
        minutes = self.timer_seconds // 60
        seconds = self.timer_seconds % 60
        
        # Change color based on remaining time
        if self.timer_seconds <= 30:
            self.payment_status_label.color = (1, 0.2, 0.2, 1)  # Bright red
        elif self.timer_seconds <= 60:
            self.payment_status_label.color = (1, 0.6, 0, 1)  # Orange
        else:
            self.payment_status_label.color = (0.906, 0.298, 0.235, 1)  # Red
        
        self.payment_status_label.text = f'Pay within {minutes}:{seconds:02d}'
    
    def timer_expired(self):
        """Handle timer expiration"""
        print("Payment timer expired")
        self.stop_timer()
        self.payment_status_label.text = 'QR code expired!'
        self.payment_status_label.color = (1, 0.2, 0.2, 1)
        
        if self.timer_callback:
            self.timer_callback()
    
    def set_timer_callback(self, callback):
        """Set the callback function to call when timer expires"""
        self.timer_callback = callback
    
    def on_enter(self, *args):
        """Called when entering the payment page - reset state"""
        self.cancel_pressed = False  # Reset cancel button debouncing
        return super().on_enter(*args)
    
    def on_leave(self, *args):
        """Called when leaving the payment page - stop timer"""
        self.stop_timer()
        self.cancel_pressed = False  # Reset cancel button debouncing
        return super().on_leave(*args)

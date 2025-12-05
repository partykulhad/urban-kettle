from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Triangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
import math
import threading
import time
import os
import requests
from utils.rfid_reader import rfid_reader


class ModernButton(Button):
    """Modern button with rounded corners and hover effects"""
    
    def __init__(self, bg_color=(0.7, 0.9, 0.8, 1), text_color=(0.2, 0.2, 0.2, 1), **kwargs):
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
            # Shadow effect
            Color(0, 0, 0, 0.1)
            RoundedRectangle(pos=(self.pos[0] + 2, self.pos[1] - 2), size=self.size, radius=[20])
            
            # Main button background
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
        
        # Update text color
        self.color = self.text_color
    
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.is_pressed = True
            if not self.original_size:
                self.original_size = self.size[:]
            
            # Scale button slightly on press
            Animation.cancel_all(self)
            press_size = (self.original_size[0] * 1.05, self.original_size[1] * 1.05)
            Animation(size=press_size, duration=0.1).start(self)
            
            return super().on_touch_down(touch)
        return False
    
    def on_touch_up(self, touch):
        if self.is_pressed:
            self.is_pressed = False
            
            # Return to original size
            if self.original_size:
                Animation.cancel_all(self)
                Animation(size=self.original_size, duration=0.15, t='out_back').start(self)
            
            return super().on_touch_up(touch)
        return False


class PremiumPaymentCard(Widget):
    """Premium transparent card with amazing shadow effects"""
    
    def __init__(self, card_type='upi', **kwargs):
        super().__init__(**kwargs)
        self.card_type = card_type
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Multiple shadow layers for depth and premium look
            
            # Outer shadow (largest, most diffused)
            Color(0, 0, 0, 0.03)
            RoundedRectangle(pos=(self.pos[0] + 15, self.pos[1] - 15), size=self.size, radius=[30])
            
            # Medium shadow layer
            Color(0, 0, 0, 0.06)
            RoundedRectangle(pos=(self.pos[0] + 10, self.pos[1] - 10), size=self.size, radius=[30])
            
            # Inner shadow layer
            Color(0, 0, 0, 0.08)
            RoundedRectangle(pos=(self.pos[0] + 6, self.pos[1] - 6), size=self.size, radius=[30])
            
            # Close shadow
            Color(0, 0, 0, 0.12)
            RoundedRectangle(pos=(self.pos[0] + 3, self.pos[1] - 3), size=self.size, radius=[30])
            
            # Main card background - bright orange color (#F29900)
            if self.card_type == 'upi':
                # Bright orange for UPI card
                Color(0.949, 0.6, 0.0, 1)

            else:
                # Same bright orange for RFID card
                Color(0.949, 0.6, 0.0, 1)
                
            RoundedRectangle(pos=self.pos, size=self.size, radius=[30])
            
            # Subtle inner glow/highlight
            Color(1, 1, 1, 0.15)
            Line(rounded_rectangle=(self.pos[0] + 2, self.pos[1] + 2, 
                                  self.size[0] - 4, self.size[1] - 4, 28), width=1)


class CenterDividerWidget(Widget):
    """Custom widget to draw the center divider line and arrow"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.clear()
        with self.canvas:
            # Draw center vertical line
            Color(0.6, 0.6, 0.6, 1)  # Gray color for the line
            Line(points=[self.center_x, self.y, self.center_x, self.top], width=2)
            
            # Draw arrow pointing to the right (RFID side)
            arrow_y = self.center_y + 50  # Position arrow slightly above center
            arrow_size = 20
            
            # Arrow shaft (horizontal line)
            Line(points=[self.center_x + 20, arrow_y, self.center_x + 60, arrow_y], width=3)
            
            # Arrow head (triangle pointing right)
            Color(0.4, 0.7, 0.4, 1)  # Green color for arrow
            arrow_points = [
                self.center_x + 60, arrow_y,  # tip
                self.center_x + 45, arrow_y + arrow_size//2,  # top back
                self.center_x + 45, arrow_y - arrow_size//2   # bottom back
            ]
            # Draw filled triangle using lines
            Line(points=arrow_points + [arrow_points[0], arrow_points[1]], width=2)
            Line(points=[arrow_points[0], arrow_points[1], arrow_points[2], arrow_points[3], arrow_points[4], arrow_points[5]], width=2)


class CupsCounterWidget(BoxLayout):
    """Simple cups counter widget with icon and number - matching reference image"""
    
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=0, **kwargs)
        self.cups_count = 0
        self.is_loading = True
        
        # Top row with icon and number - reduced to give more space for text below
        top_row = BoxLayout(orientation='horizontal', spacing=2, size_hint_y=0.5)
        
        # Cup icon image
        cup_icon_path = os.path.join('assets', 'cupnumber.png')
        
        if os.path.exists(cup_icon_path):
            self.cup_icon = Image(
                source=cup_icon_path,
                size_hint=(None, None),
                size=(50, 50),
                allow_stretch=True,
                keep_ratio=True
            )
            top_row.add_widget(self.cup_icon)
        else:
            # Fallback to text icon if image not found
            fallback_icon = Label(
                text='☕',
                font_size='40sp',
                color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
                size_hint=(None, None),
                size=(50, 50),
                halign='center',
                valign='middle'
            )
            top_row.add_widget(fallback_icon)
        
        # Number label - increased font size
        self.number_label = Label(
            text='...',
            font_size='48sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
            size_hint=(None, None),
            size=(100, 50),
            halign='left',
            valign='middle'
        )
        self.number_label.bind(size=self.number_label.setter('text_size'))
        top_row.add_widget(self.number_label)
        
        self.add_widget(top_row)
        
        # "Cups" and "Available" labels on separate lines - increased space
        self.availability_label = Label(
            text='Cups\nAvailable',  # Two lines for better visibility
            font_size='15sp',
            color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
            size_hint_y=0.5,  # Increased from 0.3 to 0.5 for more vertical space
            halign='left',
            valign='top',
            padding=(0, 0, 20, 0)  # Further reduced padding
        )
        self.availability_label.bind(size=self.availability_label.setter('text_size'))
        self.add_widget(self.availability_label)
    
    def set_cups_count(self, count):
        """Update the cups count"""
        self.is_loading = False
        self.cups_count = count
        self.number_label.text = str(count)
    
    def set_loading(self):
        """Set loading state"""
        self.is_loading = True
        self.number_label.text = '...'
    
    def set_error(self):
        """Set error state"""
        self.is_loading = False
        self.cups_count = 0
        self.number_label.text = '0'


class RFIDValidationPopup(Popup):
    """Modern popup for RFID validation results"""
    
    def __init__(self, validation_result, **kwargs):
        self.validation_result = validation_result
        
        # Create content layout
        content = FloatLayout()
        
        # Background with rounded corners
        with content.canvas.before:
            Color(0.95, 0.95, 0.95, 0.98)  # Light background
            self.bg_rect = RoundedRectangle(size=(500, 400), pos=(0, 0), radius=[25])
        
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
        
        # Determine if validation was successful (AES authentication format)
        is_authenticated = validation_result.get("authenticated", False) if validation_result else False
        is_dispensed = validation_result.get("dispensed", False) if validation_result else False
        
        # Main message based on validation result
        if not validation_result or not validation_result.get("success", False):
            # API call failed or authentication failed
            error_msg = validation_result.get("error", "Unknown error") if validation_result else "Connection failed"
            icon = "X"
            title = "Authentication Failed"
            message = f"{error_msg}\nPlease try again or contact support"
            color = (0.9, 0.3, 0.2, 1)  # Red
        elif not is_authenticated:
            # Authentication failed
            icon = "X"
            title = "Card Not Authenticated"
            message = "Card authentication failed\nPlease try again"
            color = (0.9, 0.3, 0.2, 1)  # Red
        elif not is_dispensed:
            # Authenticated but not dispensed (insufficient balance or other issue)
            icon = "$"
            title = "Cannot Dispense"
            remaining_balance = validation_result.get("remainingBalance", "0")
            message = f"Current Balance: ₹{remaining_balance}\nInsufficient balance or card issue\nPlease recharge your card"
            color = (0.9, 0.6, 0.2, 1)  # Orange
        else:
            # Authenticated and dispensed successfully
            icon = "✓"
            title = "Authentication Successful"
            remaining_balance = validation_result.get("remainingBalance", "0")
            message = f"Balance: ₹{remaining_balance}\nProceeding to dispensing..."
            color = (0.2, 0.7, 0.3, 1)  # Green
        
        # Icon and title
        icon_label = Label(
            text=icon,
            font_size='48sp',
            color=color,
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.8},
            size_hint=(None, None),
            size=(100, 60)
        )
        content.add_widget(icon_label)
        
        title_label = Label(
            text=title,
            font_size='24sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.65},
            size_hint=(None, None),
            size=(450, 40)
        )
        content.add_widget(title_label)
        
        # Message
        message_label = Label(
            text=message,
            font_size='18sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.4},
            size_hint=(None, None),
            size=(450, 120)
        )
        content.add_widget(message_label)
        
        # Card info if available
        if validation_result and validation_result.get("success", False):
            card_id = validation_result.get('cardId', 'N/A')
            location = validation_result.get('machineLocation', 'N/A')
            card_info = f"Card: {card_id}\nLocation: {location}"
            info_label = Label(
                text=card_info,
                font_size='14sp',
                color=(0.7, 0.7, 0.7, 1),
                halign='center',
                pos_hint={'center_x': 0.5, 'center_y': 0.15},
                size_hint=(None, None),
                size=(450, 60)
            )
            content.add_widget(info_label)
        
        super().__init__(
            title='',
            content=content,
            size_hint=(None, None),
            size=(500, 400),
            auto_dismiss=False,  # Prevent dismissing by clicking outside
            separator_height=0,  # Remove title separator
            **kwargs
        )
        
        # Update background rect when popup size changes
        content.bind(size=self.update_bg_rect, pos=self.update_bg_rect)
        
        # Auto-close for successful authentication or failed attempts
        if is_authenticated and is_dispensed:
            Clock.schedule_once(self.auto_close, 2)  # Auto-close after 2 seconds for success
        elif not validation_result or not validation_result.get("success", False) or not is_authenticated:
            Clock.schedule_once(self.auto_close, 2)  # Auto-close after 2 seconds for failed authentication
    
    def update_bg_rect(self, *args):
        """Update background rectangle size and position"""
        self.bg_rect.size = self.content.size
        self.bg_rect.pos = self.content.pos
    
    def auto_close(self, dt=None):
        """Auto-dismiss the popup"""
        self.dismiss()


class RFIDInstructionPopup(Popup):
    """Popup to show RFID card usage instruction"""
    
    def __init__(self, **kwargs):
        # Create content layout
        content = FloatLayout()
        
        # Background with rounded corners
        with content.canvas.before:
            Color(0.95, 0.95, 0.95, 0.98)  # Light background
            self.bg_rect = RoundedRectangle(size=(450, 280), pos=(0, 0), radius=[25])
        
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
        
        # Arrow mark image at top - larger and centered
        arrow_path = os.path.join('assets', 'arrowmark.png')
        if os.path.exists(arrow_path):
            arrow_image = Image(
                source=arrow_path,
                size_hint=(None, None),
                size=(100, 100),  # Larger size
                pos_hint={'center_x': 0.5, 'center_y': 0.75},  # Top center
                allow_stretch=True,
                keep_ratio=True
            )
            content.add_widget(arrow_image)
        else:
            # Fallback to arrow emoji if image not found
            icon_label = Label(
                text='---->',
                font_size='64sp',
                color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
                halign='center',
                pos_hint={'center_x': 0.5, 'center_y': 0.75},
                size_hint=(None, None),
                size=(100, 80)
            )
            content.add_widget(icon_label)
        
        # Main instruction text
        instruction_label = Label(
            text='Keep the card on reader',
            font_size='26sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.45},
            size_hint=(None, None),
            size=(400, 60)
        )
        content.add_widget(instruction_label)
        
        # Countdown timer label
        self.countdown_label = Label(
            text='Auto-closing in 3 seconds...',
            font_size='16sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.2},
            size_hint=(None, None),
            size=(300, 40)
        )
        content.add_widget(self.countdown_label)
        
        super().__init__(
            title='',
            content=content,
            size_hint=(None, None),
            size=(450, 280),
            auto_dismiss=False,
            separator_height=0,
            **kwargs
        )
        
        # Update background rect when popup size changes
        content.bind(size=self.update_bg_rect, pos=self.update_bg_rect)
        
        # Auto-close timer variables
        self.countdown_time = 3
        self.countdown_event = None
    
    def update_bg_rect(self, *args):
        """Update background rectangle size and position"""
        self.bg_rect.size = self.content.size
        self.bg_rect.pos = self.content.pos
    
    def open(self, *args):
        """Override open to start countdown"""
        super().open(*args)
        self.start_countdown()
    
    def start_countdown(self):
        """Start the 3-second countdown timer"""
        self.countdown_time = 3
        self.update_countdown_display()
        self.countdown_event = Clock.schedule_interval(self.update_countdown, 1)
    
    def update_countdown(self, dt):
        """Update countdown timer"""
        self.countdown_time -= 1
        if self.countdown_time <= 0:
            self.dismiss()
            return False  # Stop the timer
        else:
            self.update_countdown_display()
            return True  # Continue the timer
    
    def update_countdown_display(self):
        """Update the countdown display text"""
        self.countdown_label.text = f'Auto-closing in {self.countdown_time} seconds...'
    
    def dismiss(self, *args):
        """Override dismiss to clean up timers"""
        # Cancel countdown timer
        if self.countdown_event:
            self.countdown_event.cancel()
            self.countdown_event = None
        
        super().dismiss(*args)


class CupsAvailabilityPopup(Popup):
    """Modern popup for cups availability notification with auto-close"""
    
    def __init__(self, available_cups, **kwargs):
        self.available_cups = available_cups
        
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
        
        # Icon - using a cup symbol
        icon_label = Label(
            text="CUP",
            font_size='36sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.8},
            size_hint=(None, None),
            size=(100, 60)
        )
        content.add_widget(icon_label)
        
        # Title
        title_label = Label(
            text="Cups Available",
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
        if available_cups == 1:
            message_text = f"Only {available_cups} cup is available right now"
        else:
            message_text = f"Only {available_cups} cups are available right now"
            
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
        
        # Countdown timer label
        self.countdown_label = Label(
            text="Auto-closing in 2 seconds...",
            font_size='16sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.25},
            size_hint=(None, None),
            size=(300, 40)
        )
        content.add_widget(self.countdown_label)
        
        super().__init__(
            title='',
            content=content,
            size_hint=(None, None),
            size=(450, 300),
            auto_dismiss=False,  # Prevent dismissing by clicking outside
            separator_height=0,  # Remove title separator
            **kwargs
        )
        
        # Update background rect when popup size changes
        content.bind(size=self.update_bg_rect, pos=self.update_bg_rect)
        
        # Auto-close timer variables
        self.countdown_time = 2
        self.countdown_event = None
        
    def update_bg_rect(self, *args):
        """Update background rectangle size and position"""
        self.bg_rect.size = self.content.size
        self.bg_rect.pos = self.content.pos
    
    def open(self, *args):
        """Override open to start countdown"""
        super().open(*args)
        self.start_countdown()
    
    def start_countdown(self):
        """Start the 2-second countdown timer"""
        self.countdown_time = 2
        self.update_countdown_display()
        self.countdown_event = Clock.schedule_interval(self.update_countdown, 1)
    
    def update_countdown(self, dt):
        """Update countdown timer"""
        self.countdown_time -= 1
        if self.countdown_time <= 0:
            self.dismiss()
            return False  # Stop the timer
        else:
            self.update_countdown_display()
            return True  # Continue the timer
    
    def update_countdown_display(self):
        """Update the countdown display text"""
        self.countdown_label.text = f"Auto-closing in {self.countdown_time} seconds..."
    
    def dismiss(self, *args):
        """Override dismiss to clean up timers"""
        # Cancel countdown timer
        if self.countdown_event:
            self.countdown_event.cancel()
            self.countdown_event = None
        
        super().dismiss(*args)


class OfflinePopup(Popup):
    """Modern popup for machine offline status with auto-close and close button"""
    
    def __init__(self, **kwargs):
        # Create content layout
        content = FloatLayout()
        
        # Background with rounded corners
        with content.canvas.before:
            Color(0.95, 0.95, 0.95, 0.98)  # Light background
            self.bg_rect = RoundedRectangle(size=(450, 350), pos=(0, 0), radius=[25])
        
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
        
        # Main message
        main_label = Label(
            text="We'll be back soon!",
            font_size='32sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.75},
            size_hint=(None, None),
            size=(400, 60)
        )
        content.add_widget(main_label)
        
        # Sub message
        sub_label = Label(
            text="Refiller is on its way\nTry again after some time",
            font_size='20sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            size_hint=(None, None),
            size=(400, 80)
        )
        content.add_widget(sub_label)
        
        # Countdown timer label
        self.countdown_label = Label(
            text="Auto-closing in 10 seconds...",
            font_size='16sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.25},
            size_hint=(None, None),
            size=(300, 40)
        )
        content.add_widget(self.countdown_label)
        
        # Animated dots for loading effect
        self.dots_label = Label(
            text="●●●",
            font_size='24sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.1},
            size_hint=(None, None),
            size=(100, 40)
        )
        content.add_widget(self.dots_label)
        
        super().__init__(
            title='',
            content=content,
            size_hint=(None, None),
            size=(450, 350),
            auto_dismiss=False,  # Prevent dismissing by clicking outside
            separator_height=0,  # Remove title separator
            **kwargs
        )
        
        # Update background rect when popup size changes
        content.bind(size=self.update_bg_rect, pos=self.update_bg_rect)
        
        # Auto-close timer variables
        self.countdown_time = 10
        self.countdown_event = None
        self.dots_event = None
        
    def update_bg_rect(self, *args):
        """Update background rectangle size and position"""
        self.bg_rect.size = self.content.size
        self.bg_rect.pos = self.content.pos
    
    def open(self, *args):
        """Override open to start countdown and animations"""
        super().open(*args)
        self.start_countdown()
        self.animate_dots()
    
    def start_countdown(self):
        """Start the 10-second countdown timer"""
        self.countdown_time = 10
        self.update_countdown_display()
        self.countdown_event = Clock.schedule_interval(self.update_countdown, 1)
    
    def update_countdown(self, dt):
        """Update countdown timer"""
        self.countdown_time -= 1
        if self.countdown_time <= 0:
            self.dismiss()
            return False  # Stop the timer
        else:
            self.update_countdown_display()
            return True  # Continue the timer
    
    def update_countdown_display(self):
        """Update the countdown display text"""
        self.countdown_label.text = f"Auto-closing in {self.countdown_time} seconds..."
    
    def animate_dots(self):
        """Animate the loading dots"""
        def update_dots(dt):
            current_text = self.dots_label.text
            if current_text == "●●●":
                self.dots_label.text = "○●●"
            elif current_text == "○●●":
                self.dots_label.text = "○○●"
            elif current_text == "○○●":
                self.dots_label.text = "○○○"
            else:
                self.dots_label.text = "●●●"
        
        self.dots_event = Clock.schedule_interval(update_dots, 0.5)
    
    def dismiss(self, *args):
        """Override dismiss to clean up timers"""
        # Cancel countdown timer
        if self.countdown_event:
            self.countdown_event.cancel()
            self.countdown_event = None
        
        # Cancel dots animation
        if self.dots_event:
            self.dots_event.cancel()
            self.dots_event = None
        
        super().dismiss(*args)


class PaymentMethodPage(Screen):
    """Payment method selection page - UPI on left, RFID on right with center divider"""
    
    def __init__(self, **kwargs):
        super(PaymentMethodPage, self).__init__(**kwargs)
        
        # Initialize popup references
        self.offline_popup = None
        self.rfid_popup = None
        self.rfid_instruction_popup = None
        
        # RFID card detection variables
        self.rfid_listening = True
        self.last_rfid_scan_time = 0
        
        # Cups count refresh timer
        self.cups_refresh_timer = None
        self.cups_refresh_interval = 3  # Refresh every 3 seconds
        
        # Main layout with beige background
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Top bar with logo on left and cups counter on right
        top_bar = FloatLayout(size_hint_y=0.15)
        
        # Urban Kettle logo on the left side
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                pos_hint={'x': 0.0, 'top': 1.35},  # Moved to very top-left corner
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
        
        # Cups counter widget (absolute top-right corner) - increased height significantly
        self.cups_counter = CupsCounterWidget(
            size_hint=(None, None),
            size=(180, 110),  # Further increased height to 110
            pos_hint={'right': 0.98, 'top': 0.92}  # Adjusted top position
        )
        top_bar.add_widget(self.cups_counter)
        
        main_layout.add_widget(top_bar)
        
        # Reduced spacing since logo is now in top bar
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # Title centered
        title_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.08)
        title_label = Label(
            text='SELECT PAYMENT MODE',
            font_size='32sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            valign='center'
        )
        title_section.add_widget(title_label)
        
        main_layout.add_widget(title_section)
        
        # Spacing after welcome text
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # Main content area - horizontal layout with UPI left, RFID right (optimized for 7-inch)
        content_layout = BoxLayout(orientation='horizontal', size_hint_y=0.60, spacing=10, padding=[30, 0])
        
        # Left side - UPI section as clickable card
        from kivy.uix.button import ButtonBehavior
        
        # Create clickable UPI card container
        class ClickableCard(ButtonBehavior, AnchorLayout):
            pass
        
        upi_card_container = ClickableCard(anchor_x='center', anchor_y='center', size_hint_x=0.45)
        upi_card_container.bind(on_press=self.on_upi_selected)
        
        # Create premium UPI card background (reduced size)
        upi_card = PremiumPaymentCard(card_type='upi', size_hint=(0.75, 0.75))
        upi_card_container.add_widget(upi_card)
        
        # UPI content on top of card
        upi_section = BoxLayout(orientation='vertical', size_hint=(0.75, 0.8))
        
        # Top spacing
        upi_section.add_widget(Widget(size_hint_y=0.2))
        
        # UPI icon/image section
        upi_image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.5)

        upi_image_path = os.path.join('assets', 'upilogo3.png')

        if os.path.exists(upi_image_path):
            upi_image = Image(
                source=upi_image_path,
                size_hint=(None, None),
                size=(200, 150),
                allow_stretch=True,
                keep_ratio=True
            )
            upi_image_section.add_widget(upi_image)
        else:
            fallback_label = Label(
                text='UPI',
                font_size='48sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='center'
            )
            upi_image_section.add_widget(fallback_label)

        upi_section.add_widget(upi_image_section)
        
        # UPI text label
        upi_text = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.2)
        upi_text_label = Label(
            text='',
            font_size='36sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center'
        )
        upi_text.add_widget(upi_text_label)
        upi_section.add_widget(upi_text)
        
        # Bottom spacing
        upi_section.add_widget(Widget(size_hint_y=0.1))
        
        upi_card_container.add_widget(upi_section)
        content_layout.add_widget(upi_card_container)
        
        # Reduced spacing between cards
        content_layout.add_widget(Widget(size_hint_x=0.05))
        
        # Right side - RFID section (keeps RFID listening functionality)
        # Create clickable RFID card container
        class ClickableRFIDCard(ButtonBehavior, AnchorLayout):
            pass
        
        rfid_card_container = ClickableRFIDCard(anchor_x='center', anchor_y='center', size_hint_x=0.45)
        rfid_card_container.bind(on_press=self.on_rfid_clicked)
        
        # Create premium RFID card background (reduced size)
        rfid_card = PremiumPaymentCard(card_type='rfid', size_hint=(0.75, 0.75))
        rfid_card_container.add_widget(rfid_card)
        
        # RFID content on top of card
        rfid_section = BoxLayout(orientation='vertical', size_hint=(0.75, 0.8))
        
        # Top spacing
        rfid_section.add_widget(Widget(size_hint_y=0.2))
        
        # RFID image section
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.5)
        
        rfid_image_path = os.path.join('assets', 'rfidlogo2.png')
        
        if os.path.exists(rfid_image_path):
            rfid_image = Image(
                source=rfid_image_path,
                size_hint=(None, None),
                size=(250, 200),
                allow_stretch=True,
                keep_ratio=True
            )
            image_section.add_widget(rfid_image)
        else:
            fallback_label = Label(
                text='RFID',
                font_size='48sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='center'
            )
            image_section.add_widget(fallback_label)
        
        rfid_section.add_widget(image_section)
        
        # RFID text label
        rfid_text = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.15)
        rfid_text_label = Label(
            text='',
            font_size='36sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center'
        )
        rfid_text.add_widget(rfid_text_label)
        rfid_section.add_widget(rfid_text)
        
        # "one cup per tap" subtitle
        tap_info = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.1)
        tap_info_label = Label(
            text='',
            font_size='26sp',
            color=(0.5, 0.5, 0.5, 1),  # Gray color
            halign='center',
            italic=True
        )
        tap_info.add_widget(tap_info_label)
        rfid_section.add_widget(tap_info)
        
        # Bottom spacing
        rfid_section.add_widget(Widget(size_hint_y=0.05))
        
        rfid_card_container.add_widget(rfid_section)
        content_layout.add_widget(rfid_card_container)
        
        main_layout.add_widget(content_layout)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.10))
        
        self.add_widget(main_layout)
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def open_debug_page(self, instance):
        """Open hardware debug page"""
        self.manager.current = 'hardware_debug'
    
    def on_upi_selected(self, instance):
        """Navigate to selection page using cached cups count (no API calls needed)"""
        # Use the cached cups count from the continuously refreshed counter
        if hasattr(self, 'cups_counter') and hasattr(self.cups_counter, 'cups_count'):
            cups_count = self.cups_counter.cups_count
            
            # Check if loading state
            if self.cups_counter.is_loading:
                print("Cups data still loading, please wait...")
                return
            
            if cups_count <= 0:
                print(f"No cups available ({cups_count}), ignoring click - will auto-navigate to machine empty page")
                # Don't show popup - background refresh will handle navigation to machine empty page
                return
            else:
                print(f"Cups available ({cups_count}), navigating to selection page")
                # Pass the available cups count to selection page
                from kivy.app import App
                app = App.get_running_app()
                app.selection_page.set_max_cups(cups_count)
                
                # Navigate to selection page
                self.navigate_to_selection()
        else:
            # Fallback - just ignore if cups counter not available
            print("Cups counter not available, ignoring click")
            return
    
    def navigate_to_selection(self):
        """Navigate to selection page"""
        self.manager.current = 'selection'
    
    def on_rfid_clicked(self, instance):
        """Show instruction popup when RFID card is clicked"""
        print("RFID card clicked - showing instruction popup")
        
        # Close any existing instruction popup
        if self.rfid_instruction_popup and self.rfid_instruction_popup._window:
            self.rfid_instruction_popup.dismiss()
        
        # Create and show new instruction popup
        self.rfid_instruction_popup = RFIDInstructionPopup()
        self.rfid_instruction_popup.open()
    
    def show_offline_popup(self):
        """Show offline popup"""
        # Create and show offline popup
        if not self.offline_popup or not self.offline_popup._window:
            self.offline_popup = OfflinePopup()
        
        self.offline_popup.open()
    
    def on_rfid_tap(self):
        """Handle RFID tap (to be implemented later)"""
        # For now, just print - will implement RFID logic later
        print("RFID tapped - functionality to be implemented")
    
    def check_machine_availability(self):
        """Check machine status and cups count before showing page"""
        from kivy.app import App
        app = App.get_running_app()
        
        try:
            # Set loading state
            Clock.schedule_once(lambda dt: self.cups_counter.set_loading())
            
            # Check machine status first
            if hasattr(app, 'api_client') and hasattr(app, 'MACHINE_ID'):
                # Check machine status
                status_data = app.api_client.check_machine_status(app.MACHINE_ID)
                
                if status_data and status_data.get("success", False):
                    # Get status from nested data object
                    data = status_data.get("data", {})
                    machine_status = data.get("status", "offline")
                    is_online = machine_status.lower() == "online"
                    
                    print(f"Machine status: {machine_status}, is_online: {is_online}")
                    
                    if not is_online:
                        # Machine is offline - navigate to machine empty page
                        print("Machine is offline, navigating to machine empty page")
                        Clock.schedule_once(lambda dt: self.navigate_to_machine_empty(), 0.5)
                        return
                
                # Check cups count
                cups_data = app.api_client.get_remaining_cups(app.MACHINE_ID)
                
                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    Clock.schedule_once(lambda dt: self.update_cups_display(cups_count))
                    
                    if cups_count <= 0:
                        # No cups available - navigate to machine empty page
                        print("No cups available, navigating to machine empty page")
                        Clock.schedule_once(lambda dt: self.navigate_to_machine_empty(), 0.5)
                        return
                    
                    # Machine is online and has cups - start periodic refresh
                    Clock.schedule_once(lambda dt: self.start_cups_refresh_timer())
                else:
                    # API call failed - show error
                    Clock.schedule_once(lambda dt: self.cups_counter.set_error())
            else:
                # No API client - show error
                Clock.schedule_once(lambda dt: self.cups_counter.set_error())
                
        except Exception as e:
            print(f"Error checking machine availability: {e}")
            Clock.schedule_once(lambda dt: self.cups_counter.set_error())
    
    def load_cups_count(self, show_loading=False):
        """Load cups count from API"""
        # Only set loading state if explicitly requested (initial load)
        if show_loading:
            self.cups_counter.set_loading()
        
        # Load cups count in a separate thread
        threading.Thread(target=self.fetch_cups_count, daemon=True).start()
    
    def fetch_cups_count(self):
        """Fetch cups count from API in background thread"""
        from kivy.app import App
        app = App.get_running_app()
        
        try:
            # Call API to get remaining cups and check machine status
            if hasattr(app, 'api_client') and hasattr(app, 'MACHINE_ID'):
                # Check machine status first
                status_data = app.api_client.check_machine_status(app.MACHINE_ID)
                
                if status_data and status_data.get("success", False):
                    # Get status from nested data object
                    data = status_data.get("data", {})
                    machine_status = data.get("status", "offline")
                    is_online = machine_status.lower() == "online"
                    
                    if not is_online:
                        # Machine is offline - navigate to machine empty page
                        print("Machine went offline, navigating to machine empty page")
                        Clock.schedule_once(lambda dt: self.navigate_to_machine_empty(), 0.5)
                        return
                
                # Get cups count
                cups_data = app.api_client.get_remaining_cups(app.MACHINE_ID)
                
                # Schedule UI update on main thread
                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    Clock.schedule_once(lambda dt: self.update_cups_display(cups_count))
                else:
                    # API call failed - show error
                    Clock.schedule_once(lambda dt: self.cups_counter.set_error())
            else:
                # No API client - show error
                Clock.schedule_once(lambda dt: self.cups_counter.set_error())
                
        except Exception as e:
            print(f"Error fetching cups count: {e}")
            # On error, show error state
            Clock.schedule_once(lambda dt: self.cups_counter.set_error())
    
    def update_cups_display(self, cups_count):
        """Update the cups counter display"""
        self.cups_counter.set_cups_count(cups_count)
        
        # If cups count is 0, navigate to machine empty page
        if cups_count <= 0:
            print("Machine is empty (0 cups), navigating to machine empty page")
            Clock.schedule_once(lambda dt: self.navigate_to_machine_empty(), 0.5)
    
    def refresh_cups_count(self):
        """Refresh cups count (can be called from other parts of the app)"""
        self.load_cups_count()
    
    def start_cups_refresh_timer(self):
        """Start periodic timer to refresh cups count every 5 seconds"""
        # Stop any existing timer first
        self.stop_cups_refresh_timer()
        
        # Schedule periodic refresh
        self.cups_refresh_timer = Clock.schedule_interval(
            lambda dt: self.load_cups_count(), 
            self.cups_refresh_interval
        )
        print(f"Started cups count refresh timer (every {self.cups_refresh_interval} seconds)")
    
    def stop_cups_refresh_timer(self):
        """Stop the periodic cups count refresh timer"""
        if self.cups_refresh_timer:
            self.cups_refresh_timer.cancel()
            self.cups_refresh_timer = None
            print("Stopped cups count refresh timer")
    
    def handle_rfid_card_detected(self, card_uid):
        """Handle RFID card detection from ACR122U reader"""
        print(f"🏷️ Processing RFID Card UID: {card_uid}")
        
        # Only process if we're listening and on the payment method page
        if not self.rfid_listening:
            print("🏷️ RFID listening disabled, ignoring card")
            return
        
        # Check for 5-second cooldown to prevent multiple taps
        current_time = time.time()
        if current_time - self.last_rfid_scan_time < 5:
            print(f"🏷️ RFID cooldown active, ignoring card (last scan: {current_time - self.last_rfid_scan_time:.1f}s ago)")
            return
        
        # Update last scan time
        self.last_rfid_scan_time = current_time
        
        # Check if cups count is 0 (machine effectively offline)
        if hasattr(self, 'cups_counter') and hasattr(self.cups_counter, 'cups_count'):
            if self.cups_counter.cups_count <= 0:
                print("No cups remaining, showing offline popup")
                Clock.schedule_once(lambda dt: self.show_offline_popup_for_rfid())
                return
        
        # Disable RFID listening and STOP POLLING to prevent interference
        self.rfid_listening = False
        self.stop_rfid_polling()
        print("🏷️ Stopped polling for authentication")
        
        # Re-enable RFID listening and restart polling after 5 seconds
        Clock.schedule_once(lambda dt: self.restart_rfid_after_auth(), 5)
        
        # Check machine status first, then authenticate card
        threading.Thread(target=self.authenticate_rfid_card, daemon=True).start()
    
    def restart_rfid_after_auth(self):
        """Restart RFID polling after authentication attempt"""
        self.rfid_listening = True
        self.start_rfid_polling()
        print("🏷️ Restarted RFID polling")
    
    def authenticate_rfid_card(self):
        """Authenticate RFID card using AES authentication (card already read)"""
        from kivy.app import App
        app = App.get_running_app()
        
        try:
            if hasattr(app, 'api_client') and hasattr(app, 'MACHINE_ID'):
                # Show RFID auth page
                Clock.schedule_once(lambda dt: app.show_page('rfid_auth'))
                Clock.schedule_once(lambda dt: app.rfid_auth_page.start_auth())
                
                # Skip machine status check - already verified when page loaded
                # This saves ~0.5s per authentication
                
                # Perform AES authentication directly
                print("🔐 Starting AES authentication...")
                
                # Update to step 2
                Clock.schedule_once(lambda dt: app.rfid_auth_page.update_step(2, "Authenticating..."), 0.1)
                
                # Perform AES authentication (card UID already read in handle_rfid_card_detected)
                validation_result = app.api_client.validate_rfid_card_aes(app.rfid_auth_handler)
                
                # Update to step 3
                Clock.schedule_once(lambda dt: app.rfid_auth_page.update_step(3, "Verifying..."))
                
                # Process validation result
                Clock.schedule_once(lambda dt: self.handle_rfid_validation_result(validation_result))
            else:
                # No API client - show offline
                Clock.schedule_once(lambda dt: self.show_offline_popup_for_rfid())
                Clock.schedule_once(lambda dt: self.restart_rfid_after_auth(), 3)
                
        except Exception as e:
            print(f"Error authenticating RFID card: {e}")
            # On error, show error on auth page
            Clock.schedule_once(lambda dt: app.rfid_auth_page.show_error(str(e)))
            Clock.schedule_once(lambda dt: self.restart_rfid_after_auth(), 3)
            Clock.schedule_once(lambda dt: app.show_page('payment_method'), 3)
    
    def handle_rfid_validation_result(self, validation_result):
        """Handle RFID validation result and show appropriate popup"""
        from kivy.app import App
        app = App.get_running_app()
        
        # Check for maintenance card
        if validation_result and validation_result.get("cardCategory") == "maintenance":
            # Maintenance card detected
            print("🔧 Maintenance Card Detected")
            print(f"   Action: {validation_result.get('action')}")
            print(f"   Message: {validation_result.get('message')}")
            print(f"   Duration: {validation_result.get('duration')} seconds")
            
            # Show maintenance message on auth page
            app.rfid_auth_page.show_success("Maintenance")
            app.rfid_auth_page.step_label.text = validation_result.get('message', 'Maintenance mode activated')
            
            # Get duration from validation result (in seconds), convert to milliseconds
            # Default to 10 seconds if not specified
            duration_seconds = validation_result.get('duration', 10)
            duration_ms = int(duration_seconds * 1000)
            
            # Send solenoid control command in background thread
            def send_command():
                self.send_maintenance_solenoid_command(duration_ms)
            
            threading.Thread(target=send_command, daemon=True).start()
            
            # Return to payment method page after 3 seconds
            Clock.schedule_once(lambda dt: self.restart_rfid_after_auth(), 3)
            Clock.schedule_once(lambda dt: app.show_page('payment_method'), 3)
            return
        
        # Check if authentication was successful and dispensed (regular dispensing card)
        if validation_result and validation_result.get("success", False) and validation_result.get("authenticated", False) and validation_result.get("dispensed", False):
            # Authentication successful
            print("✅ AES Authentication successful - proceeding to dispensing")
            print(f"   Card: {validation_result.get('cardId')}")
            print(f"   Balance: ₹{validation_result.get('remainingBalance')}")
            print(f"   Location: {validation_result.get('machineLocation')}")
            
            # Show success on auth page
            balance = validation_result.get('remainingBalance', '0')
            app.rfid_auth_page.show_success(balance)
            
            # Set default cup count for RFID payment (1 cup)
            app.set_selected_cups(1)
            
            # Reduce cups count for RFID payment
            app.reduce_cups_after_payment()
            
            # Navigate to dispensing after showing success
            Clock.schedule_once(lambda dt: self.navigate_to_dispensing(), 1.5)
        else:
            # Authentication failed - determine specific error message
            print("❌ AES Authentication failed")
            
            # Default error message
            error_msg = "Card is not valid\nPlease contact your admin"
            
            if validation_result:
                error = validation_result.get('error', '').lower()
                print(f"   Error: {error}")
                
                # Check for specific error types
                if 'insufficient' in error or 'low balance' in error or 'balance' in error:
                    # Low balance
                    error_msg = "Low balance\nPlease contact your admin"
                elif 'removed' in error or 'card was removed' in error:
                    # Card removed during authentication
                    error_msg = "Card removed\nPlease keep the card until\nauthentication is done"
                # All other errors (authentication, not found, etc.) show "card not valid"
            
            # Show error on auth page
            app.rfid_auth_page.show_error(error_msg)
            
            # Re-enable RFID and return to payment method page
            Clock.schedule_once(lambda dt: self.restart_rfid_after_auth(), 3)
            Clock.schedule_once(lambda dt: app.show_page('payment_method'), 3)
    
    def navigate_to_dispensing(self):
        """Navigate directly to dispensing for RFID payment"""
        from kivy.app import App
        app = App.get_running_app()
        
        # Show transaction processing first, then dispensing
        app.show_transaction_processing_page()
        Clock.schedule_once(lambda dt: app.show_dispensing_page(), 4)
    
    def send_maintenance_solenoid_command(self, duration_ms=10000):
        """Send solenoid control command for maintenance card"""
        try:
            print("\n" + "="*80)
            print("🔧 SOLENOID COMMAND - MAINTENANCE MODE")
            print("="*80)
            print(f"🔧 Duration: {duration_ms}ms ({duration_ms/1000}s)")
            print(f"🔧 Command ID: cmd_solenoid_001")
            print(f"🔧 Device ID: UK_14335C5D48C8")
            
            # API endpoint (using localhost for testing)
            # TODO: Change to dynamic IP later for production
            url = "http://localhost:5000/api/device/command"
            
            # Device ID (hardcoded as per requirement)
            device_id = "UK_14335C5D48C8"
            
            # Prepare the request payload
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": "cmd_solenoid_001",
                "deviceId": device_id,
                "command": {
                    "action": "open_solenoid",
                    "parameters": {
                        "duration": duration_ms
                    }
                }
            }
            
            print(f"🔧 API Endpoint: {url}")
            print(f"🔧 Payload:")
            import json
            print(json.dumps(payload, indent=2))
            print("="*80)
            print("⏳ Sending request to polling server...")
            print("="*80)
            
            # Send POST request with longer timeout for ESP32 response
            response = requests.post(url, json=payload, timeout=30)
            
            print("="*80)
            print("📥 RESPONSE RECEIVED")
            print("="*80)
            print(f"✓ Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Response JSON:")
                print(json.dumps(result, indent=2))
                
                status = result.get('response', {}).get('status')
                pump_state = result.get('response', {}).get('data', {}).get('pumpState')
                
                print(f"\n✅ SOLENOID COMMAND SUCCESSFUL!")
                print(f"   Response Status: {status}")
                print(f"   Pump State: {pump_state}")
                print(f"   Command ID: {result.get('commandId')}")
                print("="*80 + "\n")
                
                return True
            else:
                print(f"❌ SOLENOID COMMAND FAILED")
                print(f"   Status Code: {response.status_code}")
                print(f"   Response: {response.text}")
                print("="*80 + "\n")
                return False
                
        except Exception as e:
            print("="*80)
            print(f"❌ ERROR SENDING SOLENOID COMMAND")
            print("="*80)
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            print("="*80 + "\n")
            return False
    
    def navigate_to_machine_empty(self):
        """Navigate to machine empty page when cups are 0"""
        self.manager.current = 'machine_empty'
    
    def show_offline_popup_for_rfid(self):
        """Show offline popup for RFID"""
        if not self.offline_popup or not self.offline_popup._window:
            self.offline_popup = OfflinePopup()
        
        self.offline_popup.open()
    
    def re_enable_rfid_listening(self):
        """Re-enable RFID listening after error or failed validation"""
        if hasattr(self, 'rfid_listening'):
            self.rfid_listening = True
            print("🏷️ RFID listening re-enabled")
    
    def on_enter(self):
        """Called when the screen is displayed"""
        # Check machine status and cups count before showing page
        threading.Thread(target=self.check_machine_availability, daemon=True).start()
        
        # Enable RFID listening
        self.rfid_listening = True
        
        # Initialize AES auth handler if not already done
        from kivy.app import App
        app = App.get_running_app()
        if not hasattr(app, 'rfid_auth_handler'):
            print("🔐 Initializing RFID AES Auth Handler...")
            from utils.rfid_aes_auth import RFIDAESAuth
            app.rfid_auth_handler = RFIDAESAuth(
                base_url="https://www.ukteawallet.com",
                machine_id="UK_0007"
            )
            if app.rfid_auth_handler.reader_active:
                print("✓ RFID Auth Handler initialized successfully")
            else:
                print("❌ RFID Auth Handler initialization failed - reader not active")
        else:
            print("✓ RFID Auth Handler already initialized")
        
        # Start polling for RFID cards
        self.start_rfid_polling()
    
    def on_leave(self):
        """Called when leaving the screen"""
        # Stop periodic cups count refresh
        self.stop_cups_refresh_timer()
        
        # Disable RFID listening
        self.rfid_listening = False
        
        # Stop RFID polling
        self.stop_rfid_polling()
    
    def start_rfid_polling(self):
        """Start polling for RFID cards"""
        if not hasattr(self, 'rfid_poll_event') or self.rfid_poll_event is None:
            self._checking_card = False
            # Poll every 0.5 seconds
            self.rfid_poll_event = Clock.schedule_interval(self.poll_for_rfid_card, 0.5)
            print("🏷️ Started RFID card polling (every 0.5s)")
            print("🏷️ Place your card on the reader...")
    
    def stop_rfid_polling(self):
        """Stop polling for RFID cards"""
        if hasattr(self, 'rfid_poll_event') and self.rfid_poll_event:
            self.rfid_poll_event.cancel()
            self.rfid_poll_event = None
            print("🏷️ Stopped RFID card polling")
    
    def poll_for_rfid_card(self, dt):
        """Poll for RFID card presence"""
        if not self.rfid_listening:
            return
        
        # Check if already checking for card
        if hasattr(self, '_checking_card') and self._checking_card:
            return
        
        # Run card detection in background thread
        self._checking_card = True
        threading.Thread(target=self.check_for_card, daemon=True).start()
    
    def check_for_card(self):
        """Check if a card is present and read its UID"""
        from kivy.app import App
        app = App.get_running_app()
        
        try:
            if not hasattr(app, 'rfid_auth_handler'):
                print("⚠️ RFID auth handler not initialized")
                return
            
            # Try to read card UID
            card_uid = app.rfid_auth_handler.get_card_uid()
            
            # Track last detected UID to only trigger on new card
            if not hasattr(self, '_last_detected_uid'):
                self._last_detected_uid = None
            
            if card_uid and card_uid != self._last_detected_uid:
                # New card detected
                print(f"🏷️ New card detected in polling: {card_uid}")
                self._last_detected_uid = card_uid
                # Card detected, process it on main thread
                Clock.schedule_once(lambda dt: self.handle_rfid_card_detected(card_uid), 0)
            elif not card_uid and self._last_detected_uid:
                # Card removed
                print(f"🏷️ Card removed: {self._last_detected_uid}")
                self._last_detected_uid = None
        except Exception as e:
            # Log errors for debugging
            print(f"⚠️ Error checking for card: {e}")
        finally:
            self._checking_card = False

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.clock import Clock
import threading
import time
import os
from utils.api_client import get_localhost_session



class ClickableImage(ButtonBehavior, Image):
    """Image widget that behaves like a button"""
    pass


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
            text='x',
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
            text='Auto-closing in 2 seconds...',
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
        self.countdown_label.text = f'Auto-closing in {self.countdown_time} seconds...'
    
    def dismiss(self, *args, **kwargs):
        """Override dismiss to clean up timers"""
        # Cancel countdown timer
        if self.countdown_event:
            self.countdown_event.cancel()
            self.countdown_event = None
        
        # Call parent dismiss without arguments
        super().dismiss()


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
        
        # Machine status monitoring
        self.status_check_timer = None
        self.status_check_interval = 3  # Check every 3 seconds
        
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
            logo_image = ClickableImage(
                source=logo_path,
                size_hint=(None, None),
                size=(220, 100),
                pos_hint={'x': 0.02, 'top': 0.95},
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
        
        # Create clickable UPI card container with explicit touch handling
        class ClickableCard(ButtonBehavior, AnchorLayout):
            def on_touch_down(self, touch):
                # Only handle touch if it's within the actual card bounds (first child)
                if not self.collide_point(*touch.pos):
                    return False
                
                # Check if touch is within the card widget itself (not just container)
                if self.children:
                    # Get the card widget (PremiumPaymentCard is the first child)
                    for child in self.children:
                        if hasattr(child, '__class__') and 'PremiumPaymentCard' in child.__class__.__name__:
                            if not child.collide_point(*touch.pos):
                                return False  # Touch is outside the actual card
                            break
                
                # Ensure touch is processed only by this button
                touch.grab(self)
                return super(ClickableCard, self).on_touch_down(touch)
            
            def on_touch_up(self, touch):
                # Only handle release if this widget grabbed the touch
                if touch.grab_current is not self:
                    return False
                touch.ungrab(self)
                return super(ClickableCard, self).on_touch_up(touch)
        
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
        # Create clickable RFID card container with explicit touch handling
        class ClickableRFIDCard(ButtonBehavior, AnchorLayout):
            def on_touch_down(self, touch):
                # Only handle touch if it's within the actual card bounds
                if not self.collide_point(*touch.pos):
                    return False
                
                # Check if touch is within the card widget itself (not just container)
                if self.children:
                    # Get the card widget (PremiumPaymentCard is the first child)
                    for child in self.children:
                        if hasattr(child, '__class__') and 'PremiumPaymentCard' in child.__class__.__name__:
                            if not child.collide_point(*touch.pos):
                                return False  # Touch is outside the actual card
                            break
                
                # Ensure touch is processed only by this button
                touch.grab(self)
                return super(ClickableRFIDCard, self).on_touch_down(touch)
            
            def on_touch_up(self, touch):
                # Only handle release if this widget grabbed the touch
                if touch.grab_current is not self:
                    return False
                touch.ungrab(self)
                return super(ClickableRFIDCard, self).on_touch_up(touch)
        
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
    
    
    def on_upi_selected(self, instance):
        """Navigate to selection page using cached cups count (no API calls needed)"""
        print(f"🔵 DEBUG: UPI button pressed! Instance: {instance}")
        # Use the cached cups count from the continuously refreshed counter
        if hasattr(self, 'cups_counter') and hasattr(self.cups_counter, 'cups_count'):
            cups_count = self.cups_counter.cups_count
            
            # Check if loading state
            if self.cups_counter.is_loading:
                print("Cups data still loading, please wait...")
                return
            
            from config import MACHINE_EMPTY_THRESHOLD
            if cups_count <= MACHINE_EMPTY_THRESHOLD:
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

                # Prefetch 1-cup QR while user is on selection page (Disabled for Option A)
                # app.trigger_qr_prefetch(1)
        else:
            # Fallback - just ignore if cups counter not available
            print("Cups counter not available, ignoring click")
            return
    
    def navigate_to_selection(self):
        """Navigate to selection page"""
        self.manager.current = 'selection'
    
    def on_rfid_clicked(self, instance):
        """Show instruction popup when RFID card is clicked"""
        print(f"🟠 DEBUG: RFID button pressed! Instance: {instance}")
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
            # Use local cups count only when it's above the empty threshold — a
            # local count at/below the threshold is stale from the previous dispense
            # and must be verified with the API before showing machine_empty (the
            # machine may have been refilled).
            from config import MACHINE_EMPTY_THRESHOLD
            if hasattr(app, 'cups_count_initialized') and app.cups_count_initialized and hasattr(app, 'local_cups_count') and app.local_cups_count is not None:
                if app.local_cups_count > MACHINE_EMPTY_THRESHOLD:
                    print(f"✅ Using local cups count: {app.local_cups_count}")
                    Clock.schedule_once(lambda dt: self.update_cups_display(app.local_cups_count))
                    return
                # local count is at/below the threshold — fall through to API to confirm before navigating
                print(f"⚠️ Local count is {app.local_cups_count} (<= {MACHINE_EMPTY_THRESHOLD}), verifying with API before showing machine_empty...")
            
            # Verify cups count via API (local is 0 or not yet initialized).
            # Machine "online/offline" status is NOT checked here — a transient cloud
            # status blip must not show machine_empty. Only a confirmed 0 cups count
            # from the API is authoritative. Machine offline is handled separately by
            # the global status monitor in main_app.py (consecutive-check guard).
            print("🔄 Verifying cups count via API...")
            Clock.schedule_once(lambda dt: self.cups_counter.set_loading())

            if hasattr(app, 'api_client') and hasattr(app, 'MACHINE_ID'):
                cups_data = app.api_client.get_remaining_cups(app.MACHINE_ID)

                if cups_data and cups_data.get("success", False):
                    cups_count = cups_data.get("cups", 0)
                    print(f"✅ API cups count: {cups_count}")
                    Clock.schedule_once(lambda dt: app.set_local_cups_count(cups_count))
                    Clock.schedule_once(lambda dt: self.update_cups_display(cups_count))

                    if cups_count <= MACHINE_EMPTY_THRESHOLD:
                        # Only navigate to machine_empty if the local counter was already
                        # initialised and at/below the threshold (i.e. we previously
                        # decremented down via a real dispense).  If local was never
                        # initialised (startup DNS failure, first boot) the cloud might
                        # be returning stale/wrong data — be conservative and just show
                        # an error indicator instead.
                        if app.cups_count_initialized:
                            print(f"No cups available (API confirmed cups={cups_count}, local was initialised), navigating to machine empty page")
                            Clock.schedule_once(lambda dt: self.navigate_to_machine_empty(), 0.5)
                        else:
                            print(f"⚠️ API returned cups={cups_count} but local was never initialised — showing error (not machine_empty)")
                            Clock.schedule_once(lambda dt: self.cups_counter.set_error())
                else:
                    # API call failed — don't navigate, just show error indicator
                    Clock.schedule_once(lambda dt: self.cups_counter.set_error())
            else:
                Clock.schedule_once(lambda dt: self.cups_counter.set_error())
                
        except Exception as e:
            print(f"Error checking machine availability: {e}")
            Clock.schedule_once(lambda dt: self.cups_counter.set_error())
    
    def load_cups_count(self, show_loading=False):
        """Load cups count - now uses local counter instead of API"""
        from kivy.app import App
        app = App.get_running_app()
        
        # Use local cups count if available
        if hasattr(app, 'local_cups_count') and app.local_cups_count is not None:
            self.update_cups_display(app.local_cups_count)
        else:
            print("⚠️ Local cups count not available")
    
    def fetch_cups_count(self):
        """Deprecated - now uses local counter. Use app.get_local_cups_count() instead"""
        from kivy.app import App
        app = App.get_running_app()
        
        # Use local cups count
        if hasattr(app, 'local_cups_count') and app.local_cups_count is not None:
            Clock.schedule_once(lambda dt: self.update_cups_display(app.local_cups_count))
        else:
            Clock.schedule_once(lambda dt: self.cups_counter.set_error())
    
    def update_cups_display(self, cups_count):
        """Update the cups counter display"""
        self.cups_counter.set_cups_count(cups_count)
            
    def refresh_cups_count(self):
        """Refresh cups count display using local counter"""
        from kivy.app import App
        app = App.get_running_app()
        
        # Use local cups count if available
        if hasattr(app, 'local_cups_count') and app.local_cups_count is not None:
            self.update_cups_display(app.local_cups_count)
        else:
            print("⚠️ Local cups count not available")
    
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
        
        # Check for 3-second cooldown to prevent multiple taps (reduced from 5)
        current_time = time.time()
        if current_time - self.last_rfid_scan_time < 3:
            print(f"🏷️ RFID cooldown active, ignoring card (last scan: {current_time - self.last_rfid_scan_time:.1f}s ago)")
            return
        
        # Update last scan time
        self.last_rfid_scan_time = current_time
        
        # Check if cups count is at/below the empty threshold (machine effectively offline).
        # Use app.local_cups_count — cups_counter may be stale if this page was never entered.
        from kivy.app import App as _App
        from config import MACHINE_EMPTY_THRESHOLD
        _app = _App.get_running_app()
        _local_cups = getattr(_app, 'local_cups_count', None)
        if _local_cups is not None and _local_cups <= MACHINE_EMPTY_THRESHOLD:
            print("No cups remaining, showing offline popup")
            Clock.schedule_once(lambda dt: self.show_offline_popup_for_rfid())
            return
        
        # Disable RFID listening and STOP POLLING to prevent interference
        self.rfid_listening = False
        self.stop_rfid_polling()
        print("🏷️ Stopped polling for authentication")
        
        # Schedule restart in case of failure (will be cancelled if successful)
        # Re-enable RFID listening and restart polling after 3 seconds (reduced from 5)
        self.restart_rfid_event = Clock.schedule_once(lambda dt: self.restart_rfid_after_auth(), 3)
        
        # Check machine status first, then authenticate card
        threading.Thread(target=self.authenticate_rfid_card, daemon=True).start()
    
    def restart_rfid_after_auth(self):
        """Restart RFID polling after authentication attempt"""
        from kivy.app import App
        app = App.get_running_app()
        # Restart on any home-equivalent screen (selection is the new home)
        current = app.screen_manager.current if app else None
        if current not in ('payment_method', 'selection'):
            print(f"🏷️ RFID restart skipped — no longer on home page (current: {current})")
            return
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
                # restart_rfid_event (set in handle_rfid_card_detected) already handles restart

        except Exception as e:
            print(f"Error authenticating RFID card: {e}")
            Clock.schedule_once(lambda dt: app.rfid_auth_page.show_error(str(e)))
            Clock.schedule_once(lambda dt: app.show_payment_method_page(), 3)
            # restart_rfid_event (set in handle_rfid_card_detected) already handles restart
    
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
            Clock.schedule_once(lambda dt: app.show_payment_method_page(), 3)
            return
        
        # Check if authentication was successful (regular dispensing card).
        # 'dispensed' is a server-side billing flag \u2014 do NOT gate on it.
        # The machine controls the physical dispense; we only need the server
        # to confirm the card is valid (success=True) and authenticated (authenticated=True).
        if validation_result and validation_result.get("success", False) and validation_result.get("authenticated", False):
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
            
            # DON'T reduce cups here - cups will be reduced when user clicks "Confirm to Dispense" button
            # Cups reduction happens in place_cup_page.py -> on_continue_pressed() -> app.reduce_one_cup()
            
            # IMPORTANT: Cancel scheduled restart since authentication succeeded
            if hasattr(self, 'restart_rfid_event') and self.restart_rfid_event:
                self.restart_rfid_event.cancel()
                self.restart_rfid_event = None
                print("🏷️ Cancelled RFID restart - authentication successful")
            
            # Keep RFID disabled - user is proceeding to dispensing
            # Polling will be stopped by on_leave() when navigating away

            # Check temperature before dispensing — same guard the UPI flow has
            # (selection_page._check_temp_before_qr). Without this, an RFID
            # customer could be sent straight to place_cup/dispensing on cold
            # water with no heating page ever shown.
            Clock.schedule_once(
                lambda dt: threading.Thread(
                    target=self._check_temp_before_rfid_dispense, args=(app,), daemon=True
                ).start(),
                1.5
            )
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
            Clock.schedule_once(lambda dt: app.show_payment_method_page(), 3)
    
    def navigate_to_dispensing(self):
        """Navigate directly to dispensing for RFID payment.
        The caller already waits 1.5s (to show the success message) before calling
        this method, so we navigate immediately without an extra delay.
        """
        from kivy.app import App
        app = App.get_running_app()
        app.show_dispensing_page()

    def _check_temp_before_rfid_dispense(self, app):
        """Background: read cached temp; if below serving temp, heat before dispensing.
        Mirrors selection_page._check_temp_before_qr — the RFID flow previously had
        no temperature check at all before sending the customer to place_cup/dispensing.
        """
        from config import SERVING_TEMP, DEVICE_ID, POLLING_SERVER_URL
        from utils.api_client import get_localhost_session
        cached_temp = None
        try:
            _r = get_localhost_session().get(
                f"{POLLING_SERVER_URL}/api/device/{DEVICE_ID}/temperature",
                timeout=2
            )
            if _r.status_code == 200:
                _t = _r.json().get('pt100_temperature')
                if _t is not None and -10 <= float(_t) <= 120:
                    cached_temp = float(_t)
        except Exception:
            pass

        if cached_temp is not None and cached_temp < SERVING_TEMP:
            print(f"🌡 Pre-dispense temp check (RFID): {cached_temp:.1f}°C < {SERVING_TEMP}°C "
                  f"— heating before dispensing")
            app._pending_rfid_dispense_after_heating = True
            Clock.schedule_once(lambda dt: app.show_heating_page(cached_temp), 0)
        else:
            Clock.schedule_once(lambda dt: self.navigate_to_dispensing(), 0)
    
    def send_maintenance_solenoid_command(self, duration_ms=10000):
        """Send solenoid control command for maintenance card"""
        try:
            # Get device ID from central config
            from config import DEVICE_ID
            
            print("\n" + "="*80)
            print("🔧 SOLENOID COMMAND - MAINTENANCE MODE")
            print("="*80)
            print(f"🔧 Duration: {duration_ms}ms ({duration_ms/1000}s)")
            import uuid as _uuid
            _cmd_id = f"cmd_solenoid_{_uuid.uuid4().hex[:12]}"
            print(f"🔧 Command ID: {_cmd_id}")
            print(f"🔧 Device ID: {DEVICE_ID}")

            # API endpoint (using localhost for testing)
            # TODO: Change to dynamic IP later for production
            url = "http://localhost:5000/api/device/command"

            # Device ID from central config
            device_id = DEVICE_ID

            # Prepare the request payload
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": _cmd_id,
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
            
            # 35s: enough for one ESP32 poll cycle + execution
            session = get_localhost_session()
            response = session.post(url, json=payload, timeout=35)
            
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
        """Navigate to machine empty page when cups are 0 (only from home screens)"""
        if self.manager.current in ('payment_method', 'selection'):
            self.manager.current = 'machine_empty'
        else:
            print(f"Skipping auto-navigation to machine_empty as user has moved to: {self.manager.current}")
    
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

        # Note: Global status monitoring in main_app.py handles continuous checks

        # Pre-warm the QR cache for 1 cup as soon as the home page is visible (Disabled for Option A)
        # from kivy.app import App
        # app = App.get_running_app()
        # if hasattr(app, 'trigger_qr_prefetch'):
        #     app.trigger_qr_prefetch(1)

        # Enable RFID listening
        self.rfid_listening = True
        
        # Initialize RFID handler in background thread to avoid blocking UI
        threading.Thread(target=self._init_rfid_handler_background, daemon=True).start()
        
        # Start polling for RFID cards (will work if reader is active)
        self.start_rfid_polling()
    
    def _init_rfid_handler_background(self):
        """Initialize RFID auth handler in background thread to avoid UI lag"""
        from kivy.app import App
        app = App.get_running_app()
        
        if not hasattr(app, 'rfid_auth_handler') or app.rfid_auth_handler is None:
            # Handler not initialized or failed at startup, try to initialize now
            print("🔐 RFID Auth Handler not initialized, attempting initialization...")
            from config import MACHINE_ID, RFID_MACHINE_ID
            try:
                from utils.rfid_aes_auth import RFIDAESAuth
                app.rfid_auth_handler = RFIDAESAuth(
                    base_url="https://www.ukteawallet.com",
                    machine_id=RFID_MACHINE_ID
                )
                if app.rfid_auth_handler.reader_active:
                    print("✅ RFID Auth Handler initialized successfully")
                else:
                    print("⚠️ RFID Auth Handler initialization failed - reader not active")
                    print("⚠️ Please check if RFID reader is connected")
            except Exception as e:
                print(f"❌ Failed to initialize RFID Auth Handler: {e}")
                app.rfid_auth_handler = None
        elif hasattr(app.rfid_auth_handler, 'reader_active') and app.rfid_auth_handler.reader_active:
            print("✅ RFID Auth Handler already initialized and active")
        else:
            print("⚠️ RFID Auth Handler exists but reader is not active")
            print("⚠️ Please check if RFID reader is connected")
    
    def on_leave(self):
        """Called when leaving the screen"""
        self.rfid_listening = False
        self.stop_rfid_polling()

        # Cancel the 3s fallback restart timer so it doesn't fire after
        # we've already navigated away and restart RFID on the wrong page.
        if hasattr(self, 'restart_rfid_event') and self.restart_rfid_event:
            self.restart_rfid_event.cancel()
            self.restart_rfid_event = None
    
    def start_rfid_polling(self):
        """Start polling for RFID cards"""
        if not hasattr(self, 'rfid_poll_event') or self.rfid_poll_event is None:
            self._checking_card = False
            # Poll every 0.5 seconds
            self.rfid_poll_event = Clock.schedule_interval(self.poll_for_rfid_card, 0.5)
            print("🏷️ Started RFID card polling (every 0.5s)")
            print("🏷️ Place your card on the reader...")
            
            # Start connection keep-alive to prevent cold start issues
            self._start_rfid_keepalive()
    
    def _start_rfid_keepalive(self):
        """Keep RFID HTTP connection warm to prevent first-request slowness"""
        if not hasattr(self, 'rfid_keepalive_event') or self.rfid_keepalive_event is None:
            # Refresh connection every 30 seconds
            self.rfid_keepalive_event = Clock.schedule_interval(self._rfid_keepalive_tick, 30)
            print("🔄 Started RFID connection keep-alive (every 30s)")
    
    def _rfid_keepalive_tick(self, dt):
        """Periodic tick to keep RFID HTTP connection warm"""
        from kivy.app import App
        app = App.get_running_app()
        if hasattr(app, 'rfid_auth_handler') and app.rfid_auth_handler:
            threading.Thread(target=app.rfid_auth_handler.refresh_connection, daemon=True).start()
    
    def _stop_rfid_keepalive(self):
        """Stop the RFID keep-alive timer"""
        if hasattr(self, 'rfid_keepalive_event') and self.rfid_keepalive_event:
            self.rfid_keepalive_event.cancel()
            self.rfid_keepalive_event = None

    def stop_rfid_polling(self):
        """Stop polling for RFID cards"""
        if hasattr(self, 'rfid_poll_event') and self.rfid_poll_event:
            self.rfid_poll_event.cancel()
            self.rfid_poll_event = None
            print("🏷️ Stopped RFID card polling")
        
        # Also stop keep-alive
        self._stop_rfid_keepalive()
    
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
            if not hasattr(app, 'rfid_auth_handler') or app.rfid_auth_handler is None:
                # Handler not initialized
                self._checking_card = False
                return
            
            if not hasattr(app.rfid_auth_handler, 'reader_active') or not app.rfid_auth_handler.reader_active:
                # Reader not active
                self._checking_card = False
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

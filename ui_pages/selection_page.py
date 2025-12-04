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
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.floatlayout import FloatLayout
import os


class SimpleButton(Button):
    """Simple button without animations or effects"""
    
    def __init__(self, bg_color=(0.851, 0.647, 0.125, 1), **kwargs):
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


class NumberDisplay(Label):
    """Simple number display without 3D effects"""
    
    def __init__(self, number_text="1", **kwargs):
        super().__init__(**kwargs)
        self.text = number_text
        self.font_size = '56sp'
        self.bold = True
        self.color = (0.714, 0.478, 0.176, 1)  # Brown color
        self.halign = 'center'
        self.valign = 'middle'
        
        # Background
        with self.canvas.before:
            Color(0.98, 0.95, 0.85, 1)  # Light cream background
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
        
        self.bind(size=self.update_bg, pos=self.update_bg)
    
    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
    
    def set_number(self, number):
        self.text = str(number)


class MaxCupsLimitPopup(Popup):
    """Popup to show maximum 5 cups per transaction limit"""
    
    def __init__(self, **kwargs):
        # Create content layout
        content = FloatLayout()
        
        # Background with rounded corners
        with content.canvas.before:
            Color(0.95, 0.95, 0.95, 0.98)  # Light background
            self.bg_rect = RoundedRectangle(size=(450, 300), pos=(0, 0), radius=[25])
        
        # Close button (X) in top-right corner
        close_btn = Button(
            text='X',
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
        
        # Icon
        icon_label = Label(
            text="!",
            font_size='64sp',
            bold=True,
            color=(0.9, 0.6, 0.2, 1),  # Orange warning color
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.75},
            size_hint=(None, None),
            size=(100, 60)
        )
        content.add_widget(icon_label)
        
        # Title
        title_label = Label(
            text="Transaction Limit Reached",
            font_size='24sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.55},
            size_hint=(None, None),
            size=(400, 40)
        )
        content.add_widget(title_label)
        
        # Message
        message_label = Label(
            text="Maximum 5 cups is allowed\nfor single transaction",
            font_size='20sp',
            color=(0.5, 0.5, 0.5, 1),
            halign='center',
            pos_hint={'center_x': 0.5, 'center_y': 0.35},
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
            pos_hint={'center_x': 0.5, 'center_y': 0.15},
            size_hint=(None, None),
            size=(300, 40)
        )
        content.add_widget(self.countdown_label)
        
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


class SelectionPage(Screen):
    def __init__(self, **kwargs):
        super(SelectionPage, self).__init__(**kwargs)
        self.number_of_cups = 1
        self.max_cups = 10  # Default maximum, will be updated from API
        self.max_cups_per_transaction = 5  # Maximum 5 cups per transaction
        
        # Inactivity timer variables
        self.inactivity_timeout = 10  # 10 seconds
        self.inactivity_timer = None
        
        # Main layout - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=10)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)

        # Back button section
        back_section = BoxLayout(orientation='horizontal', size_hint_y=0.07)
        
        # Back button
        back_btn = SimpleButton(
            text='Back',
            size_hint=(None, None),
            size=(100, 40),
            font_size='18sp',
            color=(1, 1, 1, 1),
            bg_color=(0.6, 0.6, 0.6, 1)  # Gray color
        )
        back_btn.bind(on_press=self.on_back_pressed)
        back_section.add_widget(back_btn)
        
        # Spacer to push back button to the left
        back_section.add_widget(Widget())
        
        main_layout.add_widget(back_section)
        
        # Urban Ketl logo section - reduced size
        logo_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.15)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(200, 180),
                allow_stretch=True,
                keep_ratio=True
            )
            logo_section.add_widget(logo_image)
        else:
            # Fallback to text if image not found
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='32sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='center'
            )
            logo_section.add_widget(fallback_logo)
        
        main_layout.add_widget(logo_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.02))

        # "SELECT NUMBER OF CUPS" label
        selection_label = Label(
            text='SELECT NUMBER OF CUPS',
            font_size='32sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),  # Brown color
            size_hint_y=0.08,
            halign='center'
        )
        main_layout.add_widget(selection_label)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.02))

        # Cup image - reduced size
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.30)
        image_path = os.path.join('assets', 'cup.png')
        
        if os.path.exists(image_path):
            self.cup_image = Image(
                source=image_path,
                size_hint=(None, None), 
                size=(250, 250),
                allow_stretch=True,
                keep_ratio=True
            )
            image_section.add_widget(self.cup_image)
        
        main_layout.add_widget(image_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.02))

        # Counter section with minus, number, plus
        counter_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.13)
        
        counter_box = BoxLayout(
            orientation='horizontal', 
            spacing=15,
            size_hint=(None, None), 
            size=(400, 70)
        )

        # Minus button
        self.minus_btn = SimpleButton(
            text='−', 
            font_size='40sp',
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(100, 70),
            bg_color=(0.944, 0.679, 0.166, 1)  # Orange/gold color
        )
        self.minus_btn.bind(on_press=self.decrease_cups)
        counter_box.add_widget(self.minus_btn)

        # Number display
        self.number_display = NumberDisplay(
            number_text=str(self.number_of_cups),
            size_hint=(None, None),
            size=(170, 70)
        )
        counter_box.add_widget(self.number_display)

        # Plus button
        self.plus_btn = SimpleButton(
            text='+', 
            font_size='40sp',
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(100, 70),
            bg_color=(0.944, 0.679, 0.166, 1)  # Orange/gold color
        )
        self.plus_btn.bind(on_press=self.increase_cups)
        counter_box.add_widget(self.plus_btn)
        
        counter_section.add_widget(counter_box)
        main_layout.add_widget(counter_section)

        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))

        # Confirm button
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.11)
        
        self.confirm_btn = SimpleButton(
            text='CONFIRM TO PROCEED',
            size_hint=(None, None),
            size=(500, 70),
            font_size='24sp',
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=(0.944, 0.679, 0.166, 1)  # Orange/gold color
        )
        self.confirm_btn.bind(on_press=self.on_confirm_pay)
        button_section.add_widget(self.confirm_btn)
        
        main_layout.add_widget(button_section)

        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        self.add_widget(main_layout)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def increase_cups(self, instance):
        # Reset inactivity timer on user interaction
        self.reset_inactivity_timer()
        
        # Check transaction limit first (5 cups max per transaction)
        if self.number_of_cups >= self.max_cups_per_transaction:
            # Show popup for transaction limit
            self.show_transaction_limit_popup()
        elif self.number_of_cups < self.max_cups:
            self.number_of_cups += 1
            self.number_display.set_number(self.number_of_cups)
        else:
            # Show popup when trying to exceed available cups
            self.show_cups_limit_popup()

    def decrease_cups(self, instance):
        # Reset inactivity timer on user interaction
        self.reset_inactivity_timer()
        
        if self.number_of_cups > 1:
            self.number_of_cups -= 1
            self.number_display.set_number(self.number_of_cups)

    def on_confirm_pay(self, instance):
        # Stop inactivity timer when confirming
        self.stop_inactivity_timer()
        
        app = App.get_running_app()
        app.show_payment_page(self.number_of_cups)
    
    def on_back_pressed(self, instance):
        """Navigate back to payment method page"""
        # Stop inactivity timer when going back
        self.stop_inactivity_timer()
        
        self.manager.current = 'payment_method'

    def get_cup_count(self):
        return self.number_of_cups
    
    def on_enter(self):
        """Reset when page becomes active"""
        # Start inactivity timer
        self.start_inactivity_timer()
        
        # Bind touch events to reset timer on any interaction
        Window.bind(on_touch_down=self.on_user_interaction)
    
    def on_leave(self):
        """Clean up when leaving page"""
        # Stop inactivity timer
        self.stop_inactivity_timer()
        
        # Unbind touch events
        Window.unbind(on_touch_down=self.on_user_interaction)
    
    def on_user_interaction(self, window, touch):
        """Reset inactivity timer on any touch interaction"""
        self.reset_inactivity_timer()
    
    def start_inactivity_timer(self):
        """Start the inactivity timer"""
        self.stop_inactivity_timer()  # Cancel any existing timer
        self.inactivity_timer = Clock.schedule_once(self.on_inactivity_timeout, self.inactivity_timeout)
        print(f"Selection page: Inactivity timer started ({self.inactivity_timeout} seconds)")
    
    def reset_inactivity_timer(self):
        """Reset the inactivity timer"""
        if self.inactivity_timer:
            self.start_inactivity_timer()
    
    def stop_inactivity_timer(self):
        """Stop the inactivity timer"""
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
            self.inactivity_timer = None
            print("Selection page: Inactivity timer stopped")
    
    def on_inactivity_timeout(self, dt):
        """Handle inactivity timeout - return to payment method page"""
        print("Selection page: Inactivity timeout - returning to payment method page")
        self.manager.current = 'payment_method'
    
    def set_max_cups(self, max_cups):
        """Set the maximum number of cups available"""
        self.max_cups = max_cups
        print(f"Selection page: Maximum cups set to {max_cups}")
        
        # If current selection exceeds max, reduce it
        if self.number_of_cups > self.max_cups:
            self.number_of_cups = min(self.max_cups, 1)  # At least 1 cup
            self.number_display.set_number(self.number_of_cups)
    
    def show_cups_limit_popup(self):
        """Show popup when user tries to select more cups than available"""
        from ui_pages.payment_method_page import CupsAvailabilityPopup
        
        popup = CupsAvailabilityPopup(available_cups=self.max_cups)
        popup.open()
    
    def show_transaction_limit_popup(self):
        """Show popup when user tries to select more than 5 cups per transaction"""
        popup = MaxCupsLimitPopup()
        popup.open()

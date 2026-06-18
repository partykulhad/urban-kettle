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
import time
import threading


class CupsCounterWidget(BoxLayout):
    """Cups counter widget for top-right of selection page — matches payment_method_page design."""

    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', spacing=0, **kwargs)
        self.cups_count = 0
        self.is_loading = True

        top_row = BoxLayout(orientation='horizontal', spacing=2, size_hint_y=0.5)

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
            fallback_icon = Label(
                text='☕',
                font_size='40sp',
                color=(0.714, 0.478, 0.176, 1),
                size_hint=(None, None),
                size=(50, 50),
                halign='center',
                valign='middle'
            )
            top_row.add_widget(fallback_icon)

        self.number_label = Label(
            text='...',
            font_size='48sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint=(None, None),
            size=(100, 50),
            halign='left',
            valign='middle'
        )
        self.number_label.bind(size=self.number_label.setter('text_size'))
        top_row.add_widget(self.number_label)
        self.add_widget(top_row)

        self.availability_label = Label(
            text='Cups\nAvailable',
            font_size='15sp',
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=0.5,
            halign='left',
            valign='top',
            padding=(0, 0, 20, 0)
        )
        self.availability_label.bind(size=self.availability_label.setter('text_size'))
        self.add_widget(self.availability_label)

    def update_count(self, count):
        if count is None:
            self.is_loading = True
            self.number_label.text = '...'
            return
        self.is_loading = False
        self.cups_count = count
        self.number_label.text = str(count)
        self.number_label.color = (0.714, 0.478, 0.176, 1)

    def set_loading(self):
        self.is_loading = True
        self.number_label.text = '...'


class SimpleButton(Button):
    """Simple button without animations or effects"""

    def __init__(self, bg_color=(0.949, 0.6, 0.0, 1), **kwargs):
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
            text="Maximum 4 cups is allowed\nfor single transaction",
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
        self.max_cups_per_transaction = 4  # Maximum 4 cups per transaction
        
        # Touch debouncing variables for Raspberry Pi touchscreen
        self.last_button_press_time = 0
        self.button_cooldown = 0.1  # 100ms cooldown - fast but prevents accidental double-tap
        self._confirm_blocked_until = 0  # entry grace period for confirm button
        
        # Inactivity timer variables — longer in test mode so screensaver doesn't
        # interfere with manual testing (offline detection skipped on screensaver).
        import os as _os
        self.inactivity_timeout = 30 if _os.environ.get("UK_TEST_MODE") else 10
        self.inactivity_timer = None
        
        # Debounce timer — fires prefetch 0.2s after user stops tapping
        self.prefetch_timer = None

        # Main layout - no padding to match payment_method_page exactly
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)

        # Top bar with logo on left (like payment_method_page) and back button
        from kivy.uix.floatlayout import FloatLayout
        top_bar = FloatLayout(size_hint_y=0.15)
        
        # Urban Kettle logo on the left side - same as payment_method_page
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                pos_hint={'x': 0.0, 'top': 1.35},  # Same as payment_method_page
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
        
        # Cups counter widget in top-right area (selection is now home — no Back button)
        self.cups_counter = CupsCounterWidget(
            size_hint=(None, None),
            size=(160, 80)
        )
        self.cups_counter.pos_hint = {'right': 0.98, 'top': 0.72}
        top_bar.add_widget(self.cups_counter)

        main_layout.add_widget(top_bar)

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
            cup_image = Image(
                source=image_path,
                size_hint=(None, None), 
                size=(250, 250),
                allow_stretch=True,
                keep_ratio=True
            )
            image_section.add_widget(cup_image)
        
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
            bg_color=(0.949, 0.6, 0.0, 1)  # Orange color
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
            bg_color=(0.949, 0.6, 0.0, 1)  # Orange color
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
            bg_color=(0.949, 0.6, 0.0, 1)  # Orange color
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
        # Touch debouncing - prevent multiple rapid touches on Raspberry Pi
        current_time = time.time()
        if current_time - self.last_button_press_time < self.button_cooldown:
            print(f"🚫 Button cooldown active, ignoring touch (last press: {current_time - self.last_button_press_time:.3f}s ago)")
            return  # Ignore rapid touches
        self.last_button_press_time = current_time
        
        # Reset inactivity timer on user interaction
        self.reset_inactivity_timer()
        
        # Check transaction limit first (max 4 cups per transaction)
        if self.number_of_cups >= self.max_cups_per_transaction:
            # Show popup for transaction limit
            self.show_transaction_limit_popup()
        elif self.number_of_cups < self.max_cups:
            self.number_of_cups += 1
            self.number_display.set_number(self.number_of_cups)
            print(f"✅ Increased cups to {self.number_of_cups}")
            self._schedule_prefetch()
        else:
            # Show popup when trying to exceed available cups
            self.show_cups_limit_popup()

    def decrease_cups(self, instance):
        # Touch debouncing - prevent multiple rapid touches on Raspberry Pi
        current_time = time.time()
        if current_time - self.last_button_press_time < self.button_cooldown:
            print(f"🚫 Button cooldown active, ignoring touch (last press: {current_time - self.last_button_press_time:.3f}s ago)")
            return  # Ignore rapid touches
        self.last_button_press_time = current_time
        
        # Reset inactivity timer on user interaction
        self.reset_inactivity_timer()
        
        if self.number_of_cups > 1:
            self.number_of_cups -= 1
            self.number_display.set_number(self.number_of_cups)
            print(f"✅ Decreased cups to {self.number_of_cups}")
            self._schedule_prefetch()
        else:
            print("⚠️ Minimum 1 cup required")

    def _schedule_prefetch(self):
        """Debounce: wait 0.2s after last tap before firing API call."""
        if self.prefetch_timer:
            self.prefetch_timer.cancel()
        self.prefetch_timer = Clock.schedule_once(self._execute_prefetch, 0.2)

    def _execute_prefetch(self, dt):
        print(f"🚀 Prefetching QR for {self.number_of_cups} cups...")
        App.get_running_app().trigger_qr_prefetch(self.number_of_cups)

    def on_confirm_pay(self, instance):
        current_time = time.time()
        # Entry grace period: block for 0.8s after page enters (prevents touch-through)
        if current_time < getattr(self, '_confirm_blocked_until', 0):
            remaining = self._confirm_blocked_until - current_time
            print(f"🚫 Confirm blocked: entry grace period ({remaining:.2f}s remaining)")
            return
        # Normal cooldown guard (same as +/- buttons)
        if current_time - self.last_button_press_time < self.button_cooldown:
            print(f"🚫 Confirm cooldown active ({current_time - self.last_button_press_time:.3f}s ago)")
            return
        self.last_button_press_time = current_time

        # Stop inactivity timer when confirming
        self.stop_inactivity_timer()

        app = App.get_running_app()

        # Guard: if machine is at/below the empty threshold, show empty page instead of starting payment
        from config import MACHINE_EMPTY_THRESHOLD
        if app.local_cups_count is not None and app.local_cups_count <= MACHINE_EMPTY_THRESHOLD:
            print(f"⚠️ Cups at {app.local_cups_count} (<= {MACHINE_EMPTY_THRESHOLD}) — showing machine empty page")
            app.machine_empty_page.set_mode('empty')
            app.show_page('machine_empty')
            return

        # Clamp selection to what's actually available (in case display lagged)
        if app.local_cups_count is not None and self.number_of_cups > app.local_cups_count:
            self.number_of_cups = max(1, app.local_cups_count)
            self.number_display.set_number(self.number_of_cups)

        # Check cached temp before generating QR — if cold, heat first then resume
        num_cups = self.number_of_cups
        threading.Thread(
            target=self._check_temp_before_qr,
            args=(app, num_cups),
            daemon=True
        ).start()

    def _check_temp_before_qr(self, app, num_cups):
        """Background: read cached temp; if below serving temp, heat before QR."""
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
            print(f"🌡 Pre-QR temp check: {cached_temp:.1f}°C < {SERVING_TEMP}°C "
                  f"— heating before QR for {num_cups} cups")
            app._pending_cups_after_heating = num_cups
            Clock.schedule_once(lambda dt: app.show_heating_page(cached_temp), 0)
        else:
            Clock.schedule_once(lambda dt: app.show_payment_page(num_cups), 0)

    def update_cups_display(self, count):
        """Update the cups counter widget and sync the +/- upper limit."""
        if count is not None:
            self.set_max_cups(count)
        if hasattr(self, 'cups_counter'):
            self.cups_counter.update_count(count)

    def refresh_cups_count(self):
        """Trigger a background refresh of the cups count."""
        App.get_running_app().fetch_and_store_cups_count()

    def get_cup_count(self):
        return self.number_of_cups
    
    def on_enter(self):
        """Reset when page becomes active"""
        # Reset cup selection to 1
        self.number_of_cups = 1
        if hasattr(self, 'number_display'):
            self.number_display.set_number(1)

        # Block confirm button for 0.8s after page entry.
        # Prevents touch-through: a cancel tap on the payment page can land on
        # the confirm button here if both are in the same screen position.
        self._confirm_blocked_until = time.time() + 0.8
        self.last_button_press_time = time.time()

        app = App.get_running_app()

        # Show current local cups count immediately, then refresh in background
        if hasattr(self, 'cups_counter'):
            if app.local_cups_count is not None:
                self.cups_counter.update_count(app.local_cups_count)
            else:
                self.cups_counter.set_loading()
        app.fetch_and_store_cups_count()

        # Pre-fetch QR for the default 1-cup selection immediately
        app.trigger_qr_prefetch(1)

        # Start inactivity timer
        self.start_inactivity_timer()

        # Bind touch events to reset timer on any interaction
        Window.bind(on_touch_down=self.on_user_interaction)

        # Delegate RFID polling to payment_method_page — it holds all RFID/AES logic.
        # Selection is the home screen, so RFID should be active here.
        if hasattr(app, 'payment_method_page'):
            pmp = app.payment_method_page
            pmp._last_detected_uid = None  # reset so any present card is treated as new
            pmp.rfid_listening = True
            pmp.start_rfid_polling()

    def on_leave(self):
        """Clean up when leaving page"""
        self.stop_inactivity_timer()
        Window.unbind(on_touch_down=self.on_user_interaction)
        # Cancel any pending debounced prefetch so it doesn't fire after leaving
        if self.prefetch_timer:
            self.prefetch_timer.cancel()
            self.prefetch_timer = None

        # Stop RFID polling when leaving selection (the home page)
        app = App.get_running_app()
        if hasattr(app, 'payment_method_page'):
            pmp = app.payment_method_page
            pmp.rfid_listening = False
            pmp.stop_rfid_polling()
    
    def on_user_interaction(self, window, touch):
        """Reset inactivity timer on any touch interaction"""
        self.reset_inactivity_timer()
    
    def start_inactivity_timer(self):
        """Start the inactivity timer"""
        self.stop_inactivity_timer()  # Cancel any existing timer
        self.inactivity_timer = Clock.schedule_once(self.on_inactivity_timeout, self.inactivity_timeout)
        print(f"Selection page: Inactivity timer started ({self.inactivity_timeout} seconds)")
    
    def reset_inactivity_timer(self):
        """Reset the inactivity timer — always restarts even if timer already fired."""
        self.start_inactivity_timer()
    
    def stop_inactivity_timer(self):
        """Stop the inactivity timer"""
        if self.inactivity_timer:
            self.inactivity_timer.cancel()
            self.inactivity_timer = None
            print("Selection page: Inactivity timer stopped")
    
    def on_inactivity_timeout(self, dt):
        """Handle inactivity timeout — go to screensaver (selection is now home)"""
        print("Selection page: Inactivity timeout - going to screensaver")
        app = App.get_running_app()
        app.cancel_prefetched_qrs()
        app.activate_screensaver()
    
    def set_max_cups(self, max_cups):
        """Set the maximum number of cups available"""
        self.max_cups = max_cups
        print(f"Selection page: Maximum cups set to {max_cups}")
        
        # If current selection exceeds what's available, clamp it down
        if self.number_of_cups > self.max_cups:
            self.number_of_cups = max(1, self.max_cups)  # clamp to available, never below 1
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

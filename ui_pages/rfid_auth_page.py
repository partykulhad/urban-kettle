from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock


class RFIDAuthPage(Screen):
    """RFID Authentication Progress Page"""
    
    def __init__(self, **kwargs):
        super(RFIDAuthPage, self).__init__(**kwargs)
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=[40, 30], spacing=15)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Top spacing
        main_layout.add_widget(Widget(size_hint_y=0.15))
        
        # Card icon/animation area
        self.icon_label = Label(
            text='🏷️',
            font_size='80sp',
            size_hint_y=0.2,
            halign='center'
        )
        main_layout.add_widget(self.icon_label)
        
        # Status message
        self.status_label = Label(
            text='Keep card on reader...',
            font_size='28sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),  # Urban Ketl brown
            size_hint_y=0.12,
            halign='center'
        )
        main_layout.add_widget(self.status_label)
        
        # Progress steps
        self.step_label = Label(
            text='Step 1 of 3: Reading card...',
            font_size='20sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=0.08,
            halign='center'
        )
        main_layout.add_widget(self.step_label)
        
        # Timer/countdown
        self.timer_label = Label(
            text='Please wait...',
            font_size='18sp',
            color=(0.6, 0.6, 0.6, 1),
            size_hint_y=0.08,
            halign='center'
        )
        main_layout.add_widget(self.timer_label)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.37))
        
        self.add_widget(main_layout)
        
        # Animation
        self.pulse_animation = None
        self.start_time = 0
        self.timer_event = None
        self.timeout_event = None  # 9-second timeout
        self.auth_completed = False  # Track if auth completed
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def start_auth(self):
        """Start authentication process"""
        self.start_time = Clock.get_time()
        self.auth_completed = False
        self.update_step(1, "Reading card...")
        self.start_pulse_animation()
        self.start_timer()
        self.start_timeout()
    
    def update_step(self, step, message):
        """Update the current step"""
        self.step_label.text = f'Step {step} of 3: {message}'
        self.status_label.text = 'Keep card on reader...'
    
    def start_pulse_animation(self):
        """Start pulsing animation for icon"""
        if self.pulse_animation:
            self.pulse_animation.cancel(self.icon_label)
        
        # Pulse animation using opacity instead of font_size
        anim = Animation(opacity=0.5, duration=0.5) + Animation(opacity=1.0, duration=0.5)
        anim.repeat = True
        anim.start(self.icon_label)
        self.pulse_animation = anim
    
    def stop_pulse_animation(self):
        """Stop pulsing animation"""
        if self.pulse_animation:
            self.pulse_animation.cancel(self.icon_label)
            self.pulse_animation = None
    
    def start_timer(self):
        """Start elapsed time timer"""
        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.update_timer, 0.1)
    
    def stop_timer(self):
        """Stop timer"""
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
    
    def start_timeout(self):
        """Start 9-second timeout - auto-return to payment method if auth takes too long"""
        self.cancel_timeout()
        self.timeout_event = Clock.schedule_once(self.on_timeout, 9)
        print("⏱️ RFID auth 9-second timeout started")
    
    def cancel_timeout(self):
        """Cancel the timeout"""
        if self.timeout_event:
            self.timeout_event.cancel()
            self.timeout_event = None
    
    def on_timeout(self, dt):
        """Called when 9-second timeout expires"""
        if self.auth_completed:
            # Auth already completed, ignore timeout
            return
        
        print("⏱️ RFID auth timeout (9s) - returning to payment method page")
        self.stop_pulse_animation()
        self.stop_timer()
        self.icon_label.text = '⏱️'
        self.status_label.text = 'Authentication Timeout'
        self.status_label.color = (0.9, 0.6, 0.2, 1)  # Orange
        self.step_label.text = 'Please try again'
        self.timer_label.text = 'Timed out after 9s'
        
        # Navigate back to payment method page after 1.5 seconds
        from kivy.app import App
        app = App.get_running_app()
        Clock.schedule_once(lambda dt: app.show_page('payment_method'), 1.5)
        
        # Restart RFID polling
        if hasattr(app, 'payment_method_page') and hasattr(app.payment_method_page, 'restart_rfid_after_auth'):
            Clock.schedule_once(lambda dt: app.payment_method_page.restart_rfid_after_auth(), 1.5)
    
    def update_timer(self, dt):
        """Update elapsed time"""
        elapsed = Clock.get_time() - self.start_time
        self.timer_label.text = f'Elapsed: {elapsed:.1f}s'
    
    def show_success(self, balance):
        """Show success message"""
        self.auth_completed = True  # Mark as completed
        self.cancel_timeout()  # Cancel the 9-second timeout
        self.stop_pulse_animation()
        self.stop_timer()
        self.icon_label.text = '✅'
        self.status_label.text = 'Authentication Successful!'
        self.status_label.color = (0.18, 0.8, 0.44, 1)  # Green
        self.step_label.text = f'Balance: ₹{balance}'
        elapsed = Clock.get_time() - self.start_time
        self.timer_label.text = f'Completed in {elapsed:.1f}s'
    
    def show_error(self, error_msg):
        """Show error message"""
        self.auth_completed = True  # Mark as completed
        self.cancel_timeout()  # Cancel the 9-second timeout
        self.stop_pulse_animation()
        self.stop_timer()
        self.icon_label.text = '❌'
        self.status_label.text = 'Authentication Failed'
        self.status_label.color = (0.906, 0.298, 0.235, 1)  # Red
        self.step_label.text = error_msg
        elapsed = Clock.get_time() - self.start_time
        self.timer_label.text = f'Failed after {elapsed:.1f}s'
    
    def on_leave(self):
        """Clean up when leaving"""
        self.stop_pulse_animation()
        self.stop_timer()
        self.cancel_timeout()  # Cancel timeout when leaving page
        return super().on_leave()

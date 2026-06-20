from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
import os


class SimpleButton(Button):
    """Simple button without animations or effects"""
    
    def __init__(self, bg_color=(0.714, 0.478, 0.176, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.bg_color = bg_color
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def update_graphics(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Simple button background - tea cup color
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[15])


class ThankYouPage(Screen):
    """Clean and simple thank you page matching the design"""
    
    def __init__(self, **kwargs):
        super(ThankYouPage, self).__init__(**kwargs)
        
        # Main layout - no padding to match payment_method_page exactly
        main_layout = BoxLayout(orientation='vertical')
        
        # Background
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=(0, 0))
        main_layout.bind(size=self._update_rect)
        
        # Top bar with logo on left - matching payment_method_page exactly
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
        
        # "ENJOY YOUR CHAI!" text
        enjoy_label = Label(
            text='ENJOY YOUR CHAI!',
            font_size='32sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.08
        )
        main_layout.add_widget(enjoy_label)
        
        # Spacing after ENJOY text
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Thank you image section
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.40)
        thankyou_image = Image(
            source=os.path.join('assets', 'thankyou.png'),
            size_hint=(None, None),
            size=(260, 260),
            allow_stretch=True,
            keep_ratio=True
        )
        image_section.add_widget(thankyou_image)
        main_layout.add_widget(image_section)
        
        # Spacing after video
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # "Dispensing complete. Have a great day!" text - reduced size
        message_section = BoxLayout(orientation='vertical', size_hint_y=0.12, spacing=3)
        
        complete_label = Label(
            text='Dispensing complete.',
            font_size='24sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        message_section.add_widget(complete_label)
        
        great_day_label = Label(
            text='Have a great day!',
            font_size='24sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        message_section.add_widget(great_day_label)
        
        main_layout.add_widget(message_section)
        
        # Spacing before button
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Simple button section - reduced size
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.09)
        
        self.new_order_btn = SimpleButton(
            text='Place New Order',
            size_hint=(None, None),
            size=(260, 55),
            font_size='20sp',
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=(0.944, 0.679, 0.166, 1) 
        )
        self.new_order_btn.bind(on_press=self.on_new_order)
        button_section.add_widget(self.new_order_btn)
        
        main_layout.add_widget(button_section)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.05))
        
        self.add_widget(main_layout)
        
        # Auto-return timer
        self.auto_return_event = None
        
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def on_new_order(self, instance=None):
        """Handle new order button"""
        print("🏠 Thank you page: Returning to payment method page")
        if self.auto_return_event:
            self.auto_return_event.cancel()
            self.auto_return_event = None
        
        app = App.get_running_app()
        app.show_payment_method_page()
    
    def on_enter(self):
        print("⏱️ Thank you page: Starting 5-second auto-return timer")
        self.auto_return_event = Clock.schedule_once(lambda dt: self.on_new_order(), 5)

    def on_leave(self):
        if self.auto_return_event:
            self.auto_return_event.cancel()
            self.auto_return_event = None

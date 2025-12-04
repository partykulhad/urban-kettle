from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
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
        
        # Main layout - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=15)
        
        # Background
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=(0, 0))
        main_layout.bind(size=self._update_rect)
        
        # Top spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # Urban Ketl logo section
        logo_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.12)
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
                font_size='28sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='center'
            )
            logo_section.add_widget(fallback_logo)
        
        main_layout.add_widget(logo_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # "ENJOY YOUR CHAI!" text
        enjoy_label = Label(
            text='ENJOY YOUR CHAI!',
            font_size='36sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),  # Tea cup brown color
            halign='center',
            size_hint_y=0.10
        )
        main_layout.add_widget(enjoy_label)
        
        # Thank you image (tea cup with steam)
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.35)
        thankyou_image_path = os.path.join('assets', 'thankyou.png')
        
        if os.path.exists(thankyou_image_path):
            thankyou_image = Image(
                source=thankyou_image_path,
                size_hint=(None, None),
                size=(250, 250),
                allow_stretch=True,
                keep_ratio=True
            )
            image_section.add_widget(thankyou_image)
        else:
            # Fallback if image not found
            fallback_text = Label(
                text='☕',
                font_size='120sp',
                color=(0.714, 0.478, 0.176, 1),
                halign='center'
            )
            image_section.add_widget(fallback_text)
        
        main_layout.add_widget(image_section)
        
        # "Dispensing complete. Have a great day!" text
        message_section = BoxLayout(orientation='vertical', size_hint_y=0.15, spacing=5)
        
        complete_label = Label(
            text='Dispensing complete.',
            font_size='28sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        message_section.add_widget(complete_label)
        
        great_day_label = Label(
            text='Have a great day!',
            font_size='28sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        message_section.add_widget(great_day_label)
        
        main_layout.add_widget(message_section)
        
        # Spacing before button
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        # Simple button section
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.10)
        
        self.new_order_btn = SimpleButton(
            text='Place New Order',
            size_hint=(None, None),
            size=(280, 60),
            font_size='22sp',
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
        if self.auto_return_event:
            self.auto_return_event.cancel()
            self.auto_return_event = None
        
        app = App.get_running_app()
        app.show_payment_method_page()
    
    def on_enter(self):
        """Start auto-return timer when page enters"""
        # Auto-return to payment method after 10 seconds
        self.auto_return_event = Clock.schedule_once(lambda dt: self.on_new_order(), 10)
    
    def on_leave(self):
        """Clean up when leaving page"""
        if self.auto_return_event:
            self.auto_return_event.cancel()
            self.auto_return_event = None

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window

class HeatingPage(Screen):
    """Page displayed while tea is heating up"""
    
    def __init__(self, **kwargs):
        super(HeatingPage, self).__init__(**kwargs)
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical')
        
        # Background
        with main_layout.canvas.before:
            Color(0.98, 0.97, 0.95, 1)  # Warm cream background
            self.bg_rect = Rectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top section with logo
        top_section = BoxLayout(orientation='horizontal', size_hint_y=0.2, padding=[20, 30, 20, 10])
        
        # Urban Kettle logo image (left corner)
        from kivy.uix.image import Image
        logo_image = Image(
            source='assets/urban_ketl_logo.png',
            size_hint=(None, None),
            size=(230, 200),
            allow_stretch=True,
            keep_ratio=True,
            pos_hint={'center_x': 0, 'center_y': 0.5}
        )
        
        top_section.add_widget(logo_image)
        top_section.add_widget(BoxLayout())  # Right spacer
        
        main_layout.add_widget(top_section)
        
        # Content layout (reduced top spacing)
        content_layout = BoxLayout(orientation='vertical', padding=[40, 0, 40, 40], spacing=25)
        
        # Small top spacer
        content_layout.add_widget(BoxLayout(size_hint_y=0.05))
        
        # Heating icon container
        icon_container = BoxLayout(size_hint_y=0.3, orientation='vertical')
        
        # Animated heating icon (will be added via canvas)
        self.icon_widget = BoxLayout(size_hint=(None, None), size=(150, 150))
        self.icon_widget.pos_hint = {'center_x': 0.5}
        
        with self.icon_widget.canvas:
            # Steam effect (animated circles)
            Color(0.714, 0.478, 0.176, 0.3)  # #b67a2d with transparency
            self.steam1 = Ellipse(pos=(50, 100), size=(20, 20))
            self.steam2 = Ellipse(pos=(80, 110), size=(15, 15))
            self.steam3 = Ellipse(pos=(65, 120), size=(18, 18))
            
            # Tea cup
            Color(0.714, 0.478, 0.176, 1)  # #b67a2d
            # Cup body
            Line(points=[40, 40, 40, 80, 110, 80, 110, 40], width=4)
            Line(points=[30, 40, 120, 40], width=4)
            # Handle
            Line(circle=(125, 60, 15, 0, 180), width=4)
        
        icon_container.add_widget(self.icon_widget)
        content_layout.add_widget(icon_container)
        
        # Heating message
        self.temp_label = Label(
            text='Please Wait\nTea is Heating Up',
            font_size='42sp',
            bold=True,
            halign='center',
            color=(0.714, 0.478, 0.176, 1),  # #b67a2d
            size_hint_y=0.25
        )
        self.temp_label.bind(size=self.temp_label.setter('text_size'))
        content_layout.add_widget(self.temp_label)
        
        # Temperature display
        self.current_temp_label = Label(
            text='Current: --°C',
            font_size='28sp',
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=0.12
        )
        content_layout.add_widget(self.current_temp_label)
        
        # Target temperature
        target_label = Label(
            text='Target: 83°C',
            font_size='22sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=0.1
        )
        content_layout.add_widget(target_label)
        
        # Bottom spacer
        content_layout.add_widget(BoxLayout(size_hint_y=0.18))
        
        main_layout.add_widget(content_layout)
        
        self.add_widget(main_layout)
        
        # Animation
        self.steam_animation = None
    
    def _update_rect(self, instance, value):
        self.bg_rect.size = instance.size
        self.bg_rect.pos = instance.pos
    
    def on_enter(self):
        """Start animations when page is shown"""
        self.animate_steam()
    
    def on_leave(self):
        """Stop animations when leaving"""
        if self.steam_animation:
            self.steam_animation.cancel_all(self.steam1)
            self.steam_animation.cancel_all(self.steam2)
            self.steam_animation.cancel_all(self.steam3)
    
    def animate_steam(self):
        """Animate rising steam"""
        # Animate steam circles rising and fading
        def reset_steam(*args):
            self.steam1.pos = (50, 100)
            self.steam2.pos = (80, 110)
            self.steam3.pos = (65, 120)
            anim1 = Animation(pos=(50, 140), duration=2)
            anim2 = Animation(pos=(80, 150), duration=2.2)
            anim3 = Animation(pos=(65, 155), duration=2.1)
            anim1.bind(on_complete=reset_steam)
            anim1.start(self.steam1)
            anim2.start(self.steam2)
            anim3.start(self.steam3)
        
        reset_steam()
    
    def update_temperature(self, current_temp):
        """Update current temperature display"""
        if current_temp is not None:
            self.current_temp_label.text = f'Current: {current_temp:.1f}°C'
        else:
            self.current_temp_label.text = 'Current: --°C'

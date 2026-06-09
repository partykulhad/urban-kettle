from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window


class FlushPage(Screen):
    """Shown while the machine is executing a maintenance flush (water + tea).

    Blocks new orders and shows a live countdown so the user knows exactly
    when the machine will be ready.  Navigates automatically to the payment
    method page once the flush finishes.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._tick_event = None      # Kivy Clock interval for countdown
        self._remaining = 0          # seconds left (counts down to 0)
        self._drop_anim = None       # water-drop animation handle

        # ── Background ──────────────────────────────────────────────────────
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(0.97, 0.98, 1.0, 1)   # Very light blue-white
            self.bg_rect = Rectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)

        # ── Logo ─────────────────────────────────────────────────────────────
        from kivy.uix.floatlayout import FloatLayout
        from kivy.uix.image import Image
        import os
        top_bar = FloatLayout(size_hint_y=0.15)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            top_bar.add_widget(Image(
                source=logo_path,
                size_hint=(None, None),
                size=(260, 230),
                allow_stretch=True,
                keep_ratio=True,
                pos_hint={'x': 0.0, 'top': 1.35}
            ))
        main_layout.add_widget(top_bar)

        # ── Animated water-drop icon ─────────────────────────────────────────
        icon_box = BoxLayout(
            size_hint_y=0.22,
            orientation='vertical'
        )
        self._drop_widget = BoxLayout(
            size_hint=(None, None),
            size=(120, 120)
        )
        self._drop_widget.pos_hint = {'center_x': 0.5}
        with self._drop_widget.canvas:
            # Outer ripple ring
            Color(0.3, 0.6, 1.0, 0.25)
            self._ring = Ellipse(pos=(5, 5), size=(110, 110))
            # Inner water drop body
            Color(0.18, 0.52, 0.89, 1)
            self._drop_body = Ellipse(pos=(30, 35), size=(60, 65))
            # Droplet tip
            Color(0.18, 0.52, 0.89, 1)
            self._drop_tip = Ellipse(pos=(48, 88), size=(24, 24))
            # Shine highlight
            Color(1, 1, 1, 0.45)
            self._shine = Ellipse(pos=(38, 55), size=(20, 22))
        icon_box.add_widget(self._drop_widget)
        main_layout.add_widget(icon_box)

        # ── Title ────────────────────────────────────────────────────────────
        title = Label(
            text='Machine Cleaning in Progress',
            font_size='30sp',
            bold=True,
            color=(0.18, 0.52, 0.89, 1),
            size_hint_y=0.09,
            halign='center',
            valign='middle'
        )
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        main_layout.add_widget(title)

        # ── Subtitle ─────────────────────────────────────────────────────────
        self._phase_label = Label(
            text='Flushing water path...',
            font_size='20sp',
            color=(0.4, 0.55, 0.75, 1),
            size_hint_y=0.07,
            halign='center',
            valign='middle'
        )
        self._phase_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        main_layout.add_widget(self._phase_label)

        main_layout.add_widget(Widget(size_hint_y=0.03))

        # ── Countdown number ─────────────────────────────────────────────────
        self._countdown_label = Label(
            text='--',
            font_size='72sp',
            bold=True,
            color=(0.906, 0.298, 0.235, 1),
            size_hint_y=0.18,
            halign='center',
            valign='middle'
        )
        self._countdown_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        main_layout.add_widget(self._countdown_label)

        # ── "seconds remaining" unit ─────────────────────────────────────────
        self._unit_label = Label(
            text='seconds remaining',
            font_size='18sp',
            color=(0.55, 0.55, 0.6, 1),
            size_hint_y=0.06,
            halign='center'
        )
        main_layout.add_widget(self._unit_label)

        main_layout.add_widget(Widget(size_hint_y=0.02))

        # ── Bottom note ──────────────────────────────────────────────────────
        note = Label(
            text='Your next cup will be ready shortly.',
            font_size='18sp',
            color=(0.5, 0.5, 0.55, 1),
            size_hint_y=0.07,
            halign='center'
        )
        note.bind(size=lambda l, s: setattr(l, 'text_size', s))
        main_layout.add_widget(note)

        main_layout.add_widget(Widget(size_hint_y=0.11))

        self.add_widget(main_layout)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _update_rect(self, instance, value):
        self.bg_rect.size = instance.size
        self.bg_rect.pos = instance.pos

    def _animate_drop(self):
        """Gently pulse the water-drop icon."""
        if self._drop_anim:
            self._drop_anim.cancel(self._drop_widget)
        anim = (
            Animation(opacity=0.7, duration=0.8) +
            Animation(opacity=1.0, duration=0.8)
        )
        anim.repeat = True
        anim.start(self._drop_widget)
        self._drop_anim = anim

    def _stop_drop_anim(self):
        if self._drop_anim:
            self._drop_anim.cancel(self._drop_widget)
            self._drop_anim = None
            self._drop_widget.opacity = 1.0

    # ── Public API called from main_app.py ───────────────────────────────────

    def show_waiting(self):
        """Show waiting state — ESP32 drives the duration, no countdown needed."""
        self._stop_tick()
        self._countdown_label.text = '...'
        self._unit_label.text = 'Please wait'
        self._phase_label.text = 'Flushing water path...'

    def set_phase(self, phase):
        """Update phase label: 'water' or 'tea'."""
        if phase == 'tea':
            self._phase_label.text = 'Flushing tea path...'
        elif phase == 'done':
            self._phase_label.text = 'Cleaning complete!'
            self._countdown_label.text = ''
            self._unit_label.text = ''
        else:
            self._phase_label.text = 'Flushing water path...'

    def _stop_tick(self):
        if self._tick_event:
            self._tick_event.cancel()
            self._tick_event = None

    # ── Kivy lifecycle ───────────────────────────────────────────────────────

    def on_enter(self):
        from kivy.app import App
        app = App.get_running_app()
        # Hard guard: only allow this page while a flush is actually running.
        # If we somehow land here with no active flush, bounce straight back.
        if not getattr(app, 'flush_in_progress', False):
            Clock.schedule_once(lambda dt: app.show_payment_method_page(), 0)
            return
        self._animate_drop()

    def on_leave(self):
        self._stop_tick()
        self._stop_drop_anim()

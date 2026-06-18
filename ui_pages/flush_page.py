from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
import os


class FlushPage(Screen):
    """Shown while the machine executes a maintenance flush (water + tea).

    Sequence:  water flush  →  10 s countdown  →  tea flush  →  done.
    Design matches the heating/machine_empty pages (cream background, brown accents).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._tick_event = None
        self._remaining = 0
        self._steam_anim = None
        self.dots_animation_state = 0
        self.dots_timer = None

        # ── Background (warm cream — matches heating page) ───────────────────
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(0.98, 0.97, 0.95, 1)
            self.bg_rect = Rectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)

        # ── Top bar with logo (identical to heating page) ────────────────────
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

        # ── Content ──────────────────────────────────────────────────────────
        content = BoxLayout(
            orientation='vertical',
            padding=[40, 0, 40, 40],
            spacing=18
        )

        content.add_widget(Widget(size_hint_y=0.04))

        # Icon — animated steam over cup (same canvas style as heating page)
        icon_anchor = AnchorLayout(
            anchor_x='center', anchor_y='center', size_hint_y=0.28
        )
        self.icon_widget = BoxLayout(
            size_hint=(None, None), size=(150, 150)
        )
        self.icon_widget.pos_hint = {'center_x': 0.5}

        with self.icon_widget.canvas:
            # Steam circles
            Color(0.714, 0.478, 0.176, 0.3)
            self._steam1 = Ellipse(pos=(50, 100), size=(20, 20))
            self._steam2 = Ellipse(pos=(80, 110), size=(15, 15))
            self._steam3 = Ellipse(pos=(65, 120), size=(18, 18))
            # Cup body
            Color(0.714, 0.478, 0.176, 1)
            Line(points=[40, 40, 40, 80, 110, 80, 110, 40], width=4)
            Line(points=[30, 40, 120, 40], width=4)
            # Handle
            Line(circle=(125, 60, 15, 0, 180), width=4)
            # Water drop inside cup (shows it's being cleaned)
            Color(0.2, 0.55, 0.9, 0.7)
            self._drop = Ellipse(pos=(65, 48), size=(20, 22))

        icon_anchor.add_widget(self.icon_widget)
        content.add_widget(icon_anchor)

        # Title
        title = Label(
            text='Cleaning in Progress',
            font_size='28sp',
            bold=True,
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=0.10,
            halign='center',
            valign='middle'
        )
        title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(title)

        # Phase label (changes as flush progresses)
        self._phase_label = Label(
            text='Flushing water path...',
            font_size='22sp',
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=0.09,
            halign='center',
            valign='middle'
        )
        self._phase_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(self._phase_label)

        content.add_widget(Widget(size_hint_y=0.02))

        # Countdown number (large, brown) — shown during 10 s wait
        self._countdown_label = Label(
            text='',
            font_size='72sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=0.18,
            halign='center',
            valign='middle'
        )
        self._countdown_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(self._countdown_label)

        # "seconds remaining" unit label (shown only during countdown)
        self._unit_label = Label(
            text='',
            font_size='18sp',
            color=(0.6, 0.6, 0.6, 1),
            size_hint_y=0.06,
            halign='center',
            valign='middle'
        )
        self._unit_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(self._unit_label)

        # Animated dots (●●● style — same as machine_empty_page)
        dots_anchor = AnchorLayout(
            anchor_x='center', anchor_y='center', size_hint_y=0.08
        )
        self.dots_label = Label(
            text='●●●',
            font_size='26sp',
            color=(0.714, 0.478, 0.176, 1),
            halign='center'
        )
        dots_anchor.add_widget(self.dots_label)
        content.add_widget(dots_anchor)

        # Step indicator (e.g. "Refill flush: Step 1/3") — hidden for normal flush
        self._note_label = Label(
            text='',
            font_size='16sp',
            color=(0.714, 0.478, 0.176, 0.85),
            size_hint_y=0.06,
            halign='center',
            valign='middle'
        )
        self._note_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(self._note_label)

        # Bottom note
        note = Label(
            text='Your next cup will be ready shortly.',
            font_size='17sp',
            color=(0.55, 0.55, 0.55, 1),
            size_hint_y=0.07,
            halign='center',
            valign='middle'
        )
        note.bind(size=lambda l, s: setattr(l, 'text_size', s))
        content.add_widget(note)

        content.add_widget(Widget(size_hint_y=0.08))

        main_layout.add_widget(content)
        self.add_widget(main_layout)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _update_rect(self, instance, value):
        self.bg_rect.size = instance.size
        self.bg_rect.pos = instance.pos

    def _start_steam_anim(self):
        if self._steam_anim:
            self._steam_anim.cancel(self.icon_widget)
        anim = (
            Animation(opacity=0.6, duration=0.9) +
            Animation(opacity=1.0, duration=0.9)
        )
        anim.repeat = True
        anim.start(self.icon_widget)
        self._steam_anim = anim

    def _stop_steam_anim(self):
        if self._steam_anim:
            self._steam_anim.cancel(self.icon_widget)
            self._steam_anim = None
            self.icon_widget.opacity = 1.0

    def _start_dots(self):
        self.dots_animation_state = 0
        if self.dots_timer:
            self.dots_timer.cancel()
        self.dots_timer = Clock.schedule_interval(self._tick_dots, 0.5)

    def _tick_dots(self, dt):
        states = ['●●●', '○●●', '○○●', '○○○', '●○○', '●●○']
        self.dots_animation_state = (self.dots_animation_state + 1) % len(states)
        self.dots_label.text = states[self.dots_animation_state]

    def _stop_dots(self):
        if self.dots_timer:
            self.dots_timer.cancel()
            self.dots_timer = None

    def _stop_tick(self):
        if self._tick_event:
            self._tick_event.cancel()
            self._tick_event = None

    # ── Public API (called from main_app.py) ─────────────────────────────────

    def set_note(self, text):
        """Show or hide the step indicator (e.g. 'Refill flush: Step 1/3')."""
        self._note_label.text = text or ''

    def show_waiting(self):
        """Initial state — water flush about to start."""
        self._stop_tick()
        self._countdown_label.text = ''
        self._unit_label.text = ''
        self._phase_label.text = 'Flushing water path...'

    def set_phase(self, phase):
        """Update the display for the current flush phase.

        phase values: 'water', 'wait', 'tea', 'done'
        """
        self._stop_tick()
        if phase == 'water':
            self._phase_label.text = 'Flushing water path...'
            self._countdown_label.text = ''
            self._unit_label.text = ''
        elif phase == 'wait':
            self._phase_label.text = 'Preparing tea flush...'
            self._countdown_label.text = ''
            self._unit_label.text = ''
        elif phase == 'tea':
            self._phase_label.text = 'Flushing tea path...'
            self._countdown_label.text = ''
            self._unit_label.text = ''
        elif phase == 'done':
            self._phase_label.text = 'Cleaning complete!'
            self._countdown_label.text = ''
            self._unit_label.text = ''

    def start_wait_countdown(self, seconds):
        """Show a live countdown during the N-second pause between flushes."""
        self._stop_tick()
        self._remaining = seconds
        self._phase_label.text = 'Preparing tea flush...'
        self._countdown_label.text = str(seconds)
        self._unit_label.text = 'seconds until tea flush'
        self._tick_event = Clock.schedule_interval(self._countdown_tick, 1.0)

    def _countdown_tick(self, dt):
        self._remaining -= 1
        if self._remaining > 0:
            self._countdown_label.text = str(self._remaining)
        else:
            self._stop_tick()
            self._countdown_label.text = ''
            self._unit_label.text = ''

    # ── Kivy lifecycle ───────────────────────────────────────────────────────

    def on_enter(self):
        from kivy.app import App
        app = App.get_running_app()
        if not getattr(app, 'flush_in_progress', False):
            Clock.schedule_once(lambda dt: app.show_payment_method_page(), 0)
            return
        self._start_steam_anim()
        self._start_dots()

    def on_leave(self):
        self._stop_tick()
        self._stop_steam_anim()
        self._stop_dots()
        self._note_label.text = ''

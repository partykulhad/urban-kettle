from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.core.window import Window
from kivy.uix.behaviors import ButtonBehavior
from kivy.app import App
from kivy.clock import Clock
import os
import threading


class PremiumButton(ButtonBehavior, Label):
    def __init__(self, text='', bg_color=(0.714, 0.478, 0.176, 1), radius=[15], **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.bg_color = bg_color
        self.radius = radius
        self.bold = True
        self.font_size = kwargs.get('font_size', '18sp')
        self.color = (1, 1, 1, 1)
        with self.canvas.before:
            self.color_obj = Color(*self.bg_color)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=self.radius)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def on_press(self):
        self.color_obj.a = 0.7

    def on_release(self):
        self.color_obj.a = 1.0


class MaintenancePage(Screen):
    """Maintenance Interface — 7-inch kiosk display"""

    def __init__(self, **kwargs):
        super(MaintenancePage, self).__init__(**kwargs)

        self.duration_ms = 8000
        from config import DEVICE_ID
        self.device_id = DEVICE_ID

        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = RoundedRectangle(size=Window.size, pos=self.pos)
        self.bind(size=self._update_bg)

        main_layout = BoxLayout(orientation='vertical', padding=[20, 8, 20, 8], spacing=6)

        # ── 1. Top bar ──
        top_bar = BoxLayout(size_hint_y=0.10)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            top_bar.add_widget(Image(
                source=logo_path,
                size_hint=(None, 1),
                width=180,
                allow_stretch=True,
                keep_ratio=True
            ))
        top_bar.add_widget(Widget())
        main_layout.add_widget(top_bar)

        # ── 2. Title ──
        main_layout.add_widget(Label(
            text='MAINTENANCE SETTINGS',
            font_size='22sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=0.07
        ))

        # ── 3. Auto Flush Timing card (from backend) ──
        flush_card = BoxLayout(orientation='vertical', padding=[15, 10, 15, 10],
                               spacing=6, size_hint_y=0.22)
        with flush_card.canvas.before:
            Color(0.94, 0.97, 1.0, 1)
            self.f_rect = RoundedRectangle(pos=flush_card.pos, size=flush_card.size, radius=[18])
            Color(0.2, 0.55, 0.85, 0.25)
            self.f_line = Line(
                rounded_rectangle=(flush_card.x, flush_card.y,
                                   flush_card.width, flush_card.height, 18), width=1.2)
        flush_card.bind(pos=self._update_f_card, size=self._update_f_card)

        flush_card.add_widget(Label(
            text='AUTO FLUSH TIMING  (from backend)',
            font_size='12sp', bold=True,
            color=(0.2, 0.45, 0.75, 1),
            size_hint_y=0.25
        ))

        flush_row = BoxLayout(orientation='horizontal', spacing=12, size_hint_y=0.5)

        self.flush_time_label = Label(
            text='-- min',
            font_size='36sp',
            bold=True,
            color=(0.2, 0.45, 0.75, 1),
            size_hint_x=0.55,
            halign='center',
            valign='middle'
        )
        self.flush_time_label.bind(size=lambda l, s: setattr(l, 'text_size', s))

        self.flush_sync_btn = PremiumButton(
            text='SYNC',
            bg_color=(0.2, 0.55, 0.85, 1),
            font_size='14sp',
            size_hint_x=0.45,
            radius=[12]
        )
        self.flush_sync_btn.bind(on_release=self.sync_flush_time)

        flush_row.add_widget(self.flush_time_label)
        flush_row.add_widget(self.flush_sync_btn)
        flush_card.add_widget(flush_row)

        self.flush_status_label = Label(
            text='Tap SYNC to fetch latest timing from server',
            font_size='11sp',
            color=(0.5, 0.55, 0.65, 1),
            size_hint_y=0.25,
            halign='center',
            valign='middle'
        )
        self.flush_status_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        flush_card.add_widget(self.flush_status_label)

        main_layout.add_widget(flush_card)

        # ── 4. Pump Duration card ──
        duration_card = BoxLayout(orientation='vertical', padding=[15, 8, 15, 8],
                                  spacing=6, size_hint_y=0.25)
        with duration_card.canvas.before:
            Color(0.98, 0.96, 0.94, 1)
            self.d_rect = RoundedRectangle(pos=duration_card.pos, size=duration_card.size, radius=[18])
            Color(0.714, 0.478, 0.176, 0.15)
            self.d_line = Line(
                rounded_rectangle=(duration_card.x, duration_card.y,
                                   duration_card.width, duration_card.height, 18), width=1.2)
        duration_card.bind(pos=self._update_d_card, size=self._update_d_card)

        duration_card.add_widget(Label(
            text='PUMP DURATION',
            font_size='12sp', bold=True,
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=0.2
        ))

        controls = BoxLayout(orientation='horizontal', spacing=16, size_hint_y=0.5)

        minus_btn = PremiumButton(text='−', font_size='28sp', size_hint_x=0.2)
        minus_btn.bind(on_release=self.decrement_duration)

        self.duration_label = Label(
            text=f'{self.duration_ms / 1000:.1f}s',
            font_size='36sp', bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_x=0.6,
            halign='center', valign='middle'
        )
        self.duration_label.bind(size=lambda l, s: setattr(l, 'text_size', s))

        plus_btn = PremiumButton(text='+', font_size='28sp', size_hint_x=0.2)
        plus_btn.bind(on_release=self.increment_duration)

        controls.add_widget(minus_btn)
        controls.add_widget(self.duration_label)
        controls.add_widget(plus_btn)
        duration_card.add_widget(controls)

        apply_btn = PremiumButton(
            text='APPLY SETTINGS',
            bg_color=(0.949, 0.6, 0.0, 1),
            size_hint=(0.75, 0.3),
            pos_hint={'center_x': 0.5},
            font_size='14sp',
            radius=[12]
        )
        apply_btn.bind(on_release=self.trigger_update_settings)
        duration_card.add_widget(apply_btn)

        main_layout.add_widget(duration_card)

        # ── 5. Hardware Status card ──
        status_card = BoxLayout(orientation='vertical', padding=[12, 8, 12, 8],
                                spacing=4, size_hint_y=0.24)
        with status_card.canvas.before:
            Color(0.96, 0.96, 0.96, 1)
            self.s_rect = RoundedRectangle(pos=status_card.pos, size=status_card.size, radius=[18])
        status_card.bind(pos=self._update_s_card, size=self._update_s_card)

        status_card.add_widget(Label(
            text='HARDWARE STATUS',
            font_size='12sp', bold=True,
            color=(0.6, 0.6, 0.6, 1),
            size_hint_y=0.2
        ))

        self.status_info = Label(
            text='IDLE\n--',
            font_size='17sp', bold=True,
            color=(0.2, 0.2, 0.2, 1),
            halign='center', valign='middle',
            size_hint_y=0.5
        )
        self.status_info.bind(size=lambda l, s: setattr(l, 'text_size', s))
        status_card.add_widget(self.status_info)

        refresh_btn = PremiumButton(
            text='REFRESH STATUS',
            bg_color=(0.2, 0.3, 0.5, 1),
            size_hint=(0.5, 0.3),
            pos_hint={'center_x': 0.5},
            font_size='13sp',
            radius=[10]
        )
        refresh_btn.bind(on_release=self.trigger_get_status)
        status_card.add_widget(refresh_btn)

        main_layout.add_widget(status_card)

        # ── 6. Close button ──
        close_btn = PremiumButton(
            text='CLOSE MAINTENANCE',
            bg_color=(0.2, 0.2, 0.2, 1),
            size_hint_y=0.10,
            font_size='15sp',
            radius=[10]
        )
        close_btn.bind(on_release=self.go_back)
        main_layout.add_widget(close_btn)

        self.add_widget(main_layout)

    # ── Canvas update helpers ──
    def _update_bg(self, instance, value):
        self.bg_rect.size = value

    def _update_f_card(self, instance, value):
        self.f_rect.pos = instance.pos
        self.f_rect.size = instance.size
        self.f_line.rounded_rectangle = (instance.x, instance.y,
                                         instance.width, instance.height, 18)

    def _update_d_card(self, instance, value):
        self.d_rect.pos = instance.pos
        self.d_rect.size = instance.size
        self.d_line.rounded_rectangle = (instance.x, instance.y,
                                         instance.width, instance.height, 18)

    def _update_s_card(self, instance, value):
        self.s_rect.pos = instance.pos
        self.s_rect.size = instance.size

    # ── Lifecycle ──
    def on_enter(self):
        try:
            from config import DEVICE_ID
            self.device_id = DEVICE_ID
        except Exception:
            pass
        # Auto-sync flush time and hardware status on page open
        self.sync_flush_time(None)
        self.trigger_get_status(None)

    def go_back(self, instance):
        self.manager.current = 'payment_method'

    # ── Auto Flush Timing (backend) ──
    def sync_flush_time(self, instance):
        """Fetch flushTimeMinutes from kulhad.vercel.app and update display"""
        self.flush_time_label.text = '...'
        self.flush_status_label.text = 'Fetching from server...'
        self.flush_sync_btn.disabled = True

        app = App.get_running_app()

        def fetch():
            try:
                result = app.api_client.get_machine_data(app.MACHINE_ID)
                if result and result.get('success'):
                    flush_mins = result.get('data', {}).get('flushTimeMinutes')
                    if flush_mins and flush_mins != 'N/A':
                        mins = float(flush_mins)
                        # Update the app-level flush timer too
                        app.flush_time_minutes = mins
                        def update(dt):
                            self.flush_time_label.text = f'{mins:.0f} min'
                            self.flush_status_label.text = f'Active timer: {mins:.0f} min  |  Flush runs for {app.flush_duration_seconds}s'
                            self.flush_sync_btn.disabled = False
                        Clock.schedule_once(update)
                    else:
                        def update(dt):
                            self.flush_time_label.text = 'Not set'
                            self.flush_status_label.text = 'flushTimeMinutes not configured on backend'
                            self.flush_sync_btn.disabled = False
                        Clock.schedule_once(update)
                else:
                    def update(dt):
                        self.flush_time_label.text = f'{app.flush_time_minutes:.0f} min'
                        self.flush_status_label.text = 'Server error — showing cached value'
                        self.flush_sync_btn.disabled = False
                    Clock.schedule_once(update)
            except Exception as e:
                def update(dt):
                    self.flush_time_label.text = '-- min'
                    self.flush_status_label.text = f'Error: {e}'
                    self.flush_sync_btn.disabled = False
                Clock.schedule_once(update)

        threading.Thread(target=fetch, daemon=True).start()

    # ── Pump Duration ──
    def increment_duration(self, instance):
        self.duration_ms = min(30000, self.duration_ms + 500)
        self.duration_label.text = f'{self.duration_ms / 1000:.1f}s'

    def decrement_duration(self, instance):
        self.duration_ms = max(1000, self.duration_ms - 500)
        self.duration_label.text = f'{self.duration_ms / 1000:.1f}s'

    def trigger_update_settings(self, instance):
        self.status_info.text = 'Sending...'
        app = App.get_running_app()

        def run():
            res = app.api_client.update_pump_settings(self.device_id, self.duration_ms)
            msg = f'Applied!\n{self.duration_ms}ms' if res else 'Failed'
            Clock.schedule_once(lambda dt: setattr(self.status_info, 'text', msg))

        threading.Thread(target=run, daemon=True).start()

    # ── Hardware Status ──
    def trigger_get_status(self, instance):
        app = App.get_running_app()

        def run():
            res = app.api_client.get_pump_status(self.device_id)
            if res and 'response' in res:
                d = res['response'].get('data', {})
                txt = (f"{d.get('pumpState', 'N/A').upper()}\n"
                       f"{d.get('progress', 0)}%  ({d.get('remainingTime', 0)}s left)")
            else:
                txt = 'OFFLINE'
            Clock.schedule_once(lambda dt: setattr(self.status_info, 'text', txt))

        threading.Thread(target=run, daemon=True).start()

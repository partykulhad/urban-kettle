from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
import os
import threading

class DispensingPage(Screen):
    """Dispensing page with real-time hardware status and video animation"""
    
    def __init__(self, **kwargs):
        super(DispensingPage, self).__init__(**kwargs)
        
        # Tracking variables
        self.total_cups = 1
        self.current_cup = 1
        self.is_paused = False
        self.pump_check_event = None
        self.safety_timeout_event = None
        self.updates_received = 0
        self.has_started_dispensing = False
        self.completion_handled = False
        self._checking_pump = False
        # Consecutive idle/off polls required before accepting completion.
        # Prevents a single stray "idle" reading mid-dispense from exiting early.
        self._consecutive_idle_count = 0
        self._IDLE_EXIT_THRESHOLD = 3  # 3 × 0.5 s = 1.5 s of confirmed idle
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical')
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top bar with logo
        from kivy.uix.floatlayout import FloatLayout
        top_bar = FloatLayout(size_hint_y=0.10)
        
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(200, 160),
                pos_hint={'x': 0.0, 'top': 1.1},
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
                pos_hint={'x': 0.02, 'top': 0.95}
            )
            top_bar.add_widget(fallback_logo)
        
        main_layout.add_widget(top_bar)
        
        # Labels
        self.dispensing_title = Label(
            text='DISPENSING...',
            font_size='36sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=0.10,
            halign='center',
            valign='middle'
        )
        self.dispensing_title.bind(size=lambda l, s: setattr(l, 'text_size', s))
        main_layout.add_widget(self.dispensing_title)
        
        self.cup_counter_label = Label(
            text='Cup 1 of 1',
            font_size='24sp',
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=0.08,
            halign='center',
            valign='middle'
        )
        self.cup_counter_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        main_layout.add_widget(self.cup_counter_label)
        
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # Video section — plays ONCE at native 30fps
        video_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.40)
        from ui_pages.screensaver_page import VideoWidget
        self.video_widget = VideoWidget(loop=False, size_hint=(None, None), size=(320, 240))
        video_path = os.path.join('assets', 'dispensing.mp4')
        self.video_widget.set_video_path(video_path)
        video_section.add_widget(self.video_widget)
        main_layout.add_widget(video_section)

        # Instruction text — animates with moving dots after video ends
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.08)
        self.instruction_label = Label(
            text='Your tea is being prepared.',
            font_size='22sp',
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            valign='middle'
        )
        self.instruction_label.bind(size=lambda l, s: setattr(l, 'text_size', s))
        instruction_section.add_widget(self.instruction_label)
        main_layout.add_widget(instruction_section)
        self._dot_event = None
        self._dot_state = 0
        
        # Progress Bar removed as requested
        # progress_layout = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.06)
        # self.progress_bar = ProgressBar(max=100, value=0, size_hint=(0.8, None), height=15)
        # progress_layout.add_widget(self.progress_bar)
        # main_layout.add_widget(progress_layout)
        
        main_layout.add_widget(Widget(size_hint_y=0.03))
        self.add_widget(main_layout)
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def set_cup_info(self, current_cup, total_cups):
        self.current_cup = current_cup
        self.total_cups = total_cups
        self.cup_counter_label.text = f'Cup {current_cup} of {total_cups}'
    
    def on_enter(self):
        self.updates_received = 0
        self.has_started_dispensing = False
        self.completion_handled = False
        self._consecutive_idle_count = 0
        self._dot_state = 0
        if hasattr(self, 'dispensing_title'):
            self.dispensing_title.text = 'DISPENSING...'
            self.dispensing_title.color = (0.714, 0.478, 0.176, 1)
        if hasattr(self, 'instruction_label'):
            self.instruction_label.text = 'Your tea is being prepared.'
            self.instruction_label.color = (0.3, 0.3, 0.3, 1)
        if hasattr(self, '_dot_event') and self._dot_event:
            self._dot_event.cancel()
            self._dot_event = None
        if hasattr(self, 'video_widget'):
            # Video is 13.94s — longer than any pump duration (max 13.3s for 120ml).
            # Pump completion always stops the video before it ends → zero freeze.
            # Dot animation fires only if pump somehow takes > 14s (safety net).
            Clock.schedule_once(lambda dt: self._start_dot_animation(), 14.0)
            self.video_widget.start_video()
        self.start_pump_monitoring()
        self.safety_timeout_event = Clock.schedule_once(self.handle_safety_timeout, 60)

    def on_leave(self):
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()
        if hasattr(self, '_dot_event') and self._dot_event:
            self._dot_event.cancel()
            self._dot_event = None
        self.stop_pump_monitoring()
        self._consecutive_idle_count = 0
        if self.safety_timeout_event:
            self.safety_timeout_event.cancel()
            self.safety_timeout_event = None
    
    def _start_dot_animation(self):
        """After video ends, animate dots on the instruction label so there is
        always visible motion during the remaining pump time."""
        if self.completion_handled:
            return
        dots = ['Dispensing .  ', 'Dispensing .. ', 'Dispensing ...']
        def _tick(dt):
            if self.completion_handled or not hasattr(self, 'instruction_label'):
                return False
            self.instruction_label.text = dots[self._dot_state % 3]
            self._dot_state += 1
            return True
        self._dot_event = Clock.schedule_interval(_tick, 0.5)

    def start_pump_monitoring(self):
        print("🔍 Monitoring hardware status (Reference Logic)...")
        # self.progress_bar.value = 0
        self.pump_check_event = Clock.schedule_interval(self.check_pump_state, 0.5)
    
    def stop_pump_monitoring(self):
        if self.pump_check_event:
            self.pump_check_event.cancel()
            self.pump_check_event = None
    
    def check_pump_state(self, dt):
        if hasattr(self, '_checking_pump') and self._checking_pump:
            return True
        self._checking_pump = True
        threading.Thread(target=self._do_pump_check, daemon=True).start()
        return True
    
    def _do_pump_check(self):
        try:
            from config import DEVICE_ID
            app = App.get_running_app()
            result = app.api_client.get_pump_status(DEVICE_ID)
            if result and 'response' in result:
                data = result['response'].get('data', {})
                Clock.schedule_once(lambda dt: self._update_pump_state(data), 0)
        except Exception as e:
            print(f"Status check error: {e}")
        finally:
            self._checking_pump = False
            
    def _update_pump_state(self, data):
        self.updates_received += 1
        pump_state = data.get('pumpState', 'idle').lower()
        progress = data.get('progress', 0.0)

        # Pull timing fields from ESP32 (milliseconds → seconds)
        elapsed_ms  = data.get('elapsedTime', 0) or 0
        remaining_ms = data.get('remainingTime', 0) or 0
        elapsed_s   = elapsed_ms / 1000.0
        remaining_s = remaining_ms / 1000.0

        print(
            f"🔄 Pump: state={pump_state}  progress={progress:.1f}%  "
            f"elapsed={elapsed_s:.1f}s  remaining={remaining_s:.1f}s  "
            f"started={self.has_started_dispensing}  "
            f"idle_streak={self._consecutive_idle_count}"
        )

        # Track if dispensing has genuinely begun
        if pump_state == 'ongoing' or progress > 0:
            self.has_started_dispensing = True
            self._consecutive_idle_count = 0

        # ── EXIT CONDITIONS ───────────────────────────────────────────────────
        # 1. Hardware explicitly says "completed" or progress hit 100%
        is_done = (pump_state == 'completed') or (progress >= 100)

        # 2. Hardware is idle/off AFTER dispensing started.
        #    Require _IDLE_EXIT_THRESHOLD consecutive idle polls to avoid
        #    exiting on a single stray "idle" reading mid-dispense.
        #    NOTE: never exits on idle if pump never started — waits for
        #    safety timeout instead (60 s), which is correct behaviour when
        #    pump_status doesn't update for start_dispense commands.
        if pump_state in ('idle', 'off') and self.has_started_dispensing:
            self._consecutive_idle_count += 1
        elif pump_state not in ('idle', 'off'):
            self._consecutive_idle_count = 0

        is_idle_exit = (
            pump_state in ('idle', 'off')
            and self.has_started_dispensing
            and self._consecutive_idle_count >= self._IDLE_EXIT_THRESHOLD
        )
        # ─────────────────────────────────────────────────────────────────────

        if is_done or is_idle_exit:
            reason = 'completed' if is_done else f'idle×{self._consecutive_idle_count}'
            print(
                f"✅ Dispensing done ({reason}) — "
                f"state={pump_state}  progress={progress:.1f}%  elapsed={elapsed_s:.1f}s"
            )
            self.handle_completion()
        elif pump_state == 'ongoing' and self.is_paused:
            self.resume_dispensing()
        elif pump_state == 'paused' and not self.is_paused:
            self.pause_dispensing()

                
    def handle_completion(self):
        if self.completion_handled:
            return
        self.completion_handled = True
        print("🎉 Dispensing complete!")
        self.stop_pump_monitoring()
        if self.safety_timeout_event:
            self.safety_timeout_event.cancel()
            self.safety_timeout_event = None

        # Stop video immediately — no frozen last frame possible
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()
        if hasattr(self, '_dot_event') and self._dot_event:
            self._dot_event.cancel()
            self._dot_event = None
        if hasattr(self, 'dispensing_title'):
            self.dispensing_title.text = 'YOUR TEA IS READY!'
            self.dispensing_title.color = (0.18, 0.7, 0.44, 1)
        if hasattr(self, 'instruction_label'):
            self.instruction_label.text = 'Enjoy your chai!'
            self.instruction_label.color = (0.18, 0.7, 0.44, 1)

        app = App.get_running_app()
        Clock.schedule_once(lambda dt: app.handle_cup_completion(), 2.0)

    def handle_safety_timeout(self, dt):
        print("⚠️ Safety timeout - force completing")
        self.handle_completion()

    def pause_dispensing(self):
        self.is_paused = True
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()

    def resume_dispensing(self):
        self.is_paused = False
        if hasattr(self, 'video_widget'):
            self.video_widget.start_video()

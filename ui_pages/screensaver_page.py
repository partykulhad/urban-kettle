from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics.texture import Texture
import cv2
import numpy as np
import os

class VideoWidget(Widget):
    def __init__(self, **kwargs):
        self.loop = kwargs.pop('loop', True)  # not a Kivy property — must extract before super()
        super().__init__(**kwargs)
        self.video_path = None
        self.cap = None
        self.is_playing = False
        self.video_event = None
        self.texture = None
        self._target_duration = None  # if set, video speed is adjusted to match
        
        # Create texture for video frames
        self.bind(size=self.update_video_size)
        
    def update_video_size(self, *args):
        """Update video display when widget size changes"""
        if self.texture:
            self.canvas.clear()
            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=self.texture, pos=self.pos, size=self.size)
    
    def set_video_path(self, path):
        """Set video file path"""
        self.video_path = path

    def set_playback_duration(self, duration_seconds):
        """Adjust playback speed so the video finishes in exactly duration_seconds."""
        self._target_duration = duration_seconds

    def start_video(self):
        """Start video playback"""
        if not self.video_path or not os.path.exists(self.video_path):
            print(f"Video file not found: {self.video_path}")
            self.show_placeholder()
            return

        self.cap = cv2.VideoCapture(self.video_path)
        self.is_playing = True

        if not self.cap.isOpened():
            print("Failed to open video capture")
            self.show_placeholder()
            return

        video_fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)

        # If a pump duration was set, stretch/compress the video to match it exactly
        if self._target_duration and total_frames > 0:
            playback_fps = total_frames / self._target_duration
            print(f"Video: {total_frames:.0f} frames @ {video_fps}fps → "
                  f"adjusted to {playback_fps:.1f}fps to match {self._target_duration:.1f}s pump duration")
        else:
            playback_fps = video_fps
            print(f"Video FPS: {playback_fps}")

        self.video_event = Clock.schedule_interval(self.update_frame, 1.0 / playback_fps)
    
    def update_frame(self, dt):
        """Update video frame"""
        if not self.is_playing or not self.cap or not self.cap.isOpened():
            return False
        
        ret, frame = self.cap.read()
        if ret and frame is not None:
            # Convert frame from BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Get widget dimensions (ensure they're integers and not zero)
            widget_w = max(1, int(self.width))
            widget_h = max(1, int(self.height))
            
            # Resize frame to exactly match widget size (stretch to fill)
            frame = cv2.resize(frame, (widget_w, widget_h))
            
            # Create texture from resized frame
            self.texture = Texture.create(size=(widget_w, widget_h))
            self.texture.blit_buffer(frame.flatten(), colorfmt='rgb', bufferfmt='ubyte')
            self.texture.flip_vertical()
            
            # Update canvas to fill the entire widget
            self.canvas.clear()
            with self.canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=self.texture, pos=self.pos, size=self.size)
        else:
            if self.loop:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                # Video finished — hold on the last frame, no abrupt freeze
                # stop_video() is called by on_leave() when the page navigates away
                self.is_playing = False
                if self.video_event:
                    self.video_event.cancel()
                    self.video_event = None
        
        return True
    
    def stop_video(self):
        """Stop video playback"""
        self.is_playing = False
        if self.video_event:
            self.video_event.cancel()
            self.video_event = None
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
    
    def show_placeholder(self):
        """Show placeholder when video is not available"""
        self.canvas.clear()
        with self.canvas:
            Color(0.1, 0.1, 0.1, 1)  # Dark background
            Rectangle(pos=self.pos, size=self.size)
            
            # Draw Urban Kettle logo as placeholder
            Color(0.714, 0.478, 0.176, 1)  # #b67a2d
            center_x, center_y = self.center
            
            # Draw cup outline
            Line(circle=(center_x, center_y, 80), width=4)
            Line(points=[center_x + 80, center_y, center_x + 100, center_y, 
                        center_x + 100, center_y - 20, center_x + 90, center_y - 40], width=4)

class ScreensaverPage(Screen):
    """Modern screensaver page with video playback"""
    
    def __init__(self, **kwargs):
        super(ScreensaverPage, self).__init__(**kwargs)
        
        # Main layout - use a simple widget to allow full screen video
        main_layout = Widget()
        with main_layout.canvas.before:
            Color(0, 0, 0, 1)  # Black background
            self.rect = Rectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect)
        
        # Video widget - full screen
        self.video_widget = VideoWidget()
        # Bind video widget size to main layout size to ensure it fills the screen
        main_layout.bind(size=self._update_video_size, pos=self._update_video_pos)
        main_layout.add_widget(self.video_widget)
        
        # Overlay with branding (subtle) - positioned on top
        overlay = AnchorLayout(anchor_x='right', anchor_y='bottom', size_hint=(1, 1))
        
        # Brand label with transparency
        brand_container = BoxLayout(orientation='vertical', size_hint=(None, None), 
                                  size=(200, 80), padding=[10, 10])
        
        brand_label = Label(
            text='Urban [color=b67a2d]ketl[/color]',
            font_size='18sp',
            markup=True,
            bold=True,
            color=(1, 1, 1, 0.7),  # Semi-transparent white
            size_hint_y=None,
            height='30sp'
        )
        
        tagline = Label(
            text='Authentic milk chai',
            font_size='12sp',
            color=(1, 1, 1, 0.5),  # More transparent
            size_hint_y=None,
            height='20sp'
        )
        
        brand_container.add_widget(brand_label)
        brand_container.add_widget(tagline)
        overlay.add_widget(brand_container)
        
        main_layout.add_widget(overlay)
        
        self.add_widget(main_layout)
        
        # Store video path
        self.video_path = "input.mp4"  # Default video path
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def _update_video_size(self, instance, value):
        """Update video widget size to match main layout"""
        self.video_widget.size = instance.size
    
    def _update_video_pos(self, instance, value):
        """Update video widget position to match main layout"""
        self.video_widget.pos = instance.pos
    
    def set_video_path(self, path):
        """Set a new video path"""
        self.video_path = path
        self.video_widget.set_video_path(path)
    
    def on_enter(self):
        """Called when screen is entered - start video"""
        self.video_widget.set_video_path(self.video_path)
        self.video_widget.start_video()
    
    def on_leave(self):
        """Called when screen is left - stop video"""
        self.video_widget.stop_video()

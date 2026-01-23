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
        super().__init__(**kwargs)
        self.video_path = None
        self.cap = None
        self.is_playing = False
        self.video_event = None
        self.texture = None
        self._texture_size = (0, 0)  # Track texture size to enable reuse
        self._rect = None  # Persistent rectangle reference for texture updates
        
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
    
    def start_video(self):
        """Start video playback"""
        if not self.video_path or not os.path.exists(self.video_path):
            print(f"Video file not found: {self.video_path}")
            self.show_placeholder()
            return
        
        # Initialize video capture
        self.cap = cv2.VideoCapture(self.video_path)
        self.is_playing = True
        
        if not self.cap.isOpened():
            print("Failed to open video capture")
            self.show_placeholder()
            return
        
        # Get video FPS
        video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0:
            video_fps = 30  # Default to 30 FPS if unable to get FPS
        
        print(f"Video FPS: {video_fps}")
        
        # Start updating frames at the video's actual FPS
        self.video_event = Clock.schedule_interval(self.update_frame, 1/video_fps)
    
    def update_frame(self, dt):
        """Update video frame"""
        if not self.is_playing or not self.cap or not self.cap.isOpened():
            return False
        
        ret, frame = self.cap.read()
        if ret and frame is not None:
            # Convert frame from BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Flip frame vertically (OpenCV uses top-left origin, Kivy uses bottom-left)
            frame = cv2.flip(frame, 0)
            
            # Get widget dimensions (ensure they're integers and not zero)
            widget_w = max(1, int(self.width))
            widget_h = max(1, int(self.height))
            
            # Resize frame to exactly match widget size (stretch to fill)
            frame = cv2.resize(frame, (widget_w, widget_h))
            
            # Reuse existing texture if size matches, otherwise create new one
            current_size = (widget_w, widget_h)
            if self.texture is None or self._texture_size != current_size:
                self.texture = Texture.create(size=current_size)
                self._texture_size = current_size
                # Rebuild canvas only when texture is recreated
                self.canvas.clear()
                with self.canvas:
                    Color(1, 1, 1, 1)
                    self._rect = Rectangle(texture=self.texture, pos=self.pos, size=self.size)
            
            # Update texture buffer (reuses existing GPU texture)
            self.texture.blit_buffer(frame.tobytes(), colorfmt='rgb', bufferfmt='ubyte')
            
            # Update rectangle texture reference and position/size if needed
            if self._rect:
                self._rect.texture = self.texture
                self._rect.pos = self.pos
                self._rect.size = self.size
        else:
            # Restart video when it ends
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
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
        # Reset texture tracking for clean restart
        self._texture_size = (0, 0)
        self._rect = None
    
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
        
        # No overlay - just video (branding removed as requested)
        
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
        """Called when screen is left - stop video in background to avoid UI lag"""
        # Stop video in background thread to prevent blocking UI during transition
        import threading
        threading.Thread(target=self.video_widget.stop_video, daemon=True).start()
    
    def on_touch_down(self, touch):
        """Handle touch to immediately exit screensaver"""
        from kivy.app import App
        app = App.get_running_app()
        
        # Immediately deactivate screensaver on touch
        if app.screensaver_active:
            print("👆 Screensaver touched - exiting immediately")
            app.deactivate_screensaver()
            return True  # Consume the touch event
        
        return super(ScreensaverPage, self).on_touch_down(touch)

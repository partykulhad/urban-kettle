from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle, Ellipse
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.app import App
import os
import math
import random
import requests
import threading
import uuid


class ModernProgressBar(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.progress = 0
        self.size_hint = (None, None)
        self.size = (350, 25)
        self.glow_intensity = 0.0
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        self.start_glow_animation()
        
    def start_glow_animation(self):
        """Subtle glow animation for progress bar"""
        def update_glow(*args):
            self.glow_intensity = (math.sin(Clock.get_time() * 2) + 1) / 2 * 0.3
            self.update_graphics()
        Clock.schedule_interval(update_glow, 1/30)
        
    def update_graphics(self, *args):
        self.canvas.clear()
        with self.canvas:
            # Background shadow
            Color(0, 0, 0, 0.1)
            RoundedRectangle(pos=(self.pos[0] + 2, self.pos[1] - 2), size=self.size, radius=[15])
            
            # Background
            Color(0.95, 0.95, 0.95, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
            
            # Progress fill with gradient effect
            if self.progress > 0:
                progress_width = (self.width * self.progress / 100)
                
                # Main progress fill
                Color(0.714 + self.glow_intensity, 0.478 + self.glow_intensity, 0.176 + self.glow_intensity, 1)
                RoundedRectangle(pos=self.pos, size=(progress_width, self.height), radius=[12])
                
                # Top highlight
                Color(1, 1, 1, 0.4)
                RoundedRectangle(pos=self.pos, size=(progress_width, self.height * 0.4), radius=[12, 12, 5, 5])
                
                # Glow effect
                if self.glow_intensity > 0.1:
                    Color(1, 1, 1, self.glow_intensity)
                    RoundedRectangle(pos=(self.pos[0] - 2, self.pos[1] - 2), 
                                   size=(progress_width + 4, self.height + 4), radius=[14])
    
    def set_progress(self, value):
        self.progress = max(0, min(100, value))
        self.update_graphics()


class ModernSteamEffect(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.steam_particles = []
        self.size_hint = (None, None)
        self.size = (200, 300)
        self.animation_event = None
        
    def start_animation(self):
        """Start the modern steam effect"""
        self.animation_event = Clock.schedule_interval(self.update_steam, 1/60)
    
    def stop_animation(self):
        """Stop the steam effect"""
        if self.animation_event:
            self.animation_event.cancel()
            self.animation_event = None
        self.steam_particles.clear()
    
    def update_steam(self, dt):
        """Update steam particles with modern floating effect"""
        # Add new steam particles
        if len(self.steam_particles) < 12 and random.random() < 0.4:
            self.steam_particles.append({
                'x': self.center_x + random.uniform(-20, 20),
                'y': self.center_y + 40,
                'size': random.uniform(8, 16),
                'alpha': random.uniform(0.3, 0.7),
                'speed': random.uniform(30, 60),
                'drift': random.uniform(-15, 15),
                'life': 0
            })
        
        # Update existing particles
        for particle in self.steam_particles[:]:
            particle['y'] += particle['speed'] * dt
            particle['x'] += particle['drift'] * dt * 0.5
            particle['life'] += dt
            particle['alpha'] *= 0.99  # Fade out
            particle['size'] += dt * 5  # Expand
            
            if particle['alpha'] < 0.1 or particle['y'] > self.top + 50:
                self.steam_particles.remove(particle)
        
        # Redraw
        self.canvas.clear()
        with self.canvas:
            # Draw steam particles
            for particle in self.steam_particles:
                Color(1, 1, 1, particle['alpha'])
                size = particle['size']
                Ellipse(pos=(particle['x'] - size/2, particle['y'] - size/2), size=(size, size))


class CupGlowEffect(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.glow_intensity = 0.0
        self.pulse_offset = 0.0
        self.bind(size=self.update_graphics, pos=self.update_graphics)
        
    def start_glow(self):
        """Start the glowing effect around the cup"""
        def update_glow(*args):
            self.pulse_offset += 0.05
            self.glow_intensity = (math.sin(self.pulse_offset) + 1) / 2 * 0.8 + 0.2
            self.update_graphics()
        Clock.schedule_interval(update_glow, 1/60)
        
    def update_graphics(self, *args):
        self.canvas.clear()
        with self.canvas:
            center_x = self.center_x
            center_y = self.center_y
            
            # Outer glow rings
            for i in range(3):
                radius = 80 + i * 15
                alpha = self.glow_intensity * (0.3 - i * 0.1)
                Color(0.714, 0.478, 0.176, alpha)
                Line(circle=(center_x, center_y, radius), width=3)
            
            # Inner warm glow
            Color(1, 0.8, 0.4, self.glow_intensity * 0.2)
            Ellipse(pos=(center_x - 70, center_y - 70), size=(140, 140))


class PlaceCupPage(Screen):
    """Simple page to instruct user to place cup - matching the design"""
    
    def __init__(self, **kwargs):
        super(PlaceCupPage, self).__init__(**kwargs)
        
        # Main layout - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=10)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top section with logo on left - matching other pages
        from kivy.uix.floatlayout import FloatLayout
        top_section = BoxLayout(orientation='vertical', size_hint_y=0.16, padding=[10, 5])
        
        # Logo on the left
        logo_float = FloatLayout(size_hint_y=0.7)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(230, 200),
                pos_hint={'x': -0.05, 'top': 1.4},  # More left
                allow_stretch=True,
                keep_ratio=True
            )
            logo_float.add_widget(logo_image)
        else:
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='32sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='left'
            )
            logo_float.add_widget(fallback_logo)
        
        top_section.add_widget(logo_float)
        
        # "PAYMENT RECEIVED" text - bigger font
        payment_label = Label(
            text='PAYMENT RECEIVED',
            font_size='38sp',  # Increased from 32sp
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.3
        )
        top_section.add_widget(payment_label)
        
        main_layout.add_widget(top_section)
        
        # Place cup image - bigger
        image_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.35)
        placecup_image_path = os.path.join('assets', 'placecup.png')
        
        if os.path.exists(placecup_image_path):
            placecup_image = Image(
                source=placecup_image_path,
                size_hint=(None, None),
                size=(260, 260),  # Increased from 220
                allow_stretch=True,
                keep_ratio=True
            )
            image_section.add_widget(placecup_image)
        else:
            fallback_widget = Widget(size_hint=(None, None), size=(260, 260))
            with fallback_widget.canvas:
                Color(0.714, 0.478, 0.176, 1)
                RoundedRectangle(pos=(0, 0), size=(260, 260), radius=[20])
            image_section.add_widget(fallback_widget)
        
        main_layout.add_widget(image_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # "Please place your cup in the holder." text - bigger fonts
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.12, spacing=5)
        
        place_label = Label(
            text='Please place your cup',
            font_size='28sp',  # Increased from 24sp
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(place_label)
        
        holder_label = Label(
            text='in the holder.',
            font_size='28sp',  # Increased from 24sp
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(holder_label)
        
        main_layout.add_widget(instruction_section)
        
        # Spacing before button - move button down
        main_layout.add_widget(Widget(size_hint_y=0.02))
        
        # Continue button - bigger with proper text fit
        button_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.11)
        
        # Simple button class for this page
        class SimpleButton(Button):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.background_color = (0, 0, 0, 0)
                self.background_normal = ''
                self.bind(size=self.update_graphics, pos=self.update_graphics)
            
            def update_graphics(self, *args):
                self.canvas.before.clear()
                with self.canvas.before:
                    Color(0.851, 0.647, 0.125, 1)
                    RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
        
        self.continue_button = SimpleButton(
            text='Continue Dispensing',
            font_size='22sp',  # Reduced from 24sp for better fit
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(400, 70)  # Increased width from 340 to fit full text
        )
        self.continue_button.bind(on_press=self.on_continue_pressed)
        self.continue_button.disabled = True
        self.continue_button.opacity = 0.5
        
        button_section.add_widget(self.continue_button)
        main_layout.add_widget(button_section)
        
        # Cup status label - bigger font
        self.cup_status_label = Label(
            text='Waiting for cup...',
            font_size='20sp',  # Increased from 16sp
            color=(0.906, 0.298, 0.235, 1),
            size_hint_y=0.06,
            halign='center'
        )
        main_layout.add_widget(self.cup_status_label)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.03))
        
        self.add_widget(main_layout)
        
        # Cup sensor checking
        self.cup_check_event = None
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def update_cup_info(self, current_cup, total_cups):
        """Update the cup information display (not shown in this design)"""
        pass
    
    def send_dispense_command(self):
        """Send dispense command to ESP32 via polling server
        Returns: (success, status_code, response_data)
        """
        try:
            # Generate unique job ID
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            command_id = f"cmd_dispense_{int(threading.get_ident()) % 1000000}"
            
            print("="*80)
            print("🚀 DISPENSE COMMAND - SENDING TO ESP32")
            print("="*80)
            print(f"🔧 Job ID: {job_id}")
            print(f"🔧 Command ID: {command_id}")
            print(f"🔧 Device ID: UK_14335C5D48C8")
            
            # API endpoint
            url = "http://localhost:5000/api/device/command"
            
            # Prepare the request payload
            payload = {
                "messageType": "command",
                "commandType": "control",
                "version": "1.0",
                "commandId": command_id,
                "deviceId": "UK_14335C5D48C8",
                "command": {
                    "action": "start_dispense",
                    "parameters": {
                        "jobId": job_id
                    }
                }
            }
            
            print(f"🔧 API Endpoint: {url}")
            print(f"🔧 Payload:")
            import json
            print(json.dumps(payload, indent=2))
            print("="*80)
            print("⏳ Sending request to polling server...")
            print("="*80)
            
            # Send POST request with longer timeout for ESP32 response
            response = requests.post(url, json=payload, timeout=30)
            
            print("="*80)
            print("📥 RESPONSE RECEIVED")
            print("="*80)
            print(f"✓ HTTP Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Response JSON:")
                print(json.dumps(result, indent=2))
                
                # Get the status code from ESP32 response
                esp_status_code = result.get('response', {}).get('statusCode', 200)
                status = result.get('response', {}).get('status')
                
                print(f"\n✅ DISPENSE COMMAND SUCCESSFUL!")
                print(f"   Response Status: {status}")
                print(f"   ESP32 Status Code: {esp_status_code}")
                print(f"   Command ID: {result.get('commandId')}")
                print("="*80)
                
                return (True, esp_status_code, result)
            else:
                print(f"❌ DISPENSE COMMAND FAILED")
                print(f"   HTTP Status Code: {response.status_code}")
                print(f"   Response: {response.text}")
                print("="*80)
                return (False, response.status_code, None)
                
        except Exception as e:
            print("="*80)
            print(f"❌ ERROR SENDING DISPENSE COMMAND")
            print("="*80)
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            print("="*80)
            return (False, None, None)
    
    def show_technical_error_popup(self, status_code):
        """Show popup for machine technical issues"""
        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # Error icon/message
        error_label = Label(
            text='⚠️',
            font_size='60sp',
            size_hint_y=0.3
        )
        content.add_widget(error_label)
        
        # Error message
        message_label = Label(
            text='Machine has some technical issue\nPlease wait for some time',
            font_size='20sp',
            halign='center',
            valign='middle',
            size_hint_y=0.4
        )
        message_label.bind(size=message_label.setter('text_size'))
        content.add_widget(message_label)
        
        # Status code info
        code_label = Label(
            text=f'Error Code: {status_code}',
            font_size='16sp',
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=0.2
        )
        content.add_widget(code_label)
        
        # OK button
        ok_button = Button(
            text='OK',
            size_hint_y=0.3,
            font_size='18sp',
            background_color=(0.851, 0.647, 0.125, 1)
        )
        content.add_widget(ok_button)
        
        # Create popup
        popup = Popup(
            title='Technical Issue',
            content=content,
            size_hint=(0.7, 0.5),
            auto_dismiss=False
        )
        
        # Bind OK button to close popup and go home
        def on_ok_press(instance):
            popup.dismiss()
            # Navigate to home page
            app = App.get_running_app()
            Clock.schedule_once(lambda dt: app.show_page('payment_method'), 0.5)
        
        ok_button.bind(on_press=on_ok_press)
        popup.open()
    
    def on_continue_pressed(self, instance):
        """Handle continue button press"""
        print("\n" + "="*80)
        print("🎯 CONFIRM TO DISPENSE BUTTON PRESSED")
        print("="*80)
        
        # Send dispense command in background thread
        def send_command_and_check():
            print("🔄 Starting dispense command in background thread...")
            success, status_code, response_data = self.send_dispense_command()
            
            # Check for technical error codes
            technical_error_codes = [700, 701, 705, 706, 707, 711]
            
            if success and status_code in technical_error_codes:
                # Show error popup on main thread
                print(f"❌ Technical error detected: Status Code {status_code}")
                print("   Showing error popup and returning to home...")
                Clock.schedule_once(lambda dt: self.show_technical_error_popup(status_code), 0)
                
            elif success and status_code == 200:
                # Normal success - proceed with dispensing
                print("✅ Dispense command successful (Status 200)")
                print("   Starting dispensing animation...")
                # Start dispensing animation on main thread
                app = App.get_running_app()
                Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)
                
            elif success:
                # Other status codes - continue with dispensing
                print(f"⚠️ Non-200 status code ({status_code}), but continuing with dispensing...")
                app = App.get_running_app()
                Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)
                
            else:
                # Request failed
                print("❌ Dispense command failed completely")
                print("   Continuing with animation anyway...")
                app = App.get_running_app()
                Clock.schedule_once(lambda dt: app.start_dispensing_current_cup(), 0)
        
        threading.Thread(target=send_command_and_check, daemon=True).start()
        print("="*80 + "\n")
    
    def on_enter(self):
        """Called when page is entered"""
        # Start checking for cup sensor
        self.start_cup_sensor_check()
    
    def on_leave(self):
        """Called when leaving page"""
        # Stop checking cup sensor
        self.stop_cup_sensor_check()
    
    def start_cup_sensor_check(self):
        """Start checking cup sensor status"""
        from utils.hardware_monitor import hardware_monitor
        
        # Check every 0.5 seconds
        self.cup_check_event = Clock.schedule_interval(self.check_cup_sensor, 0.5)
    
    def stop_cup_sensor_check(self):
        """Stop checking cup sensor"""
        if self.cup_check_event:
            self.cup_check_event.cancel()
            self.cup_check_event = None
    
    def check_cup_sensor(self, dt):
        """Check if cup is placed"""
        from utils.hardware_monitor import hardware_monitor
        import threading
        
        # Check in background thread
        threading.Thread(target=self._do_cup_check, daemon=True).start()
    
    def _do_cup_check(self):
        """Actual cup check in background"""
        from utils.hardware_monitor import hardware_monitor
        
        cup_present = hardware_monitor.get_cup_status()
        
        # Update UI on main thread
        Clock.schedule_once(lambda dt: self._update_cup_status(cup_present), 0)
    
    def _update_cup_status(self, cup_present):
        """Update UI based on cup status"""
        # For now, assume cup is always present (dummy mode)
        cup_present = True
        
        if cup_present:
            # Cup detected!
            self.cup_status_label.text = ''
            self.cup_status_label.color = (0.18, 0.8, 0.44, 1)  # Green
            self.continue_button.text = 'Cup Placed - Confirm to Dispense'
            self.continue_button.disabled = False
            self.continue_button.opacity = 1.0
        else:
            # No cup
            self.cup_status_label.text = 'Waiting for cup...'
            self.cup_status_label.color = (0.906, 0.298, 0.235, 1)  # Red
            self.continue_button.text = 'Continue Dispensing'
            self.continue_button.disabled = True
            self.continue_button.opacity = 0.5


class DispensingPage(Screen):
    """Simple dispensing page matching the design with video"""
    
    def __init__(self, **kwargs):
        super(DispensingPage, self).__init__(**kwargs)
        
        # Cup tracking variables
        self.total_cups = 1
        self.current_cup = 1
        
        # Progress tracking
        self.current_progress = 0
        self.progress_event = None
        self.dispensing_duration = 8  # 8 seconds
        
        # Main layout - optimized for 7-inch tablet
        main_layout = BoxLayout(orientation='vertical', padding=[30, 20], spacing=10)
        with main_layout.canvas.before:
            Color(1, 1, 1, 1)  # White background
            self.rect = RoundedRectangle(size=Window.size, pos=self.pos)
        main_layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Top section with logo on left - matching other pages
        from kivy.uix.floatlayout import FloatLayout
        top_section = BoxLayout(orientation='vertical', size_hint_y=0.15, padding=[10, 5])
        
        # Logo on the left
        logo_float = FloatLayout(size_hint_y=0.6)
        logo_path = os.path.join('assets', 'urban_ketl_logo.png')
        
        if os.path.exists(logo_path):
            logo_image = Image(
                source=logo_path,
                size_hint=(None, None),
                size=(230, 200),
                pos_hint={'x': -0.05, 'top': 1.2},  # More left
                allow_stretch=True,
                keep_ratio=True
            )
            logo_float.add_widget(logo_image)
        else:
            fallback_logo = Label(
                text='Urban Ketl',
                font_size='32sp',
                bold=True,
                color=(0.714, 0.478, 0.176, 1),
                halign='left'
            )
            logo_float.add_widget(fallback_logo)
        
        top_section.add_widget(logo_float)
        
        # "DISPENSING..." text - bigger font
        dispensing_label = Label(
            text='DISPENSING...',
            font_size='40sp',  # Increased from 32sp
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.4
        )
        top_section.add_widget(dispensing_label)
        
        main_layout.add_widget(top_section)
        
        # Cup counter - bigger font
        self.cup_counter_label = Label(
            text='Cup 1 of 1',
            font_size='26sp',  # Increased from 20sp
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            halign='center',
            size_hint_y=0.06
        )
        main_layout.add_widget(self.cup_counter_label)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # Video section using OpenCV (same as screensaver)
        video_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.38)
        
        # Import VideoWidget from screensaver
        from ui_pages.screensaver_page import VideoWidget
        
        self.video_widget = VideoWidget(size_hint=(None, None), size=(600, 230))
        video_path = os.path.join('assets', 'dispensing.mp4')
        self.video_widget.set_video_path(video_path)
        
        video_section.add_widget(self.video_widget)
        main_layout.add_widget(video_section)
        
        # Spacing
        main_layout.add_widget(Widget(size_hint_y=0.01))
        
        # Instruction text - bigger fonts
        instruction_section = BoxLayout(orientation='vertical', size_hint_y=0.10, spacing=5)
        
        tea_label = Label(
            text='Your tea is being prepared.',
            font_size='26sp',  # Increased from 22sp
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(tea_label)
        
        wait_label = Label(
            text='Please wait.',
            font_size='26sp',  # Increased from 22sp
            color=(0.3, 0.3, 0.3, 1),
            halign='center'
        )
        instruction_section.add_widget(wait_label)
        
        main_layout.add_widget(instruction_section)
        
        # Progress bar section - bigger
        progress_section = AnchorLayout(anchor_x='center', anchor_y='center', size_hint_y=0.13)
        progress_container = BoxLayout(orientation='vertical', size_hint=(None, None), 
                                     size=(400, 65), spacing=10)  # Increased size
        
        # Progress bar
        self.progress_bar = ModernProgressBar()
        self.progress_bar.size = (400, 28)  # Bigger progress bar
        progress_container.add_widget(self.progress_bar)
        
        # Progress percentage - bigger font
        self.progress_label = Label(
            text='0%',
            font_size='24sp',  # Increased from 18sp
            bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=None,
            height='28sp'
        )
        progress_container.add_widget(self.progress_label)
        
        progress_section.add_widget(progress_container)
        main_layout.add_widget(progress_section)
        
        # Bottom spacing
        main_layout.add_widget(Widget(size_hint_y=0.05))
        
        self.add_widget(main_layout)
    
    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos
    
    def set_cup_info(self, current_cup, total_cups):
        """Set the cup information for display"""
        self.current_cup = current_cup
        self.total_cups = total_cups
        self.cup_counter_label.text = f'Cup {current_cup} of {total_cups}'
    
    def start_dispensing_animation(self):
        """Start the dispensing animation"""
        # Reset progress
        self.current_progress = 0
        self.progress_bar.set_progress(0)
        self.progress_label.text = '0%'
        
        # Start video if available
        if hasattr(self, 'video_widget'):
            self.video_widget.start_video()
        
        # Start progress animation (8 seconds total)
        self.progress_event = Clock.schedule_interval(self.update_progress, 0.08)  # 100 steps in 8 seconds
    
    def update_progress(self, dt):
        """Update progress bar and percentage"""
        self.current_progress += 1  # 1% every 0.08 seconds = 8 seconds total
        
        if self.current_progress <= 100:
            self.progress_bar.set_progress(self.current_progress)
            self.progress_label.text = f'{int(self.current_progress)}%'
            return True
        else:
            # Dispensing complete
            self.stop_animations()
            # Check if more cups need to be dispensed
            app = App.get_running_app()
            Clock.schedule_once(lambda dt: app.handle_cup_completion(), 1.0)
            return False
    
    def stop_animations(self):
        """Stop all animations"""
        if self.progress_event:
            self.progress_event.cancel()
            self.progress_event = None
        
        # Stop video if available
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()
    
    def on_enter(self):
        """Called when entering the screen"""
        # Ensure video starts playing
        if hasattr(self, 'video_widget'):
            self.video_widget.start_video()
    
    def on_leave(self):
        """Called when leaving the screen"""
        # Stop video when leaving
        if hasattr(self, 'video_widget'):
            self.video_widget.stop_video()
        
        self.steam_effect.stop_animation()
    
    def on_enter(self):
        """Called when screen is entered"""
        self.last_status_index = -1
        self.start_dispensing_animation()
    
    def on_leave(self):
        """Called when screen is left"""
        self.stop_animations()

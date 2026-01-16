#!/usr/bin/env python3
"""
Test script to run the dispensing page directly for testing purposes.
This allows you to see how the dispensing animation works in isolation.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.clock import Clock
from ui_pages.dispensing_page import DispensingPage


class TestDispensingApp(App):
    def build(self):
        self.title = "Test Dispensing Animation"
        
        # Set window size to match main app
        Window.size = (1024, 600)
        
        # Cup management variables for testing
        self.selected_cups = 1  # Test with 1 cup
        self.current_cup_number = 1
        
        # Create screen manager
        self.screen_manager = ScreenManager()
        
        # Add only dispensing page
        self.dispensing_page = DispensingPage(name='dispensing')
        self.screen_manager.add_widget(self.dispensing_page)
        
        # Start directly with dispensing
        self.screen_manager.current = 'dispensing'
        
        # Initialize the dispensing page
        Clock.schedule_once(lambda dt: self.start_dispensing(), 0.5)
        
        return self.screen_manager
    
    def start_dispensing(self):
        """Start the dispensing animation"""
        print(f"🚀 Starting dispensing animation - Cup {self.current_cup_number} of {self.selected_cups}")
        self.dispensing_page.set_cup_info(self.current_cup_number, self.selected_cups)
        self.dispensing_page.start_dispensing_animation()
    
    def handle_cup_completion(self):
        """Handle completion of dispensing (called by DispensingPage)"""
        print(f"✅ Dispensing completed! Restarting in 2 seconds...")
        # Restart the animation after 2 seconds
        Clock.schedule_once(lambda dt: self.start_dispensing(), 2.0)
    
    def show_thank_you_page(self):
        """Placeholder method (called by DispensingPage)"""
        print("📝 Dispensing complete - would show thank you page")
        self.handle_cup_completion()


if __name__ == "__main__":
    TestDispensingApp().run()

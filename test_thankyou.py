#!/usr/bin/env python3
"""
Test script to run the thank you page directly for testing purposes.
This allows you to see how the thank you animations work in isolation.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from ui_pages.thank_you_page import ThankYouPage

class TestThankYouApp(App):
    def build(self):
        self.title = "Test Thank You Page"
        
        # Set window size to match main app
        Window.size = (800, 600)
        
        # Create screen manager
        screen_manager = ScreenManager()
        
        # Add thank you page
        thank_you_page = ThankYouPage(name='thankyou')
        screen_manager.add_widget(thank_you_page)
        
        # Set initial screen
        screen_manager.current = 'thankyou'
        
        return screen_manager

if __name__ == "__main__":
    TestThankYouApp().run()
#!/usr/bin/env python3
"""
Simple test script to view the Heating Page UI
This bypasses the temperature check and shows the page directly
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from ui_pages.heating_page import HeatingPage
from kivy.clock import Clock

class TestHeatingApp(App):
    def build(self):
        # Create screen manager
        sm = ScreenManager()
        
        # Add heating page
        heating_page = HeatingPage(name='heating')
        sm.add_widget(heating_page)
        
        # Show heating page
        sm.current = 'heating'
        
        # Simulate temperature updates
        def update_temp(dt):
            import random
            # Simulate temperature rising from 25°C to 80°C
            temp = 25 + (dt * 5) + random.uniform(-1, 1)
            if temp < 80:
                heating_page.update_temperature(temp)
                print(f"Current temperature: {temp:.1f}°C")
            else:
                heating_page.update_temperature(80)
                print(f"✅ Target reached: 80°C")
                return False  # Stop updates
            
            return True  # Continue updates
        
        # Update temperature every second
        Clock.schedule_interval(update_temp, 1)
        
        print("=" * 60)
        print("🔥 HEATING PAGE TEST")
        print("=" * 60)
        print("The heating page will display with simulated temperature")
        print("Temperature will rise from ~25°C to 80°C")
        print("Press Ctrl+C to exit")
        print("=" * 60)
        
        return sm

if __name__ == "__main__":
    TestHeatingApp().run()

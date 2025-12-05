#!/usr/bin/env python3
"""
Test script to run the dispensing page directly for testing purposes.
This allows you to see how the dispensing animation works in isolation with multi-cup functionality.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.clock import Clock
from ui_pages.dispensing_page import DispensingPage, PlaceCupPage


class TestDispensingApp(App):
    def build(self):
        self.title = "Test Dispensing Page - Multi Cup"
        
        # Set window size to match main app
        Window.size = (1024, 600)
        
        # Cup management variables for testing
        self.selected_cups = 3  # Test with 3 cups (you can change this)
        self.current_cup_number = 1
        
        # Create screen manager
        self.screen_manager = ScreenManager()
        
        # Add both place cup and dispensing pages
        self.place_cup_page = PlaceCupPage(name='place_cup')
        self.dispensing_page = DispensingPage(name='dispensing')
        
        self.screen_manager.add_widget(self.place_cup_page)
        self.screen_manager.add_widget(self.dispensing_page)
        
        # Start with place cup page
        self.screen_manager.current = 'place_cup'
        
        # Initialize the test
        self.start_test_cycle()
        
        return self.screen_manager
    
    def start_test_cycle(self):
        """Start the test cycle"""
        self.current_cup_number = 1
        print(f"🚀 Starting test cycle with {self.selected_cups} cups")
        self.show_place_cup_page()
    
    def show_place_cup_page(self):
        """Show the place cup page with current cup info"""
        print(f"📄 Showing place cup page - Cup {self.current_cup_number} of {self.selected_cups}")
        self.place_cup_page.update_cup_info(self.current_cup_number, self.selected_cups)
        self.screen_manager.current = 'place_cup'
    
    def start_dispensing_current_cup(self):
        """Start dispensing for the current cup (called by PlaceCupPage)"""
        print(f"☕ Starting dispensing for cup {self.current_cup_number} of {self.selected_cups}")
        self.dispensing_page.set_cup_info(self.current_cup_number, self.selected_cups)
        self.screen_manager.current = 'dispensing'
    
    def handle_cup_completion(self):
        """Handle completion of a single cup (called by DispensingPage)"""
        print(f"✅ Cup {self.current_cup_number} of {self.selected_cups} completed")
        
        if self.current_cup_number < self.selected_cups:
            # More cups to dispense
            self.current_cup_number += 1
            print(f"➡️  Moving to cup {self.current_cup_number} of {self.selected_cups}")
            # Show place cup page for next cup after a short delay
            Clock.schedule_once(lambda dt: self.show_place_cup_page(), 1.5)
        else:
            # All cups completed
            print(f"🎉 All {self.selected_cups} cups completed! Restarting test in 3 seconds...")
            # Restart the test cycle
            Clock.schedule_once(lambda dt: self.start_test_cycle(), 3.0)
    
    def show_thank_you_page(self):
        """Placeholder method (called by DispensingPage if no handle_cup_completion exists)"""
        print("📝 Thank you page would be shown here")
        self.handle_cup_completion()


# Alternative test configurations
class TestDispensingApp1Cup(TestDispensingApp):
    """Test with only 1 cup"""
    def build(self):
        result = super().build()
        self.selected_cups = 1
        self.start_test_cycle()
        return result


class TestDispensingApp5Cups(TestDispensingApp):
    """Test with 5 cups"""
    def build(self):
        result = super().build()
        self.selected_cups = 5
        self.start_test_cycle()
        return result


if __name__ == "__main__":
    # You can change which test to run:
    
    # Test with 3 cups (default)
    TestDispensingApp().run()
    
    # Uncomment one of these to test different scenarios:
    # TestDispensingApp1Cup().run()  # Test with 1 cup
    # TestDispensingApp5Cups().run()  # Test with 5 cups

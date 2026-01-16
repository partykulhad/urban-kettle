from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from ui_pages.place_cup_page import PlaceCupPage

# Set window size for 7-inch tablet (1024x600)
Window.size = (1024, 600)


class TestPlaceCupApp(App):
    def build(self):
        # Create screen manager
        self.sm = ScreenManager()
        
        # Add cup tracking attributes for testing multi-cup flow
        self.selected_cups = 3  # Test with 3 cups
        self.current_cup_number = 1  # Start with cup 1
        
        # Add place cup page
        self.place_cup_page = PlaceCupPage(name='place_cup')
        self.sm.add_widget(self.place_cup_page)
        
        # Set current screen
        self.sm.current = 'place_cup'
        
        return self.sm
    
    def show_payment_method_page(self):
        """Mock method for testing - just print message"""
        print("🏠 Would navigate to payment method page (test mode)")
        print("   In real app, this would show the payment method page")
        App.get_running_app().stop()  # Stop app when going home
    
    def handle_cup_completion(self):
        """Mock method for testing multi-cup flow"""
        print(f"Cup {self.current_cup_number} of {self.selected_cups} completed")
        
        if self.current_cup_number < self.selected_cups:
            # More cups to dispense
            self.current_cup_number += 1
            print(f"Moving to cup {self.current_cup_number} of {self.selected_cups}")
            # Reset the page for the next cup (this triggers on_enter)
            self.place_cup_page.on_enter()
        else:
            # All cups completed
            print("All cups completed! Would show thank you page")
            self.show_payment_method_page()
    
    def start_dispensing_current_cup(self):
        """Mock method for testing - just print message"""
        print("💧 Would start dispensing (test mode)")
        print("   In real app, this would navigate to dispensing page")
        print("   Button click was successful!")


if __name__ == '__main__':
    TestPlaceCupApp().run()

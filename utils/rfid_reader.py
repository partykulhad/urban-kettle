#!/usr/bin/env python3
"""
RFID Reader Module for automatic card detection
"""

import threading
import time
import os
from kivy.clock import Clock
from kivy.core.window import Window


class RFIDReader:
    """RFID Reader class to handle automatic card detection using keyboard events"""
    
    def __init__(self):
        self.is_listening = False
        self.callback = None
        self.last_card_time = 0
        self.card_buffer = ""
        self.last_key_time = 0
        self.card_input_timeout = 0.1  # 100ms timeout for card input
        
    def start_listening(self, callback):
        """Start listening for RFID card input via keyboard events"""
        self.callback = callback
        self.is_listening = True
        
        # Bind to Kivy window keyboard events - this should work for RFID readers
        # that act as HID keyboard devices
        Window.bind(on_key_down=self.on_key_down)
        
        # Also bind to text input events
        Window.bind(on_textinput=self.on_text_input)
        
        print("🏷️ RFID Reader started - listening for card taps...")
    
    def stop_listening(self):
        """Stop listening for RFID card input"""
        self.is_listening = False
        self.callback = None
        
        # Unbind keyboard events
        Window.unbind(on_key_down=self.on_key_down)
        Window.unbind(on_textinput=self.on_text_input)
        
        print("🏷️ RFID Reader stopped")
    
    def on_text_input(self, window, text):
        """Handle text input events (alternative method)"""
        if not self.is_listening:
            return False
        
        # If we get a complete card number at once
        if text and text.isdigit() and len(text) >= 8:
            self._process_card_input(text)
            return True
        
        return False
    
    def on_key_down(self, window, key, scancode, codepoint, modifier):
        """Handle keyboard input from RFID reader"""
        if not self.is_listening:
            return False
        
        current_time = time.time()
        
        # Check if this is part of a card number sequence
        if codepoint and codepoint.isdigit():
            # If too much time has passed since last digit, start new card
            if current_time - self.last_key_time > self.card_input_timeout:
                self.card_buffer = ""
            
            # Add digit to buffer
            self.card_buffer += codepoint
            self.last_key_time = current_time
            
            # Schedule card processing check
            Clock.schedule_once(self.check_card_complete, self.card_input_timeout)
            
            return True  # Consume the key event
        
        elif key == 13:  # Enter key - RFID readers often send this after card number
            if self.card_buffer and len(self.card_buffer) >= 8:
                self._process_card_input(self.card_buffer)
            self.card_buffer = ""
            return True
        
        return False
    
    def check_card_complete(self, dt):
        """Check if card input is complete after timeout"""
        current_time = time.time()
        
        # If enough time has passed and we have a valid card number
        if (current_time - self.last_key_time >= self.card_input_timeout and 
            self.card_buffer and len(self.card_buffer) >= 8):
            
            self._process_card_input(self.card_buffer)
            self.card_buffer = ""
    
    def _process_card_input(self, card_number):
        """Process detected card input"""
        current_time = time.time()
        
        # Prevent duplicate reads within 3 seconds
        if current_time - self.last_card_time < 3:
            print(f"🏷️ Duplicate card scan ignored: {card_number}")
            return
        
        self.last_card_time = current_time
        
        print(f"🏷️ RFID Card Detected: {card_number}")
        
        # Schedule callback on main thread
        if self.callback:
            Clock.schedule_once(lambda dt: self.callback(card_number))
    
    def simulate_card_tap(self, card_number):
        """Simulate a card tap for testing purposes"""
        if self.callback:
            print(f"🏷️ Simulating RFID Card: {card_number}")
            Clock.schedule_once(lambda dt: self.callback(card_number))


# Global RFID reader instance
rfid_reader = RFIDReader()
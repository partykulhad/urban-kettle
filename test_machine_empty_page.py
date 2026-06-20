#!/usr/bin/env python3
"""
Simple test script to view the Machine Empty / Under Maintenance page UI.
No hardware, no ESP32, no Kulhad connection needed.

Press 1 -> 'empty' mode      (low cup count — "Refill on its way")
Press 2 -> 'offline' mode    ("Under Maintenance")
Press 3 -> 'water_low' mode  ("Under Maintenance")
Press Ctrl+C to exit.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from ui_pages.machine_empty_page import MachineEmptyPage

# Windowed desktop view, not fullscreen/rotated — same pattern main_app.py
# uses for UK_TEST_MODE.
Window.size = (881, 661)
Window.resizable = True


class TestMachineEmptyApp(App):
    def build(self):
        sm = ScreenManager()
        self.page = MachineEmptyPage(name='machine_empty')
        sm.add_widget(self.page)
        sm.current = 'machine_empty'

        def on_key(window, key, *args):
            if key == ord('1'):
                self.page.set_mode('empty')
                print("-> mode: empty")
            elif key == ord('2'):
                self.page.set_mode('offline')
                print("-> mode: offline")
            elif key == ord('3'):
                self.page.set_mode('water_low')
                print("-> mode: water_low")
            return False

        Window.bind(on_key_down=on_key)

        print("=" * 60)
        print("🚧 MACHINE EMPTY / UNDER MAINTENANCE PAGE TEST")
        print("=" * 60)
        print("Press 1 -> empty mode      (\"Refill on its way\")")
        print("Press 2 -> offline mode    (\"Under Maintenance\")")
        print("Press 3 -> water_low mode  (\"Under Maintenance\")")
        print("Press Ctrl+C to exit")
        print("=" * 60)

        return sm


if __name__ == "__main__":
    TestMachineEmptyApp().run()

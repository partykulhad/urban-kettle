"""
Urban Kettle — Live UI Test (No Hardware Required)
===================================================
Fetches real data from Kulhad API and runs a full UI simulation.

What this tests:
  - All Kulhad API calls (machine status, cups, ml, price)
  - Dispensing video at correct pump-matched speed
  - Heating page animation
  - Payment method page layout
  - Thank you page
  - QR payment page (generates a real QR, auto-cancels it)

Run:
    cd urban-kettle-withRFID
    python3 test_live_ui.py
"""

import os
import sys
import threading
import time

# ── Must be set before Kivy imports ──────────────────────────────────────────
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.core.window import Window
from kivy.clock import Clock

Window.size = (881, 661)

# ── Kulhad API fetch ──────────────────────────────────────────────────────────
MACHINE_ID  = "KH-03"
BASE_URL    = "https://kulhad.vercel.app/api"
PUMP_RATE   = 9.0   # ml/s  (540 ml/min)

kulhad_data = {
    "status":           "fetching...",
    "cups":             "...",
    "ml_to_dispense":   90.0,
    "price":            "...",
    "flush_minutes":    "...",
    "pump_duration_s":  10.0,
    "pump_duration_ms": 10000,
    "machine_name":     "...",
    "error":            None,
}

def fetch_kulhad():
    import requests
    try:
        # Machine status
        r = requests.get(f"{BASE_URL}/MachinesStatus?machineId={MACHINE_ID}", timeout=5)
        d = r.json().get("data", {})
        kulhad_data["status"]       = d.get("status", "unknown")
        kulhad_data["machine_name"] = d.get("machineName", "")

        # Machine data
        r = requests.get(f"{BASE_URL}/getMachineData?machineId={MACHINE_ID}", timeout=5)
        d = r.json().get("data", {})
        ml_raw = float(d.get("mlToDispense", 90))
        ml     = ml_raw if ml_raw >= 50 else 90.0
        kulhad_data["ml_to_dispense"]   = ml
        kulhad_data["price"]            = d.get("price", "?")
        kulhad_data["flush_minutes"]    = d.get("flushTimeMinutes", "?")
        kulhad_data["pump_duration_s"]  = round(ml / PUMP_RATE, 2)
        kulhad_data["pump_duration_ms"] = round((ml / PUMP_RATE) * 1000)

        # Cups
        r = requests.post(f"{BASE_URL}/reduce-cups",
                          json={"machineId": MACHINE_ID, "cupsToReduce": 0}, timeout=5)
        kulhad_data["cups"] = r.json().get("cups", "?")

        print(f"✅ Kulhad data loaded: {kulhad_data}")
    except Exception as e:
        kulhad_data["error"] = str(e)
        print(f"❌ Kulhad fetch error: {e}")


# ── Reusable button style ─────────────────────────────────────────────────────
class FlatButton(Button):
    def __init__(self, bg=(0.949, 0.6, 0.0, 1), **kwargs):
        super().__init__(**kwargs)
        self.background_normal  = ""
        self.background_color   = (0, 0, 0, 0)
        self._bg = bg
        self.bind(size=self._draw, pos=self._draw)

    def _draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[12])


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — Dashboard
# ══════════════════════════════════════════════════════════════════════════════
class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=20, spacing=12)
        with root.canvas.before:
            Color(0.97, 0.97, 0.97, 1)
            self._bg = Rectangle(size=Window.size)
        root.bind(size=lambda i, v: setattr(self._bg, "size", v))

        # Title
        root.add_widget(Label(
            text="Urban Kettle — Live UI Test",
            font_size="26sp", bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=None, height=50
        ))

        # Status card
        self.status_label = Label(
            text="Fetching Kulhad data...",
            font_size="16sp",
            color=(0.2, 0.2, 0.2, 1),
            halign="left", valign="top",
            size_hint_y=None, height=200,
            text_size=(820, None)
        )
        root.add_widget(self.status_label)

        # Button grid
        grid = GridLayout(cols=3, spacing=10, size_hint_y=None, height=160)

        btns = [
            ("🫖  Dispensing\n    Video",     (0.18, 0.52, 0.89, 1), "dispensing"),
            ("💳  Payment\n    Method",       (0.949, 0.6, 0.0, 1),  "payment_method"),
            ("🔥  Heating\n    Page",         (0.85, 0.33, 0.1, 1),  "heating"),
            ("✅  Thank You\n    Page",        (0.18, 0.7, 0.44, 1),  "thankyou"),
            ("📷  QR Payment\n    (live)",     (0.5, 0.18, 0.89, 1),  "qr_payment"),
            ("🔄  Refresh\n    Kulhad",        (0.4, 0.4, 0.4, 1),    "refresh"),
        ]
        for text, color, target in btns:
            b = FlatButton(
                text=text, bg=color,
                font_size="15sp", bold=True,
                color=(1, 1, 1, 1)
            )
            b.bind(on_press=lambda _, t=target: self.go(t))
            grid.add_widget(b)

        root.add_widget(grid)
        root.add_widget(Widget())  # spacer
        self.add_widget(root)

    def on_enter(self):
        self.refresh_display()

    def refresh_display(self):
        err = kulhad_data.get("error")
        if err:
            txt = f"[ERROR] {err}"
        else:
            txt = (
                f"Machine:       {kulhad_data['machine_name']}  ({MACHINE_ID})\n"
                f"Status:        {kulhad_data['status'].upper()}\n"
                f"Cups:          {kulhad_data['cups']}\n"
                f"Price:         ₹{kulhad_data['price']} per cup\n"
                f"ml to dispense:{kulhad_data['ml_to_dispense']} ml\n"
                f"Pump duration: {kulhad_data['pump_duration_ms']} ms  "
                f"({kulhad_data['pump_duration_s']}s)\n"
                f"Flush timer:   {kulhad_data['flush_minutes']} min after last dispense\n"
                f"Flow rate:     {PUMP_RATE} ml/s  (540 ml/min)"
            )
        self.status_label.text = txt

    def go(self, target):
        if target == "refresh":
            self.status_label.text = "Refreshing..."
            threading.Thread(target=self._do_refresh, daemon=True).start()
        else:
            self.manager.current = target

    def _do_refresh(self):
        fetch_kulhad()
        Clock.schedule_once(lambda _: self.refresh_display())


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — Dispensing video
# ══════════════════════════════════════════════════════════════════════════════
class DispensingTestScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = Rectangle(size=Window.size)
        root.bind(size=lambda i, v: setattr(self._bg, "size", v))

        # Import the real dispensing page
        sys.path.insert(0, os.path.dirname(__file__))
        from ui_pages.dispensing_page import DispensingPage

        self.disp_page = DispensingPage(name="_disp_inner")
        self.disp_page.size_hint = (1, 1)
        root.add_widget(self.disp_page)

        # Override completion to return to dashboard
        original_handle = self.disp_page.handle_completion
        def patched_completion():
            original_handle()
        self.disp_page.handle_completion = patched_completion

        # Back button overlay
        from kivy.uix.floatlayout import FloatLayout
        overlay = FloatLayout()
        back = FlatButton(
            text="← Back",
            bg=(0.5, 0.5, 0.5, 0.85),
            size_hint=(None, None), size=(110, 40),
            pos_hint={"x": 0.01, "top": 0.99},
            font_size="14sp", color=(1, 1, 1, 1)
        )
        back.bind(on_press=lambda _: self._back())
        overlay.add_widget(back)

        # Info label
        self.info_lbl = Label(
            text="",
            font_size="13sp",
            color=(0.3, 0.3, 0.3, 1),
            size_hint=(None, None), size=(340, 30),
            pos_hint={"right": 0.99, "top": 0.99},
            halign="right"
        )
        overlay.add_widget(self.info_lbl)

        self.add_widget(root)
        self.add_widget(overlay)

    def on_enter(self):
        ml  = kulhad_data["ml_to_dispense"]
        dur = kulhad_data["pump_duration_s"]
        self.info_lbl.text = f"{ml} ml  →  {dur}s  (simulated)"

        # Set cup info and pump duration on the real dispensing page
        self.disp_page.set_cup_info(1, 1)

        # Inject ml_to_dispense so the video widget gets the right duration
        app = App.get_running_app()
        app.ml_to_dispense = ml

        self.disp_page.on_enter()

        # Simulate dispensing starting after 1.5s and completing after pump duration
        Clock.schedule_once(lambda _: self._simulate_pump_start(), 1.5)

    def _simulate_pump_start(self):
        self.disp_page.has_started_dispensing = True
        dur = kulhad_data["pump_duration_s"]
        print(f"🔧 Simulated pump start — will complete in {dur}s")
        Clock.schedule_once(lambda _: self._simulate_pump_done(), dur)

    def _simulate_pump_done(self):
        print("✅ Simulated pump complete")
        # Inject a completed state into the dispensing page
        self.disp_page._update_pump_state({
            "pumpState": "completed",
            "progress": 100,
            "elapsedTime": int(kulhad_data["pump_duration_ms"]),
            "remainingTime": 0
        })

    def _back(self):
        self.disp_page.on_leave()
        self.manager.current = "dashboard"


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — Payment Method
# ══════════════════════════════════════════════════════════════════════════════
class PaymentMethodTestScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")

        from ui_pages.payment_method_page import PaymentMethodPage
        self.pm_page = PaymentMethodPage(name="_pm_inner")
        root.add_widget(self.pm_page)

        from kivy.uix.floatlayout import FloatLayout
        overlay = FloatLayout()
        back = FlatButton(
            text="← Back", bg=(0.5, 0.5, 0.5, 0.85),
            size_hint=(None, None), size=(110, 40),
            pos_hint={"x": 0.01, "top": 0.99},
            font_size="14sp", color=(1, 1, 1, 1)
        )
        back.bind(on_press=lambda _: self._back())
        overlay.add_widget(back)
        self.add_widget(root)
        self.add_widget(overlay)

    def on_enter(self):
        app = App.get_running_app()
        app.local_cups_count     = kulhad_data["cups"]
        app.cups_count_initialized = True
        self.pm_page.on_enter()

    def _back(self):
        try:
            self.pm_page.on_leave()
        except Exception:
            pass
        self.manager.current = "dashboard"


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — Heating page
# ══════════════════════════════════════════════════════════════════════════════
class HeatingTestScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")

        from ui_pages.heating_page import HeatingPage
        self.h_page = HeatingPage(name="_h_inner")
        root.add_widget(self.h_page)

        from kivy.uix.floatlayout import FloatLayout
        overlay = FloatLayout()
        back = FlatButton(
            text="← Back", bg=(0.5, 0.5, 0.5, 0.85),
            size_hint=(None, None), size=(110, 40),
            pos_hint={"x": 0.01, "top": 0.99},
            font_size="14sp", color=(1, 1, 1, 1)
        )
        back.bind(on_press=lambda _: self._back())
        overlay.add_widget(back)

        self.temp_lbl = Label(
            text="", font_size="13sp", color=(0.3, 0.3, 0.3, 1),
            size_hint=(None, None), size=(300, 30),
            pos_hint={"right": 0.99, "top": 0.99}, halign="right"
        )
        overlay.add_widget(self.temp_lbl)
        self.add_widget(root)
        self.add_widget(overlay)
        self._tick_event = None

    def on_enter(self):
        self._sim_temp = 45.0
        self.h_page.update_temperature(self._sim_temp)
        self.h_page.on_enter()
        self._tick_event = Clock.schedule_interval(self._tick_temp, 1.5)

    def _tick_temp(self, _):
        self._sim_temp = min(self._sim_temp + 2.5, 85.0)
        self.h_page.update_temperature(self._sim_temp)
        self.temp_lbl.text = f"Simulated: {self._sim_temp:.1f}°C / {kulhad_data.get('ml_to_dispense',90):.0f}ml"
        if self._sim_temp >= 80.0:
            self._tick_event.cancel()
            self._tick_event = None
            self.temp_lbl.text = "✅ Ready!"

    def _back(self):
        if self._tick_event:
            self._tick_event.cancel()
            self._tick_event = None
        try:
            self.h_page.on_leave()
        except Exception:
            pass
        self.manager.current = "dashboard"


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 5 — Thank You
# ══════════════════════════════════════════════════════════════════════════════
class ThankYouTestScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")

        from ui_pages.thank_you_page import ThankYouPage
        self.ty_page = ThankYouPage(name="_ty_inner")
        root.add_widget(self.ty_page)

        from kivy.uix.floatlayout import FloatLayout
        overlay = FloatLayout()
        back = FlatButton(
            text="← Back", bg=(0.5, 0.5, 0.5, 0.85),
            size_hint=(None, None), size=(110, 40),
            pos_hint={"x": 0.01, "top": 0.99},
            font_size="14sp", color=(1, 1, 1, 1)
        )
        back.bind(on_press=lambda _: self._back())
        overlay.add_widget(back)
        self.add_widget(root)
        self.add_widget(overlay)

    def on_enter(self):
        self.ty_page.on_enter()

    def _back(self):
        try:
            self.ty_page.on_leave()
        except Exception:
            pass
        self.manager.current = "dashboard"


# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 6 — Live QR Payment
# ══════════════════════════════════════════════════════════════════════════════
class QRPaymentTestScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._qr_id = None

        root = BoxLayout(orientation="vertical", padding=30, spacing=15)
        with root.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = Rectangle(size=Window.size)
        root.bind(size=lambda i, v: setattr(self._bg, "size", v))

        root.add_widget(Label(
            text="Live QR Payment Test",
            font_size="22sp", bold=True,
            color=(0.714, 0.478, 0.176, 1),
            size_hint_y=None, height=45
        ))

        self.status_lbl = Label(
            text="Press Generate to create a real Razorpay QR",
            font_size="16sp", color=(0.3, 0.3, 0.3, 1),
            halign="center", size_hint_y=None, height=40,
            text_size=(820, None)
        )
        root.add_widget(self.status_lbl)

        from ui_pages.payment_page import PaymentPage
        self.pay_page = PaymentPage(name="_pay_inner")
        self.pay_page.size_hint_y = 0.75
        root.add_widget(self.pay_page)

        btn_row = BoxLayout(size_hint_y=None, height=55, spacing=15)
        self.gen_btn = FlatButton(
            text="Generate QR", bg=(0.18, 0.52, 0.89, 1),
            font_size="16sp", bold=True, color=(1, 1, 1, 1)
        )
        self.gen_btn.bind(on_press=lambda _: self._generate())

        self.cancel_btn = FlatButton(
            text="Cancel QR", bg=(0.85, 0.2, 0.2, 1),
            font_size="16sp", bold=True, color=(1, 1, 1, 1)
        )
        self.cancel_btn.bind(on_press=lambda _: self._cancel())
        self.cancel_btn.disabled = True

        back_btn = FlatButton(
            text="← Back", bg=(0.5, 0.5, 0.5, 1),
            font_size="16sp", color=(1, 1, 1, 1)
        )
        back_btn.bind(on_press=lambda _: self._back())

        btn_row.add_widget(self.gen_btn)
        btn_row.add_widget(self.cancel_btn)
        btn_row.add_widget(back_btn)
        root.add_widget(btn_row)
        self.add_widget(root)

    def _generate(self):
        self.gen_btn.disabled = True
        self.status_lbl.text = "⏳ Calling Kulhad API..."
        threading.Thread(target=self._do_generate, daemon=True).start()

    def _do_generate(self):
        import requests, qrcode
        from PIL import Image as PILImage
        try:
            r = requests.post(
                "https://kulhad.vercel.app/api/direct-payment",
                json={"machineId": MACHINE_ID, "numberOfCups": 1},
                timeout=10
            )
            data = r.json()
            self._qr_id = data.get("id")
            content    = data.get("imageContent", "")
            amount     = data.get("amount", "?")
            expires_at = data.get("expiresAt", 0)
            expires_in = max(0, expires_at - int(time.time()))

            # Generate QR image
            qr = qrcode.QRCode(box_size=6, border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(content)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

            Clock.schedule_once(lambda _: self._show_qr(img, data, expires_in))
        except Exception as e:
            Clock.schedule_once(lambda _: self._set_status(f"❌ Error: {e}"))
            Clock.schedule_once(lambda _: setattr(self.gen_btn, 'disabled', False))

    def _show_qr(self, pil_img, data, expires_in):
        self._qr_id = data.get("id")
        self.pay_page.update(pil_img, data)
        self.pay_page.set_timer_callback(lambda: self._on_timer_expired())
        self.status_lbl.text = (
            f"✅ QR generated!  Amount: ₹{data.get('amount')}  "
            f"ID: {self._qr_id}  Expires in: ~{expires_in}s"
        )
        self.cancel_btn.disabled = False

    def _on_timer_expired(self):
        self.status_lbl.text = "⏱️ QR timer expired — cancelling..."
        self._cancel()

    def _cancel(self):
        if not self._qr_id:
            return
        qr_id = self._qr_id
        self._qr_id = None
        self.cancel_btn.disabled = True
        self.gen_btn.disabled = False
        self.status_lbl.text = f"Cancelling {qr_id}..."
        threading.Thread(target=lambda: self._do_cancel(qr_id), daemon=True).start()

    def _do_cancel(self, qr_id):
        import requests
        try:
            r = requests.post(
                "https://kulhad.vercel.app/api/qrcode-close",
                json={"qrCodeId": qr_id}, timeout=5
            )
            msg = "✅ QR cancelled" if r.json().get("success") else "⚠️ Cancel failed"
        except Exception as e:
            msg = f"❌ Cancel error: {e}"
        Clock.schedule_once(lambda _: self._set_status(msg))

    def _set_status(self, msg):
        self.status_lbl.text = msg

    def _back(self):
        if self._qr_id:
            self._cancel()
        try:
            self.pay_page.stop_timer()
        except Exception:
            pass
        self.manager.current = "dashboard"


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════
class TestApp(App):
    def build(self):
        self.title = "Urban Kettle — Live Test"

        # Minimal app state expected by pages
        self.MACHINE_ID             = MACHINE_ID
        self.ml_to_dispense         = kulhad_data["ml_to_dispense"]
        self.local_cups_count       = kulhad_data["cups"]
        self.cups_count_initialized = False
        self.selected_cups          = 1
        self.current_cup_number     = 1
        self.rfid_auth_handler      = None
        self.screensaver_active     = False
        self._current_page          = "dashboard"

        # Stub api_client so dispensing_page pump polling fails silently
        class _ApiStub:
            def get_pump_status(self, *a, **kw): return None
            def generate_payment_qr(self, *a, **kw): return None
            def check_payment_status(self, *a, **kw): return None
            def cancel_payment(self, *a, **kw): return None
            def get_remaining_cups(self, *a, **kw): return {"cups": kulhad_data["cups"], "success": True}
            def check_machine_status(self, *a, **kw): return {"success": True, "data": {"status": "online"}}
            def reduce_cups(self, *a, **kw): return {"success": True, "newCups": 49}
        self.api_client = _ApiStub()

        # Stub methods pages may call on the app
        self.show_payment_method_page   = lambda **_: self._go("dashboard")
        self.show_page                  = lambda p, **_: self._go(p)
        self.handle_cup_completion      = lambda: self._go("thankyou")
        self.cancel_payment             = lambda **_: None
        self.cancel_prefetched_qrs      = lambda: None
        self.trigger_qr_prefetch        = lambda *_: None
        self.set_selected_cups          = lambda n: setattr(self, 'selected_cups', n)
        self.set_local_cups_count       = lambda c: setattr(self, 'local_cups_count', c)
        self.decrement_local_cups       = lambda n=1: None
        self.reduce_one_cup             = lambda: None
        self.refresh_cups_count         = lambda: None
        self.start_dispensing_current_cup = lambda: self._go("dispensing")
        self.show_selection_page        = lambda: self._go("dashboard")

        sm = ScreenManager(transition=NoTransition())
        self.sm = sm

        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(DispensingTestScreen(name="dispensing"))
        sm.add_widget(PaymentMethodTestScreen(name="payment_method"))
        sm.add_widget(HeatingTestScreen(name="heating"))
        sm.add_widget(ThankYouTestScreen(name="thankyou"))
        sm.add_widget(QRPaymentTestScreen(name="qr_payment"))

        # Fetch Kulhad data in background, then refresh dashboard
        def _fetch_and_refresh():
            fetch_kulhad()
            self.ml_to_dispense         = kulhad_data["ml_to_dispense"]
            self.local_cups_count       = kulhad_data["cups"]
            self.cups_count_initialized = True
            Clock.schedule_once(lambda _: sm.get_screen("dashboard").refresh_display())

        threading.Thread(target=_fetch_and_refresh, daemon=True).start()

        return sm

    def _go(self, page):
        if page in [s.name for s in self.sm.screens]:
            self.sm.current = page
            self._current_page = page

    def get_screen(self, name):
        return self.sm.get_screen(name)

    # Properties some pages access via App.get_running_app()
    @property
    def screen_manager(self):
        return self.sm

    @property
    def payment_method_page(self):
        return self.sm.get_screen("payment_method")


if __name__ == "__main__":
    TestApp().run()

#!/usr/bin/env python3
"""
Kivy UI Performance Profiler
============================
Hooks into Kivy to measure:
- Frame render times
- Touch input latency
- Event processing delays
- Widget creation times
- Screen transition times

Import this at the TOP of main_app.py to enable profiling:

    import kivy_profiler
    kivy_profiler.enable()

Then run your app normally. Press F12 to show/hide profiler overlay.
"""

import time
import threading
import statistics
from collections import deque, defaultdict
from functools import wraps
import json
from datetime import datetime

# Metrics storage
_metrics = {
    'enabled': False,
    'frame_times': deque(maxlen=120),  # Last 2 seconds at 60fps
    'touch_latencies': deque(maxlen=100),
    'screen_transitions': [],
    'slow_frames': [],
    'event_times': defaultdict(lambda: deque(maxlen=50)),
    'widget_create_times': deque(maxlen=100),
    'last_touch_down': 0,
    'last_frame_time': 0,
    'start_time': 0,
}

_lock = threading.Lock()


def enable():
    """Enable the Kivy profiler"""
    _metrics['enabled'] = True
    _metrics['start_time'] = time.time()
    print("📊 Kivy Profiler: ENABLED")
    print("   - Frame timing active")
    print("   - Touch latency tracking active")
    print("   - Press F12 for overlay (if using ProfilerApp)")
    _patch_kivy()


def disable():
    """Disable the Kivy profiler"""
    _metrics['enabled'] = False
    print("📊 Kivy Profiler: DISABLED")


def _patch_kivy():
    """Patch Kivy internals to capture metrics"""
    try:
        from kivy.clock import Clock
        from kivy.base import EventLoop
        from kivy.core.window import Window
        
        # Patch frame callback
        original_tick = Clock.tick
        
        def profiled_tick():
            if not _metrics['enabled']:
                return original_tick()
            
            start = time.perf_counter()
            result = original_tick()
            frame_time = (time.perf_counter() - start) * 1000
            
            with _lock:
                _metrics['frame_times'].append(frame_time)
                _metrics['last_frame_time'] = frame_time
                
                # Track slow frames (>16.67ms = <60fps)
                if frame_time > 16.67:
                    _metrics['slow_frames'].append({
                        'time': time.time(),
                        'frame_ms': frame_time,
                    })
                    # Keep only last 100 slow frames
                    if len(_metrics['slow_frames']) > 100:
                        _metrics['slow_frames'] = _metrics['slow_frames'][-100:]
            
            return result
        
        Clock.tick = profiled_tick
        
        # Patch touch events
        original_on_touch_down = EventLoop.on_touch_down
        original_on_touch_up = EventLoop.on_touch_up
        
        def profiled_touch_down(touch):
            if _metrics['enabled']:
                _metrics['last_touch_down'] = time.perf_counter()
            return original_on_touch_down(touch)
        
        def profiled_touch_up(touch):
            if _metrics['enabled'] and _metrics['last_touch_down'] > 0:
                latency = (time.perf_counter() - _metrics['last_touch_down']) * 1000
                with _lock:
                    _metrics['touch_latencies'].append(latency)
            return original_on_touch_up(touch)
        
        EventLoop.on_touch_down = profiled_touch_down
        EventLoop.on_touch_up = profiled_touch_up
        
        print("   ✓ Kivy patches applied")
        
    except Exception as e:
        print(f"   ⚠️  Patch error: {e}")


def record_screen_transition(from_screen, to_screen, duration_ms):
    """Record a screen transition time"""
    if not _metrics['enabled']:
        return
    
    with _lock:
        _metrics['screen_transitions'].append({
            'time': time.time(),
            'from': from_screen,
            'to': to_screen,
            'duration_ms': duration_ms,
        })
        
        if duration_ms > 100:
            print(f"⚠️  Slow transition: {from_screen} → {to_screen}: {duration_ms:.1f}ms")


def record_event_time(event_name, duration_ms):
    """Record an event processing time"""
    if not _metrics['enabled']:
        return
    
    with _lock:
        _metrics['event_times'][event_name].append(duration_ms)


def time_function(name=None):
    """Decorator to time a function"""
    def decorator(func):
        func_name = name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not _metrics['enabled']:
                return func(*args, **kwargs)
            
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            
            record_event_time(func_name, duration)
            
            if duration > 50:
                print(f"⚠️  Slow function: {func_name}: {duration:.1f}ms")
            
            return result
        return wrapper
    return decorator


def get_stats():
    """Get current profiler statistics"""
    with _lock:
        frame_times = list(_metrics['frame_times'])
        touch_latencies = list(_metrics['touch_latencies'])
        
        stats = {
            'frame_times': {
                'count': len(frame_times),
                'avg_ms': statistics.mean(frame_times) if frame_times else 0,
                'max_ms': max(frame_times) if frame_times else 0,
                'min_ms': min(frame_times) if frame_times else 0,
                'fps': 1000 / statistics.mean(frame_times) if frame_times and statistics.mean(frame_times) > 0 else 0,
            },
            'touch_latency': {
                'count': len(touch_latencies),
                'avg_ms': statistics.mean(touch_latencies) if touch_latencies else 0,
                'max_ms': max(touch_latencies) if touch_latencies else 0,
            },
            'slow_frames': len(_metrics['slow_frames']),
            'screen_transitions': len(_metrics['screen_transitions']),
            'last_frame_ms': _metrics['last_frame_time'],
        }
        
        return stats


def get_report():
    """Generate a full profiler report"""
    stats = get_stats()
    
    lines = []
    lines.append("=" * 60)
    lines.append("KIVY UI PERFORMANCE REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    
    # Frame Performance
    lines.append("\n📊 FRAME PERFORMANCE")
    lines.append("-" * 40)
    if stats['frame_times']['count'] > 0:
        lines.append(f"  Average FPS: {stats['frame_times']['fps']:.1f}")
        lines.append(f"  Avg Frame Time: {stats['frame_times']['avg_ms']:.2f}ms")
        lines.append(f"  Max Frame Time: {stats['frame_times']['max_ms']:.2f}ms")
        lines.append(f"  Slow Frames: {stats['slow_frames']} (>16.67ms)")
        
        if stats['frame_times']['avg_ms'] > 16.67:
            lines.append(f"  ⚠️  Average FPS below 60!")
        if stats['frame_times']['max_ms'] > 100:
            lines.append(f"  ⚠️  Frame spikes >100ms detected!")
    else:
        lines.append("  No frame data collected")
    
    # Touch Latency
    lines.append("\n👆 TOUCH INPUT LATENCY")
    lines.append("-" * 40)
    if stats['touch_latency']['count'] > 0:
        lines.append(f"  Average: {stats['touch_latency']['avg_ms']:.1f}ms")
        lines.append(f"  Max: {stats['touch_latency']['max_ms']:.1f}ms")
        lines.append(f"  Samples: {stats['touch_latency']['count']}")
        
        if stats['touch_latency']['avg_ms'] > 100:
            lines.append(f"  ⚠️  Touch latency is HIGH!")
    else:
        lines.append("  No touch data collected")
    
    # Screen Transitions
    lines.append("\n📱 SCREEN TRANSITIONS")
    lines.append("-" * 40)
    with _lock:
        if _metrics['screen_transitions']:
            for trans in _metrics['screen_transitions'][-10:]:  # Last 10
                status = "⚠️" if trans['duration_ms'] > 100 else "✓"
                lines.append(f"  {status} {trans['from']} → {trans['to']}: {trans['duration_ms']:.1f}ms")
        else:
            lines.append("  No transitions recorded")
    
    # Event Times
    lines.append("\n⚡ EVENT PROCESSING TIMES")
    lines.append("-" * 40)
    with _lock:
        for event_name, times in _metrics['event_times'].items():
            times_list = list(times)
            if times_list:
                avg = statistics.mean(times_list)
                max_t = max(times_list)
                status = "⚠️" if avg > 50 else "✓"
                lines.append(f"  {status} {event_name}: avg {avg:.1f}ms, max {max_t:.1f}ms")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


def save_report(filename=None):
    """Save the profiler report to a file"""
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'kivy_profile_{timestamp}.txt'
    
    report = get_report()
    with open(filename, 'w') as f:
        f.write(report)
    
    print(f"📄 Report saved to: {filename}")
    
    # Also save raw data as JSON
    json_file = filename.replace('.txt', '.json')
    with _lock:
        data = {
            'frame_times': list(_metrics['frame_times']),
            'touch_latencies': list(_metrics['touch_latencies']),
            'screen_transitions': _metrics['screen_transitions'],
            'slow_frames': _metrics['slow_frames'],
            'event_times': {k: list(v) for k, v in _metrics['event_times'].items()},
        }
    
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"📊 Data saved to: {json_file}")


def print_stats():
    """Print current stats to console"""
    stats = get_stats()
    print(f"\n📊 FPS: {stats['frame_times']['fps']:.1f} | "
          f"Frame: {stats['last_frame_ms']:.1f}ms | "
          f"Touch: {stats['touch_latency']['avg_ms']:.1f}ms | "
          f"Slow: {stats['slow_frames']}")


# ============================================================================
# OVERLAY WIDGET (optional)
# ============================================================================

def create_overlay_widget():
    """Create a Kivy widget that shows live profiler stats"""
    try:
        from kivy.uix.label import Label
        from kivy.clock import Clock
        from kivy.graphics import Color, Rectangle
        
        class ProfilerOverlay(Label):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.size_hint = (None, None)
                self.size = (300, 150)
                self.pos = (10, 10)
                self.font_size = '12sp'
                self.color = (0, 1, 0, 1)
                self.halign = 'left'
                self.valign = 'top'
                self.text_size = self.size
                
                with self.canvas.before:
                    Color(0, 0, 0, 0.7)
                    self.bg = Rectangle(pos=self.pos, size=self.size)
                
                Clock.schedule_interval(self.update_stats, 0.5)
            
            def update_stats(self, dt):
                stats = get_stats()
                
                fps_color = "[color=00ff00]" if stats['frame_times']['fps'] > 55 else "[color=ffff00]" if stats['frame_times']['fps'] > 30 else "[color=ff0000]"
                
                self.text = (
                    f"[b]PROFILER[/b]\n"
                    f"{fps_color}FPS: {stats['frame_times']['fps']:.1f}[/color]\n"
                    f"Frame: {stats['frame_times']['avg_ms']:.1f}ms (max: {stats['frame_times']['max_ms']:.1f}ms)\n"
                    f"Touch: {stats['touch_latency']['avg_ms']:.1f}ms\n"
                    f"Slow Frames: {stats['slow_frames']}\n"
                    f"Transitions: {stats['screen_transitions']}"
                )
                self.markup = True
        
        return ProfilerOverlay()
    
    except Exception as e:
        print(f"Could not create overlay: {e}")
        return None


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def patch_screen_manager(sm):
    """Patch a ScreenManager to track transitions"""
    original_switch = sm.switch_to
    
    def profiled_switch(screen, **kwargs):
        if not _metrics['enabled']:
            return original_switch(screen, **kwargs)
        
        from_screen = sm.current if sm.current else 'none'
        to_screen = screen.name if hasattr(screen, 'name') else str(screen)
        
        start = time.perf_counter()
        result = original_switch(screen, **kwargs)
        duration = (time.perf_counter() - start) * 1000
        
        record_screen_transition(from_screen, to_screen, duration)
        
        return result
    
    sm.switch_to = profiled_switch
    print("   ✓ ScreenManager patched")


def patch_show_page(app):
    """Patch the show_page method in main_app"""
    if not hasattr(app, 'show_page'):
        return
    
    original_show_page = app.show_page
    
    def profiled_show_page(page_name, *args, **kwargs):
        if not _metrics['enabled']:
            return original_show_page(page_name, *args, **kwargs)
        
        from_page = getattr(app, 'current_page', 'unknown')
        
        start = time.perf_counter()
        result = original_show_page(page_name, *args, **kwargs)
        duration = (time.perf_counter() - start) * 1000
        
        record_screen_transition(from_page, page_name, duration)
        
        return result
    
    app.show_page = profiled_show_page
    print("   ✓ show_page patched")


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == '__main__':
    print("Kivy Profiler Module")
    print("====================")
    print("\nUsage:")
    print("  1. Add to top of main_app.py:")
    print("     import kivy_profiler")
    print("     kivy_profiler.enable()")
    print("")
    print("  2. To patch your app's show_page method:")
    print("     class UrbanKettleApp(App):")
    print("         def build(self):")
    print("             kivy_profiler.patch_show_page(self)")
    print("             ...")
    print("")
    print("  3. To save a report after testing:")
    print("     kivy_profiler.save_report()")
    print("")
    print("  4. Use @kivy_profiler.time_function('name') decorator on slow functions")

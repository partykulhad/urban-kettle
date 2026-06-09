"""
Test dispensing video playback with pump-duration-matched speed.
Run this on your desktop (no hardware needed).

Usage:
    python3 test_dispensing_video.py           # uses default 90ml / 10s
    python3 test_dispensing_video.py --ml 120  # test with 120ml / 13.3s
    python3 test_dispensing_video.py --sec 8   # test with fixed 8s duration
"""

import sys
import os
import argparse
import cv2

# ── Parse arguments ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Test dispensing video playback")
parser.add_argument("--ml",  type=float, default=None, help="ml to dispense (uses flow rate)")
parser.add_argument("--sec", type=float, default=None, help="fixed pump duration in seconds")
args = parser.parse_args()

# ── Config ───────────────────────────────────────────────────────────────────
PUMP_FLOW_RATE_ML_PER_SEC = 9.0   # 540 ml/min
VIDEO_PATH = os.path.join(os.path.dirname(__file__), "assets", "dispensing.mp4")

# ── Calculate target duration ────────────────────────────────────────────────
if args.sec:
    target_duration_s = args.sec
    print(f"Fixed duration: {target_duration_s:.1f}s")
elif args.ml:
    target_duration_s = args.ml / PUMP_FLOW_RATE_ML_PER_SEC
    print(f"Volume: {args.ml} ml  →  {target_duration_s:.2f}s at {PUMP_FLOW_RATE_ML_PER_SEC} ml/s")
else:
    # Default: fetch from Kulhad KH-03
    try:
        import requests
        r = requests.get("https://kulhad.vercel.app/api/getMachineData?machineId=KH-03", timeout=5)
        ml = float(r.json()["data"]["mlToDispense"])
        target_duration_s = ml / PUMP_FLOW_RATE_ML_PER_SEC
        print(f"Fetched from Kulhad: {ml} ml  →  {target_duration_s:.2f}s")
    except Exception as e:
        print(f"⚠️  Could not fetch from Kulhad ({e}), using default 90ml")
        target_duration_s = 90.0 / PUMP_FLOW_RATE_ML_PER_SEC

# ── Open video ───────────────────────────────────────────────────────────────
if not os.path.exists(VIDEO_PATH):
    print(f"❌ Video not found: {VIDEO_PATH}")
    sys.exit(1)

cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print("❌ Could not open video")
    sys.exit(1)

original_fps    = cap.get(cv2.CAP_PROP_FPS) or 30
total_frames    = cap.get(cv2.CAP_PROP_FRAME_COUNT)
original_dur    = total_frames / original_fps
adjusted_fps    = total_frames / target_duration_s
frame_delay_ms  = max(1, int(1000 / adjusted_fps))

print()
print("=" * 50)
print(f"  Video:          dispensing.mp4")
print(f"  Original:       {original_dur:.2f}s  @  {original_fps:.0f} fps  ({total_frames:.0f} frames)")
print(f"  Pump duration:  {target_duration_s:.2f}s")
print(f"  Adjusted FPS:   {adjusted_fps:.1f} fps")
print(f"  Frame delay:    {frame_delay_ms} ms")
if original_dur > target_duration_s:
    pct = ((original_dur / target_duration_s) - 1) * 100
    print(f"  Effect:         ▶▶ {pct:.0f}% faster (video longer than pump)")
else:
    pct = ((target_duration_s / original_dur) - 1) * 100
    print(f"  Effect:         ▷  {pct:.0f}% slower (video shorter than pump)")
print("=" * 50)
print()
print("Press Q to quit  |  Space to restart")
print()

# ── Playback loop ─────────────────────────────────────────────────────────────
import time

def play_video(cap, frame_delay_ms, target_duration_s):
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    start = time.time()
    frame_count = 0

    while True:
        ret, frame = cap.read()

        if not ret:
            # Video ended — show last frame frozen until pump time elapses
            elapsed = time.time() - start
            remaining = target_duration_s - elapsed
            if remaining > 0:
                cv2.putText(frame_last, f"Pump running... {remaining:.1f}s left",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 0), 2)
                cv2.imshow("Dispensing Video Test", frame_last)
                key = cv2.waitKey(100)
                if key == ord('q') or key == 27:
                    return False
                if key == ord(' '):
                    return True
                continue
            else:
                print(f"✅ Video + pump complete  ({time.time()-start:.2f}s total)")
                return True

        frame_last = frame.copy()
        frame_count += 1
        elapsed = time.time() - start

        # Overlay info
        cv2.putText(frame, f"Elapsed: {elapsed:.1f}s / {target_duration_s:.1f}s",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Frame: {frame_count}/{int(total_frames)}",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)
        cv2.putText(frame, f"FPS: {adjusted_fps:.1f} (orig {original_fps:.0f})",
                    (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 0), 2)

        cv2.imshow("Dispensing Video Test", frame)
        key = cv2.waitKey(frame_delay_ms)

        if key == ord('q') or key == 27:
            return False
        if key == ord(' '):
            return True

    return True

frame_last = None
while True:
    restart = play_video(cap, frame_delay_ms, target_duration_s)
    if not restart:
        break
    print("↩  Restarting...")

cap.release()
cv2.destroyAllWindows()
print("Done.")

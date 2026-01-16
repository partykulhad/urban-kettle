# Hardware Navigation Test Guide

## What This Test Does

Tests the automatic navigation from **Hardware Error Page** → **Payment Method Page** when handshake becomes available.

## Test Flow

```
1. Mock server starts (port 5000)
   ↓
2. For first 3 seconds:
   - GET /api/devices → Returns empty []
   - App detects "Hardware Not Connected"
   - App shows Hardware Error Page
   ↓
3. After 3 seconds:
   - GET /api/devices → Returns ["UK_TEST_DEVICE_12345678"]
   - App detects handshake complete
   - App automatically navigates to Payment Method Page
```

## How to Run

### Terminal 1: Start Mock Server
```bash
cd /home/mitron/Documents/urban-kettle
python3 test_hardware_navigation.py
```

**You should see:**
```
🧪 HARDWARE NAVIGATION TEST SERVER
Simulating handshake delay: 3 seconds
Server running on http://127.0.0.1:5000

  0-3s: No handshake → Should show Hardware Error Page
  3s+:  Handshake complete → Should navigate to Payment Method Page

⏱️  1s: No handshake - App should be on Hardware Error Page
⏱️  2s: No handshake - App should be on Hardware Error Page
⏱️  3s: No handshake - App should be on Hardware Error Page
✅ 4s: Handshake complete - App should navigate to Payment Method Page!
```

### Terminal 2: Run Main App
```bash
cd /home/mitron/Documents/urban-kettle
python3 main_app.py
```

## Expected Visual Behavior

### Timeline:

| Time | Screen | Why |
|------|--------|-----|
| 0s | Payment Method Page | App starts |
| 0-2s | Payment Method Page | First error check pending |
| 2s | **Hardware Error Page** | No handshake detected |
| 2-5s | **Hardware Error Page** | Waiting for handshake |
| 5s | **Payment Method Page** | Handshake complete! Auto-navigate |

## Success Criteria

✅ **Test PASSES if:**
1. App shows Hardware Error Page within 2 seconds
2. Error message shows "Hardware Not Connected"
3. After 3-5 seconds, app automatically returns to Payment Method Page
4. No manual interaction needed

❌ **Test FAILS if:**
- App stays on Hardware Error Page forever
- App doesn't navigate back automatically
- Navigation requires manual button press

## API Endpoints Tested

The mock server implements:
- `GET /api/devices` - Handshake check (same as polling_server2.py)
- `GET /api/status` - Server health check
- `GET /api/device/{id}/history` - Device health data

## Stop the Test

Press `Ctrl+C` in Terminal 1 to stop the mock server.

## Notes

- Mock server uses port 5000 (same as polling_server2.py)
- Make sure polling_server2.py is NOT running before this test
- Test delay is 3 seconds (configurable in script)

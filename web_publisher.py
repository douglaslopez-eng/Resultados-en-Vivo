import http.server
import socketserver
import threading
import subprocess
import re
import socket
import os
import time

class WebPublisher:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.httpd = None
        self.server_thread = None
        self.ssh_process = None
        self.is_running = False
        self.port = 0
        self.public_url = None
        self._callback = None
        self._web_dir = None

    def find_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def start(self, web_dir, callback_url):
        # Detener servidor previo si existe
        self.stop()
        
        self.port = self.find_free_port()
        self.is_running = True
        self.public_url = None
        self._callback = callback_url
        self._web_dir = web_dir
        
        # Start HTTP server
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=web_dir, **kwargs)
                
            def log_message(self, format, *args):
                pass  # Suppress logging
                
        self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), Handler)
        self.httpd.allow_reuse_address = True
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        
        # Start SSH tunnel in background thread (with auto-reconnect)
        self.tunnel_thread = threading.Thread(target=self._run_tunnel_loop, daemon=True)
        self.tunnel_thread.start()

    def _run_tunnel_once(self):
        """Runs a single SSH tunnel session using pinggy.io. Returns the URL found (or None)."""
        cmd = [
            "ssh", "-p", "443",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "BatchMode=yes",
            "-R", f"0:127.0.0.1:{self.port}",
            "a.pinggy.io"
        ]
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        self.ssh_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            startupinfo=startupinfo,
            bufsize=1
        )

        for line in self.ssh_process.stdout:
            if not self.is_running:
                break
            line = line.strip()
            # pinggy.io outputs the URL as a plain https:// line
            if line.startswith("https://") and ("pinggy" in line or "run.pinggy" in line):
                self.public_url = line
                if self._callback:
                    self._callback(line)
                # We got one URL — use it. Continue reading to keep the tunnel alive.

        self.ssh_process.wait()

    def _run_tunnel_loop(self):
        """Keep retrying the SSH tunnel if it expires, as long as is_running is True."""
        retry_delay = 5
        while self.is_running:
            try:
                self._run_tunnel_once()
            except Exception as e:
                if self.is_running and self._callback:
                    self._callback(f"Error: {str(e)}")
            
            if self.is_running:
                # Tunnel dropped — wait a moment then reconnect
                time.sleep(retry_delay)
                if self.is_running and self._callback:
                    self._callback("__reconnecting__")

    def stop(self):
        self.is_running = False
        if self.ssh_process:
            try:
                self.ssh_process.terminate()
            except:
                pass
            self.ssh_process = None
            
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except:
                pass
            self.httpd = None

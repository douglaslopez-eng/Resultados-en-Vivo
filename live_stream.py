# =============================================================================
# AtletismoPro — Módulo de Transmisión en Vivo
# Copyright (c) 2025-2026 Douglas José López López
# Todos los derechos reservados. All rights reserved.
#
# Este software es propiedad exclusiva de Douglas José López López.
# Queda prohibida su copia, distribución o modificación sin autorización
# expresa y por escrito del titular. Ver archivo LICENSE para más detalles.
# =============================================================================
import os
import time
import json
import threading
from pathlib import Path

class LiveStreamManager:
    # Constantes de reintentos
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2  # segundos
    DEFAULT_POLL_INTERVAL = 2.0

    def __init__(self, config_path):
        self.config_path = config_path
        self.is_online = False
        self.thread = None
        self.api_url = "http://localhost:5000/api/update"
        self.api_key = None
        self.poll_interval = self.DEFAULT_POLL_INTERVAL
        # Estado de conexión: "OK", "ERROR", "OFFLINE", "CONNECTING"
        self.connection_status = "OFFLINE"
        self.last_error = ""
        self.retry_count = 0
        self._lock = threading.Lock()
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.api_url = data.get("api_url", "http://localhost:5000/api/update")
                    self.api_key = data.get("api_key", None)
                    self.poll_interval = data.get("poll_interval_seconds", self.DEFAULT_POLL_INTERVAL)
        except Exception as e:
            print(f"Error loading live stream config: {e}")

    def get_lynx_dir(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("lynx_shared_dir", "")
        except Exception:
            pass
        return ""

    def get_status_info(self):
        """Retorna un dict con el estado actual de la transmisión para la UI."""
        with self._lock:
            return {
                "is_online": self.is_online,
                "connection_status": self.connection_status,
                "last_error": self.last_error,
                "retry_count": self.retry_count
            }

    def start_streaming(self):
        if self.is_online: return
        self.is_online = True
        with self._lock:
            self.connection_status = "CONNECTING"
            self.last_error = ""
            self.retry_count = 0
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop_streaming(self):
        self.is_online = False
        # Send offline status
        try:
            self._load_config()
            self._send_payload({"is_online": False})
        except Exception as e:
            print(f"Error sending offline status: {e}")
        with self._lock:
            self.connection_status = "OFFLINE"
            self.last_error = ""
            self.retry_count = 0

    def _send_payload(self, payload):
        """Envía un payload al servidor con reintentos y backoff exponencial."""
        import urllib.request
        
        for attempt in range(self.MAX_RETRIES):
            try:
                headers = {'Content-Type': 'application/json'}
                if self.api_key:
                    headers['X-API-Key'] = self.api_key
                req = urllib.request.Request(
                    self.api_url, 
                    data=json.dumps(payload).encode('utf-8'), 
                    headers=headers, 
                    method='POST'
                )
                resp = urllib.request.urlopen(req, timeout=5)
                if resp.status >= 400:
                    raise Exception(f"HTTP {resp.status}")
                
                # Éxito — resetear estado de error
                with self._lock:
                    self.connection_status = "OK"
                    self.last_error = ""
                    self.retry_count = 0
                return True
                
            except Exception as e:
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)  # 2s, 4s, 8s
                with self._lock:
                    self.retry_count = attempt + 1
                    self.connection_status = "ERROR"
                    self.last_error = f"Intento {attempt + 1}/{self.MAX_RETRIES}: {str(e)[:80]}"
                
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(delay)
        
        # Todos los reintentos fallaron
        with self._lock:
            self.connection_status = "ERROR"
            self.last_error = f"Falló después de {self.MAX_RETRIES} intentos"
        return False

    def _monitor_loop(self):
        known_signatures = {}
        last_sent_event = {}
        
        while self.is_online:
            try:
                self._load_config()
                shared_dir = self.get_lynx_dir()
                if not shared_dir or not os.path.exists(shared_dir):
                    time.sleep(self.poll_interval)
                    continue
                    
                path = Path(shared_dir)
                latest_file = None
                latest_mtime = 0
                
                # Find the most recently modified .lif file
                for file in path.glob("*.lif"):
                    try:
                        mtime = os.path.getmtime(file)
                        if mtime > latest_mtime:
                            latest_mtime = mtime
                            latest_file = file
                    except OSError:
                        pass
                
                if latest_file:
                    # Check if it's a new or updated file
                    if latest_file.name not in known_signatures or known_signatures[latest_file.name] < latest_mtime:
                        known_signatures[latest_file.name] = latest_mtime
                        
                        # Read the first line to get event info
                        with open(latest_file, "r", encoding="utf-8", errors="replace") as f:
                            first_line = f.readline().strip()
                        
                        if first_line:
                            parts = first_line.split(",")
                            if len(parts) >= 4:
                                event_name_raw = parts[3]
                                heat_no = parts[2]
                                
                                # Clean up event name, separate category/gender if possible
                                category = "-"
                                gender = "-"
                                event_name = event_name_raw
                                
                                if "(" in event_name_raw and ")" in event_name_raw:
                                    base = event_name_raw[:event_name_raw.find("(")].strip()
                                    g_abbr = event_name_raw[event_name_raw.find("(")+1:event_name_raw.find(")")]
                                    event_name = base
                                    gender = "Masculino" if g_abbr == "M" else "Femenino" if g_abbr == "F" else "Mixto"
                                
                                payload = {
                                    "is_online": True,
                                    "event_name": event_name,
                                    "category": category,
                                    "gender": gender,
                                    "heat_info": f"Serie {heat_no}" if heat_no.isdigit() else heat_no,
                                    "timestamp": time.time()
                                }
                                
                                # Avoid spamming the same event unless it changed
                                if payload != last_sent_event:
                                    self._send_payload(payload)
                                    last_sent_event = payload
                
            except Exception as e:
                with self._lock:
                    self.connection_status = "ERROR"
                    self.last_error = f"Error en monitor: {str(e)[:80]}"
                print(f"Error in LiveStreamManager: {e}")
                
            time.sleep(self.poll_interval)

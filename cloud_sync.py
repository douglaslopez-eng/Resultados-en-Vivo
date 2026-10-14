# =============================================================================
# AtletismoPro — Modulo de sincronizacion con Supabase Storage
# Sube los datos como JSON a la nube para que la web publica los lea.
# Requiere: pip install supabase
#
# CONFIGURACION (una sola vez):
#   1. Crea cuenta gratis en https://supabase.com
#   2. Crea un proyecto nuevo
#   3. Ve a Storage > Create bucket > nombre: "atletismo-web" > Public: SI
#   4. Ve a Settings > API y copia:
#      - Project URL  -> SUPABASE_URL
#      - anon/public key -> SUPABASE_KEY
#   5. Pega esos valores en config.json o en variables de entorno
# =============================================================================

import os
import json
import requests
from datetime import datetime
import database
import export_web

# ---- Leer configuracion de Supabase ----

def get_supabase_config():
    """Lee URL y clave de Supabase desde config.json."""
    cfg = database.load_config()
    return {
        "url":    cfg.get("supabase_url", ""),
        "key":    cfg.get("supabase_key", ""),
        "bucket": cfg.get("supabase_bucket", "atletismo-web"),
    }

def save_supabase_config(url, key, bucket="atletismo-web"):
    cfg = database.load_config()
    cfg["supabase_url"]    = url
    cfg["supabase_key"]    = key
    cfg["supabase_bucket"] = bucket
    database.save_config(cfg)




def upload_to_supabase():
    """
    Exporta el torneo actual y lo sube a Supabase. El índice se FUSIONA
    con el existente en Supabase para no borrar otras competencias.
    Retorna (exito: bool, mensaje: str, url_publica: str)
    """
    cfg = get_supabase_config()
    if not cfg["url"] or not cfg["key"]:
        return False, "Configura la URL y clave de Supabase primero.", ""

    try:
        # 1. Exportar el torneo actual al directorio local
        web_dir, json_filename = export_web.export_to_web_dir()
        if not web_dir or not json_filename:
            return False, "Error al exportar datos localmente.", ""

        supabase_url = cfg["url"].rstrip("/")
        supabase_key = cfg["key"]
        bucket = cfg["bucket"]

        headers = {
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type":  "application/json",
            "x-upsert":      "true",
        }

        # 2. Subir el JSON del torneo actual a Supabase
        with open(os.path.join(web_dir, json_filename), "rb") as f:
            json_bytes = f.read()

        upload_endpoint = f"{supabase_url}/storage/v1/object/{bucket}/{json_filename}"
        resp = requests.put(upload_endpoint, data=json_bytes, headers=headers, timeout=15)

        if resp.status_code not in (200, 201):
            return False, f"Error al subir torneo ({resp.status_code}): {resp.text[:200]}", ""

        # 3. Descargar el índice ACTUAL de Supabase (para no borrar otras competencias)
        index_url = f"{supabase_url}/storage/v1/object/public/{bucket}/indice_competencias.json"
        index_data = {"competitions": []}
        try:
            r = requests.get(index_url, timeout=10)
            if r.status_code == 200:
                fetched = r.json()
                # Aceptar tanto {competitions:[...]} como lista directa
                if isinstance(fetched, list):
                    index_data = {"competitions": fetched}
                elif isinstance(fetched, dict) and "competitions" in fetched:
                    index_data = fetched
        except Exception:
            pass  # Si no existe aún, comenzamos con índice vacío

        # 4. Leer la info del torneo actual desde el JSON local
        try:
            local_data = json.loads(json_bytes.decode("utf-8"))
            comp_info = local_data.get("competition_info", {})
            comp_name = comp_info.get("competition_name") or database.get_db_name()
            comp_date = comp_info.get("start_date", "")
            comp_sport = local_data.get("sport", "")
        except Exception:
            comp_name = database.get_db_name()
            comp_date = ""
            comp_sport = ""

        # 5. Fusionar: agregar/actualizar este torneo sin tocar los demás
        comps = index_data.get("competitions", [])
        found = False
        for item in comps:
            if item.get("filename") == json_filename or item.get("file") == json_filename:
                item["name"] = comp_name
                item["date"] = comp_date
                item["filename"] = json_filename
                item["sport"] = comp_sport
                item.pop("file", None)  # normalizar a "filename"
                found = True
                break
        if not found:
            comps.append({"filename": json_filename, "name": comp_name, "date": comp_date, "sport": comp_sport})

        index_data["competitions"] = comps

        # 6. Subir el índice fusionado a Supabase
        index_bytes = json.dumps(index_data, ensure_ascii=False).encode("utf-8")
        index_endpoint = f"{supabase_url}/storage/v1/object/{bucket}/indice_competencias.json"
        resp_idx = requests.put(index_endpoint, data=index_bytes, headers=headers, timeout=15)

        if resp_idx.status_code in (200, 201):
            public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{json_filename}"
            return True, f"Publicado '{comp_name}' a las {datetime.now().strftime('%H:%M:%S')}", public_url
        else:
            return False, f"Error al subir índice ({resp_idx.status_code}): {resp_idx.text[:200]}", ""

    except requests.exceptions.ConnectionError:
        return False, "Sin conexión a internet. Verifica tu red.", ""
    except Exception as e:
        return False, f"Error inesperado: {str(e)}", ""


def get_public_data_url(filename="datos.json"):
    """Retorna la URL publica del JSON en Supabase."""
    cfg = get_supabase_config()
    if not cfg["url"] or not cfg["bucket"]:
        return ""
    return f"{cfg['url'].rstrip('/')}/storage/v1/object/public/{cfg['bucket']}/{filename}"
import threading
import time
import cloud_sync

class AutoSyncManager:
    def __init__(self, interval_seconds=60):
        self.interval = interval_seconds
        self.is_running = False
        self.thread = None

    def start(self):
        if self.is_running: return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False

    def _run_loop(self):
        while self.is_running:
            try:
                # Intenta subir los datos. upload_to_supabase() retorna True/False.
                ok, msg, url = cloud_sync.upload_to_supabase()
                if ok:
                    print(f"[AutoSync] {msg}")
                else:
                    print(f"[AutoSync] Error: {msg}")
            except Exception as e:
                print(f"[AutoSync] Fallo en el hilo: {e}")
            time.sleep(self.interval)

# Instancia global
_sync_manager = AutoSyncManager()

def start_auto_sync():
    _sync_manager.start()

def stop_auto_sync():
    _sync_manager.stop()

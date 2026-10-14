# =============================================================================
# AtletismoPro — Auto-Sync con Supabase Storage
# Publica automáticamente los resultados a Supabase cada vez que se
# guardan resultados, de forma silenciosa en un hilo de fondo.
#
# Ventajas sobre GitHub Pages:
#   - Sin límite de peticiones / sin errores 409
#   - La página web puede refrescarse cada 60s leyendo desde Supabase
#   - Ideal para uso en tiempo real durante una competencia
# =============================================================================

import threading
import time

_lock = threading.Lock()
_pending = False          # hay cambios pendientes de subir
_running = False          # el worker está activo
_worker_thread = None
_DEBOUNCE_SECONDS = 8     # espera 8s después del último guardado antes de subir

_status_callback = None   # función opcional (msg: str) para mostrar estado en la UI


def set_status_callback(fn):
    """Registra una función que recibe mensajes de estado (para mostrar en la UI)."""
    global _status_callback
    _status_callback = fn


def _log(msg):
    print(f"[AutoSync] {msg}")
    if _status_callback:
        try:
            _status_callback(msg)
        except Exception:
            pass


def _do_sync():
    """Genera el JSON + index y sube todo a Supabase Storage. Corre en background."""
    try:
        import cloud_sync

        cfg = cloud_sync.get_supabase_config()
        if not cfg["url"] or not cfg["key"]:
            _log("Supabase no configurado — saltando auto-sync")
            return

        _log("Subiendo datos a Supabase...")
        ok, msg, url = cloud_sync.upload_to_supabase()
        if ok:
            _log(f"✅ {msg}")
        else:
            _log(f"⚠️ {msg}")

    except Exception as e:
        _log(f"Error en auto-sync: {e}")


def _worker():
    """Hilo de fondo: espera cambios y los publica con debounce."""
    global _pending, _running
    _running = True
    _log("Worker iniciado")

    while _running:
        time.sleep(1)
        with _lock:
            if not _pending:
                continue
            _pending = False

        # Debounce: esperar un poco por si vienen más cambios seguidos
        time.sleep(_DEBOUNCE_SECONDS)
        with _lock:
            if _pending:
                # Llegaron más cambios mientras esperábamos — reiniciar ciclo
                continue

        _log("Iniciando auto-sync a Supabase...")
        _do_sync()

    _log("Worker detenido")


def schedule_sync():
    """Llamar esto cada vez que se guarden resultados.
    Marca que hay cambios pendientes y arranca el worker si no está corriendo."""
    global _pending, _worker_thread, _running

    with _lock:
        _pending = True

    # Arrancar el worker si no está activo
    if _worker_thread is None or not _worker_thread.is_alive():
        _running = True
        _worker_thread = threading.Thread(target=_worker, daemon=True, name="AutoSyncWorker")
        _worker_thread.start()


def stop():
    """Detener el worker al cerrar la app."""
    global _running
    _running = False

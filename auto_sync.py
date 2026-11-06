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
import database

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
    """Genera el JSON + index y sube a Supabase Storage y a GitHub (Cloudflare Pages). Corre en background."""
    web_dir = None
    try:
        import cloud_sync
        import export_web

        # 1. Exportar a web_results (una sola vez)
        web_dir, json_filename = export_web.export_to_web_dir()
        if not web_dir:
            _log("Error exportando a web_dir")
            return

        # 2. Sincronizar con Supabase (se pasa el web_dir ya exportado para evitar doble exportación)
        cfg = cloud_sync.get_supabase_config()
        if cfg.get("url") and cfg.get("key"):
            _log("Subiendo datos a Supabase...")
            ok_s, msg_s, _ = cloud_sync.upload_to_supabase(web_dir, json_filename)
            if ok_s:
                _log(f"✅ Supabase: {msg_s}")
            else:
                _log(f"⚠️ Supabase: {msg_s}")

        # 3. Sincronizar con GitHub / Cloudflare Pages
        import github_publisher
        if github_publisher.is_configured():
            _log("Subiendo datos a GitHub / Cloudflare Pages...")
            ok_gh, msg_gh, gh_url = github_publisher.publish_to_github(web_dir)
            if ok_gh:
                _log(f"✅ Cloudflare/GitHub: {msg_gh}")
            else:
                _log(f"⚠️ Cloudflare/GitHub: {msg_gh}")

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
    # En modo Supabase la web lee directo de Postgres, no hay que subir JSONs.
    # Esto evita errores 409 de GitHub y consume 0 deploys de Cloudflare Pages.
    if database.load_config().get("data_backend") == "supabase":
        return

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

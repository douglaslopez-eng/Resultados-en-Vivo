import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import export_web
import cloud_sync

# 1. Cambiar a la base de datos del torneo que quieres renombrar
db_path = "Eventos/Nica Sprint Meet.db"
database.set_db_path(db_path)

# 2. NUEVO nombre de la competencia
nuevo_nombre = "Nica Sprint Meet"

# Obtener fechas actuales para no perderlas
ci = database.get_competition_dates()
database.save_competition_dates(ci.get("start_date", ""), ci.get("end_date", ""), nuevo_nombre)
print(f"Nombre cambiado a: {nuevo_nombre}")

# 3. Exportar a web_results local
web_dir, json_filename = export_web.export_to_web_dir()
if not web_dir:
    print("Error al exportar")
    sys.exit(1)
print(f"Exportado: {json_filename} en {web_dir}")

# 4. Subir a Supabase (esto actualiza el índice y elimina duplicados)
ok, msg, url = cloud_sync.upload_to_supabase()
if ok:
    print(f"Subido a Supabase: {msg}")
    print(f"URL pública: {url}")
else:
    print(f"Error al subir: {msg}")

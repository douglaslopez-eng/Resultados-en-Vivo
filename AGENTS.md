# AtletismoPro — Agent Instructions

## Two entrypoints
- `main.py` — Desktop management GUI (CustomTkinter): athletes, events, registrations, results, seeding, FinishLynx, medals, web publishing. Compiled with PyInstaller (`AtletismoPro.spec` → `dist/AtletismoPro.exe`).
- `app.py` — Public Streamlit results website, deployed on Render.com (`render.yaml`). Reads from local SQLite or Supabase Postgres depending on `data_backend` in `config.json`.

## Run the web app
```
pip install -r requirements.txt   # streamlit, requests, pandas — Python 3.11
streamlit run app.py
```
Render build/start are in `render.yaml` (`streamlit run app.py --server.port $PORT --server.address 0.0.0.0`).

## Run the desktop app
```
python main.py   # activate .venv first on Windows: .venv\Scripts\Activate.ps1
```
Needs `customtkinter`, `Pillow`, `openpyxl` — NOT in `requirements.txt` (web-only). Install manually or use `dist/AtletismoPro.exe`.

Compile: `pyinstaller AtletismoPro.spec --noconfirm` → `dist/` (`compilar_app.bat`, `compilar_full.bat`).

## Data / database (Fase B1 — Supabase Postgres)
- `config.json` → `data_backend` controls the back-end: `"sqlite"` (default, comportamiento actual) o `"supabase"` (usa Supabase Postgres vía REST/PostgREST).
- `supabase/schema.sql` — Esquema Postgres (tablas `competitions`, `athletes`, `events`, `registrations`, `jornadas`, `event_schedule`, `categories`, `relay_members`, `combined_marks`). Ejecutar una vez en el Editor SQL de Supabase antes de cambiar a modo Supabase.
- `supabase_client.py` — Cliente REST (`requests`) que expone la misma API pública que `database.py`. No agrega dependencias nuevas.
- `database.py` ahora es un dispatcher: si `data_backend == "supabase"`, delega cada función en `SupabaseDB`; si no, usa SQLite como siempre. `main.py` y el resto del código no necesitan cambios (siguen importando `database`).
- `database.get_connection()` devuelve un `SupabaseConnection` wrapper en modo Supabase que traduce `.cursor().execute()/fetchall()` a llamadas REST (para el SQL crudo que usa `main.py`).
- SQLite `.db` files en `Eventos/` siguen siendo el back-end por defecto (gitignored, no están en el repo).
- Backups → `backups_atletismo/` (gitignored): automáticos al cerrar y `Ctrl+B`; últimos 10.

## Fase B2 — Web pública leyendo de Postgres (Completada en código)
- `web_template.py` — El frontend lee directamente de Supabase Postgres vía REST (`/rest/v1/competitions`, `/rest/v1/events`, `/rest/v1/registrations`, `/rest/v1/event_schedule`). No usa más archivos JSON consolidados.
- `main.py` — Al generar `index.html` inyecta `{{SUPABASE_URL}}` y `{{SUPABASE_ANON_KEY}}` desde `config.json`.
- `migrate_to_supabase.py` — Script para migrar datos existentes de `Eventos/*.db` a Supabase. Ejecutar con `python migrate_to_supabase.py`.
- La web lee en tiempo real: cada edición en la app se ve reflejada en la web sin deploy de Cloudflare Pages.

## Config + secrets
- `config.json` se lee y escribe en runtime (`set_db_path`, `set_age_mode` lo reescriben). Espera `git diff` en `config.json` tras usar la app.
- `config.json` contiene secrets commiteados (Supabase keys, GitHub PAT). No rotar/commit credenciales reales aquí.
- Para activar Supabase: cambiar `"data_backend": "sqlite"` → `"supabase"` en `config.json`.
- Para la web pública se necesita la **anon key** de Supabase (formato `sb_publishable_...`, solo lectura con RLS), diferente de la `sb_secret_...` (service role, solo para la app de escritorio). Agregarla en `config.json` como `supabase_key` o usar llave separada.

## Supabase — claves públicas para la web (`SUPABASE_BASE_URL` / `SUPABASE_ANON_KEY`)
- `SUPABASE_BASE_URL` → se guarda en `config.json` como `supabase_url`. Es el **Project URL** de tu proyecto en Supabase (Settings → API), ej. `https://xxxxxxxxxxxx.supabase.co`.
- `SUPABASE_ANON_KEY` → se guarda en `config.json` como `supabase_key`. Es la **anon public key** (Settings → API → Project API keys → anon public), formato `sb_publishable_...` o `eyJhbG...`. Solo lectura con RLS.
- `web_template.py` inyecta `{{SUPABASE_URL}}` y `{{SUPABASE_ANON_KEY}}` en el `index.html` generado; el navegador las usa para llamar a `/rest/v1/...`.
- No uses la `service_role` key (`sb_secret_...`) en el frontend: es secreta y tiene permisos totales.

## Web publishing flow
`cloud_sync.upload_to_supabase()` (JSON estáticos) deprecado por lecturas directas de Postgres. El flujo JSON → GitHub Pages sigue disponible como respaldo.
`export_web.export_to_web("web_results/")` → JSON + `index.html` → GitHub Pages vía `github_publisher.publish_to_github()`.

## FinishLynx
`finishlynx.LynxWatcher` vigila la carpeta compartida de `config.json` (`lynk_shared_dir`) por archivos `.lif` (`read_lif.py`).

## Testing / quality tooling
Ninguno. No hay tests, pytest, lint, typecheck, pre-commit ni CI. `test_export.py` existe pero está gitignorado — verificar manualmente ejecutando la app.

## Git
- Rama única: `main`.
- `.gitignore` excluye DBs, builds, `*.db`, `Eventos/`, `web_results/`, `auth.db`, backups. Nota: `main.py` y `auth.py` aparecen en `.gitignore` pero están trackeados — sus ediciones sí aparecen en `git status`.

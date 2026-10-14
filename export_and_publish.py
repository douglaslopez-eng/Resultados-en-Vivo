"""
Exporta la base de datos activa a JSON y sube todo a GitHub.
"""
import sys, os, json, base64

sys.path.insert(0, r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app")

import database

# Apuntar a la BD del torneo de natación (la más reciente)
DB_PATH = r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\Eventos\TORNEO AMISTOSO DE NATACIÓN CCA 2026.db"
database.set_db_path(DB_PATH)

import export_web

WEB_DIR = r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\dist\web_results"
os.makedirs(WEB_DIR, exist_ok=True)

print("Exportando datos...")
export_web.export_to_web(WEB_DIR)
print("Export listo. Archivos en web_results:")
for f in os.listdir(WEB_DIR):
    print(f" - {f}")

# Regenerar index.html con supabase url
dist_cfg = json.load(open(r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\dist\config.json", encoding="utf-8"))
s_url = ""
if dist_cfg.get("supabase_url") and dist_cfg.get("supabase_bucket"):
    s_url = f"{dist_cfg['supabase_url'].rstrip('/')}/storage/v1/object/public/{dist_cfg['supabase_bucket']}"

from web_template import HTML_TEMPLATE
tpl = HTML_TEMPLATE.replace("{{SUPABASE_URL}}", s_url)
with open(os.path.join(WEB_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(tpl)
print("index.html regenerado.")

# Subir todo a GitHub
import requests

token  = dist_cfg["github_token"]
repo   = dist_cfg["github_repo"]
branch = dist_cfg.get("github_branch", "main")
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

def upload_file(local_path, remote_name):
    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")
    url = f"https://api.github.com/repos/{repo}/contents/{remote_name}"
    r = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
    sha = r.json().get("sha") if r.status_code == 200 else None
    body = {"message": f"Actualizar {remote_name}", "branch": branch, "content": content_b64}
    if sha:
        body["sha"] = sha
    r2 = requests.put(url, headers=headers, json=body, timeout=30)
    status = "OK" if r2.status_code in (200, 201) else f"ERROR {r2.status_code}"
    print(f"  {status} -> {remote_name}")
    return r2.status_code in (200, 201)

print("\nSubiendo archivos a GitHub...")
for fname in os.listdir(WEB_DIR):
    fpath = os.path.join(WEB_DIR, fname)
    if os.path.isfile(fpath):
        upload_file(fpath, fname)

print("\n¡Publicación completada!")

# =============================================================================
# AtletismoPro — Publicador de la web permanente en GitHub Pages
# Sube el contenido de web_results (index.html + JSONs) a un repositorio de
# GitHub servido por GitHub Pages, usando la API de contenidos.
#
# CONFIGURACION (una sola vez):
#   1. Crea un repositorio PUBLICO en GitHub (ej. "atletismo-resultados")
#   2. En Settings > Pages: Source = "Deploy from a branch", Branch = main /(root)
#   3. Crea un token en https://github.com/settings/tokens?type=beta
#      (Fine-grained) con permiso "Contents: Read and Write" sobre ese repo
#   4. En la app: boton "🌍 Publicar Web Permanente" > Configurar:
#      repo = "tusuario/atletismo-resultados", token = ghp_.../github_pat_...
# =============================================================================

import os
import json
import base64
import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None

import database

DEFAULT_BRANCH = "main"


def _build_session():
    """Sesión con reintentos para evitar fallos por timeouts transitorios."""
    session = requests.Session()
    if Retry is not None:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "PUT"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    return session


_session = _build_session()


# ---- Configuración ----

def get_github_config():
    cfg = database.load_config()
    return {
        "token":  cfg.get("github_token", ""),
        "repo":   cfg.get("github_repo", ""),       # formato "usuario/repo"
        "branch": cfg.get("github_branch", DEFAULT_BRANCH),
    }


def save_github_config(token, repo, branch=DEFAULT_BRANCH):
    cfg = database.load_config()
    cfg["github_token"] = token.strip()
    cfg["github_repo"] = repo.strip().strip("/")
    cfg["github_branch"] = (branch or DEFAULT_BRANCH).strip()
    database.save_config(cfg)


def get_pages_url():
    """URL pública estimada del sitio en GitHub Pages."""
    cfg = get_github_config()
    if not cfg["repo"] or "/" not in cfg["repo"]:
        return ""
    owner, repo = cfg["repo"].split("/", 1)
    if repo == f"{owner}.github.io":
        return f"https://{owner}.github.io/"
    return f"https://{owner}.github.io/{repo}/"


def is_configured():
    cfg = get_github_config()
    return bool(cfg["token"] and cfg["repo"])


# ---- API de GitHub ----

def _headers(cfg):
    return {
        "Authorization": f"Bearer {cfg['token']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_existing_sha(cfg, path):
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{path}"
    r = _session.get(url, headers=_headers(cfg),
                     params={"ref": cfg["branch"]}, timeout=(10, 60))
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, dict):
            return data.get("sha")
    return None


def _upload_file(cfg, path, content_bytes, message):
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{path}"
    body = {
        "message": message,
        "branch": cfg["branch"],
        "content": base64.b64encode(content_bytes).decode("ascii"),
    }
    sha = _get_existing_sha(cfg, path)
    if sha:
        body["sha"] = sha
    resp = _session.put(url, headers=_headers(cfg), json=body, timeout=(10, 120))
    if resp.status_code in (200, 201):
        return True, ""
    if resp.status_code in (401, 403, 404):
        return False, (f"Error GitHub ({resp.status_code}). Revisa que el token "
                       f"tenga permiso 'Contents: Read and Write' en el repo y que "
                       f"el nombre del repo sea exactamente '{cfg['repo']}'.")
    return False, f"Error GitHub ({resp.status_code}): {resp.text[:200]}"


# Lista blanca de archivos que el shell de la web necesita (sólo en modo Supabase).
# Todo lo que NO esté aquí se considera "basura acumulada" y se borra al publicar.
WEB_SHELL_WHITELIST = frozenset({
    "index.html",
    "logo.png",
    "_headers",
    "sitemap.xml",
    ".nojekyll",
    "README.md",
})


def delete_from_github(cfg):
    """Borra del repo todo archivo que NO esté en la lista blanca.
    Esto garantiza que no queden JSONs viejos (.db, Eventos/, scripts basura...) acumulados."""
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/"
    r = _session.get(url, headers=_headers(cfg),
                     params={"ref": cfg["branch"]}, timeout=(10, 60))
    if r.status_code != 200:
        return False, f"No se pudo listar el repositorio (HTTP {r.status_code})"
    items = r.json()
    if not isinstance(items, list):
        return False, f"Respuesta inesperada al listar repo: {r.text[:200]}"

    borrados = []
    errores = []
    for item in items:
        name = item.get("name", "")
        if name in WEB_SHELL_WHITELIST:
            continue
        # Borrar este archivo o carpeta
        if item.get("type") == "file":
            path = item["path"]
            sha = item.get("sha")
            if not sha:
                continue
            del_url = f"https://api.github.com/repos/{cfg['repo']}/contents/{path}"
            body = {
                "message": f"Limpieza: eliminar {path}",
                "branch": cfg["branch"],
                "sha": sha,
            }
            d = _session.delete(del_url, headers=_headers(cfg), json=body, timeout=(10, 120))
            if d.status_code in (200, 204):
                borrados.append(path)
            else:
                errores.append(f"{path}: HTTP {d.status_code}")
    return True, f"Limpieza: {len(borrados)} borrados" + (f"; {len(errores)} errores: " + "; ".join(errores[:5]) if errores else "")

def publish_to_github(web_dir):
    """Sube el contenido de web_dir al repo configurado. Retorna (ok, mensaje, url)."""
    cfg = get_github_config()
    if not cfg["token"] or not cfg["repo"]:
        return False, ("Falta la configuración de GitHub. Usa el botón "
                       "'Configurar publicación' para ingresar repo y token."), ""

    import database as _db
    is_supabase = _db.load_config().get("data_backend") == "supabase"

    from datetime import datetime
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"Actualizar resultados ({stamp})"

    if is_supabase:
        # En modo Supabase la web lee directo de Postgres. Sólo se publica el shell:
        # index.html, logo.png, _headers, sitemap.xml, .nojekyll, README.md.
        # Se LISTA el repo y se borra TODO lo que no esté en la lista blanca,
        # para eliminar definitivamente JSONs viejos, .db, Eventos/, etc.
        ok, msg = delete_from_github(cfg)
        if not ok:
            return False, f"Fallo al limpiar el repositorio: {msg}", ""

    # Archivos a publicar: todo el contenido de web_dir + .nojekyll
    files = []
    for fname in sorted(os.listdir(web_dir)):
        fpath = os.path.join(web_dir, fname)
        if os.path.isfile(fpath) and (
                fname.lower().endswith((".html", ".json", ".css", ".js", ".png", ".ico"))
                or fname in ("_headers", "_redirects")):
            if is_supabase and fname not in WEB_SHELL_WHITELIST:
                # En modo Supabase no subimos JSONs de datos al repo
                continue
            files.append((fname, fpath))
    files.append((".nojekyll", None))  # evita procesamiento Jekyll en Pages

    if not files:
        return False, "No hay archivos para publicar en la carpeta web.", ""

    for fname, fpath in files:
        if fpath is None:
            content = b""
        else:
            with open(fpath, "rb") as f:
                content = f.read()
        ok, err = _upload_file(cfg, fname, content, message)
        if not ok:
            return False, f"Falló al subir '{fname}': {err}", ""

    return True, f"Publicado correctamente a las {datetime.now().strftime('%H:%M:%S')}", get_pages_url()

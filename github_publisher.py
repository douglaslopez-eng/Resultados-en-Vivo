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

import database

DEFAULT_BRANCH = "main"


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
    r = requests.get(url, headers=_headers(cfg),
                     params={"ref": cfg["branch"]}, timeout=15)
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
    resp = requests.put(url, headers=_headers(cfg), json=body, timeout=30)
    if resp.status_code in (200, 201):
        return True, ""
    if resp.status_code in (401, 403, 404):
        return False, (f"Error GitHub ({resp.status_code}). Revisa que el token "
                       f"tenga permiso 'Contents: Read and Write' en el repo y que "
                       f"el nombre del repo sea exactamente '{cfg['repo']}'.")
    return False, f"Error GitHub ({resp.status_code}): {resp.text[:200]}"


# ---- Publicación completa ----

def publish_to_github(web_dir):
    """Sube el contenido de web_dir al repo configurado. Retorna (ok, mensaje, url)."""
    cfg = get_github_config()
    if not cfg["token"] or not cfg["repo"]:
        return False, ("Falta la configuración de GitHub. Usa el botón "
                       "'Configurar publicación' para ingresar repo y token."), ""

    from datetime import datetime
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = f"Actualizar resultados ({stamp})"

    # Archivos a publicar: todo el contenido de web_dir + .nojekyll
    files = []
    for fname in sorted(os.listdir(web_dir)):
        fpath = os.path.join(web_dir, fname)
        if os.path.isfile(fpath) and (
                fname.lower().endswith((".html", ".json", ".css", ".js", ".png", ".ico"))
                or fname in ("_headers", "_redirects")):
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

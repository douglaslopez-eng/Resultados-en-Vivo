import os
import re
import json
import unicodedata
import database
from datetime import datetime


def sanitize_filename(name):
    """Convierte el nombre de una competencia en un nombre de archivo JSON
    seguro (sin acentos ni caracteres especiales).

    Es crucial que TODOS los lugares (export local, índice, Supabase, GitHub)
    usen exactamente el mismo nombre, porque Supabase/URLs no conservan los
    acentos y terminan guardando un archivo distinto al que referencia el
    índice (por eso una competencia nueva no aparecía en la web).
    """
    if not name:
        name = "competencia"
    if name.lower().endswith(".db"):
        name = name[:-3]
    if name.lower().endswith(".json"):
        name = name[:-5]
    # Descomponer acentos (NFKD) y eliminar los caracteres combinantes
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.replace(" ", "_")
    ascii_name = re.sub(r"[^A-Za-z0-9_.-]", "", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("_.")
    if not ascii_name:
        ascii_name = "competencia"
    return f"{ascii_name}.json"


def _normalize_existing_files(web_dir):
    """Renombra JSONs antiguos con acentos/caracteres inválidos a su versión
    ASCII segura, para que el índice, Supabase y GitHub apunten al mismo
    archivo que realmente existe."""
    try:
        entries = os.listdir(web_dir)
    except OSError:
        return
    for fname in entries:
        if not fname.lower().endswith(".json") or fname == "index.json":
            continue
        safe = sanitize_filename(fname)
        if safe == fname:
            continue
        src = os.path.join(web_dir, fname)
        dst = os.path.join(web_dir, safe)
        try:
            if os.path.exists(dst):
                # Ya existe el destino: conservar el más reciente
                if os.path.getmtime(src) > os.path.getmtime(dst):
                    os.replace(src, dst)
                else:
                    os.remove(src)
            else:
                os.replace(src, dst)
        except OSError:
            pass


def _remove_stale_variants(web_dir, keep_filename):
    """Elimina JSONs antiguos cuyo nombre normalizado coincide con el actual
    (p. ej. versiones con acento) para evitar duplicados en el índice."""
    try:
        entries = os.listdir(web_dir)
    except OSError:
        return
    for fname in entries:
        if not fname.lower().endswith(".json") or fname in ("index.json", keep_filename):
            continue
        if sanitize_filename(fname) == keep_filename:
            try:
                os.remove(os.path.join(web_dir, fname))
            except OSError:
                pass


def export_to_web(web_dir):
    # En modo Supabase la web lee directo de Postgres, no genera JSONs.
    # Esto evita que archivos muertos se suban a GitHub y que la web use datos obsoletos.
    try:
        cfg = database.load_config()
    except Exception:
        cfg = {}
    if cfg.get("data_backend") == "supabase":
        return

    comp = database.get_competition_dates()
    all_events = database.get_events()
    jornadas = database.get_jornadas()

    ev_jornada = {}
    for j in jornadas:
        for s in database.get_schedules_for_jornada(j["id"]):
            eid = s.get("event_id")
            if eid:
                ev_jornada[eid] = j["name"]

    events_out = []
    medal_table = database.get_medal_table(None)
    
    for ev in all_events:
        regs = database.get_registrations_for_event(ev["id"])
        order_asc = ev["type"] in ("Pista", "Piscina")
        heights = database.get_vertical_heights(ev["id"])
        
        valid_regs = [r for r in regs if r.get("result_value") is not None]
        
        if ev["type"] == "Campo":
            # Separar DQs
            valid_normal = [r for r in valid_regs if not r.get("is_disqualified")]
            valid_dq = [r for r in valid_regs if r.get("is_disqualified")]
            sorted_regs = database.sort_field_results(valid_normal, ev["name"]) + valid_dq
        else:
            def _sort_key(r):
                dq = r.get("is_disqualified") or 0
                val = r.get("result_value")
                if val is None:
                    val = float('inf') if order_asc else float('-inf')
                return (dq, val)
            
            sorted_regs = sorted(valid_regs, key=_sort_key, reverse=not order_asc)

        is_relay = database.is_relay_event(ev["name"])
        relay_members = database.get_relay_members(ev["id"]) if is_relay else {}

        results_out = []
        seen_clubs = set()
        for i, r in enumerate(sorted_regs):
            club = r.get("athlete_club", "")
            if is_relay:
                if club in seen_clubs:
                    continue
                seen_clubs.add(club)
                mem = relay_members.get(club, "")
                ath_name = mem if mem else r.get("athlete_name", "")
            else:
                ath_name = r.get("athlete_name", "")

            res_dict = {
                "rank": (len(results_out) + 1) if not r.get("is_disqualified") else None,
                "athlete_name": ath_name,
                "athlete_club": club,
                "athlete_category": r.get("athlete_category", ""),
                "bib": r.get("athlete_bib", ""),
                "result": r.get("result", ""),
                "is_disqualified": bool(r.get("is_disqualified")),
                "status": "DQ" if r.get("is_disqualified") else None,
                "heat_number": r.get("heat_number"),
                "lane_number": r.get("lane_number"),
                "order_number": r.get("order_number")
            }
            
            if ev["type"] == "Campo":
                raw_att = r.get("attempts")
                db_att = []
                if raw_att:
                    try:
                        db_att = json.loads(raw_att)
                    except:
                        pass
                if not db_att:
                    db_att = [r.get(f"attempt{i}", "") or "" for i in range(1, 7)]
                # Filter out empty trailing attempts to make it cleaner
                while db_att and not db_att[-1]:
                    db_att.pop()
                res_dict["attempts"] = db_att
            else:
                res_dict["attempts"] = []
                
            results_out.append(res_dict)
            
        podium_out = []
        for r in results_out[:3]:
            if not r["is_disqualified"]:
                podium_out.append(r)

        seedings_out = []
        for r in regs:
            seedings_out.append({
                "athlete_name": r.get("athlete_name", ""),
                "athlete_club": r.get("athlete_club", ""),
                "athlete_category": r.get("athlete_category", ""),
                "bib": r.get("athlete_bib", ""),
                "heat_number": r.get("heat_number"),
                "lane_number": r.get("lane_number"),
                "order_number": r.get("order_number"),
                "personal_best": r.get("personal_best", "")
            })

        events_out.append({
            "id": ev["id"],
            "name": ev["name"],
            "category": ev["category"],
            "gender": ev["gender"],
            "type": ev["type"],
            "sport": ev.get("sport") or ("Natación" if ev["type"] == "Piscina" else "Atletismo"),
            "round": ev["round"] or "Final",
            "jornada": ev_jornada.get(ev["id"], ""),
            "results": results_out,
            "seedings": seedings_out,
            "podium": podium_out,
            "heights": heights,
            "has_results": len(results_out) > 0
        })

    # Construir JSON final
    db_name = database.get_db_name()
    if db_name.endswith(".db"):
        db_name = db_name[:-3]
    
    # --- Programa (Jornadas con horarios) ---
    schedule_out = []
    for j in jornadas:
        evs_in_j = []
        for s in database.get_schedules_for_jornada(j["id"]):
            eid = s.get("event_id")
            if not eid:
                continue
            ev_info = next((e for e in all_events if e["id"] == eid), None)
            if ev_info:
                evs_in_j.append({
                    "name": ev_info["name"],
                    "category": ev_info["category"],
                    "gender": ev_info["gender"],
                    "type": ev_info["type"],
                    "round": ev_info["round"] or "Final",
                    "time": s.get("event_time", ""),
                })
        schedule_out.append({"name": j["name"], "events": evs_in_j})
        
    out_data = {
        "competition_info": {
            "competition_name": comp.get("competition_name") or db_name,
            "start_date": comp.get("start_date", ""),
            "end_date": comp.get("end_date", "")
        },
        "sport": (lambda ss: ss[0] if len(ss) == 1 else "Mixto")(sorted({ev.get("sport", "Atletismo") for ev in events_out})),
        "events": events_out,
        "medal_table": medal_table,
        "schedule": schedule_out
    }
    
    # Escribir resultados.json (usando el nombre de la bd, siempre en ASCII)
    json_filename = sanitize_filename(db_name)
    _remove_stale_variants(web_dir, json_filename)
    json_path = os.path.join(web_dir, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False)
        
    # Normalizar nombres de archivos antiguos (con acentos) antes de indexar
    _normalize_existing_files(web_dir)

    # Escribir index.json con las competencias disponibles
    index_path = os.path.join(web_dir, "index.json")
    comps = []
    
    # Escanear el directorio por todos los json para no perder competencias antiguas
    for fname in os.listdir(web_dir):
        if fname.endswith(".json") and fname != "index.json":
            fpath = os.path.join(web_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    comp_data = json.load(f)
                    
                # Extraer info
                cinfo = comp_data.get("competition_info", {})
                comps.append({
                    "filename": fname,
                    "name": cinfo.get("competition_name") or fname.replace(".json", ""),
                    "date": cinfo.get("start_date") or "",
                    "sport": comp_data.get("sport") or ""
                })
            except:
                pass
                
    # Ordenar comps por nombre o fecha si se desea, aquí lo ordenamos por fecha inversa (las más nuevas primero)
    comps.sort(key=lambda x: x.get("date", ""), reverse=True)

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"competitions": comps}, f, ensure_ascii=False)


def export_to_web_dir():
    """Exporta los resultados al directorio web_results y devuelve (web_dir, json_filename).
    Usado por auto_sync para publicación automática sin UI."""
    import sys
    if getattr(sys, "frozen", False):
        # Ejecutable .exe
        base = os.path.dirname(sys.executable)
    else:
        # Código fuente — preferir dist/web_results si existe
        src = os.path.dirname(os.path.abspath(__file__))
        _dist = os.path.join(src, "dist", "web_results")
        if os.path.isdir(_dist):
            base = os.path.dirname(_dist)  # = dist/
            web_dir = _dist
            json_filename = sanitize_filename(database.get_db_name())
            try:
                export_to_web(web_dir)
                return web_dir, json_filename
            except Exception as e:
                print(f"[export_to_web_dir] Error: {e}")
                return None, None
        base = src

    web_dir = os.path.join(base, "web_results")
    os.makedirs(web_dir, exist_ok=True)
    json_filename = sanitize_filename(database.get_db_name())
    try:
        export_to_web(web_dir)
        return web_dir, json_filename
    except Exception as e:
        print(f"[export_to_web_dir] Error: {e}")
        return None, None

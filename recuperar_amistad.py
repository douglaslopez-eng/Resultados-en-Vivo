#!/usr/bin/env python3
"""
============================================================
 recuperar_amistad.py
 Recupera datos del Torneo Intercolegial La Amistad CCA 2026
 desde Supabase y los importa a la base de datos local SQLite.
============================================================
"""

import sqlite3
import json
import os
import sys
import shutil
import requests
from datetime import datetime

# ── Configuración ─────────────────────────────────────────
SUPABASE_URL  = "https://kfcmhlsuoufvlyizqljm.supabase.co"
BUCKET        = "atletismo-web"
JSON_FILENAME = "Torneo_Intercolegial_La_Amistad_CCA_2026.json"
DB_PATH       = r"Eventos\Torneo Intercolegial La Amistad CCA 2026.db"
# ──────────────────────────────────────────────────────────


def descargar_json():
    url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{JSON_FILENAME}"
    print(f"[1/5] Descargando datos desde Supabase...")
    print(f"      URL: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    print(f"      OK  {len(data.get('events', []))} eventos encontrados")
    return data


def hacer_backup(db_path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path + f".backup_recuperacion_{ts}"
    shutil.copy2(db_path, backup)
    print(f"[2/5] Backup creado: {os.path.basename(backup)}")
    return backup


def limpiar_db(conn):
    """Elimina todos los datos pero mantiene la estructura de tablas."""
    cur = conn.cursor()
    print("[3/5] Limpiando base de datos local (manteniendo estructura)...")
    tablas = [
        "event_schedule", "relay_members", "registrations",
        "athletes", "events", "jornadas", "competition_info"
    ]
    cur.execute("PRAGMA foreign_keys = OFF;")
    for t in tablas:
        try:
            cur.execute(f'DELETE FROM "{t}"')
            print(f"      OK tabla {t} limpiada")
        except sqlite3.OperationalError as e:
            print(f"      ! Tabla {t}: {e}")
    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()


def parse_result_value(result_str, event_type):
    """Convierte el resultado textual a valor numérico para ordenar."""
    if not result_str:
        return None
    s = str(result_str).strip()
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        s_clean = s.replace("s", "").replace("m", "").replace("cm", "").strip()
        return float(s_clean)
    except (ValueError, TypeError):
        return None


def importar(conn, data):
    cur = conn.cursor()
    print("[4/5] Importando datos...")

    # competition_info
    ci = data.get("competition_info", {})
    cur.execute(
        "INSERT INTO competition_info (competition_name, start_date, end_date) VALUES (?, ?, ?)",
        (
            ci.get("competition_name", "Torneo Intercolegial La Amistad CCA 2026"),
            ci.get("start_date", ""),
            ci.get("end_date", "")
        )
    )
    print(f"      OK competition_info: {ci.get('competition_name')}")

    # Jornadas
    jornadas_vistas = {}
    for ev in data.get("events", []):
        jornada_name = ev.get("jornada") or "Jornada Principal"
        if jornada_name not in jornadas_vistas:
            cur.execute(
                "INSERT INTO jornadas (name, display_order) VALUES (?, ?)",
                (jornada_name, len(jornadas_vistas))
            )
            jornadas_vistas[jornada_name] = cur.lastrowid
    print(f"      OK Jornadas: {list(jornadas_vistas.keys())}")

    # Events (pruebas)
    event_id_map = {}
    for ev in data.get("events", []):
        ev_type = ev.get("type", "Pista")
        sport   = ev.get("sport") or ("Natacion" if ev_type == "Piscina" else "Atletismo")
        cur.execute(
            "INSERT INTO events (name, type, category, gender, lanes, round, sport) VALUES (?,?,?,?,?,?,?)",
            (
                ev.get("name", ""),
                ev_type,
                ev.get("category", ""),
                ev.get("gender", "Masculino"),
                8,
                ev.get("round") or "Final",
                sport
            )
        )
        new_id = cur.lastrowid
        event_id_map[ev["id"]] = new_id

        jornada_name = ev.get("jornada") or "Jornada Principal"
        jornada_id   = jornadas_vistas.get(jornada_name)
        if jornada_id:
            cur.execute(
                "INSERT INTO event_schedule (jornada_id, event_id, event_time, display_order) VALUES (?,?,?,?)",
                (jornada_id, new_id, "", 0)
            )

    print(f"      OK Eventos: {len(event_id_map)} pruebas importadas")

    # Athletes + Registrations
    athlete_cache = {}
    total_regs = 0

    for ev in data.get("events", []):
        new_event_id = event_id_map.get(ev["id"])
        if new_event_id is None:
            continue

        ev_type = ev.get("type", "Pista")

        result_by_name = {}
        for r in ev.get("results", []):
            key = (r.get("athlete_name", "").strip(), r.get("athlete_club", "").strip())
            result_by_name[key] = r

        seedings = ev.get("seedings") or ev.get("results", [])
        registered_in_event = set()

        for s in seedings:
            athlete_name = (s.get("athlete_name") or "").strip()
            athlete_club = (s.get("athlete_club") or "").strip()
            athlete_cat  = (s.get("athlete_category") or ev.get("category") or "").strip()
            bib          = s.get("bib") or ""

            if not athlete_name:
                continue

            cache_key = (athlete_name.lower(), athlete_club.lower(), athlete_cat.lower())
            if cache_key in athlete_cache:
                athlete_id = athlete_cache[cache_key]
            else:
                cur.execute(
                    "SELECT id FROM athletes WHERE LOWER(name)=LOWER(?) AND LOWER(club)=LOWER(?) AND LOWER(category)=LOWER(?) LIMIT 1",
                    (athlete_name, athlete_club, athlete_cat)
                )
                row = cur.fetchone()
                if row:
                    athlete_id = row[0]
                else:
                    gender_ev = ev.get("gender", "Masculino")
                    cur.execute(
                        "INSERT INTO athletes (name, club, category, gender, bib_number) VALUES (?,?,?,?,?)",
                        (athlete_name, athlete_club, athlete_cat, gender_ev, str(bib))
                    )
                    athlete_id = cur.lastrowid
                athlete_cache[cache_key] = athlete_id

            if athlete_id in registered_in_event:
                continue
            registered_in_event.add(athlete_id)

            res_key  = (athlete_name, athlete_club)
            res_data = result_by_name.get(res_key, {})

            result_str    = res_data.get("result") or None
            result_value  = parse_result_value(result_str, ev_type) if result_str else None
            is_dq         = 1 if res_data.get("is_disqualified") else 0
            status        = res_data.get("status") or "Normal"
            heat_number   = s.get("heat_number") or res_data.get("heat_number")
            lane_number   = s.get("lane_number") or res_data.get("lane_number")
            order_number  = s.get("order_number") or res_data.get("order_number")
            personal_best = s.get("personal_best")
            attempts_list = res_data.get("attempts", [])
            attempts_json = json.dumps(attempts_list) if attempts_list else None
            att = [(attempts_list[i] if i < len(attempts_list) else None) for i in range(6)]

            try:
                cur.execute("""
                    INSERT INTO registrations
                        (athlete_id, event_id, heat_number, lane_number, order_number,
                         result, result_value, is_disqualified, status,
                         attempt1, attempt2, attempt3, attempt4, attempt5, attempt6,
                         attempts, personal_best)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    athlete_id, new_event_id,
                    heat_number, lane_number, order_number,
                    result_str, result_value, is_dq, status,
                    att[0], att[1], att[2], att[3], att[4], att[5],
                    attempts_json, personal_best
                ))
                total_regs += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    print(f"      OK Atletas: {len(athlete_cache)} unicos")
    print(f"      OK Inscripciones/Resultados: {total_regs} registros")


def verificar(conn, data):
    cur = conn.cursor()
    print("\n[5/5] Verificacion final:")
    for tabla in ["competition_info", "events", "athletes", "registrations", "jornadas"]:
        cur.execute(f'SELECT COUNT(*) FROM "{tabla}"')
        n = cur.fetchone()[0]
        print(f"      {tabla}: {n} registros")

    eventos_con_resultado = sum(1 for ev in data.get("events", []) if ev.get("has_results"))
    print(f"\n   Eventos con resultados en Supabase: {eventos_con_resultado}")
    cur.execute("SELECT COUNT(*) FROM registrations WHERE result IS NOT NULL")
    n_res = cur.fetchone()[0]
    print(f"   Registros con resultado en DB local: {n_res}")


def main():
    print("=" * 60)
    print("  Recuperacion: Torneo Intercolegial La Amistad CCA 2026")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"\nERROR: No se encontro la base de datos en:\n   {DB_PATH}")
        sys.exit(1)

    data = descargar_json()
    backup_path = hacer_backup(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()
    migrations = [
        ("athletes",      "bib_number TEXT"),
        ("registrations", "wind_speed REAL"),
        ("registrations", "personal_best REAL"),
        ("registrations", "attempts TEXT"),
        ("registrations", "status TEXT DEFAULT 'Normal'"),
        ("events",        "sport TEXT DEFAULT 'Atletismo'"),
        ("events",        "round TEXT DEFAULT 'Final'"),
        ("events",        "vertical_heights TEXT"),
    ]
    for table, col_def in migrations:
        col_name = col_def.split()[0]
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def};")
        except sqlite3.OperationalError:
            pass
    conn.commit()

    try:
        limpiar_db(conn)
        importar(conn, data)
        verificar(conn, data)
        conn.close()

        print("\n" + "=" * 60)
        print("  RECUPERACION COMPLETADA EXITOSAMENTE")
        print(f"  Backup en: {os.path.basename(backup_path)}")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"\nERROR durante la importacion: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nSe conservo el backup en: {backup_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()

# =============================================================================
# AtletismoPro — Script de migración SQLite → Supabase Postgres (Fase B1/B2)
# Lee cada archivo .db en Eventos/ y sube sus datos a las tablas de Supabase.
# Usa inserts en lote (batch) para ser rápido y evitar timeouts de red.
# Uso:
#   python migrate_to_supabase.py
# Requisitos:
#   - config.json con supabase_url, supabase_key, data_backend="supabase"
#   - Ejecutado supabase/schema.sql en el proyecto de Supabase
# =============================================================================

import os
import glob
import json
import sqlite3
import time
import database
from supabase_client import SupabaseDB


def _as_int(val):
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(val):
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _read_sqlite(db_path):
    """Lee TODO el contenido de un .db de SQLite directamente (sin pasar por
    el dispatcher de database.py, que en modo Supabase iría a Postgres)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def fetch(table, columns="*", where=None, params=None, order_by=None):
        sql = f"SELECT {columns} FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        cur.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]

    data = {}

    # Competition info
    cur.execute("SELECT competition_name, start_date, end_date FROM competition_info LIMIT 1")
    row = cur.fetchone()
    data["competition"] = dict(row) if row else {}

    # Athletes
    data["athletes"] = fetch("athletes", order_by="name ASC")

    # Events
    data["events"] = fetch("events", order_by="name ASC")

    # Categories
    data["categories"] = fetch("categories", order_by="name ASC")

    # Jornadas
    data["jornadas"] = fetch("jornadas", order_by="display_order ASC, id ASC")

    # Schedules
    cur.execute("""
        SELECT es.*, e.name AS event_name, ce.name AS combined_name
        FROM event_schedule es
        LEFT JOIN events e ON es.event_id = e.id
        LEFT JOIN events ce ON es.combined_event_id = ce.id
        ORDER BY es.jornada_id ASC, es.display_order ASC, es.id ASC
    """)
    data["schedules"] = [dict(r) for r in cur.fetchall()]

    # Registrations (con datos del atleta)
    cur.execute("""
        SELECT r.*,
               a.name AS athlete_name, a.club AS athlete_club,
               a.category AS athlete_category, a.bib_number AS athlete_bib
        FROM registrations r
        JOIN athletes a ON r.athlete_id = a.id
        ORDER BY r.event_id ASC, r.heat_number ASC, r.lane_number ASC, r.order_number ASC
    """)
    data["registrations"] = [dict(r) for r in cur.fetchall()]

    # Relay members
    data["relays"] = fetch("relay_members", order_by="event_id ASC, club ASC")

    # Vertical heights
    data["vertical_heights"] = {}
    try:
        cur.execute("SELECT event_id, heights FROM vertical_heights")
        for r in cur.fetchall():
            data["vertical_heights"][r["event_id"]] = r["heights"]
    except sqlite3.OperationalError:
        pass

    # Combined marks
    data["combined_marks"] = {}
    try:
        cur.execute("SELECT event_id, athlete_id, event_index, mark_value FROM combined_marks")
        for r in cur.fetchall():
            data["combined_marks"].setdefault(r["event_id"], {})[r["athlete_id"]] = {
                r["event_index"]: r["mark_value"]
            }
    except sqlite3.OperationalError:
        pass

    conn.close()
    return data


def _bulk_insert(supabase, table, rows):
    """Inserta varias filas de una vez. Devuelve lista de dicts con los IDs generados."""
    if not rows:
        return []
    # PostgREST acepta un array de objetos para insert en lote
    created = supabase._post(table, rows, prefer="representation")
    return created or []


def migrate_db_file(db_path, supabase: SupabaseDB):
    """Migra un archivo .db de SQLite a Supabase Postgres."""
    print(f"\n=== Migrando: {db_path} ===")

    # Resetear competition_id para forzar que cada .db cree su propia competition
    supabase.competition_id = None

    # --- 1. Leer todo de SQLite (directo, sin dispatcher) -------------------
    sql = _read_sqlite(db_path)
    comp_info = sql["competition"]
    comp_name = comp_info.get("competition_name") or os.path.splitext(os.path.basename(db_path))[0]

    # --- 2. Crear/Reutilizar competition en Supabase ------------------------
    comp_id = None

    existing = supabase._get(
        "competitions",
        params={"select": "id", "name": f"eq.{comp_name}"},
    )
    if existing:
        comp_id = existing[0]["id"]
        supabase.set_competition(comp_id)
        print(f"  -> competition reutilizada: {comp_id} ({comp_name})")
    else:
        supabase.save_competition_dates(
            comp_info.get("start_date", "") or "",
            comp_info.get("end_date", "") or "",
            comp_name,
        )
        comp_id = supabase.competition_id
        if not comp_id:
            comps = supabase._get(
                "competitions",
                params={"select": "id", "limit": "1"},
            )
            comp_id = comps[0]["id"] if comps else None
            supabase.set_competition(comp_id)
        print(f"  -> competition creada: {comp_id} ({comp_name})")

    # --- 3. Migrar atletas (bulk) -------------------------------------------
    athlete_id_map = {}
    athlete_rows = []
    for a in sql["athletes"]:
        athlete_rows.append({
            "competition_id": comp_id,
            "name": a.get("name", ""),
            "club": a.get("club", ""),
            "category": a.get("category", ""),
            "gender": a.get("gender", ""),
            "birth_date": a.get("birth_date"),
            "bib_number": a.get("bib_number"),
        })
    created_athletes = _bulk_insert(supabase, "athletes", athlete_rows)
    for old_a, new_a in zip(sql["athletes"], created_athletes):
        athlete_id_map[old_a["id"]] = new_a["id"]
    print(f"  -> atletas: {len(created_athletes)}")

    # --- 4. Migrar categorías (bulk) ----------------------------------------
    category_rows = []
    for c in sql["categories"]:
        category_rows.append({
            "competition_id": comp_id,
            "name": c["name"],
            "min_age": _as_int(c.get("min_age")),
            "max_age": _as_int(c.get("max_age")),
        })
    _bulk_insert(supabase, "categories", category_rows)
    print(f"  -> categorías: {len(category_rows)}")

    # --- 5. Migrar eventos (bulk) -------------------------------------------
    event_id_map = {}
    event_rows = []
    for ev in sql["events"]:
        event_rows.append({
            "competition_id": comp_id,
            "name": ev.get("name", ""),
            "type": ev.get("type", ""),
            "category": ev.get("category", ""),
            "gender": ev.get("gender", ""),
            "lanes": _as_int(ev.get("lanes")) or 8,
            "round": ev.get("round", "Final"),
            "sport": ev.get("sport"),
        })
    created_events = _bulk_insert(supabase, "events", event_rows)
    for old_ev, new_ev in zip(sql["events"], created_events):
        event_id_map[old_ev["id"]] = new_ev["id"]
    print(f"  -> eventos: {len(created_events)}")

    # vertical heights por evento (individual, pocas filas)
    for ev in sql["events"]:
        heights = sql["vertical_heights"].get(ev["id"])
        if heights:
            ev_new = event_id_map[ev["id"]]
            try:
                heights_list = json.loads(heights) if isinstance(heights, str) else heights
            except Exception:
                heights_list = [heights]
            supabase.save_vertical_heights(ev_new, heights_list)

    # --- 6. Migrar jornadas (bulk) ------------------------------------------
    jornada_id_map = {}
    jornada_rows = []
    for j in sql["jornadas"]:
        jornada_rows.append({
            "competition_id": comp_id,
            "name": j["name"],
            "display_order": _as_int(j.get("display_order")) or 0,
        })
    created_jornadas = _bulk_insert(supabase, "jornadas", jornada_rows)
    for old_j, new_j in zip(sql["jornadas"], created_jornadas):
        jornada_id_map[old_j["id"]] = new_j["id"]
    print(f"  -> jornadas: {len(created_jornadas)}")

    # --- 7. Migrar schedules (bulk) -----------------------------------------
    schedule_rows = []
    for s in sql["schedules"]:
        j_id_new = jornada_id_map.get(s["jornada_id"])
        if not j_id_new:
            continue
        ev_sql = s.get("event_id")
        ev_new = event_id_map.get(ev_sql) if ev_sql else None
        ce_sql = s.get("combined_event_id")
        ce_new = event_id_map.get(ce_sql) if ce_sql else None
        schedule_rows.append({
            "competition_id": comp_id,
            "jornada_id": j_id_new,
            "event_id": ev_new,
            "combined_event_id": ce_new,
            "sub_event_index": _as_int(s.get("sub_event_index")),
            "sub_event_label": s.get("sub_event_label"),
            "start_accred": s.get("start_accred", ""),
            "end_accred": s.get("end_accred", ""),
            "entry_time": s.get("entry_time", ""),
            "event_time": s.get("event_time", ""),
            "display_order": _as_int(s.get("display_order")) or 0,
        })
    _bulk_insert(supabase, "event_schedule", schedule_rows)
    print(f"  -> schedules: {len(schedule_rows)}")

    # --- 8. Migrar registrations (bulk) con resultados y siembras -----------
    regs_by_event = {}
    for r in sql["registrations"]:
        regs_by_event.setdefault(r["event_id"], []).append(r)

    registration_rows = []
    reg_meta = []  # metadata para PATCH posterior (personal_best, etc.)
    for ev_id_sql, regs in regs_by_event.items():
        ev_id_new = event_id_map.get(ev_id_sql)
        if not ev_id_new:
            continue
        for r in regs:
            ath_sql = r.get("athlete_id")
            ath_new = athlete_id_map.get(ath_sql)
            if not ath_new:
                continue
            attempts = None
            raw_att = r.get("attempts")
            if raw_att:
                try:
                    attempts = json.loads(raw_att)
                except Exception:
                    attempts = None
            if attempts is None:
                attempts = [r.get(f"attempt{i}") or "" for i in range(1, 7)]

            registration_rows.append({
                "competition_id": comp_id,
                "athlete_id": ath_new,
                "event_id": ev_id_new,
                "heat_number": _as_int(r.get("heat_number")),
                "lane_number": _as_int(r.get("lane_number")),
                "order_number": _as_int(r.get("order_number")),
                "result": r.get("result", "") or "",
                "result_value": _as_float(r.get("result_value")),
                "is_disqualified": _as_int(r.get("is_disqualified")) or 0,
                "status": r.get("status", "Normal") or "Normal",
                "wind_speed": _as_float(r.get("wind_speed")),
                "personal_best": _as_float(r.get("personal_best")),
                "attempts": attempts,
            })
            reg_meta.append({
                "reg_id": None,  # se llena después del insert
                "athlete_id": ath_new,
                "heat_number": _as_int(r.get("heat_number")),
                "lane_number": _as_int(r.get("lane_number")),
                "order_number": _as_int(r.get("order_number")),
                "personal_best": _as_float(r.get("personal_best")),
            })

    created_regs = _bulk_insert(supabase, "registrations", registration_rows)
    print(f"  -> registrations: {len(created_regs)}")

    # personal_best ya se incluyó en el bulk insert, no hay que hacer PATCH extra

    # --- 9. Migrar miembros de relevos (bulk) -------------------------------
    relay_rows = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT event_id, club, members_text FROM relay_members ORDER BY event_id ASC, club ASC")
    for r in cur.fetchall():
        ev_id_new = event_id_map.get(r["event_id"])
        if not ev_id_new:
            continue
        relay_rows.append({
            "competition_id": comp_id,
            "event_id": ev_id_new,
            "club": r["club"],
            "members_text": r["members_text"],
        })
    conn.close()
    _bulk_insert(supabase, "relay_members", relay_rows)
    print(f"  -> relevos: {len(relay_rows)}")

    # --- 10. Migrar marcas combinadas (bulk) --------------------------------
    combined_rows = []
    for ev_id_sql, athletes_marks in sql["combined_marks"].items():
        ev_id_new = event_id_map.get(ev_id_sql)
        if not ev_id_new:
            continue
        for ath_id_sql, marks in athletes_marks.items():
            ath_new = athlete_id_map.get(ath_id_sql)
            if not ath_new:
                continue
            for ev_index, mark_value in marks.items():
                combined_rows.append({
                    "competition_id": comp_id,
                    "event_id": ev_id_new,
                    "athlete_id": ath_new,
                    "event_index": _as_int(ev_index),
                    "mark_value": mark_value,
                })
    _bulk_insert(supabase, "combined_marks", combined_rows)
    print(f"  -> marcas combinadas: {len(combined_rows)}")

    resumen = {
        "db_file": os.path.basename(db_path),
        "competition_id": comp_id,
        "competition_name": comp_name,
        "athletes": len(created_athletes),
        "events": len(created_events),
        "jornadas": len(created_jornadas),
        "schedules": len(schedule_rows),
        "registrations": len(created_regs),
        "relays": len(relay_rows),
        "combined_marks": len(combined_rows),
        "categories": len(category_rows),
    }
    return True, comp_id, resumen


def main():
    cfg = database.load_config()
    if cfg.get("data_backend") != "supabase":
        print("ERROR: config.json tiene data_backend != 'supabase'. "
              "Cambialo a 'supabase' antes de migrar.")
        return

    supabase = SupabaseDB()
    if not supabase.init_db():
        print("ERROR: No se pudo conectar a Supabase. Verifica supabase_url y supabase_key.")
        return

    db_files = sorted(glob.glob(os.path.join("Eventos", "*.db")))
    if not db_files:
        print("No se encontraron archivos .db en Eventos/")
        return

    print(f"Se encontraron {len(db_files)} archivos .db para migrar.")
    total = {
        "athletes": 0, "events": 0, "jornadas": 0, "schedules": 0,
        "registrations": 0, "relays": 0, "combined_marks": 0, "categories": 0,
    }

    for db_path in db_files:
        try:
            ok, comp_id, resumen = migrate_db_file(db_path, supabase)
            if ok:
                for k in total:
                    total[k] += resumen.get(k, 0)
                print(f"  [OK] {resumen['competition_name']}")
            else:
                print(f"  [FALLO] {os.path.basename(db_path)}")
        except Exception as e:
            print(f"  [ERROR] {os.path.basename(db_path)}: {e}")
            continue

    print("\n=== Resumen total ===")
    for k, v in total.items():
        print(f"  {k}: {v}")
    print("\nMigración completada.")


if __name__ == "__main__":
    main()
# =============================================================================
# AtletismoPro — Módulo de Base de Datos
# Copyright (c) 2025-2026 Douglas José López López
# Todos los derechos reservados. All rights reserved.
#
# Este software es propiedad exclusiva de Douglas José López López.
# Queda prohibida su copia, distribución o modificación sin autorización
# expresa y por escrito del titular. Ver archivo LICENSE para más detalles.
# =============================================================================
import sqlite3
import os
import sys
import json
import shutil
from datetime import date, datetime

if getattr(sys, 'frozen', False):
    # Directorio del ejecutable (.exe)
    DB_DIR = os.path.dirname(sys.executable)
else:
    # Directorio del script (.py)
    DB_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(DB_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config_data):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
    except Exception:
        pass

def load_last_db_path():
    data = load_config()
    path = data.get("last_db_path")
    if path and os.path.exists(os.path.dirname(path)):
        return path
    return os.path.join(DB_DIR, "atletismo.db")

def get_age_mode():
    data = load_config()
    return data.get("age_mode", "calendario")

def set_age_mode(mode):
    data = load_config()
    data["age_mode"] = mode
    save_config(data)

DB_PATH = load_last_db_path()

def set_db_path(new_path):
    global DB_PATH
    DB_PATH = new_path
    data = load_config()
    data["last_db_path"] = new_path
    save_config(data)

def get_db_name():
    return os.path.basename(DB_PATH)



def get_connection():
    """Establece una conexión con la base de datos SQLite y habilita claves foráneas."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Crea las tablas necesarias en la base de datos si no existen."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Pruebas (Eventos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT NOT NULL,
        gender TEXT NOT NULL CHECK(gender IN ('Masculino', 'Femenino', 'Mixto')),
        lanes INTEGER DEFAULT 8,
        sport TEXT DEFAULT 'Atletismo'
    );
    """)
    
    # Tabla de Atletas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS athletes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        club TEXT NOT NULL,
        category TEXT NOT NULL,
        gender TEXT NOT NULL CHECK(gender IN ('Masculino', 'Femenino', 'Mixto')),
        birth_date TEXT
    );
    """)
    
    # Tabla de Inscripciones y Resultados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        athlete_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        heat_number INTEGER, -- Número de serie (para Pista)
        lane_number INTEGER, -- Número de carril (para Pista)
        order_number INTEGER, -- Orden de participación (para Campo o Pista)
        result TEXT,         -- Formato de texto para mostrar (ej: "10.45s", "7.15m")
        result_value REAL,   -- Valor numérico para ordenar resultados (ej: 10.45 o 7.15)
        is_disqualified INTEGER DEFAULT 0 CHECK(is_disqualified IN (0, 1)),
        status TEXT DEFAULT 'Normal',
        attempt1 TEXT,
        attempt2 TEXT,
        attempt3 TEXT,
        attempt4 TEXT,
        attempt5 TEXT,
        attempt6 TEXT,
        FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
        UNIQUE(athlete_id, event_id)
    );
    """)

    # Tabla de información de la competencia (fechas y nombre)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS competition_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_name TEXT,
        start_date TEXT,
        end_date TEXT
    );
    """)

    # Tabla de Miembros de Relevos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relay_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        club TEXT NOT NULL,
        members_text TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
        UNIQUE(event_id, club)
    );
    """)

    # Tabla de jornadas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jornadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        display_order INTEGER DEFAULT 0
    );
    """)

    # Tabla de horarios por prueba
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        jornada_id INTEGER NOT NULL,
        event_id INTEGER,
        combined_event_id INTEGER,
        sub_event_index INTEGER,
        sub_event_label TEXT,
        start_accred TEXT,
        end_accred TEXT,
        entry_time TEXT,
        event_time TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        FOREIGN KEY (jornada_id) REFERENCES jornadas(id) ON DELETE CASCADE,
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY (combined_event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    """)

    # Tabla de categorias dinamicas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        min_age INTEGER NOT NULL,
        max_age INTEGER NOT NULL
    );
    """)
    
    # Insertar categorias por defecto si esta vacia
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("Sub-12", 0, 11),
            ("Sub-14", 12, 13),
            ("Sub-16", 14, 15),
            ("Sub-18", 16, 17),
            ("Sub-20", 18, 19),
            ("Mayor", 20, 99)
        ]
        cursor.executemany("INSERT INTO categories (name, min_age, max_age) VALUES (?, ?, ?)", default_categories)

    
    conn.commit()
    conn.close()

    # Ejecutar migraciones para agregar columnas si no existen en bases de datos existentes
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN status TEXT DEFAULT 'Normal';")
    except sqlite3.OperationalError:
        pass
    for i in range(1, 7):
        try:
            cursor.execute(f"ALTER TABLE registrations ADD COLUMN attempt{i} TEXT;")
        except sqlite3.OperationalError:
            pass
    # Migración: agregar birth_date a athletes si no existe
    try:
        cursor.execute("ALTER TABLE athletes ADD COLUMN birth_date TEXT;")
    except sqlite3.OperationalError:
        pass
    # Migración: agregar bib_number a athletes si no existe
    try:
        cursor.execute("ALTER TABLE athletes ADD COLUMN bib_number TEXT;")
    except sqlite3.OperationalError:
        pass
    # Migración: agregar round a events si no existe
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN round TEXT DEFAULT 'Final';")
    except sqlite3.OperationalError:
        pass
    # Migración: agregar wind_speed a registrations (Punto 7 — Viento)
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN wind_speed REAL;")
    except sqlite3.OperationalError:
        pass
    # Migración: agregar personal_best a registrations (Punto 1 — Siembra por marcas)
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN personal_best REAL;")
    except sqlite3.OperationalError:
        pass
    # Migración: agregar competition_name a competition_info si no existe
    try:
        cursor.execute("ALTER TABLE competition_info ADD COLUMN competition_name TEXT;")
    except sqlite3.OperationalError:
        pass
    # Migración: agregar vertical_heights a events si no existe
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN vertical_heights TEXT;")
    except sqlite3.OperationalError:
        pass
        
    # Migración: agregar attempts a registrations si no existe (para saltos con más de 6 intentos)
    try:
        cursor.execute("ALTER TABLE registrations ADD COLUMN attempts TEXT;")
    except sqlite3.OperationalError:
        pass

    # Migración: agregar sport a events si no existe (disciplina: Atletismo, Natación, etc.)
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN sport TEXT DEFAULT 'Atletismo';")
        cursor.execute("UPDATE events SET sport = 'Natación' WHERE type = 'Piscina';")
    except sqlite3.OperationalError:
        pass

    # Migración: relajar CHECK de type en events para admitir Lucha/Ciclismo/Patinaje
    try:
        row = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='events'").fetchone()
        if row and "CHECK(type IN" in row[0] and "Lucha" not in row[0]:
            conn.commit()
            conn.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("CREATE TABLE events_new (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, type TEXT NOT NULL CHECK(type IN ('Pista', 'Campo', 'Piscina', 'Lucha', 'Ciclismo', 'Patinaje')), category TEXT NOT NULL, gender TEXT NOT NULL, lanes INTEGER DEFAULT 8, round TEXT DEFAULT 'Final', vertical_heights TEXT, sport TEXT DEFAULT 'Atletismo')")
            cursor.execute("INSERT INTO events_new (id, name, type, category, gender, lanes, round, vertical_heights, sport) SELECT id, name, type, category, gender, lanes, round, vertical_heights, COALESCE(sport, 'Atletismo') FROM events")
            cursor.execute("DROP TABLE events")
            cursor.execute("ALTER TABLE events_new RENAME TO events")
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON;")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# --- RELEVOS (RELAYS) ---

def is_relay_event(event_name):
    if not event_name:
        return False
    name_lower = event_name.lower()
    return "relevo" in name_lower or "4x" in name_lower

def save_relay_members(event_id, club, members_text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM relay_members WHERE event_id=? AND club=?", (event_id, club))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE relay_members SET members_text=? WHERE id=?", (members_text, row["id"]))
    else:
        cursor.execute("INSERT INTO relay_members (event_id, club, members_text) VALUES (?, ?, ?)", (event_id, club, members_text))
    conn.commit()
    conn.close()

def get_relay_members(event_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT club, members_text FROM relay_members WHERE event_id = ?", (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row["club"]: row["members_text"] for row in rows}

# --- SALTOS VERTICALES (Alturas) ---

def save_vertical_heights(event_id, heights_list):
    """
    Guarda las alturas configuradas para una prueba de salto vertical.
    heights_list: lista de strings, ej: ["1.60", "1.65", "1.70"]
    """
    import json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET vertical_heights=? WHERE id=?",
                   (json.dumps(heights_list), event_id))
    conn.commit()
    conn.close()


def get_vertical_heights(event_id):
    """
    Retorna la lista de alturas configuradas para el evento.
    Retorna [] si no hay alturas configuradas.
    """
    import json
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vertical_heights FROM events WHERE id=?", (event_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row["vertical_heights"]:
        try:
            return json.loads(row["vertical_heights"])
        except (json.JSONDecodeError, TypeError):
            return []
    return []

# --- CATEGORÍAS DINÁMICAS ---

def add_category(name, min_age, max_age):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name, min_age, max_age) VALUES (?, ?, ?)", (name, min_age, max_age))
        conn.commit()
        success = True
        msg = "Categoría agregada."
    except sqlite3.IntegrityError:
        success = False
        msg = "Ya existe una categoría con ese nombre."
    conn.close()
    return success, msg

def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY min_age ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_athlete_full(athlete_id, name, club, category, gender, birth_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE athletes
        SET name = ?, club = ?, category = ?, gender = ?, birth_date = ?
        WHERE id = ?
    """, (name, club, category, gender, birth_date, athlete_id))
    conn.commit()
    conn.close()

def delete_category(cat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()

def calculate_category_from_birthdate(birth_date_str):
    """
    Calcula la categoría de un atleta según su fecha de nacimiento leyendo desde la base de datos.
    La edad se calcula por año calendario o por edad cumplida, según la configuración.
    """
    try:
        birth = date.fromisoformat(birth_date_str)  # formato YYYY-MM-DD
        today = date.today()
        
        mode = get_age_mode()
        if mode == "cumplida":
            # Edad cumplida al 31 de diciembre del año anterior (año competitivo)
            ref_date = date(today.year - 1, 12, 31)
            age = ref_date.year - birth.year - ((ref_date.month, ref_date.day) < (birth.month, birth.day))
        else:
            # La edad por año calendario es el año actual menos el año de nacimiento
            age = today.year - birth.year

        
        categories = get_categories()
        for cat in categories:
            if cat["min_age"] <= age <= cat["max_age"]:
                return cat["name"], age
                
        # Si no encaja en ninguna
        return "Libre", age
    except (ValueError, TypeError):
        return None, None


# --- OPERACIONES DE PRUEBAS (EVENTS) ---

def add_event(name, event_type, category, gender, lanes=8, round_type='Final', sport=None):
    if sport is None:
        sport = 'Natación' if event_type == 'Piscina' else 'Atletismo'
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (name, type, category, gender, lanes, round, sport) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, event_type, category, gender, lanes, round_type, sport)
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return event_id

def get_events():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_event(event_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

def update_event(event_id, name, event_type, category, gender, lanes, round_type, sport=None):
    if sport is None:
        sport = 'Natación' if event_type == 'Piscina' else 'Atletismo'
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET name = ?, type = ?, category = ?, gender = ?, lanes = ?, round = ?, sport = ? WHERE id = ?",
        (name, event_type, category, gender, lanes, round_type, sport, event_id)
    )
    conn.commit()
    conn.close()

# --- OPERACIONES DE ATLETAS (ATHLETES) ---

def add_athlete(name, club, category, gender, birth_date=None, bib_number=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO athletes (name, club, category, gender, birth_date, bib_number) VALUES (?, ?, ?, ?, ?, ?)",
        (name, club, category, gender, birth_date, bib_number)
    )
    conn.commit()
    athlete_id = cursor.lastrowid
    conn.close()
    return athlete_id

def get_athletes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM athletes ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_athlete(athlete_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM athletes WHERE id = ?", (athlete_id,))
    conn.commit()
    conn.close()

def update_athlete_bib(athlete_id, bib_number):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE athletes SET bib_number = ? WHERE id = ?", (bib_number, athlete_id))
    conn.commit()
    conn.close()

def update_athlete_category(athlete_id, category):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE athletes SET category = ? WHERE id = ?", (category, athlete_id))
    conn.commit()
    conn.close()

# --- OPERACIONES DE INSCRIPCIONES Y SIEMBRAS ---

def register_athlete_to_event(athlete_id, event_id):
    """Inscribe a un atleta en una prueba."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO registrations (athlete_id, event_id) VALUES (?, ?)",
            (athlete_id, event_id)
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False # Ya está inscrito
    conn.close()
    return success

def unregister_athlete_from_event(athlete_id, event_id):
    """Elimina la inscripción de un atleta de una prueba."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM registrations WHERE athlete_id = ? AND event_id = ?",
        (athlete_id, event_id)
    )
    conn.commit()
    conn.close()

def get_registrations_for_event(event_id):
    """Obtiene los atletas inscritos en una prueba, con sus detalles de siembra y resultados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, a.name AS athlete_name, a.club AS athlete_club, a.category AS athlete_category, a.gender AS athlete_gender, a.bib_number AS athlete_bib
        FROM registrations r
        JOIN athletes a ON r.athlete_id = a.id
        WHERE r.event_id = ?
        ORDER BY r.heat_number ASC, r.lane_number ASC, r.order_number ASC
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_events_for_athlete(athlete_id):
    """Obtiene las pruebas en las que está inscrito un atleta."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, r.result, r.heat_number, r.lane_number, r.order_number
        FROM registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.athlete_id = ?
    """, (athlete_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_registration_seeding(reg_id, heat_number, lane_number, order_number):
    """Actualiza la siembra (serie, carril u orden) de una inscripción."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE registrations
        SET heat_number = ?, lane_number = ?, order_number = ?
        WHERE id = ?
    """, (heat_number, lane_number, order_number, reg_id))
    conn.commit()
    conn.close()

def reset_event_seeding(event_id):
    """Limpia todos los datos de siembra (serie/carril/orden) de un evento.
    Debe llamarse ANTES de cualquier re-siembra para evitar datos obsoletos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE registrations
        SET heat_number = NULL, lane_number = NULL, order_number = NULL
        WHERE event_id = ?
    """, (event_id,))
    conn.commit()
    conn.close()

# --- OPERACIONES DE RESULTADOS ---

def update_result(reg_id, result_str, result_value, is_disqualified=0, status='Normal', attempts=None, wind_speed=None):
    """Actualiza la marca/resultado de un atleta inscrito."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Si tiene un estado especial, la marca se anula
    if status != 'Normal':
        result_value = None
        result_str = status
        is_disqualified = 1 if status == 'DQ' else 0
        
    # Convertir attempts a JSON si existe
    attempts_json = None
    if attempts:
        import json
        attempts_json = json.dumps(attempts)
        
    # Preparar campos de intentos de manera retrocompatible
    if attempts and len(attempts) >= 6:
        cursor.execute("""
            UPDATE registrations
            SET result = ?, result_value = ?, is_disqualified = ?, status = ?,
                attempt1 = ?, attempt2 = ?, attempt3 = ?, attempt4 = ?, attempt5 = ?, attempt6 = ?,
                wind_speed = ?, attempts = ?
            WHERE id = ?
        """, (result_str, result_value, is_disqualified, status, 
              attempts[0], attempts[1], attempts[2], attempts[3], attempts[4], attempts[5], 
              wind_speed, attempts_json, reg_id))
    else:
        cursor.execute("""
            UPDATE registrations
            SET result = ?, result_value = ?, is_disqualified = ?, status = ?, wind_speed = ?, attempts = ?
            WHERE id = ?
        """, (result_str, result_value, is_disqualified, status, wind_speed, attempts_json, reg_id))
    conn.commit()
    conn.close()


def has_results(event_id):
    """Verifica si una prueba ya tiene resultados digitados (registrados)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND result_value IS NOT NULL", (event_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def sort_field_results(rows, event_name):
    """
    Ordena los resultados de campo aplicando reglas de desempate de World Athletics.
    Retorna los rows ordenados y con una clave de ordenamiento inyectada '_sort_key'.
    """
    is_vertical = any(k in event_name.lower() for k in ("alto", "pértiga", "pertiga", "garrocha"))

    def get_sort_key(row):
        val = row.get("result_value")
        if val is None:
            val = -99999
            
        if is_vertical:
            attempts_at_best = 999
            total_x = 0
            
            # Obtener intentos desde el json o desde las 6 columnas
            import json
            att_list = []
            if row.get("attempts"):
                try:
                    att_list = json.loads(row["attempts"])
                except:
                    pass
            
            if not att_list:
                for i in range(1, 7):
                    if row.get(f"attempt{i}"):
                        att_list.append(row[f"attempt{i}"])
            
            for att in att_list:
                if att and "-" in att:
                    parts = att.split("-", 1)
                    if len(parts) == 2:
                        h_str, res = parts
                        try:
                            h = float(h_str.replace("m", "").replace(" ", ""))
                            res = res.upper()
                            total_x += res.count("X")
                            if h == val:
                                if res in ["O", "XO", "XXO"]:
                                    attempts_at_best = res.count("X") + 1
                        except ValueError:
                            pass
            return (val, -attempts_at_best, -total_x)
            
        else:
            import json
            att_list = []
            if row.get("attempts"):
                try:
                    att_list = json.loads(row["attempts"])
                except:
                    pass
            if not att_list:
                for i in range(1, 7):
                    if row.get(f"attempt{i}"):
                        att_list.append(row.get(f"attempt{i}"))

            marks = []
            for att in att_list:
                if att and att.upper() != "X" and att != "-":
                    try:
                        m = float(att.replace("m", "").replace(" ", ""))
                        marks.append(m)
                    except ValueError:
                        pass
            marks.sort(reverse=True)
            while len(marks) < 6:
                marks.append(0.0)
            return tuple(marks)

    dict_rows = [dict(r) for r in rows]
    for r in dict_rows:
        r["_sort_key"] = get_sort_key(r)
        
    dict_rows.sort(key=lambda x: x["_sort_key"], reverse=True)
    return dict_rows

def get_podium_for_event(event_id):
    """
    Calcula los 3 mejores lugares para una prueba.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, type FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return []
        
    event_type = event["type"]
    event_name = event["name"]
    order_by = "ASC" if event_type in ("Pista", "Piscina") else "DESC"
    
    query = f"""
        SELECT r.*, a.name AS athlete_name, a.club AS athlete_club
        FROM registrations r
        JOIN athletes a ON r.athlete_id = a.id
        WHERE r.event_id = ? AND r.result_value IS NOT NULL AND (r.status = 'Normal' OR r.status IS NULL) AND r.is_disqualified = 0
        ORDER BY r.result_value {order_by}
    """
    cursor.execute(query, (event_id,))
    rows = cursor.fetchall()
    
    if event_type == "Campo":
        rows = sort_field_results(rows, event_name)
    else:
        rows = [dict(r) for r in rows]
        # Agregamos sort key base para Pista
        for r in rows:
            r["_sort_key"] = r.get("result_value")
    
    if is_relay_event(event_name):
        relay_members = get_relay_members(event_id)
        clubs_seen = set()
        podium = []
        for r in rows:
            club = r["athlete_club"]
            if club not in clubs_seen:
                clubs_seen.add(club)
                r_dict = dict(r)
                members = relay_members.get(club, "")
                if members:
                    r_dict["relay_members"] = members
                    # Guardamos el club en athlete_name para la UI
                    r_dict["athlete_name"] = f"{club}"
                    r_dict["relay_members_display"] = members
                else:
                    r_dict["athlete_name"] = f"{club}"
                    r_dict["relay_members_display"] = "Sin nombres registrados"
                podium.append(r_dict)
                if len(podium) >= 3:
                    break
        conn.close()
        return podium
    else:
        conn.close()
        return rows[:3]

def get_medal_table(gender_filter=None):
    """
    Calcula la tabla general de medallería.
    Maneja empates: Si hay 2 oros, el siguiente es bronce.
    Los relevos cuentan como 1 medalla para el club.
    gender_filter: None (General), 'Masculino', 'Femenino'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Obtener todos los eventos finales o únicos
    query_events = "SELECT id, name, type, gender FROM events WHERE 1=1"
    if gender_filter:
        query_events += " AND gender = ?"
        cursor.execute(query_events, (gender_filter,))
    else:
        cursor.execute(query_events)
    events = cursor.fetchall()
    
    club_medals = {} # {club_name: {"oro": 0, "plata": 0, "bronce": 0}}
    
    for event in events:
        event_id = event["id"]
        event_type = event["type"]
        event_name = event["name"].lower()
        is_relay = "relevo" in event_name or "4x" in event_name
        
        order_by = "ASC" if event_type in ("Pista", "Piscina") else "DESC"
        
        # Obtener todos los resultados válidos para este evento
        cursor.execute(f"""
            SELECT r.*, a.club 
            FROM registrations r
            JOIN athletes a ON r.athlete_id = a.id
            WHERE r.event_id = ? AND r.result_value IS NOT NULL AND (r.status = 'Normal' OR r.status IS NULL) AND r.is_disqualified = 0
            ORDER BY r.result_value {order_by}
        """, (event_id,))
        results = cursor.fetchall()
        
        if not results:
            continue
            
        if event_type == "Campo":
            results = sort_field_results(results, event_name)
        else:
            results = [dict(r) for r in results]
            for r in results:
                r["_sort_key"] = r.get("result_value")
            
        medals_awarded_to_club = set()
        
        current_val = results[0]["_sort_key"]
        current_rank = 1
        athletes_at_current_rank = 0
        
        for row in results:
            club = row["club"]
            val = row["_sort_key"]
            
            if val != current_val:
                current_rank += athletes_at_current_rank
                current_val = val
                athletes_at_current_rank = 1
            else:
                athletes_at_current_rank += 1
                
            if current_rank > 3:
                break # Ya no hay medallas
                
            # Si es relevo y el club ya ganó medalla en este evento, saltar al siguiente atleta
            if is_relay and club in medals_awarded_to_club:
                continue
                
            if club not in club_medals:
                club_medals[club] = {"oro": 0, "plata": 0, "bronce": 0}
                
            if current_rank == 1:
                club_medals[club]["oro"] += 1
            elif current_rank == 2:
                club_medals[club]["plata"] += 1
            elif current_rank == 3:
                club_medals[club]["bronce"] += 1
                
            if is_relay:
                medals_awarded_to_club.add(club)
                
    conn.close()
    
    # Formatear y ordenar
    medal_table = []
    for club, medals in club_medals.items():
        total = medals["oro"] + medals["plata"] + medals["bronce"]
        if total > 0:
            medal_table.append({
                "club": club,
                "oro": medals["oro"],
                "plata": medals["plata"],
                "bronce": medals["bronce"],
                "total": total
            })
            
    # Ordenar por Oros (desc), Platas (desc), Bronces (desc)
    medal_table.sort(key=lambda x: (x["oro"], x["plata"], x["bronce"]), reverse=True)
    
    # Asignar posiciones y marcar ganador absoluto
    for i, row in enumerate(medal_table):
        row["position"] = i + 1
        
    return medal_table



# --- MARCA PERSONAL (PERSONAL BEST) PARA SIEMBRA POR MARCAS ---

def update_personal_best(reg_id, personal_best):
    """Actualiza la marca personal de un atleta para una inscripción (usada en siembra por marcas)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE registrations SET personal_best = ? WHERE id = ?", (personal_best, reg_id))
    conn.commit()
    conn.close()

def get_registrations_with_pb(event_id):
    """Obtiene inscripciones con marca personal para siembra por marcas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, a.name AS athlete_name, a.club AS athlete_club,
               a.category AS athlete_category, a.gender AS athlete_gender,
               a.bib_number AS athlete_bib
        FROM registrations r
        JOIN athletes a ON r.athlete_id = a.id
        WHERE r.event_id = ?
        ORDER BY r.personal_best ASC NULLS LAST
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- HISTORIAL DE MARCAS POR ATLETA ---

def get_athlete_history(athlete_id):
    """Obtiene todos los resultados de un atleta en todos los eventos del DB actual."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.result, r.result_value, r.status, r.wind_speed,
               r.heat_number, r.lane_number, r.is_disqualified,
               e.name AS event_name, e.type AS event_type,
               e.category AS event_category, e.gender AS event_gender,
               e.round AS event_round
        FROM registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.athlete_id = ?
        ORDER BY e.name ASC
    """, (athlete_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- BACKUP AUTOMÁTICO ---

def get_backup_dir():
    """Retorna la ruta de la carpeta de respaldos junto al DB actual."""
    db_dir = os.path.dirname(DB_PATH)
    backup_dir = os.path.join(db_dir, "backups_atletismo")
    return backup_dir

def create_backup(db_path=None):
    """Crea una copia de seguridad del archivo .db con timestamp.
    Retorna (éxito: bool, ruta_backup: str, mensaje: str)."""
    if db_path is None:
        db_path = DB_PATH
    if not os.path.exists(db_path):
        return False, "", "La base de datos no existe."
    try:
        backup_dir = get_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        db_name = os.path.splitext(os.path.basename(db_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{db_name}_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        shutil.copy2(db_path, backup_path)
        # Limpiar backups antiguos (mantener solo los últimos 10)
        _cleanup_old_backups(backup_dir, db_name, max_keep=10)
        return True, backup_path, f"Backup creado: {backup_filename}"
    except Exception as e:
        return False, "", f"Error al crear backup: {e}"

def _cleanup_old_backups(backup_dir, db_name, max_keep=10):
    """Elimina los backups más antiguos si hay más de max_keep."""
    try:
        pattern = f"{db_name}_backup_"
        backups = [
            f for f in os.listdir(backup_dir)
            if f.startswith(pattern) and f.endswith(".db")
        ]
        backups.sort()  # Ordenados por timestamp en el nombre
        if len(backups) > max_keep:
            for old_backup in backups[:len(backups) - max_keep]:
                os.remove(os.path.join(backup_dir, old_backup))
    except Exception:
        pass

def get_last_backup_info():
    """Retorna información del último backup (nombre, fecha) o None."""
    try:
        backup_dir = get_backup_dir()
        if not os.path.exists(backup_dir):
            return None
        db_name = os.path.splitext(os.path.basename(DB_PATH))[0]
        pattern = f"{db_name}_backup_"
        backups = [
            f for f in os.listdir(backup_dir)
            if f.startswith(pattern) and f.endswith(".db")
        ]
        if not backups:
            return None
        backups.sort()
        latest = backups[-1]
        latest_path = os.path.join(backup_dir, latest)
        mtime = os.path.getmtime(latest_path)
        return {
            "filename": latest,
            "path": latest_path,
            "date": datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S"),
            "size_kb": round(os.path.getsize(latest_path) / 1024, 1)
        }
    except Exception:
        return None

# --- PRUEBAS COMBINADAS: Guardado de Marcas por Prueba ---

def init_combined_marks_table():
    """Crea la tabla para guardar marcas parciales de pruebas combinadas si no existe."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS combined_marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        athlete_id INTEGER NOT NULL,
        event_index INTEGER NOT NULL,
        mark_value TEXT,
        UNIQUE(event_id, athlete_id, event_index),
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()

def save_combined_mark(event_id, athlete_id, event_index, mark_value):
    """Guarda o actualiza la marca de un atleta para una sub-prueba combinada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO combined_marks (event_id, athlete_id, event_index, mark_value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(event_id, athlete_id, event_index)
        DO UPDATE SET mark_value = excluded.mark_value
    """, (event_id, athlete_id, event_index, mark_value))
    conn.commit()
    conn.close()

def get_combined_marks(event_id, athlete_id):
    """Obtiene todas las marcas guardadas de un atleta para un evento combinado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_index, mark_value FROM combined_marks
        WHERE event_id = ? AND athlete_id = ?
        ORDER BY event_index ASC
    """, (event_id, athlete_id))
    rows = cursor.fetchall()
    conn.close()
    return {row["event_index"]: row["mark_value"] for row in rows}

def get_all_combined_marks_for_event(event_id):
    """Obtiene todas las marcas guardadas para todos los atletas de un evento combinado."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT athlete_id, event_index, mark_value FROM combined_marks
        WHERE event_id = ?
        ORDER BY athlete_id ASC, event_index ASC
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        aid = row["athlete_id"]
        if aid not in result:
            result[aid] = {}
        result[aid][row["event_index"]] = row["mark_value"]
    return result


# --- OPERACIONES DE COMPETENCIA (FECHAS) ---

def save_competition_dates(start_date, end_date, competition_name=""):
    """Guarda o actualiza las fechas y nombre de la competencia."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM competition_info LIMIT 1")
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE competition_info SET start_date = ?, end_date = ?, competition_name = ? WHERE id = ?",
                       (start_date, end_date, competition_name, row["id"]))
    else:
        cursor.execute("INSERT INTO competition_info (start_date, end_date, competition_name) VALUES (?, ?, ?)",
                       (start_date, end_date, competition_name))
    conn.commit()
    conn.close()

def get_competition_dates():
    """Obtiene el nombre y fechas de la competencia."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT competition_name, start_date, end_date FROM competition_info LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"competition_name": "", "start_date": "", "end_date": ""}

# --- OPERACIONES DE JORNADAS ---

def add_jornada(name, display_order=0):
    """Crea una nueva jornada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jornadas (name, display_order) VALUES (?, ?)",
                   (name, display_order))
    conn.commit()
    jornada_id = cursor.lastrowid
    conn.close()
    return jornada_id

def get_jornadas():
    """Obtiene todas las jornadas ordenadas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jornadas ORDER BY display_order ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_jornada(jornada_id):
    """Elimina una jornada y sus horarios asociados."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jornadas WHERE id = ?", (jornada_id,))
    conn.commit()
    conn.close()

def update_jornada(jornada_id, name, display_order):
    """Actualiza el nombre y orden de una jornada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jornadas SET name = ?, display_order = ? WHERE id = ?",
                   (name, display_order, jornada_id))
    conn.commit()
    conn.close()

# --- OPERACIONES DE HORARIOS (EVENT_SCHEDULE) ---

def add_schedule_entry(jornada_id, event_id=None, combined_event_id=None, sub_event_index=None,
                       sub_event_label=None, start_accred='', end_accred='', entry_time='',
                       event_time='', display_order=0):
    """Agrega una entrada de horario para una prueba en una jornada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO event_schedule 
        (jornada_id, event_id, combined_event_id, sub_event_index, sub_event_label,
         start_accred, end_accred, entry_time, event_time, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (jornada_id, event_id, combined_event_id, sub_event_index, sub_event_label,
          start_accred, end_accred, entry_time, event_time, display_order))
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    return entry_id

def get_schedules_for_jornada(jornada_id):
    """Obtiene todos los horarios de una jornada con datos del evento y ordena por hora correcta."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT es.*, 
               e.name AS event_name, e.type AS event_type, 
               e.category AS event_category, e.gender AS event_gender,
               e.round AS event_round,
               ce.name AS combined_name, ce.category AS combined_category,
               ce.gender AS combined_gender
        FROM event_schedule es
        LEFT JOIN events e ON es.event_id = e.id
        LEFT JOIN events ce ON es.combined_event_id = ce.id
        WHERE es.jornada_id = ?
    """, (jornada_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = [dict(r) for r in rows]
    
    # Python time sort to handle AM/PM properly
    from datetime import datetime
    def parse_time(t_str):
        if not t_str:
            return datetime.max
        try:
            # Common format for AM/PM like "08:30 AM" or "8:30 am"
            return datetime.strptime(t_str.strip().lower(), "%I:%M %p")
        except:
            pass
        try:
            # 24h format like "08:30" or "14:30"
            return datetime.strptime(t_str.strip(), "%H:%M")
        except:
            pass
        # Fallback to string sorting if format is unknown
        return t_str

    results.sort(key=lambda x: (parse_time(x.get('event_time', '')), x.get('display_order', 999)))
    return results

def get_all_schedules_grouped():
    """Obtiene todos los horarios agrupados por jornada."""
    jornadas = get_jornadas()
    result = []
    for j in jornadas:
        schedules = get_schedules_for_jornada(j["id"])
        result.append({"jornada": j, "schedules": schedules})
    return result

def delete_schedule_entry(entry_id):
    """Elimina una entrada de horario."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM event_schedule WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

def update_schedule_entry(entry_id, start_accred, end_accred, entry_time, event_time, display_order=0):
    """Actualiza los horarios de una entrada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE event_schedule 
        SET start_accred = ?, end_accred = ?, entry_time = ?, event_time = ?, display_order = ?
        WHERE id = ?
    """, (start_accred, end_accred, entry_time, event_time, display_order, entry_id))
    conn.commit()
    conn.close()

def get_schedule_for_event(event_id):
    """Obtiene el horario de un evento específico."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT es.*, j.name AS jornada_name
        FROM event_schedule es
        JOIN jornadas j ON es.jornada_id = j.id
        WHERE es.event_id = ?
        ORDER BY es.event_time ASC
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_assigned_event_ids():
    """Obtiene los IDs de eventos que ya están asignados a alguna jornada."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT event_id FROM event_schedule WHERE event_id IS NOT NULL
        UNION
        SELECT DISTINCT combined_event_id FROM event_schedule WHERE combined_event_id IS NOT NULL
    """)
    rows = cursor.fetchall()
    conn.close()
    return {r[0] for r in rows if r[0] is not None}

def get_assigned_combined_sub_indices(combined_event_id):
    """Obtiene los índices de sub-pruebas combinadas ya asignadas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sub_event_index FROM event_schedule 
        WHERE combined_event_id = ? AND sub_event_index IS NOT NULL
    """, (combined_event_id,))
    rows = cursor.fetchall()
    conn.close()
    return {r[0] for r in rows}


def get_athletes_count_per_club():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT club, COUNT(*) as total FROM athletes GROUP BY club ORDER BY total DESC, club ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Inicializar base de datos
if __name__ == "__main__":
    init_db()
    print("Base de datos inicializada correctamente.")


import sqlite3
import os
import sys

# Append the directory so we can import database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import database

def patch_database():
    conn = database.get_connection()
    # Disable foreign keys temporarily
    conn.execute("PRAGMA foreign_keys = OFF;")
    
    # We will rename the old table and recreate it
    try:
        # Create a new events table with the correct CHECK constraint
        conn.execute("""
        CREATE TABLE events_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Pista', 'Campo', 'Piscina')),
            category TEXT NOT NULL,
            gender TEXT NOT NULL CHECK(gender IN ('Masculino', 'Femenino', 'Mixto')),
            lanes INTEGER DEFAULT 8,
            round TEXT DEFAULT 'Final'
        );
        """)
        
        # Copy data
        # Check if 'round' column exists in old table
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(events);")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'round' in columns:
            conn.execute("INSERT INTO events_new SELECT * FROM events;")
        else:
            conn.execute("INSERT INTO events_new (id, name, type, category, gender, lanes) SELECT id, name, type, category, gender, lanes FROM events;")
            
        # Drop old table
        conn.execute("DROP TABLE events;")
        
        # Rename new table
        conn.execute("ALTER TABLE events_new RENAME TO events;")
        
        conn.commit()
        print("Base de datos parcheada con éxito.")
    except Exception as e:
        conn.rollback()
        print(f"Error al parchear: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    patch_database()

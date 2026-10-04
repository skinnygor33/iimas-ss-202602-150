# crear_db.py
# Crea la base de datos SQLite de tráfico de red (vacía, solo estructura).
import sqlite3

DB_FILE = "trafico_red.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trafico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    ip_origen TEXT,
    ip_destino TEXT,
    puerto_origen INTEGER,
    puerto_destino INTEGER,
    protocolo TEXT,
    bytes INTEGER,
    paquetes INTEGER,
    duracion REAL,
    clasificacion TEXT,
    confianza REAL,
    archivo_origen TEXT
);

CREATE TABLE IF NOT EXISTS archivos_procesados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_archivo TEXT UNIQUE,
    fecha_ingesta TEXT,
    estado TEXT DEFAULT 'pendiente',
    registros_extraidos INTEGER DEFAULT 0
);
"""

def crear_base():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Base de datos '{DB_FILE}' creada con tablas 'trafico' y 'archivos_procesados' (vacías).")

if __name__ == "__main__":
    crear_base()

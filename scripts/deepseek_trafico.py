# deepseek_trafico.py
# Consultas en lenguaje natural (español) sobre la base de tráfico de red, usando DeepSeek vía Ollama.
# Incluye insertar_registro(): punto de entrada de ingesta para el futuro parser de PCAPs / API.
import sys
import sqlite3
import ollama

db_file = "trafico_red.sqlite"
model_name = "deepseek-r1:14b"

def get_database_schema(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = [t[0] for t in cursor.fetchall()]

        schema = ""
        for tabla in tablas:
            cursor.execute(f"PRAGMA table_info({tabla});")
            columnas = cursor.fetchall()
            schema += f"Tabla '{tabla}':\n"
            for col in columnas:
                schema += f"  - {col[1]} ({col[2]})\n"
            schema += "\n"

        conn.close()
        return schema
    except Exception as e:
        print(f"[Error] No se pudo leer el esquema: {e}")
        return None

def insertar_registro(datos: dict):
    """Inserta un registro en la tabla 'trafico'. 'datos' usa como llaves los nombres de columna."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    columnas = ", ".join(datos.keys())
    marcadores = ", ".join(["?"] * len(datos))
    cursor.execute(
        f"INSERT INTO trafico ({columnas}) VALUES ({marcadores})",
        list(datos.values())
    )
    conn.commit()
    conn.close()

def preguntar(pregunta, schema):
    prompt = f"""
    Tú eres un experto en SQL. Basado en este esquema:
    ---
    {schema}
    ---
    Escribe una consulta SQL (y NADA MÁS) para responder:
    Pregunta: "{pregunta}"

    SQL Query:
    """
    response = ollama.chat(
        model=model_name,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0.0}
    )
    sql = response['message']['content'].strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.replace(';', '').strip()

def main():
    schema = get_database_schema(db_file)
    if schema is None:
        print(f"[Error] No se encontró '{db_file}'. Corre primero crear_db.py")
        sys.exit()

    print("--- Conectado a trafico_red.sqlite ---")

    while True:
        pregunta = input("\nPregunta: ")
        if pregunta.lower() in ['salir', 'exit', 'quit']:
            break
        if not pregunta:
            continue

        sql_query = preguntar(pregunta, schema)
        print(f"[Debug] SQL: {sql_query}")

        if not sql_query.upper().startswith("SELECT"):
            print("[Error] Solo se permiten SELECTs.")
            continue

        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            resultados = cursor.fetchall()
            conn.close()
            print(resultados if resultados else "(sin resultados)")
        except Exception as e:
            print(f"[Error en consulta] {e}")

if __name__ == "__main__":
    main()

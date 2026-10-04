# chinook_deepseek.py
# Prueba de concepto original: DeepSeek (vía Ollama) traduce preguntas en español a SQL
# sobre la base de datos de ejemplo Chinook. Es el "punto de partida" de deepseek_trafico.py.
import sys
import sqlite3
import ollama

db_file = "Chinook_Sqlite.sqlite"
model_name = "deepseek-r1:14b"

def get_database_schema(db_path):
    print("Obteniendo esquema de la base de datos...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = [tabla[0] for tabla in cursor.fetchall()]

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

    except sqlite3.OperationalError:
        return None
    except Exception as e:
        print(f"[Error] No se pudo leer el esquema de la DB: {e}")
        return None

def main():
    schema = get_database_schema(db_file)

    if schema is None:
        print(f"\n[Error] No se pudo encontrar o leer la base de datos '{db_file}'.")
        print("Descárgala con:")
        print("wget https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite")
        sys.exit()

    print("\n--- ¡Conexión exitosa! ---")
    print("El LLM ahora conoce el esquema de la base de datos Chinook.")
    print("Escribe 'salir' para terminar.")

    while True:
        try:
            pregunta = input("\nPregunta: ")
            if pregunta.lower() in ['salir', 'exit', 'quit']:
                print("¡Adiós!")
                break
            if not pregunta:
                continue

            prompt = f"""
            Tú eres un experto en SQL. Basado en el siguiente esquema de base de datos SQL:
            ---
            {schema}
            ---

            Escribe una consulta SQL (y NADA MÁS que la consulta SQL) para responder a la siguiente pregunta del usuario.

            Pregunta: "{pregunta}"

            SQL Query:
            """

            print("[Debug] Generando SQL con DeepSeek...")
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': 0.0}
            )

            sql_query = response['message']['content'].strip()

            if sql_query.startswith("```sql"):
                sql_query = sql_query[5:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.replace(';', '').strip()

            print(f"[Debug] SQL Generado: {sql_query}")

            if not sql_query.upper().startswith("SELECT"):
                print("[Error] El modelo intentó ejecutar una consulta no permitida (solo se permiten SELECTs).")
                continue

            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            resultados = cursor.fetchall()

            print("\n--- Resultados de la Base de Datos ---")
            if not resultados:
                print("(No se encontraron resultados)")
            else:
                for fila in resultados:
                    print(fila)

            conn.close()

        except ollama.ResponseError:
            print("\n[Error] No se pudo conectar al servidor de Ollama.")
            print(f"Asegúrate de que Ollama esté corriendo y de haber instalado el modelo con: ollama run {model_name}")
            sys.exit()
        except Exception as e:
            print(f"[Error en la consulta] {e}")

if __name__ == "__main__":
    main()

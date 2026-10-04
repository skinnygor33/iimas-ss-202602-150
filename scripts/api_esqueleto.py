# api_esqueleto.py  --  *** NO PROBADO ***
# Esqueleto de API (FastAPI) que reutiliza deepseek_trafico.py. Sirve como punto de partida.
# Ejecutar (desde scripts/): uvicorn api_esqueleto:app --host 0.0.0.0 --port 8000
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3

from deepseek_trafico import get_database_schema, preguntar, db_file

app = FastAPI(title="API de detección de tráfico malicioso")

class PreguntaRequest(BaseModel):
    pregunta: str

class RegistroTrafico(BaseModel):
    timestamp: str
    ip_origen: str
    ip_destino: str
    puerto_origen: int
    puerto_destino: int
    protocolo: str
    bytes: int
    paquetes: int
    duracion: float
    clasificacion: str
    confianza: float
    archivo_origen: str

@app.get("/status")
def status():
    return {"db_conectada": get_database_schema(db_file) is not None}

@app.post("/preguntar")
def hacer_pregunta(req: PreguntaRequest):
    schema = get_database_schema(db_file)
    if schema is None:
        raise HTTPException(status_code=500, detail="No se pudo leer la base de datos")
    sql_query = preguntar(req.pregunta, schema)
    if not sql_query.upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Consulta generada no permitida")
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        resultados = cursor.fetchall()
        conn.close()
        return {"sql": sql_query, "resultados": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingesta")
def ingerir_registro(registro: RegistroTrafico):
    datos = registro.dict()  # en pydantic v2 usar registro.model_dump()
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    columnas = ", ".join(datos.keys())
    marcadores = ", ".join(["?"] * len(datos))
    cursor.execute(f"INSERT INTO trafico ({columnas}) VALUES ({marcadores})", list(datos.values()))
    conn.commit()
    conn.close()
    return {"status": "insertado", "registro": datos}

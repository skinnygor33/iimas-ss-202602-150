# Pipeline de detección de tráfico malicioso + consulta en lenguaje natural

Servicio social, IIMAS-UNAM (Facultad de Ingeniería). Autora: Emilia Macarena Arriaga Rodríguez.
Responsable: Ing. Román Victoriano Osorio Comparán.

Este repositorio es el **punto cero** para quien retome el proyecto. Documenta qué se construyó, cómo correrlo, qué decisiones se tomaron, qué funciona, qué no está probado y qué falta.

---

## 1. Qué hace este proyecto

Dos piezas independientes que, al final, se conectan a través de una base de datos:

1. **Clasificador de tráfico (Modelo A, Machine Learning).** Un Random Forest que recibe flujos de red (features tipo CICFlowMeter) y decide si son `BENIGN` o `MALICIOSO`. **Esta es la pieza que detecta.**
2. **Consulta en lenguaje natural (Modelo B, LLM).** DeepSeek corriendo local con Ollama traduce preguntas en español a SQL y las ejecuta sobre la base de datos de tráfico. **Esta pieza no detecta nada**: solo consulta lo que ya esté en la base (incluida la columna `clasificacion` que llena el Modelo A).

Arquitectura objetivo:

```
PCAP → [extracción de flujos: Zeek / CICFlowMeter] → [Modelo A: clasificador]
                                                           ↓
                                              [SQLite: tabla trafico]
                                                           ↓
                              [Modelo B: DeepSeek NL→SQL]  ←  [API (FastAPI)]
```

## 2. Estado actual

| Pieza | Estado |
|---|---|
| Base de datos SQLite (vacía, con esquema) | Hecho y probado |
| DeepSeek + Ollama consultando la base | Hecho y probado (base vacía) |
| Prueba de concepto con Chinook | Hecho y probado |
| Entrenamiento y evaluación del clasificador (CICIDS2017) | Hecho y probado |
| Extracción de flujos desde PCAP real (Zeek/CICFlowMeter) | **Pendiente** |
| Conectar `modelo.predict()` con `insertar_registro()` | **Pendiente** |
| API (FastAPI) | Esqueleto **sin probar** |
| Base de datos poblada | **Pendiente** (hoy está vacía a propósito) |

## 3. Estructura del repositorio

```
.
├── README.md
├── requirements.txt
├── .gitignore
└── scripts/
    ├── chinook_deepseek.py     # prueba de concepto original (base Chinook)
    ├── crear_db.py             # crea trafico_red.sqlite (vacía)
    ├── deepseek_trafico.py     # consultas en español sobre trafico_red.sqlite + insertar_registro()
    ├── entrenar_modelo.py      # entrena y evalúa el clasificador con CICIDS2017
    └── api_esqueleto.py        # esqueleto de API (NO PROBADO)
```

Los archivos `.sqlite`, `.pkl`, `.csv` y el dataset están en `.gitignore` a propósito (pesan mucho y se regeneran).

## 4. Instalación

Probado en Ubuntu (nodo de clúster), Python 3.

```bash
# 1. Entorno virtual
python3 -m venv venv
source venv/bin/activate          # hay que activarlo en cada terminal nueva
pip install -r requirements.txt

# 2. Ollama (binario de sistema, no es paquete de Python; puede requerir sudo)
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &                    # solo si el nodo no usa systemd
ollama pull deepseek-r1:14b       # ~9 GB; el nodo necesita salida a internet
```

Si el nodo de cómputo no tiene internet, descargar el modelo desde otra máquina y copiar `~/.ollama/models`.

## 5. Descripción de los scripts

Todos se corren desde `scripts/` con el venv activado.

### `crear_db.py`
Crea `trafico_red.sqlite` con dos tablas, sin filas:
- `trafico`: un registro por flujo (`timestamp`, `ip_origen`, `ip_destino`, `puerto_origen`, `puerto_destino`, `protocolo`, `bytes`, `paquetes`, `duracion`, `clasificacion`, `confianza`, `archivo_origen`).
- `archivos_procesados`: control de qué PCAPs ya se ingirieron (`nombre_archivo` único, `estado`, `registros_extraidos`).

> **Supuesto:** este esquema lo propuse yo; no me lo especificaron. Si el equipo define uno distinto, hay que cambiar el `CREATE TABLE` aquí y los campos de `RegistroTrafico` en la API. El esquema es de **SQLite**; si el proyecto migra a PostgreSQL o a una base NoSQL (como plantean los objetivos de la tesina) habrá que adaptarlo.

Uso: `python crear_db.py`

### `deepseek_trafico.py`
Bucle interactivo: lee el esquema de la base, se lo pasa a DeepSeek en un prompt, recibe SQL, lo valida y lo ejecuta.
- `get_database_schema()` lee tablas y columnas con `PRAGMA table_info`. El LLM *necesita* el esquema para generar SQL correcto.
- `preguntar()` arma el prompt y llama a Ollama con `temperature=0.0` (queremos determinismo).
- **Medida de seguridad:** solo se ejecuta si la consulta empieza con `SELECT`. Es una validación simple, no una garantía completa (ver limitaciones).
- `insertar_registro(dict)` es el **gancho de ingesta**: recibe un diccionario con columnas de `trafico` y lo inserta. Es lo que debe llamar el futuro parser de PCAPs o la API.

Uso: `python deepseek_trafico.py` y escribir preguntas; `salir` para terminar.

### `chinook_deepseek.py`
La prueba de concepto original sobre la base de ejemplo Chinook. Se conserva como referencia de cómo nació `deepseek_trafico.py` (es el mismo patrón con otro esquema). Requiere descargar `Chinook_Sqlite.sqlite` (el script imprime el `wget`).

### `entrenar_modelo.py`
Entrena y evalúa el clasificador binario. Pasos:
1. Carga los 8 CSV de CICIDS2017 (`MachineLearningCVE/`) y los concatena. **Hay que editar la variable `carpeta`**: hoy tiene una ruta absoluta de mi usuario en el nodo.
2. Limpia: quita espacios en los nombres de columna (el dataset los trae inconsistentes), reemplaza infinitos por NaN, elimina NaN y **elimina duplicados**.
3. Define `y = 0` si `Label == BENIGN`, `1` si es cualquier ataque.
4. Split 80/20 estratificado (`random_state=42`).
5. `RandomForestClassifier(n_estimators=100, class_weight='balanced')`.
6. Imprime: reporte de clasificación, tabla cruzada y % de acierto **por tipo de ataque**, validación cruzada de 5 folds, top 10 de features.
7. Guarda `modelo_deteccion.pkl` y `columnas_modelo.pkl`.

**`columnas_modelo.pkl` es importante:** guarda el orden exacto de las columnas con que se entrenó. Al clasificar tráfico nuevo, el DataFrame debe tener esas mismas columnas en ese mismo orden.

Uso: `python entrenar_modelo.py`. Tarda bastante (millones de filas; la validación cruzada entrena 5 modelos). Conviene correrlo en `tmux` y guardar la salida: `python entrenar_modelo.py > salida.log 2>&1`.

### `api_esqueleto.py` (sin probar)
FastAPI con `/status`, `/preguntar` (NL→SQL→resultado) y `/ingesta` (inserta un registro). Reutiliza las funciones de `deepseek_trafico.py`. No se llegó a ejecutar. Nota: `registro.dict()` está deprecado en pydantic v2 (usar `model_dump()`).

## 6. Dataset

**CICIDS2017** (Canadian Institute for Cybersecurity, Univ. de New Brunswick): https://www.unb.ca/cic/datasets/ids-2017.html
Se usó `MachineLearningCSV.zip` → carpeta `MachineLearningCVE/` (8 CSV, ~78 features por flujo + `Label`). Cita: Sharafaldin, Lashkari y Ghorbani, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization", ICISSP 2018.

Distribución de clases tras limpiar (nulos, infinitos y duplicados): BENIGN 2,095,057 · DoS Hulk 172,846 · DDoS 128,014 · PortScan 90,694 · DoS GoldenEye 10,286 · FTP-Patator 5,931 · DoS slowloris 5,385 · DoS Slowhttptest 5,228 · SSH-Patator 3,219 · Bot 1,948 · Web Attack Brute Force 1,470 · Web Attack XSS 652 · Infiltration 36 · Web Attack SQL Injection 21 · Heartbleed 11.

## 7. Resultados

- **Primer entrenamiento (sin quitar duplicados):** precision, recall y F1 = 1.00 en todo. Resultado sospechoso, no bueno: CICIDS2017 tiene muchas filas duplicadas y el modelo memoriza. Por eso el script quita duplicados.
- **Validación cruzada 5-fold (F1):** 0.9490 ± 0.0182 (folds: 0.9273, 0.9657, 0.9598, 0.9264, 0.9659). *Esta cifra viene de la corrida **sin** `class_weight`; la corrida final con `class_weight='balanced'` también calcula la validación cruzada, pero no registré ese valor — actualizarlo al volver a correr.*
- **Top features:** Packet Length Std, Avg Bwd Segment Size, Packet Length Variance, Max Packet Length, Bwd Packet Length Std… Todas son de comportamiento del flujo; `Destination Port` no domina (buena señal: no hay un atajo trivial por puerto).
- **Acierto por tipo de ataque, con `class_weight='balanced'`:** >99% en la mayoría (DDoS 99.96%, DoS Hulk 99.86%, PortScan 99.79%, FTP/SSH-Patator ~100%, BENIGN 99.91%). Más débiles: Bot 85.49% (antes 76.17% sin balanceo), Infiltration 85.71% (6/7), SQL Injection 66.67% (4/6).

## 8. Limitaciones y problemas conocidos

1. **El dataset es sintético.** El tráfico benigno se generó con un perfil de usuarios simulados (B-Profile) y los ataques con herramientas automatizadas en laboratorio. Las clases son más fáciles de separar que en tráfico real. **F1 ≈ 0.95 es optimista**; con tráfico real del clúster se espera que baje. Esto es una crítica conocida de CICIDS2017.
2. **Clases casi sin datos.** Infiltration (36), SQL Injection (21) y Heartbleed (11) tienen muy pocas muestras; sus porcentajes de acierto se calculan sobre 1–7 filas de prueba y no son estadísticamente confiables. `class_weight` no resuelve esto. Opciones: SMOTE, más datos, o aceptar la limitación.
3. **DeepSeek-R1 no siempre obedece "solo SQL".** A veces antepone texto explicativo o bloques de razonamiento (`<think>…</think>`), y la validación `startswith("SELECT")` lo rechaza (esto se documentó en la tesina, Figura 7). Mejora pendiente: extraer el SQL del bloque ```` ```sql ```` con una regex y descartar el `<think>` antes de validar.
4. **La validación "solo SELECT" es básica.** Un `SELECT` puede seguir siendo costoso, y no cubre todos los casos. Para uso real, abrir la base en modo solo lectura (`sqlite3.connect("file:trafico_red.sqlite?mode=ro", uri=True)`) y limitar tiempo/filas.
5. **Rutas absolutas** en `entrenar_modelo.py` (variable `carpeta`).
6. **Paralelismo:** en una corrida vi un solo núcleo al 100 % durante la validación cruzada con `n_jobs=-1` anidado. La versión actual usa `n_jobs=1` en el modelo y `n_jobs=5` en `cross_val_score` para evitarlo; no medí si mejoró el tiempo.
7. **La clasificación es binaria.** No dice *qué* tipo de ataque es.

## 9. Siguientes pasos sugeridos

1. Extraer flujos desde PCAP real con **CICFlowMeter** (mismas ~78 columnas que el dataset, para que el modelo sea compatible) o Zeek (habría que mapear sus columnas a las del modelo).
2. Script de inferencia: cargar `modelo_deteccion.pkl` + `columnas_modelo.pkl`, ordenar columnas, `predict_proba`, y llamar a `insertar_registro()` con `clasificacion` y `confianza`.
3. Probar y completar la API; registrar PCAPs procesados en `archivos_procesados`.
4. Mejorar la limpieza de la salida de DeepSeek (punto 3 de limitaciones) y pasar a conexión de solo lectura.
5. Validar el modelo con tráfico real del clúster y, si hace falta, reentrenar con datos propios etiquetados.
6. Valorar clasificación multiclase y SMOTE para las clases raras.
7. Confirmar con el equipo el esquema definitivo de la base (y si será SQLite, PostgreSQL o NoSQL).

## 10. Reproducir el flujo completo (resumen)

```bash
source venv/bin/activate
cd scripts
python crear_db.py                 # base vacía
python deepseek_trafico.py         # consultas en español (requiere Ollama corriendo)
python entrenar_modelo.py          # requiere el dataset y editar la ruta `carpeta`
```

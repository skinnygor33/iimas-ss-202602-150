# entrenar_modelo.py
import pandas as pd
import numpy as np
import glob
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

# --- 1. Cargar todos los CSV de la carpeta ---
carpeta = "/home/emilia_mar/src/dataset/MachineLearningCSV/MachineLearningCVE/"
archivos = glob.glob(carpeta + "*.csv")

print(f"Encontrados {len(archivos)} archivos CSV. Cargando...")
dfs = []
for archivo in archivos:
    df_temp = pd.read_csv(archivo)
    df_temp.columns = df_temp.columns.str.strip()  # quita espacios en los nombres de columnas
    dfs.append(df_temp)

df = pd.concat(dfs, ignore_index=True)
print(f"Total de filas cargadas: {len(df)}")

# --- 2. Limpieza: infinitos, NaN y duplicados ---
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df.dropna(inplace=True)
print(f"Filas después de quitar NaN/infinitos: {len(df)}")

filas_antes = len(df)
df = df.drop_duplicates()
print(f"Filas después de quitar duplicados: {len(df)} (se quitaron {filas_antes - len(df)})")

df = df.reset_index(drop=True)

print(f"\nDistribución de Label (ya limpio):\n{df['Label'].value_counts()}")

# --- 3. Separar features (X) y target (y) ---
y = (df['Label'] != 'BENIGN').astype(int)
X = df.drop(columns=['Label'])
X = X.select_dtypes(include=[np.number])

# --- 4. Split train/test ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# --- 5. Entrenar RandomForest CON class_weight='balanced' ---
# Esto le da más peso a las clases minoritarias (Bot, Infiltration, SQL Injection, etc.)
# durante el entrenamiento, para que el modelo no las ignore por tener pocas muestras.
print("\nEntrenando modelo (con class_weight='balanced')...")
modelo = RandomForestClassifier(
    n_estimators=100,
    random_state=42,
    n_jobs=1,  # n_jobs=1 aquí para que cross_val_score reparta bien los núcleos más abajo
    class_weight='balanced'
)
modelo.fit(X_train, y_train)

# --- 6. Evaluar (binario) ---
y_pred = modelo.predict(X_test)
print("\n--- Resultados (BENIGN vs MALICIOSO) ---")
print(classification_report(y_test, y_pred, target_names=['BENIGN', 'MALICIOSO']))

# --- 7. Desglose por tipo de ataque real (multiclase), usando el Label original ---
labels_originales_test = df.loc[X_test.index, 'Label']

print("\n--- Desglose por tipo de ataque (comparando contra Label original) ---")
resultado_detalle = pd.DataFrame({
    'label_real': labels_originales_test.values,
    'prediccion': np.where(y_pred == 1, 'MALICIOSO', 'BENIGN')
})
tabla_cruzada = pd.crosstab(resultado_detalle['label_real'], resultado_detalle['prediccion'])
print(tabla_cruzada)

print("\n--- % de detección correcta por tipo de ataque ---")
for tipo_ataque in labels_originales_test.unique():
    mask = labels_originales_test == tipo_ataque
    esperado = 'BENIGN' if tipo_ataque == 'BENIGN' else 'MALICIOSO'
    correctos = (resultado_detalle.loc[mask.values, 'prediccion'] == esperado).sum()
    total = mask.sum()
    print(f"  {tipo_ataque}: {correctos}/{total} ({100 * correctos / total:.2f}%)")

# --- 8. Validación cruzada (5-fold) ---
print("\n--- Validación cruzada (5-fold) ---")
modelo_cv = RandomForestClassifier(
    n_estimators=100, random_state=42, n_jobs=1, class_weight='balanced'
)
scores = cross_val_score(modelo_cv, X, y, cv=5, scoring='f1', n_jobs=5)
print(f"F1 por fold: {scores}")
print(f"F1 promedio: {scores.mean():.4f} (+/- {scores.std():.4f})")

# --- 9. Revisar qué tanto pesa cada feature ---
importancias = pd.Series(modelo.feature_importances_, index=X.columns)
print("\n--- Top 10 features más importantes ---")
print(importancias.sort_values(ascending=False).head(10))

# --- 10. Guardar modelo y columnas ---
joblib.dump(modelo, 'modelo_deteccion.pkl')
joblib.dump(list(X.columns), 'columnas_modelo.pkl')
print("\nModelo guardado como 'modelo_deteccion.pkl'")
print("Columnas guardadas como 'columnas_modelo.pkl'")

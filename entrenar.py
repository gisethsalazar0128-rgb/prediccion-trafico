"""
entrenar.py
Entrena un modelo de CLASIFICACION que predice el nivel de congestion
(bajo, medio o alto) de un corredor de Bogota en la proxima media hora.
Guarda el modelo entrenado y sus metricas en la carpeta modelo/.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

RUTA_DATOS = Path("datos/trafico_bogota_simulado.csv")
CARPETA_MODELO = Path("modelo")

COLUMNAS_CATEGORICAS = ["corredor"]
COLUMNAS_NUMERICAS = ["hora", "dia_semana", "es_festivo", "lluvia_mm",
                      "flujo_vehicular", "velocidad_promedio"]
OBJETIVO = "nivel_congestion"
CLASES = ["bajo", "medio", "alto"]

datos = pd.read_csv(RUTA_DATOS)
X = datos[COLUMNAS_CATEGORICAS + COLUMNAS_NUMERICAS]
y = datos[OBJETIVO]

# 80 % para entrenar y 20 % para evaluar
X_entreno, X_prueba, y_entreno, y_prueba = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y)

# El preprocesamiento va dentro del modelo (Pipeline): asi la API recibe los
# datos tal cual y el modelo se encarga de convertir el corredor a numeros.
preprocesamiento = ColumnTransformer(
    [("corredor", OneHotEncoder(handle_unknown="ignore"), COLUMNAS_CATEGORICAS)],
    remainder="passthrough")

modelo = Pipeline([
    ("preprocesamiento", preprocesamiento),
    ("clasificador", RandomForestClassifier(
        n_estimators=150, max_depth=12, min_samples_leaf=3,
        random_state=42, n_jobs=1)),
])

modelo.fit(X_entreno, y_entreno)
predicciones = modelo.predict(X_prueba)
exactitud = accuracy_score(y_prueba, predicciones)

print(f"Registros de entrenamiento: {len(X_entreno)} | de prueba: {len(X_prueba)}")
print(f"Exactitud (accuracy) en datos de prueba: {exactitud:.4f}")
print(classification_report(y_prueba, predicciones, labels=CLASES, digits=3))
print("Matriz de confusion (filas = real, columnas = prediccion):", CLASES)
print(confusion_matrix(y_prueba, predicciones, labels=CLASES))

CARPETA_MODELO.mkdir(exist_ok=True)
joblib.dump(modelo, CARPETA_MODELO / "modelo_trafico.joblib", compress=3)

reporte = classification_report(y_prueba, predicciones, labels=CLASES, output_dict=True)
metricas = {
    "modelo": "RandomForestClassifier",
    "version": "1.0",
    "fecha_entrenamiento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "registros_entrenamiento": len(X_entreno),
    "registros_prueba": len(X_prueba),
    "exactitud": round(exactitud, 4),
    "f1_por_clase": {c: round(reporte[c]["f1-score"], 4) for c in CLASES},
    "corredores": sorted(datos["corredor"].unique().tolist()),
    "columnas": COLUMNAS_CATEGORICAS + COLUMNAS_NUMERICAS,
}
with open(CARPETA_MODELO / "metricas.json", "w", encoding="utf-8") as archivo:
    json.dump(metricas, archivo, ensure_ascii=False, indent=2)

print("Modelo guardado en", CARPETA_MODELO / "modelo_trafico.joblib")

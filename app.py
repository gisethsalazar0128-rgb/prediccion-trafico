"""
app.py
API REST que expone el modelo de prediccion de congestion.
Se ejecuta con: uvicorn app:app --host 0.0.0.0 --port 8000
"""
import json
import socket
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator

CARPETA_MODELO = Path("modelo")
modelo = joblib.load(CARPETA_MODELO / "modelo_trafico.joblib")
with open(CARPETA_MODELO / "metricas.json", encoding="utf-8") as archivo:
    METRICAS = json.load(archivo)
CORREDORES = METRICAS["corredores"]
NOMBRE_POD = socket.gethostname()   # en Kubernetes es el nombre del pod

app = FastAPI(
    title="API de prediccion de congestion vehicular - Bogota",
    description="Predice el nivel de congestion (bajo, medio, alto) en la proxima media hora.",
    version=METRICAS["version"],
)


class DatosTrafico(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "corredor": "NQS",
        "hora": 18,
        "dia_semana": 4,
        "es_festivo": 0,
        "lluvia_mm": 6.5,
        "flujo_vehicular": 80,
        "velocidad_promedio": 17,
    }]})

    corredor: str = Field(description="Corredor vial, por ejemplo: NQS, Calle 26, Autopista Norte")
    hora: int = Field(ge=0, le=23, description="Hora del dia (0 a 23)")
    dia_semana: int = Field(ge=0, le=6, description="0 = lunes ... 6 = domingo")
    es_festivo: int = Field(default=0, ge=0, le=1, description="1 si es festivo, 0 si no")
    lluvia_mm: float = Field(default=0, ge=0, le=100, description="Lluvia en mm por hora")
    flujo_vehicular: float = Field(ge=0, le=300, description="Vehiculos por minuto en el sensor")
    velocidad_promedio: float = Field(ge=0, le=120, description="Velocidad promedio en km/h")

    @field_validator("corredor")
    @classmethod
    def corredor_valido(cls, valor):
        if valor not in CORREDORES:
            raise ValueError("Corredor no reconocido. Opciones: " + ", ".join(CORREDORES))
        return valor


@app.get("/")
def inicio():
    return {
        "servicio": "prediccion-trafico",
        "version_modelo": METRICAS["version"],
        "exactitud_modelo": METRICAS["exactitud"],
        "atendido_por": NOMBRE_POD,
    }


@app.get("/salud")
def salud():
    # Kubernetes consulta esta ruta para saber si el contenedor esta vivo y listo
    return {"estado": "ok", "atendido_por": NOMBRE_POD}


@app.post("/predecir")
def predecir(datos: DatosTrafico):
    entrada = pd.DataFrame([datos.model_dump()])[METRICAS["columnas"]]
    nivel = str(modelo.predict(entrada)[0])
    probabilidades = modelo.predict_proba(entrada)[0]
    return {
        "nivel_congestion": nivel,
        "probabilidades": {str(clase): round(float(p), 3)
                           for clase, p in zip(modelo.classes_, probabilidades)},
        "atendido_por": NOMBRE_POD,
    }

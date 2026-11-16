"""
generar_datos.py
Genera un conjunto de datos SIMULADO de trafico para algunos corredores de Bogota.

Ojo: no son datos reales. Los construi con patrones conocidos de la ciudad
(horas pico, lluvia, fines de semana y festivos) para poder entrenar y probar
el modelo en la nube. En una version real estos datos llegarian de los
sensores y camaras de la ciudad.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 42          # para que siempre salgan los mismos datos
N_REGISTROS = 20000
RUTA_SALIDA = Path("datos/trafico_bogota_simulado.csv")

# Capacidad aproximada de cada corredor (vehiculos por minuto en el punto del sensor)
CORREDORES = {
    "Autopista Norte": 95,
    "Avenida Boyaca": 80,
    "NQS": 85,
    "Calle 26": 75,
    "Avenida Americas": 70,
    "Carrera Septima": 45,
    "Calle 80": 65,
}


def demanda(hora, dia_semana, es_festivo):
    """Que tan llena esta la via (0 a ~1.3) segun la hora y el tipo de dia."""
    pico_manana = np.exp(-((hora - 7.0) ** 2) / 2.5)
    pico_tarde = np.exp(-((hora - 18.0) ** 2) / 3.0)
    mediodia = 0.45 * np.exp(-((hora - 13.0) ** 2) / 4.0)
    base = 0.15 + 0.85 * np.maximum(pico_manana, pico_tarde) + mediodia
    base = np.where(hora <= 4, base * 0.3, base)            # madrugada casi vacia

    fin_de_semana = dia_semana >= 5
    factor = np.where(fin_de_semana | (es_festivo == 1), 0.6, 1.0)
    factor = np.where((dia_semana == 4) & (es_festivo == 0), factor * 1.08, factor)  # viernes
    return np.clip(base * factor, 0, 1.3)


def generar(n=N_REGISTROS, semilla=SEMILLA):
    rng = np.random.default_rng(semilla)

    corredor = rng.choice(list(CORREDORES), size=n)
    capacidad = np.array([CORREDORES[c] for c in corredor])
    hora = rng.integers(0, 24, size=n)
    dia_semana = rng.integers(0, 7, size=n)                  # 0 = lunes ... 6 = domingo
    es_festivo = ((dia_semana < 5) & (rng.random(n) < 0.04)).astype(int)

    # En Bogota llueve mas en la tarde
    prob_lluvia = np.where((hora >= 13) & (hora <= 19), 0.40, 0.20)
    llueve = rng.random(n) < prob_lluvia
    lluvia_mm = np.where(llueve, rng.gamma(1.5, 3.0, size=n), 0.0).clip(0, 40).round(1)

    dem = demanda(hora, dia_semana, es_festivo)
    flujo = (capacidad * dem * rng.normal(1.0, 0.12, size=n)).clip(0).round(1)
    ocupacion = flujo / capacidad

    velocidad = 60 * (1 - 0.65 * ocupacion ** 1.5) * (1 - 0.012 * lluvia_mm)
    velocidad = (velocidad + rng.normal(0, 4, size=n)).clip(5, 80).round(1)

    # Lo que queremos predecir: congestion en la proxima media hora.
    # Depende de como esta la via ahora y de si se viene una hora pico.
    tendencia = demanda(hora + 0.5, dia_semana, es_festivo) - dem
    puntaje = (1.1 * ocupacion + 0.5 * (1 - velocidad / 60) + 0.025 * lluvia_mm
               + 0.6 * tendencia + rng.normal(0, 0.10, size=n))
    corte_bajo, corte_alto = np.quantile(puntaje, [0.45, 0.80])
    nivel = np.where(puntaje < corte_bajo, "bajo",
                     np.where(puntaje < corte_alto, "medio", "alto"))

    return pd.DataFrame({
        "corredor": corredor,
        "hora": hora,
        "dia_semana": dia_semana,
        "es_festivo": es_festivo,
        "lluvia_mm": lluvia_mm,
        "flujo_vehicular": flujo,
        "velocidad_promedio": velocidad,
        "nivel_congestion": nivel,
    })


if __name__ == "__main__":
    datos = generar()
    RUTA_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    datos.to_csv(RUTA_SALIDA, index=False)
    print(f"Datos generados: {len(datos)} registros -> {RUTA_SALIDA}")
    print(datos["nivel_congestion"].value_counts().to_string())

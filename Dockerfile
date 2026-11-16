# Imagen base liviana con Python 3.12
FROM python:3.12-slim

# No crear archivos .pyc y mostrar los logs de inmediato
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Primero las dependencias: si solo cambia el codigo, Docker reutiliza esta capa
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo del proyecto
COPY generar_datos.py entrenar.py app.py ./

# Se generan los datos y se entrena el modelo dentro de la imagen
RUN python generar_datos.py && python entrenar.py

# Usuario sin privilegios: el contenedor no corre como root
RUN useradd --uid 1000 --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

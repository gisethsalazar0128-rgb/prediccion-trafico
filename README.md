# Predicción de congestión vehicular en Bogotá — guía de despliegue en AWS

Modelo de clasificación (Random Forest) que predice si un corredor de Bogotá va a tener
congestión **baja, media o alta** en la próxima media hora. Se empaqueta con **Docker**
y se despliega con **Kubernetes (k3s)** en una instancia **EC2**.

> Los datos son **simulados** (`generar_datos.py`). No son datos reales de la ciudad.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `generar_datos.py` | Crea 20.000 registros simulados de tráfico |
| `entrenar.py` | Entrena el modelo y guarda `modelo/modelo_trafico.joblib` y `modelo/metricas.json` |
| `app.py` | API REST (FastAPI): `/`, `/salud`, `/predecir`, `/docs` |
| `requirements.txt` | Librerías con versiones fijas |
| `Dockerfile` | Construye la imagen (entrena el modelo durante el build) |
| `ejemplo.json` | Datos de ejemplo para probar `/predecir` |
| `k8s/deployment.yaml` | 2 réplicas, límites de CPU/memoria, sondas de salud, sin root |
| `k8s/service.yaml` | Expone la API en el puerto 30080 de la instancia |
| `k8s/hpa.yaml` | Escalado automático de 2 a 4 pods según CPU |

## Antes de empezar

1. Sube **todos** los archivos de esta carpeta a un repositorio **público** de GitHub
   (en GitHub: *Add file → Upload files*, arrastra los archivos y la carpeta `k8s`).
2. Ten a mano tu cuenta de AWS. Todo se hace en la región **us-east-2 (Ohio)**. En las cuentas nuevas
   (registro por proyectos) AWS asigna la región según el país; para Colombia es Ohio.
3. Cuenta con 1 hora. Al final **termina la instancia** para que no siga cobrando.

## Paso 1 — Lanzar la instancia EC2 (consola de AWS)

EC2 → *Launch instance*:

- Nombre: `prediccion-trafico`
- AMI: **Ubuntu Server 24.04 LTS**
- Tipo: **t3.small** (2 vCPU, 2 GiB). En cuentas creadas desde el 15 de julio de 2025 aparece
  como capa gratuita. En cuentas más antiguas tiene un costo bajo por hora.
  *No uses t3.micro: con 1 GiB no alcanza la memoria para Docker + Kubernetes.*
- Par de claves: opcional (para conectarse se usa EC2 Instance Connect desde el navegador).
- Red: VPC por defecto, subred pública, **asignar IP pública: habilitado**.
- Almacenamiento: **20 GiB gp3**.
- Grupo de seguridad (reglas de entrada):
  - **SSH, puerto 22** — origen: la lista de prefijos `com.amazonaws.us-east-2.ec2-instance-connect`
    (si te cuesta seleccionarla, deja "Anywhere" solo mientras haces la práctica).
  - **TCP personalizado, puerto 30080** — origen: **Mi IP**.

📸 **Fig. 3:** instancia en estado *Running* (se vea tipo t3.small e IP pública).
📸 **Fig. 4:** reglas de entrada del grupo de seguridad (22 y 30080).

## Paso 2 — Conectarse

Selecciona la instancia → *Connect* → pestaña **EC2 Instance Connect** → *Connect*.
Se abre una terminal en el navegador con el usuario `ubuntu`.

## Paso 3 — Instalar Docker y k3s

```bash
sudo apt update
sudo apt install -y docker.io docker-buildx apache2-utils
sudo docker --version
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644 --disable traefik
kubectl get nodes
```

El nodo debe salir en estado `Ready` (puede tardar unos 30 segundos).

📸 **Fig. 5:** versión de Docker y `kubectl get nodes` con el nodo `Ready`.

## Paso 4 — Traer el proyecto

```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git prediccion-trafico
cd prediccion-trafico
ls
```

## Paso 5 — Construir la imagen (aquí se entrena el modelo)

```bash
sudo docker build --progress=plain -t prediccion-trafico:v1 .
```

Busca en la salida la línea `Exactitud (accuracy) en datos de prueba: 0.8705`.
(`--progress=plain` es para que se vea el resultado del entrenamiento.)

📸 **Fig. 6:** parte final del build donde se ve la exactitud y la matriz de confusión.

## Paso 6 — Probar el contenedor con Docker

```bash
sudo docker run -d --name prueba -p 8000:8000 prediccion-trafico:v1
sleep 5
curl http://localhost:8000/salud
curl --json @ejemplo.json http://localhost:8000/predecir
sudo docker stats --no-stream prueba
sudo docker rm -f prueba
```

La predicción del ejemplo debe ser `"nivel_congestion":"alto"`. La memoria ronda los 170 MiB.

📸 **Fig. 7:** respuestas de `/salud` y `/predecir` y la memoria del contenedor.

## Paso 7 — Pasar la imagen a k3s

k3s no usa las imágenes de Docker directamente; hay que importarlas a su containerd:

```bash
sudo docker save prediccion-trafico:v1 | sudo k3s ctr -n k8s.io images import -
sudo k3s crictl images | grep prediccion
sudo systemctl stop docker docker.socket containerd   # Docker ya no hace falta: libera memoria
```

📸 **Fig. 8:** la imagen `docker.io/library/prediccion-trafico` con la etiqueta `v1`.

## Paso 8 — Desplegar en Kubernetes

```bash
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl rollout status deployment/prediccion-trafico
kubectl get pods -o wide
kubectl get svc prediccion-trafico
```

Deben quedar **2 pods** en `Running` y `READY 1/1`, y el servicio con `80:30080/TCP`.

📸 **Fig. 9:** pods y servicio.

## Paso 9 — Probar la API

En tu navegador: `http://IP_PUBLICA_DE_LA_INSTANCIA:30080/docs` → `POST /predecir` →
*Try it out* → *Execute*. Debe responder **200** con el nivel de congestión.

📸 **Fig. 10:** Swagger con la respuesta 200.

Balanceo entre pods (en la terminal):

```bash
IP=$(hostname -I | awk '{print $1}')
for i in $(seq 1 8); do curl -s http://$IP:30080/; echo; done
```

En `atendido_por` deben aparecer los nombres de los **dos** pods.

📸 **Fig. 11:** respuestas atendidas por pods distintos.

## Paso 10 — Autorrecuperación y escalado automático

```bash
# Borrar un pod: Kubernetes crea otro solo
kubectl delete $(kubectl get pods -l app=prediccion-trafico -o name | head -1)
kubectl get pods
```

📸 **Fig. 12:** el pod nuevo (AGE de pocos segundos) y los demás en Running.

```bash
# Escalado automático (HPA)
kubectl apply -f k8s/hpa.yaml
kubectl get hpa      # espera ~1 minuto hasta que TARGETS muestre "cpu: X%/70%"
URL=http://$IP:30080/predecir
ab -t 120 -c 10 -p ejemplo.json -T application/json $URL > carga.txt &
kubectl get hpa -w   # observa cómo suben las réplicas; Ctrl+C para salir
kubectl get pods
```

📸 **Fig. 13:** HPA con la CPU por encima del 70 % y las réplicas subiendo (hasta 4).
Al terminar la carga, en unos 5 minutos el HPA vuelve a bajar a 2 réplicas.

## Paso 11 — Limpieza (¡importante!)

```bash
kubectl delete -f k8s/
```

Luego en la consola: EC2 → Instancias → seleccionar → *Instance state* → **Terminate**.

## Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| Pod en `ErrImageNeverPull` | La imagen no se importó a k3s. Repite el paso 7. |
| `kubectl` dice *permission denied* | Faltó `--write-kubeconfig-mode 644` al instalar k3s. Usa `sudo kubectl ...` o reinstala con la opción. |
| El navegador no abre el puerto 30080 | Revisa la regla de 30080 en el grupo de seguridad (Mi IP) y que uses la IP **pública**. |
| EC2 Instance Connect no conecta | La regla del puerto 22 no permite el rango de EC2 Instance Connect. |
| `TARGETS` del HPA en `<unknown>` | Es normal el primer minuto; metrics-server todavía no tiene datos. |
| Error al clonar | El repositorio debe ser público (o usa un token). |

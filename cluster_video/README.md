# Sistema de Procesamiento de Video Distribuido

Sistema distribuido para procesar videos utilizando múltiples nodos worker en una red local.

## Arquitectura

- **Admin Service** (puerto 8000): Gestiona el registro de workers
- **Broker Service** (puerto 8001): Recibe videos del cliente y distribuye frames a los workers
- **Worker Service** (puerto 8002+): Procesa frames individuales

## Requisitos

```bash
pip install fastapi uvicorn opencv-python httpx numpy
```

## Configuración

### Servidor Principal (tu laptop)

Ejecuta el Admin y el Broker:

```bash
# Terminal 1 - Admin Service
python -m uvicorn admin_service:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Broker Service
python -m uvicorn broker_service:app --reload --host 0.0.0.0 --port 8001
```

**Importante:** Averigua tu IP local para compartirla con los demás:
- Windows: `ipconfig` (busca "Dirección IPv4")
- Linux/Mac: `ifconfig` o `ip addr`

Ejemplo: `192.168.1.100`

### Workers (otras computadoras en la red)

Cada persona que quiera contribuir con un worker debe:

1. Clonar el repositorio
2. Instalar dependencias (ver arriba)
3. Configurar la IP del servidor Admin:

```bash
# Windows PowerShell
$env:ADMIN_HOST="192.168.1.100"  # Reemplaza con la IP del servidor principal
python -m uvicorn worker_service:app --reload --host 0.0.0.0 --port 8002

# Linux/Mac
export ADMIN_HOST="192.168.1.100"  # Reemplaza con la IP del servidor principal
python -m uvicorn worker_service:app --reload --host 0.0.0.0 --port 8002
```

**Nota:** El worker detecta automáticamente su IP local, no necesitas configurar `WORKER_HOST`.

### Múltiples Workers en la misma máquina

Si quieres ejecutar varios workers en una sola computadora:

```bash
# Worker 1
$env:WORKER_PORT="8002"; python -m uvicorn worker_service:app --host 0.0.0.0 --port 8002

# Worker 2 (otra terminal)
$env:WORKER_PORT="8003"; python -m uvicorn worker_service:app --host 0.0.0.0 --port 8003

# Worker 3 (otra terminal)
$env:WORKER_PORT="8004"; python -m uvicorn worker_service:app --host 0.0.0.0 --port 8004
```

## Cliente Web

El cliente Next.js se conecta al Broker. Asegúrate de configurar la URL del broker:

```bash
cd cluster-client
npm install
npm run dev
```

Si el broker está en otra máquina, crea un archivo `.env.local`:

```
NEXT_PUBLIC_BROKER_URL=http://192.168.1.100:8001
```

## Verificación

Para ver los workers registrados, visita:
```
http://192.168.1.100:8000/nodes
```

## Firewall

Asegúrate de que los puertos 8000, 8001 y 8002+ estén abiertos en el firewall del servidor principal.

Windows:
```powershell
New-NetFirewallRule -DisplayName "Cluster Video" -Direction Inbound -Protocol TCP -LocalPort 8000,8001,8002 -Action Allow
```

## Troubleshooting

**Error: "No hay nodos registrados"**
- Verifica que al menos un worker esté ejecutándose
- Revisa que el worker puede conectarse al Admin (verifica la IP)

**Error: "Failed to fetch"**
- Verifica que el Broker esté ejecutándose
- Revisa la configuración de CORS en el broker
- Confirma que el cliente tiene la URL correcta del broker

**Worker no se registra**
- Verifica la IP del Admin (`ADMIN_HOST`)
- Asegúrate de que el firewall permite las conexiones
- Revisa los logs del worker para ver el error

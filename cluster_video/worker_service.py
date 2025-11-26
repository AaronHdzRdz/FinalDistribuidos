# worker_service.py
import base64
import os
import socket
from uuid import uuid4

import cv2
import numpy as np
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from common import FrameRequest, FrameResponse, NodeInfo

# ------------ OBTENER IP LOCAL ------------
def get_local_ip():
    """Obtiene la IP local de la máquina en la red"""
    try:
        # Conecta a un servidor externo para determinar la IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ------------ VARIABLES DE ENTORNO ------------
ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8000"))
ADMIN_URL = f"http://{ADMIN_HOST}:{ADMIN_PORT}"

# Si no se especifica WORKER_HOST, detecta la IP local automáticamente
WORKER_HOST = os.getenv("WORKER_HOST") or get_local_ip()
WORKER_PORT = int(os.getenv("WORKER_PORT", "8002"))   # Puerto del worker

app = FastAPI(title="Worker Node")

# Permitir CORS por si se requiere pruebas directas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------ UTILIDADES DE IMAGEN ------------
def decode_image(b64: str) -> np.ndarray:
    data = base64.b64decode(b64)
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def encode_image(img: np.ndarray) -> str:
    # Usar PNG para evitar pérdida de calidad
    _, buffer = cv2.imencode(".png", img)
    return base64.b64encode(buffer).decode("utf-8")

def process_image(img: np.ndarray) -> np.ndarray:
    # Devolver imagen original sin modificar
    # Si quieres aplicar algún efecto, puedes modificar aquí
    return img
    
    # Ejemplos de efectos que puedes usar:
    # return cv2.GaussianBlur(img, (5, 5), 0)  # Desenfoque
    # return cv2.flip(img, 1)  # Espejo horizontal
    # return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)  # Rotar 90°
    # gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)  # Blanco y negro

# ------------ REGISTRO AUTOMÁTICO EN ADMIN ------------
@app.on_event("startup")
async def register_node():
    node_id = f"worker-{uuid4().hex[:6]}"
    node_url = f"http://{WORKER_HOST}:{WORKER_PORT}"
    node = NodeInfo(id=node_id, url=node_url)

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{ADMIN_URL}/register-node", json=node.dict())
            print(f"[WORKER] Registrado como {node_id}, url={node_url}")
        except Exception as e:
            print("[WORKER] ERROR registrando en admin:", e)

# ------------ ENDPOINT PRINCIPAL DE PROCESAMIENTO ------------
@app.post("/process-frame", response_model=FrameResponse)
async def process_frame(frame_req: FrameRequest):
    print(f"[WORKER] Procesando frame {frame_req.frame_index}")
    img = decode_image(frame_req.image)
    processed = process_image(img)
    b64 = encode_image(processed)

    return FrameResponse(
        video_id=frame_req.video_id,
        frame_index=frame_req.frame_index,
        image=b64
    )

# ------------ SALUD ------------
@app.get("/health")
def health():
    return {"status": "ok"}

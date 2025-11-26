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

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8000"))
ADMIN_URL = f"http://{ADMIN_HOST}:{ADMIN_PORT}"

WORKER_HOST = os.getenv("WORKER_HOST") or get_local_ip()
WORKER_PORT = int(os.getenv("WORKER_PORT", "8002"))  
# Filtro configurado por entorno: invert (default), grayscale, canny, blur, sepia, none
WORKER_FILTER = (os.getenv("WORKER_FILTER", "invert") or "invert").lower()

app = FastAPI(title="Worker Node")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def decode_image(b64: str) -> np.ndarray:
    data = base64.b64decode(b64)
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def encode_image(img: np.ndarray) -> str:
    _, buffer = cv2.imencode(".png", img)
    return base64.b64encode(buffer).decode("utf-8")

def process_image(img: np.ndarray) -> np.ndarray:
    if WORKER_FILTER == "invert":
        return cv2.bitwise_not(img)
    elif WORKER_FILTER == "grayscale":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    elif WORKER_FILTER == "canny":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    elif WORKER_FILTER == "blur":
        return cv2.GaussianBlur(img, (5, 5), 0)
    elif WORKER_FILTER == "sepia":
        kernel = np.array([[0.272, 0.534, 0.131],
                           [0.349, 0.686, 0.168],
                           [0.393, 0.769, 0.189]])
        sepia = cv2.transform(img, kernel)
        return np.clip(sepia, 0, 255).astype(np.uint8)
    elif WORKER_FILTER == "none":
        return img
    else:
        return img
    

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

@app.get("/health")
def health():
    return {"status": "ok"}

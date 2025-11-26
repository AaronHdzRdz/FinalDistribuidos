# broker_service.py
import base64
import os
import uuid
from typing import Dict, List

import cv2
import numpy as np
import httpx
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from common import FrameRequest, FrameResponse, NodesResponse

# ------------ VARIABLES DE ENTORNO ------------
ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8000"))
ADMIN_URL = f"http://{ADMIN_HOST}:{ADMIN_PORT}"

OUTPUT_DIR = "videos_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Broker Service")

# Configurar CORS para permitir peticiones desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

video_status: Dict[str, str] = {}
video_files: Dict[str, str] = {}

# ------------ UTILIDADES ------------
def encode_frame(frame):
    _, buffer = cv2.imencode(".jpg", frame)
    return base64.b64encode(buffer).decode("utf-8")

def decode_frame(b64):
    data = base64.b64decode(b64)
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

async def get_nodes() -> List[str]:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ADMIN_URL}/nodes")
        data = NodesResponse(**r.json())
        return [n.url for n in data.nodes]

# ------------ ENDPOINT: CLIENTE SUBE VIDEO ------------
@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    video_id = str(uuid.uuid4())
    video_status[video_id] = "processing"

    temp_path = os.path.join(OUTPUT_DIR, f"{video_id}_input.mp4")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    print(f"[BROKER] Video recibido {video_id}")

    try:
        await process_video(video_id, temp_path)
    except Exception as e:
        print("[BROKER] ERROR:", e)
        video_status[video_id] = "error"

    return {"video_id": video_id, "status": video_status[video_id]}

# ------------ PROCESAMIENTO DISTRIBUIDO ------------
async def process_video(video_id: str, video_path: str):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frames = []
    ok, frame = cap.read()
    while ok:
        frames.append(frame)
        ok, frame = cap.read()
    cap.release()

    print(f"[BROKER] {len(frames)} frames extraídos")

    nodes = await get_nodes()
    if len(nodes) == 0:
        raise RuntimeError("No hay nodos registrados")

    processed_frames: Dict[int, np.ndarray] = {}

    async with httpx.AsyncClient() as client:
        for idx, frame in enumerate(frames):
            node_url = nodes[idx % len(nodes)]  # reparto round-robin
            frame_b64 = encode_frame(frame)

            req = FrameRequest(
                video_id=video_id,
                frame_index=idx,
                image=frame_b64
            )

            print(f"[BROKER] Enviando frame {idx} → {node_url}")

            resp = await client.post(f"{node_url}/process-frame",
                                     json=req.dict(),
                                     timeout=60)
            resp_obj = FrameResponse(**resp.json())
            processed_frames[idx] = decode_frame(resp_obj.image)

    # ---- Reconstrucción del video ----
    out_path = os.path.join(OUTPUT_DIR, f"{video_id}_output.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    for i in range(len(frames)):
        writer.write(processed_frames[i])

    writer.release()

    video_status[video_id] = "done"
    video_files[video_id] = out_path

    print(f"[BROKER] Video final guardado en {out_path}")

# ------------ ENDPOINTS DE ESTADO Y DESCARGA ------------
@app.get("/status/{video_id}")
def status(video_id: str):
    return {"video_id": video_id, "status": video_status.get(video_id, "unknown")}

@app.get("/download/{video_id}")
def download(video_id: str):
    path = video_files.get(video_id)
    if not path:
        return {"error": "not_ready"}
    return FileResponse(path, media_type="video/mp4")

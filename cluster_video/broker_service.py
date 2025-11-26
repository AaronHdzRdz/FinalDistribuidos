import asyncio
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

ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8000"))
ADMIN_URL = f"http://{ADMIN_HOST}:{ADMIN_PORT}"

OUTPUT_DIR = "videos_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Broker Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

video_status: Dict[str, str] = {}
video_files: Dict[str, str] = {}

def encode_frame(frame):
    _, buffer = cv2.imencode(".png", frame)
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

async def filter_reachable(nodes: List[str]) -> List[str]:
    reachable = []
    async with httpx.AsyncClient() as client:
        for n in nodes:
            try:
                resp = await client.get(f"{n}/health", timeout=5)
                if resp.status_code == 200:
                    reachable.append(n)
            except Exception:
                print(f"[BROKER] Nodo no alcanzable: {n}")
    return reachable

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

async def process_frame_with_retry(
    client: httpx.AsyncClient,
    frame_idx: int,
    frame: np.ndarray,
    nodes: List[str],
    video_id: str
) -> tuple[int, np.ndarray]:
    frame_b64 = encode_frame(frame)
    req = FrameRequest(
        video_id=video_id,
        frame_index=frame_idx,
        image=frame_b64,
    )

    start_node = frame_idx % len(nodes)
    for attempt in range(len(nodes)):
        node_url = nodes[(start_node + attempt) % len(nodes)]
        try:
            print(f"[BROKER] Frame {frame_idx} → {node_url}")
            resp = await client.post(
                f"{node_url}/process-frame",
                json=req.dict(),
                timeout=60,
            )
            resp.raise_for_status()
            resp_obj = FrameResponse(**resp.json())
            processed = decode_frame(resp_obj.image)
            print(f"[BROKER] ✓ Frame {frame_idx} procesado")
            return (frame_idx, processed)
        except Exception as e:
            print(f"[BROKER] ✗ Frame {frame_idx} falló en {node_url}: {e}")
            if attempt == len(nodes) - 1:
                raise RuntimeError(f"Frame {frame_idx} falló en todos los nodos")
            continue

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

    nodes = await filter_reachable(nodes)
    if len(nodes) == 0:
        raise RuntimeError("No hay nodos alcanzables")

    print(f"[BROKER] Procesando con {len(nodes)} worker(s) en paralelo")

    async with httpx.AsyncClient() as client:
        batch_size = min(10, len(nodes) * 3) 
        processed_frames: Dict[int, np.ndarray] = {}
        
        for i in range(0, len(frames), batch_size):
            batch = frames[i:i + batch_size]
            tasks = [
                process_frame_with_retry(client, i + idx, frame, nodes, video_id)
                for idx, frame in enumerate(batch)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    raise result
                frame_idx, processed = result
                processed_frames[frame_idx] = processed
            
            print(f"[BROKER] Progreso: {min(i + batch_size, len(frames))}/{len(frames)} frames")

    out_path = os.path.join(OUTPUT_DIR, f"{video_id}_output.mp4")
    
    try:
        fourcc = cv2.VideoWriter_fourcc(*"avc1")  
    except:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  
    
    writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

    for i in range(len(frames)):
        writer.write(processed_frames[i])

    writer.release()

    video_status[video_id] = "done"
    video_files[video_id] = out_path

    print(f"[BROKER] Video final guardado en {out_path}")

@app.get("/status/{video_id}")
def status(video_id: str):
    return {"video_id": video_id, "status": video_status.get(video_id, "unknown")}

@app.get("/download/{video_id}")
def download(video_id: str):
    path = video_files.get(video_id)
    if not path:
        return {"error": "not_ready"}
    return FileResponse(
        path, 
        media_type="video/mp4",
        filename=f"{video_id}_processed.mp4"
    )

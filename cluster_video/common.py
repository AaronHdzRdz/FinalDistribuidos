# common.py
from pydantic import BaseModel
from typing import List

class NodeInfo(BaseModel):
    id: str       # identificador del worker
    url: str      # URL base del worker: http://IP:PORT

class FrameRequest(BaseModel):
    video_id: str
    frame_index: int
    image: str    # imagen codificada en base64

class FrameResponse(BaseModel):
    video_id: str
    frame_index: int
    image: str    # imagen procesada en base64

class NodesResponse(BaseModel):
    nodes: List[NodeInfo]

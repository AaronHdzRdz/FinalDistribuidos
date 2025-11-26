from pydantic import BaseModel
from typing import List

class NodeInfo(BaseModel):
    id: str      
    url: str      

class FrameRequest(BaseModel):
    video_id: str
    frame_index: int
    image: str    

class FrameResponse(BaseModel):
    video_id: str
    frame_index: int
    image: str

class NodesResponse(BaseModel):
    nodes: List[NodeInfo]

from fastapi import FastAPI
from typing import Dict
from common import NodeInfo, NodesResponse

app = FastAPI(title="Cluster Admin")

nodes_db: Dict[str, NodeInfo] = {}

@app.post("/register-node")
def register_node(node: NodeInfo):
    nodes_db[node.id] = node
    print(f"[ADMIN] Nodo registrado: {node.id} -> {node.url}")
    return {"message": "Node registered", "count": len(nodes_db)}

@app.get("/nodes", response_model=NodesResponse)
def get_nodes():
    print(f"[ADMIN] Enviando {len(nodes_db)} nodos registrados")
    return NodesResponse(nodes=list(nodes_db.values()))

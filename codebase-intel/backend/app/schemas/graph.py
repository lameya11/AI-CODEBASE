"""Graph schemas."""
from typing import Optional
from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # file | function | class | external
    folder: Optional[str] = None
    language: Optional[str] = None
    is_external: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str  # import | call


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    level: str  # file | function

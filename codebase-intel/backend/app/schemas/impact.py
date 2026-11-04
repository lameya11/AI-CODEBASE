"""Impact analysis schemas."""
from typing import Optional
from pydantic import BaseModel


class ImpactRequest(BaseModel):
    file_path: Optional[str] = None
    symbol: Optional[str] = None  # "file::name"
    max_depth: int = 4


class AffectedFile(BaseModel):
    file_path: str
    depth: int
    distance_via: str


class ImpactResponse(BaseModel):
    target: str
    level: str  # high | medium | low
    total_affected: int
    direct: list[AffectedFile]
    indirect: list[AffectedFile]
    affected_paths: list[str]
    explanation: str
    disclaimer: str

"""Search schemas."""
from typing import Optional
from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: int
    file_path: str
    symbol_name: Optional[str]
    start_line: int
    end_line: int
    score: float
    snippet: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    k: int

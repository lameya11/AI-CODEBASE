"""Chat schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatSource(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    snippet: str
    score: float
    related: bool = False


class ChatRequest(BaseModel):
    question: str
    history: Optional[list[ChatMessage]] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    model: Optional[str]
    llm_configured: bool


class ChatHistoryItem(BaseModel):
    id: int
    role: str
    content: str
    sources_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

"""RAG chat endpoint."""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.llm_client import get_llm_client
from app.core.rag import run_rag
from app.core.vector_store import VectorStore
from app.db import get_db
from app.db.models import ChatMessage as ChatMessageModel, Chunk, File, Repository
from app.schemas.chat import ChatHistoryItem, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/repos/{repo_id}/chat", tags=["chat"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


async def _build_chunk_map(repo_id: str, db: AsyncSession) -> tuple[dict, any]:
    """Load all chunks and build (chunk_map, file_graph_or_None)."""
    chunks_result = await db.execute(
        select(Chunk).where(Chunk.repo_id == repo_id)
    )
    chunks = chunks_result.scalars().all()

    file_ids = list({c.file_id for c in chunks})
    files_result = await db.execute(
        select(File.id, File.path).where(File.id.in_(file_ids))
    )
    file_paths: dict[int, str] = {row.id: row.path for row in files_result}

    chunk_map: dict[int, dict] = {}
    for c in chunks:
        chunk_map[c.id] = {
            "file_path": file_paths.get(c.file_id, ""),
            "symbol_name": c.symbol_name,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "language": c.language,
            "text": c.text,
        }
    return chunk_map


@router.post("", response_model=ChatResponse)
async def chat(
    repo_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ask a question about the repository."""
    repo = await _get_repo_or_404(repo_id, db)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail="Repository is not ready yet")

    index_dir = settings.get_index_dir(repo_id)
    vs = VectorStore(repo_id=repo_id, index_dir=index_dir)
    chunk_map = await _build_chunk_map(repo_id, db)

    llm = get_llm_client()

    history = [{"role": m.role, "content": m.content} for m in (body.history or [])]

    result = run_rag(
        question=body.question,
        repo_id=repo_id,
        vector_store=vs,
        chunk_map=chunk_map,
        file_graph=None,  # simplified: skip graph neighbor injection at API level
        llm_client=llm,
        history=history,
        top_k=settings.TOP_K,
        token_budget=settings.TOKEN_BUDGET,
    )

    # Persist messages
    db.add(ChatMessageModel(
        repo_id=repo_id,
        role="user",
        content=body.question,
    ))
    db.add(ChatMessageModel(
        repo_id=repo_id,
        role="assistant",
        content=result["answer"],
        sources_json=json.dumps(result["sources"]),
    ))
    await db.commit()

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        model=result["model"],
        llm_configured=result["llm_configured"],
    )


@router.get("", response_model=list[ChatHistoryItem])
async def get_chat_history(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return chat history for a repository."""
    await _get_repo_or_404(repo_id, db)
    result = await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.repo_id == repo_id)
        .order_by(ChatMessageModel.created_at)
    )
    return result.scalars().all()

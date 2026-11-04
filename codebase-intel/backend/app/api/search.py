"""Semantic search endpoint."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.embeddings import get_embedder
from app.core.vector_store import VectorStore
from app.db import get_db
from app.db.models import Chunk, File, Repository
from app.schemas.search import SearchResponse, SearchResult

router = APIRouter(prefix="/repos/{repo_id}/search", tags=["search"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


@router.get("", response_model=SearchResponse)
async def search_repo(
    repo_id: str,
    q: str = Query(..., min_length=1),
    k: int = Query(8, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Perform semantic search over the repository chunks."""
    repo = await _get_repo_or_404(repo_id, db)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail="Repository is not ready yet")

    index_dir = settings.get_index_dir(repo_id)
    vs = VectorStore(repo_id=repo_id, index_dir=index_dir)

    raw = vs.search(q, k=k)
    if not raw:
        return SearchResponse(results=[], query=q, k=k)

    # Load chunk details
    chunk_ids = [r["chunk_id"] for r in raw]
    chunks_result = await db.execute(
        select(Chunk).where(Chunk.id.in_(chunk_ids))
    )
    chunk_map: dict[int, Chunk] = {c.id: c for c in chunks_result.scalars().all()}

    # Load file paths
    file_ids = list({c.file_id for c in chunk_map.values()})
    files_result = await db.execute(
        select(File.id, File.path).where(File.id.in_(file_ids))
    )
    file_paths: dict[int, str] = {row.id: row.path for row in files_result}

    results: list[SearchResult] = []
    for r in raw:
        cid = r["chunk_id"]
        chunk = chunk_map.get(cid)
        if not chunk:
            continue
        fp = file_paths.get(chunk.file_id, "")
        results.append(SearchResult(
            chunk_id=cid,
            file_path=fp,
            symbol_name=chunk.symbol_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            score=r["score"],
            snippet=chunk.text[:300],
        ))

    return SearchResponse(results=results, query=q, k=k)

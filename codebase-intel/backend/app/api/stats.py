"""Stats endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.core.embeddings import get_embedder_name
from app.core.vector_store import get_vector_backend
from app.db import get_db
from app.db.models import File, Issue, Repository, Symbol

router = APIRouter(prefix="/repos/{repo_id}/stats", tags=["stats"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


class StatsResponse(BaseModel):
    file_count: int
    supported_file_count: int
    line_count: int
    languages: dict[str, int]
    function_count: int
    class_count: int
    route_count: int
    component_count: int
    issue_count: int
    issues_by_severity: dict[str, int]
    embedder: str
    vector_backend: str
    last_analyzed_at: str | None


@router.get("", response_model=StatsResponse)
async def get_stats(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Return aggregated statistics for a repository."""
    repo = await _get_repo_or_404(repo_id, db)

    # File counts
    files_result = await db.execute(
        select(
            func.count(File.id).label("total"),
            func.sum(func.cast(File.supported, type_=type(File.supported.property.columns[0].type))).label("supported_count"),
        ).where(File.repo_id == repo_id)
    )
    # Use a simpler approach
    all_files_result = await db.execute(
        select(File).where(File.repo_id == repo_id)
    )
    all_files = all_files_result.scalars().all()
    file_count = len(all_files)
    supported_count = sum(1 for f in all_files if f.supported)

    # Language breakdown
    lang_counts: dict[str, int] = {}
    for f in all_files:
        if f.language:
            lang_counts[f.language] = lang_counts.get(f.language, 0) + 1

    # Symbol counts by kind
    file_ids = [f.id for f in all_files]
    sym_result = await db.execute(
        select(Symbol.kind, func.count(Symbol.id).label("cnt"))
        .where(Symbol.file_id.in_(file_ids))
        .group_by(Symbol.kind)
    )
    sym_counts: dict[str, int] = {row.kind: row.cnt for row in sym_result}

    # Issue counts
    issue_result = await db.execute(
        select(Issue.severity, func.count(Issue.id).label("cnt"))
        .where(Issue.repo_id == repo_id)
        .group_by(Issue.severity)
    )
    issues_by_severity: dict[str, int] = {row.severity: row.cnt for row in issue_result}
    issue_count = sum(issues_by_severity.values())

    return StatsResponse(
        file_count=file_count,
        supported_file_count=supported_count,
        line_count=repo.line_count,
        languages=repo.language_breakdown or lang_counts,
        function_count=sym_counts.get("function", 0) + sym_counts.get("route", 0),
        class_count=sym_counts.get("class", 0),
        route_count=sym_counts.get("route", 0),
        component_count=sym_counts.get("component", 0),
        issue_count=issue_count,
        issues_by_severity=issues_by_severity,
        embedder=get_embedder_name(),
        vector_backend=get_vector_backend(),
        last_analyzed_at=repo.last_analyzed_at.isoformat() if repo.last_analyzed_at else None,
    )

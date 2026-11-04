"""Issues endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_db
from app.db.models import File, Issue, Repository
from app.schemas.issues import IssueResponse, IssuesListResponse

router = APIRouter(prefix="/repos/{repo_id}/issues", tags=["issues"])

_VALID_TYPES = {"secret", "sql_injection", "unused_import", "complexity"}
_VALID_SEVERITIES = {"info", "warning", "high"}


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


@router.get("", response_model=IssuesListResponse)
async def list_issues(
    repo_id: str,
    type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List issues with optional filters."""
    await _get_repo_or_404(repo_id, db)

    # Validate filter values
    if type and type not in _VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid type. Must be one of: {_VALID_TYPES}")
    if severity and severity not in _VALID_SEVERITIES:
        raise HTTPException(status_code=422, detail=f"Invalid severity. Must be one of: {_VALID_SEVERITIES}")

    query = select(Issue).where(Issue.repo_id == repo_id)
    if type:
        query = query.where(Issue.type == type)
    if severity:
        query = query.where(Issue.severity == severity)

    result = await db.execute(query.order_by(Issue.file_id, Issue.line))
    issues = result.scalars().all()

    # Load file paths
    file_ids = list({i.file_id for i in issues})
    file_paths: dict[int, str] = {}
    if file_ids:
        files_result = await db.execute(
            select(File.id, File.path).where(File.id.in_(file_ids))
        )
        file_paths = {row.id: row.path for row in files_result}

    # Compute counts from full (unfiltered) issue set
    counts_result = await db.execute(
        select(Issue.type, Issue.severity, func.count(Issue.id).label("cnt"))
        .where(Issue.repo_id == repo_id)
        .group_by(Issue.type, Issue.severity)
    )
    counts_by_type: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for row in counts_result:
        counts_by_type[row.type] = counts_by_type.get(row.type, 0) + row.cnt
        counts_by_severity[row.severity] = counts_by_severity.get(row.severity, 0) + row.cnt

    issue_responses = [
        IssueResponse(
            id=i.id,
            repo_id=i.repo_id,
            file_id=i.file_id,
            file_path=file_paths.get(i.file_id),
            type=i.type,
            severity=i.severity,
            line=i.line,
            message=i.message,
            suggestion=i.suggestion,
        )
        for i in issues
    ]

    return IssuesListResponse(
        issues=issue_responses,
        total=len(issue_responses),
        counts_by_type=counts_by_type,
        counts_by_severity=counts_by_severity,
    )

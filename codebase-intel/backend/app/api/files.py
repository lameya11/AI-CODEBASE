"""Files endpoints."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.db.models import Chunk, File, Issue, Repository, Symbol, Dependency

router = APIRouter(prefix="/repos/{repo_id}/files", tags=["files"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


class FileListItem(BaseModel):
    id: int
    path: str
    language: Optional[str]
    line_count: int
    size: int
    supported: bool
    parse_error: Optional[str]
    issue_count: int = 0

    model_config = {"from_attributes": True}


class SymbolItem(BaseModel):
    id: int
    name: str
    kind: str
    start_line: int
    end_line: int
    docstring: Optional[str]
    parent_name: Optional[str]
    route_method: Optional[str]
    route_path: Optional[str]

    model_config = {"from_attributes": True}


class ImportItem(BaseModel):
    target_module: str
    is_external: bool
    resolved_path: Optional[str]
    kind: str


class IssueItem(BaseModel):
    id: int
    type: str
    severity: str
    line: int
    message: str
    suggestion: str

    model_config = {"from_attributes": True}


class FileDetail(BaseModel):
    id: int
    path: str
    language: Optional[str]
    line_count: int
    size: int
    supported: bool
    parse_error: Optional[str]
    symbols: list[SymbolItem]
    imports: list[ImportItem]
    issues: list[IssueItem]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[FileListItem])
async def list_files(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Return flat list of all files in the repo."""
    await _get_repo_or_404(repo_id, db)

    result = await db.execute(
        select(File).where(File.repo_id == repo_id).order_by(File.path)
    )
    files = result.scalars().all()

    # Count issues per file efficiently
    from sqlalchemy import func
    issue_counts_result = await db.execute(
        select(Issue.file_id, func.count(Issue.id).label("cnt"))
        .where(Issue.repo_id == repo_id)
        .group_by(Issue.file_id)
    )
    issue_map: dict[int, int] = {row.file_id: row.cnt for row in issue_counts_result}

    items = []
    for f in files:
        items.append(FileListItem(
            id=f.id,
            path=f.path,
            language=f.language,
            line_count=f.line_count,
            size=f.size,
            supported=f.supported,
            parse_error=f.parse_error,
            issue_count=issue_map.get(f.id, 0),
        ))
    return items


@router.get("/{file_id}", response_model=FileDetail)
async def get_file_detail(
    repo_id: str,
    file_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return file detail with symbols, imports, and issues."""
    await _get_repo_or_404(repo_id, db)

    result = await db.execute(
        select(File)
        .where(File.id == file_id, File.repo_id == repo_id)
        .options(selectinload(File.symbols), selectinload(File.issues))
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    # Load dependencies (imports) originating from this file
    dep_result = await db.execute(
        select(Dependency).where(Dependency.source_file_id == file_id)
    )
    deps = dep_result.scalars().all()

    # Build resolved path lookup: target_file_id -> path
    target_ids = [d.target_file_id for d in deps if d.target_file_id]
    resolved_paths: dict[int, str] = {}
    if target_ids:
        files_result = await db.execute(
            select(File.id, File.path).where(File.id.in_(target_ids))
        )
        for row in files_result:
            resolved_paths[row.id] = row.path

    imports = [
        ImportItem(
            target_module=d.target_module,
            is_external=d.is_external,
            resolved_path=resolved_paths.get(d.target_file_id) if d.target_file_id else None,
            kind=d.kind,
        )
        for d in deps
    ]

    return FileDetail(
        id=f.id,
        path=f.path,
        language=f.language,
        line_count=f.line_count,
        size=f.size,
        supported=f.supported,
        parse_error=f.parse_error,
        symbols=[SymbolItem.model_validate(s) for s in f.symbols],
        imports=imports,
        issues=[IssueItem.model_validate(i) for i in f.issues],
    )


@router.get("/{file_id}/content")
async def get_file_content(
    repo_id: str,
    file_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return raw file content (text)."""
    await _get_repo_or_404(repo_id, db)
    result = await db.execute(
        select(File).where(File.id == file_id, File.repo_id == repo_id)
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    # Find the chunk with start_line=1 to reconstruct content
    # (we don't store raw content; serve from chunks or return a message)
    chunks_result = await db.execute(
        select(Chunk)
        .where(Chunk.file_id == file_id)
        .order_by(Chunk.start_line)
    )
    chunks = chunks_result.scalars().all()
    if not chunks:
        return {"content": "", "path": f.path}

    # Reconstruct from chunks (best-effort; may have gaps for large files)
    lines: dict[int, str] = {}
    for c in chunks:
        c_lines = c.text.splitlines()
        for idx, line in enumerate(c_lines):
            lineno = c.start_line + idx
            if lineno not in lines:
                lines[lineno] = line

    max_line = max(lines.keys()) if lines else 0
    reconstructed = "\n".join(lines.get(i, "") for i in range(1, max_line + 1))
    return {"content": reconstructed, "path": f.path}

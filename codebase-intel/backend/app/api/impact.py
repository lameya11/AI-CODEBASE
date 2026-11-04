"""Impact analysis endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.impact import analyze_impact
from app.db import get_db
from app.db.models import Dependency, File, Repository
from app.schemas.impact import AffectedFile, ImpactRequest, ImpactResponse

import networkx as nx

router = APIRouter(prefix="/repos/{repo_id}/impact", tags=["impact"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


async def _build_file_graph(repo_id: str, db: AsyncSession) -> tuple[nx.DiGraph, dict[str, int]]:
    """Reconstruct the file-level DiGraph from DB records."""
    files_result = await db.execute(
        select(File).where(File.repo_id == repo_id)
    )
    files = {f.id: f for f in files_result.scalars().all()}

    G = nx.DiGraph()
    for f in files.values():
        G.add_node(f.path, is_external=False)

    deps_result = await db.execute(
        select(Dependency).where(Dependency.repo_id == repo_id)
    )
    for dep in deps_result.scalars().all():
        src_file = files.get(dep.source_file_id)
        if not src_file:
            continue
        if dep.is_external:
            ext_id = f"<external>/{dep.target_module.split('.')[0]}"
            G.add_node(ext_id, is_external=True)
            G.add_edge(src_file.path, ext_id)
        else:
            tgt_file = files.get(dep.target_file_id) if dep.target_file_id else None
            if tgt_file:
                G.add_edge(src_file.path, tgt_file.path)

    path_to_id = {f.path: f.id for f in files.values()}
    return G, path_to_id


@router.post("", response_model=ImpactResponse)
async def get_impact(
    repo_id: str,
    body: ImpactRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze the impact of changing a file or symbol."""
    repo = await _get_repo_or_404(repo_id, db)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail="Repository is not ready yet")

    max_depth = min(body.max_depth, 10)

    # Determine target
    target: str
    if body.file_path:
        target = body.file_path
    elif body.symbol:
        target = body.symbol.split("::")[0]
    else:
        raise HTTPException(status_code=422, detail="Provide file_path or symbol")

    G, _ = await _build_file_graph(repo_id, db)

    if target not in G:
        raise HTTPException(status_code=404, detail=f"File '{target}' not in dependency graph")

    result = analyze_impact(target, G, max_depth=max_depth)

    return ImpactResponse(
        target=result["target"],
        level=result["level"],
        total_affected=result["total_affected"],
        direct=[AffectedFile(**d) for d in result["direct"]],
        indirect=[AffectedFile(**d) for d in result["indirect"]],
        affected_paths=result["affected_paths"],
        explanation=result["explanation"],
        disclaimer=result["disclaimer"],
    )

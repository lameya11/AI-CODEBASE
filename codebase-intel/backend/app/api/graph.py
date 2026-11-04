"""Graph endpoint."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.db.models import Dependency, File, Repository, Symbol
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse

router = APIRouter(prefix="/repos/{repo_id}/graph", tags=["graph"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


@router.get("", response_model=GraphResponse)
async def get_graph(
    repo_id: str,
    level: str = Query("file", pattern="^(file|function)$"),
    db: AsyncSession = Depends(get_db),
):
    """Return dependency graph nodes and edges."""
    await _get_repo_or_404(repo_id, db)

    # Load all files for this repo
    files_result = await db.execute(
        select(File).where(File.repo_id == repo_id)
    )
    files = {f.id: f for f in files_result.scalars().all()}

    if level == "file":
        return await _build_file_graph(repo_id, files, db)
    else:
        return await _build_function_graph(repo_id, files, db)


async def _build_file_graph(repo_id: str, files: dict, db: AsyncSession) -> GraphResponse:
    """Build file-level graph."""
    deps_result = await db.execute(
        select(Dependency).where(Dependency.repo_id == repo_id)
    )
    deps = deps_result.scalars().all()

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # Add all repo files as nodes
    for f in files.values():
        folder = "/".join(f.path.split("/")[:-1]) or "/"
        nodes[f.path] = GraphNode(
            id=f.path,
            label=f.path.split("/")[-1],
            type="file",
            folder=folder,
            language=f.language,
            is_external=False,
        )

    # Add external nodes and edges
    for dep in deps:
        src_file = files.get(dep.source_file_id)
        if not src_file:
            continue

        if dep.is_external:
            ext_id = f"<external>/{dep.target_module.split('.')[0]}"
            if ext_id not in nodes:
                nodes[ext_id] = GraphNode(
                    id=ext_id,
                    label=dep.target_module.split(".")[0],
                    type="external",
                    is_external=True,
                )
            edges.append(GraphEdge(source=src_file.path, target=ext_id, kind=dep.kind))
        else:
            tgt_file = files.get(dep.target_file_id) if dep.target_file_id else None
            if tgt_file:
                edges.append(GraphEdge(source=src_file.path, target=tgt_file.path, kind=dep.kind))

    return GraphResponse(nodes=list(nodes.values()), edges=edges, level="file")


async def _build_function_graph(repo_id: str, files: dict, db: AsyncSession) -> GraphResponse:
    """Build function-level graph."""
    syms_result = await db.execute(
        select(Symbol).where(Symbol.file_id.in_(list(files.keys())))
    )
    symbols = syms_result.scalars().all()

    nodes: dict[str, GraphNode] = {}
    for sym in symbols:
        f = files.get(sym.file_id)
        if not f:
            continue
        node_id = f"{f.path}::{sym.name}"
        nodes[node_id] = GraphNode(
            id=node_id,
            label=sym.name,
            type=sym.kind,
            folder="/".join(f.path.split("/")[:-1]) or "/",
            language=f.language,
            is_external=False,
        )

    # Edges from dependencies at function level (best-effort using file deps)
    edges: list[GraphEdge] = []

    return GraphResponse(nodes=list(nodes.values()), edges=edges, level="function")
